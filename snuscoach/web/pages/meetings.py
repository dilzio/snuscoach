import asyncio
import textwrap
from datetime import date

from nicegui import ui

from snuscoach import coach, db
from snuscoach.web.components.chat import ChatPanel
from snuscoach.web.components.nav import create_nav


# ---------------------------------------------------------------------------
# Prompt builders (mirror CLI templates in cli.py lines 555–575, 621–643)
# ---------------------------------------------------------------------------

def _build_prep_prompt(m) -> str:
    return textwrap.dedent(f"""
        TASK: Pre-meeting prep brief.

        Meeting: {m['title']}
        Attendees: {m['attendees'] or '(not specified)'}
        Meeting date: {m['date']}
        Context:
        {m['prep_context'] or '(none provided)'}

        Produce:
        1. Top 3 outcomes I should aim for, ranked.
        2. Talking points in priority order.
        3. Who to align with beforehand (if anyone) and why.
        4. Risks / things to avoid.
        5. Listen-fors — political signals I should be alert to in the meeting.
        6. Coda: what's the actual political move here, and what makes it land?

        If you need information you don't have, ASK rather than guess.
    """).strip()


def _build_debrief_prompt(m) -> str:
    return textwrap.dedent(f"""
        TASK: Post-meeting debrief.

        Meeting: {m['title']}
        Attendees: {m['attendees'] or '(not specified)'}
        Date: {m['date']}

        Raw notes:
        {m['debrief_notes'] or '(none provided)'}

        Produce, in this order:
        1. Concrete follow-ups I should commit to (with rough timing).
        2. Political signals — what was actually being negotiated, who's aligned with whom, what's unsaid.
        3. Credit & thanks list — who deserves a public or private acknowledgment, and from whom.
        4. Items to escalate — anything my manager or skip should know, framed for them.
        5. What I missed — likely interpretations of the meeting I haven't considered.
        6. Coda: the single highest-leverage thing for me to do in the next 48 hours, and why.

        Push back if my read of the meeting is naive or self-serving.
    """).strip()


# ---------------------------------------------------------------------------
# Shared async helpers
# ---------------------------------------------------------------------------

async def _do_prep(m, panel: list) -> None:
    if panel[0]:
        await panel[0].inject(_build_prep_prompt(m))


async def _do_debrief(m, panel: list) -> None:
    if panel[0]:
        await panel[0].inject(_build_debrief_prompt(m))


def _save_last_reply(meeting_id: int, field: str, notify_msg: str, panel: list) -> None:
    p = panel[0]
    if not p or not p.messages:
        ui.notify("No chat output to save.", type="warning")
        return
    for msg in reversed(p.messages):
        if msg["role"] == "assistant":
            db.update_meeting(meeting_id, **{field: msg["content"]})
            ui.notify(notify_msg)
            return
    ui.notify("No assistant reply to save yet.", type="warning")


# ---------------------------------------------------------------------------
# Status badge
# ---------------------------------------------------------------------------

def _status_badge(label: str, active: bool) -> None:
    ui.badge(label).props(f"color={'positive' if active else 'grey-5'}")


# ---------------------------------------------------------------------------
# Meeting card (single row in the list view)
# ---------------------------------------------------------------------------

def _meeting_card(m, left_col, chat_container: list, panel: list) -> None:
    has_prep = bool(m["prep_brief"] or m["prep_context"])
    has_debrief = bool(m["debrief_summary"] or m["debrief_notes"])

    def _select(mid=m["id"]):
        left_col.clear()
        with left_col:
            _render_detail(mid, left_col, chat_container, panel)
        _rewire_chat(mid, chat_container, panel)

    with ui.card().classes("w-full cursor-pointer q-mb-xs").on("click", _select):
        with ui.row().classes("w-full items-start justify-between gap-2"):
            with ui.column().classes("gap-0"):
                ui.label(m["title"]).classes("text-body1 text-bold")
                ui.label(m["date"]).classes("text-caption text-grey")
                if m["attendees"]:
                    ui.label(m["attendees"]).classes("text-caption")
            with ui.row().classes("gap-1 items-center"):
                _status_badge("P", has_prep)
                _status_badge("D", has_debrief)


# ---------------------------------------------------------------------------
# List view
# ---------------------------------------------------------------------------

def _render_list(left_col, chat_container: list, panel: list) -> None:
    meetings = db.list_meetings(limit=50)
    all_series = {s["id"]: s for s in db.list_meeting_series()}

    # Group by series_id
    buckets: dict = {}
    for m in meetings:
        sid = m["series_id"]
        buckets.setdefault(sid, []).append(m)

    # Sort: named series alphabetically, one-offs last
    named_sids = sorted(
        [sid for sid in buckets if sid is not None],
        key=lambda sid: all_series[sid]["name"].lower(),
    )

    def _open_dialog():
        _open_new_meeting_dialog(left_col, chat_container, panel)

    with ui.row().classes("w-full items-center justify-between q-pb-sm"):
        ui.label("Meetings").classes("text-h5")
        ui.button("+ New Meeting", on_click=_open_dialog).props("flat dense")

    if not meetings:
        ui.label("No meetings yet.").classes("text-caption text-grey q-mt-sm")
        return

    with ui.scroll_area().classes("w-full").style("flex: 1"):
        for sid in named_sids:
            series_name = all_series[sid]["name"]
            with ui.expansion(series_name, icon="group").classes("w-full"):
                for m in buckets[sid]:
                    _meeting_card(m, left_col, chat_container, panel)

        if None in buckets:
            ui.label("One-off meetings").classes("text-caption text-grey text-uppercase q-mt-md q-mb-xs")
            for m in buckets[None]:
                _meeting_card(m, left_col, chat_container, panel)


# ---------------------------------------------------------------------------
# Detail view
# ---------------------------------------------------------------------------

# ui.select() with {key: label} dict format — NiceGUI validates value against keys, not label strings.
# 0 is a safe "no series" sentinel since series IDs start at 1.
_NO_SERIES = 0


def _series_dict(all_series) -> dict:
    """Build {series_id: name} dict for ui.select, with 0 = no series."""
    d = {_NO_SERIES: "(none — one-off)"}
    for s in all_series:
        d[s["id"]] = s["name"]
    return d


def _render_detail(meeting_id: int, left_col, chat_container: list, panel: list) -> None:
    m = db.get_meeting(meeting_id)
    if m is None:
        ui.label("Meeting not found.").classes("text-caption text-negative")
        return

    all_series = db.list_meeting_series()
    series_opts = _series_dict(all_series)
    current_series = m["series_id"] if m["series_id"] is not None else _NO_SERIES

    # Input refs
    title_in = [None]
    date_in = [None]
    attendees_in = [None]
    series_in = [None]
    prep_context_in = [None]
    prep_brief_in = [None]
    debrief_notes_in = [None]
    debrief_summary_in = [None]

    def _go_back():
        left_col.clear()
        with left_col:
            _render_list(left_col, chat_container, panel)
        _rewire_chat(None, chat_container, panel)

    def _save_meeting():
        series_key = series_in[0].value  # int key from the {id: name} dict
        db.update_meeting(
            meeting_id,
            title=title_in[0].value or m["title"],
            date=date_in[0].value or m["date"],
            attendees=attendees_in[0].value or None,
            series_id=None if series_key == _NO_SERIES else series_key,
            prep_context=prep_context_in[0].value or None,
            prep_brief=prep_brief_in[0].value or None,
            debrief_notes=debrief_notes_in[0].value or None,
            debrief_summary=debrief_summary_in[0].value or None,
        )
        ui.notify("Saved.")

    ui.button("← Back", on_click=_go_back).props("flat dense").classes("q-mb-sm")
    ui.label(m["title"]).classes("text-h6 q-mb-xs")

    title_in[0] = ui.input(label="Title", value=m["title"]).classes("w-full")
    date_in[0] = ui.input(label="Date (YYYY-MM-DD)", value=m["date"]).classes("w-full")
    attendees_in[0] = ui.input(label="Attendees", value=m["attendees"] or "").classes("w-full")
    series_in[0] = ui.select(
        label="Series",
        options=series_opts,
        value=current_series,
    ).classes("w-full")

    ui.separator().classes("q-my-sm")
    prep_context_in[0] = ui.textarea(
        label="Prep context", value=m["prep_context"] or ""
    ).props("rows=3 outlined").classes("w-full")
    prep_brief_in[0] = ui.textarea(
        label="Prep brief (coach output)", value=m["prep_brief"] or ""
    ).props("rows=4 outlined").classes("w-full")

    ui.separator().classes("q-my-sm")
    debrief_notes_in[0] = ui.textarea(
        label="Debrief notes", value=m["debrief_notes"] or ""
    ).props("rows=3 outlined").classes("w-full")
    debrief_summary_in[0] = ui.textarea(
        label="Debrief summary (coach output)", value=m["debrief_summary"] or ""
    ).props("rows=4 outlined").classes("w-full")

    ui.button("Save", on_click=_save_meeting).props("color=primary dense").classes("q-mt-sm")


# ---------------------------------------------------------------------------
# Chat panel (right column)
# ---------------------------------------------------------------------------

def _rewire_chat(meeting_id: int | None, chat_container: list, panel: list) -> None:
    chat_container[0].clear()
    with chat_container[0]:
        if meeting_id is not None:
            m = db.get_meeting(meeting_id)
            if m is None:
                panel[0] = ChatPanel(
                    placeholder="Ask about any meeting...",
                    coach_fn=coach.stub_fn("CHAT") if coach.is_stubbed("CHAT") else coach.conversation,
                )
                return

            with ui.row().classes("q-pa-xs gap-2 items-center").style("flex-shrink: 0"):
                ui.button(
                    "Prep this meeting",
                    on_click=lambda: asyncio.ensure_future(_do_prep(m, panel)),
                ).props("flat dense color=primary")
                ui.button(
                    "Debrief this meeting",
                    on_click=lambda: asyncio.ensure_future(_do_debrief(m, panel)),
                ).props("flat dense color=secondary")
                ui.button(
                    "Save brief",
                    on_click=lambda: _save_last_reply(m["id"], "prep_brief", "Prep brief saved.", panel),
                ).props("flat dense")
                ui.button(
                    "Save summary",
                    on_click=lambda: _save_last_reply(m["id"], "debrief_summary", "Debrief summary saved.", panel),
                ).props("flat dense")

            coach_fn = coach.stub_fn("CHAT") if coach.is_stubbed("CHAT") else coach.conversation
            with ui.column().classes("w-full").style("flex: 1; min-height: 0"):
                panel[0] = ChatPanel(
                    placeholder="Follow up on this meeting...",
                    coach_fn=coach_fn,
                    thread_key=f"meeting-{meeting_id}",
                )
        else:
            panel[0] = ChatPanel(
                placeholder="Ask about any meeting...",
                coach_fn=coach.stub_fn("CHAT") if coach.is_stubbed("CHAT") else coach.conversation,
            )


# ---------------------------------------------------------------------------
# New meeting dialog
# ---------------------------------------------------------------------------

def _open_new_meeting_dialog(left_col, chat_container: list, panel: list) -> None:
    today = date.today().isoformat()
    all_series = db.list_meeting_series()
    series_opts = _series_dict(all_series)

    with ui.dialog() as dlg, ui.card().classes("w-80"):
        ui.label("New Meeting").classes("text-subtitle1 text-bold q-mb-sm")
        title_in = ui.input(label="Title *").classes("w-full")
        date_in = ui.input(label="Date (YYYY-MM-DD)", value=today).classes("w-full")
        attendees_in = ui.input(label="Attendees").classes("w-full")
        series_in = ui.select(
            label="Series", options=series_opts, value=_NO_SERIES
        ).classes("w-full")

        def _create():
            title = title_in.value.strip()
            if not title:
                ui.notify("Title is required.", type="warning")
                return
            series_key = series_in.value
            db.add_meeting(
                title=title,
                date=date_in.value or today,
                attendees=attendees_in.value or None,
                series_id=None if series_key == _NO_SERIES else series_key,
            )
            dlg.close()
            left_col.clear()
            with left_col:
                _render_list(left_col, chat_container, panel)

        with ui.row().classes("w-full justify-end gap-2 q-mt-sm"):
            ui.button("Cancel", on_click=dlg.close).props("flat dense")
            ui.button("Create", on_click=_create).props("color=primary dense")

    dlg.open()


# ---------------------------------------------------------------------------
# Page entry point
# ---------------------------------------------------------------------------

@ui.page("/meetings")
def meetings_page() -> None:
    create_nav("/meetings")
    panel: list[ChatPanel | None] = [None]
    chat_container: list = [None]

    with ui.row().classes("w-full gap-0").style(
        "height: calc(100vh - 56px); overflow: hidden"
    ):
        with ui.column().style(
            "width: 40%; height: 100%; overflow-y: auto; flex-shrink: 0"
        ).classes("q-pa-md gap-2") as left_col:
            _render_list(left_col, chat_container, panel)

        with ui.column().classes("flex-1 h-full gap-0") as right_col:
            chat_container[0] = right_col
            panel[0] = ChatPanel(
                placeholder="Ask about any meeting...",
                coach_fn=coach.stub_fn("CHAT") if coach.is_stubbed("CHAT") else coach.conversation,
            )
