import asyncio
import textwrap
from datetime import date

from nicegui import ui

from snuscoach import coach, db
from snuscoach.web.components.chat import ChatPanel
from snuscoach.web.components.nav import create_nav


# ---------------------------------------------------------------------------
# Prompt builders (mirror CLI templates in cli.py)
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
# ui.select() sentinel — series IDs start at 1, so 0 is safe for "no series"
# ---------------------------------------------------------------------------

_NO_SERIES = 0


def _series_dict(all_series) -> dict:
    d = {_NO_SERIES: "(none — one-off)"}
    for s in all_series:
        d[s["id"]] = s["name"]
    return d


# ---------------------------------------------------------------------------
# Confirmation dialog
# ---------------------------------------------------------------------------

def _confirm_overwrite(on_confirm) -> None:
    with ui.dialog() as dlg, ui.card():
        ui.label("This will overwrite the existing content. Continue?").classes("text-body2")
        with ui.row().classes("justify-end gap-2 q-mt-sm"):
            ui.button("Cancel", on_click=dlg.close).props("flat dense")
            ui.button("Overwrite", on_click=lambda: (dlg.close(), on_confirm())).props("color=negative dense")
    dlg.open()


def _confirm_delete_meeting(meeting_id: int, title: str, main_container: list) -> None:
    with ui.dialog() as dlg, ui.card():
        ui.label(f'Delete "{title}"?').classes("text-body2")
        ui.label("This cannot be undone.").classes("text-caption text-grey")
        with ui.row().classes("justify-end gap-2 q-mt-sm"):
            ui.button("Cancel", on_click=dlg.close).props("flat dense")
            ui.button(
                "Delete",
                on_click=lambda: (dlg.close(), _do_delete_meeting(meeting_id, main_container)),
            ).props("color=negative dense")
    dlg.open()


def _do_delete_meeting(meeting_id: int, main_container: list) -> None:
    db.delete_meeting(meeting_id)
    main_container[0].style("overflow-y: auto")
    main_container[0].clear()
    with main_container[0]:
        _render_list(main_container)
    ui.notify("Meeting deleted.")


def _open_new_series_dialog(series_select) -> None:
    """Create a new meeting series and auto-select it in series_select."""
    with ui.dialog() as dlg, ui.card().classes("w-64"):
        ui.label("New Series").classes("text-subtitle1 text-bold q-mb-sm")
        name_in = ui.input(label="Series name *").classes("w-full")

        def _create():
            name = name_in.value.strip()
            if not name:
                ui.notify("Name is required.", type="warning")
                return
            new_id = db.add_meeting_series(name)
            series_select.options = _series_dict(db.list_meeting_series())
            series_select.value = new_id
            series_select.update()
            dlg.close()
            ui.notify(f'Series "{name}" created.')

        with ui.row().classes("w-full justify-end gap-2 q-mt-sm"):
            ui.button("Cancel", on_click=dlg.close).props("flat dense")
            ui.button("Create", on_click=_create).props("color=primary dense")
    dlg.open()


# ---------------------------------------------------------------------------
# AI output display helpers (read-only + Edit toggle)
# ---------------------------------------------------------------------------

def _render_brief_display(meeting_id: int, brief_container: list) -> None:
    m = db.get_meeting(meeting_id)
    brief_container[0].clear()
    with brief_container[0]:
        if m["prep_brief"]:
                with ui.element("div").classes("outline-2 rounded q-pa-sm w-full q-mb-xs").style("color: black"):
                    ui.markdown(m["prep_brief"]).classes("text-body2")
        else:
            ui.label("Not yet generated — use Prep session →").classes("text-caption text-grey q-mb-xs")
        ui.button("Edit ✎", on_click=lambda: _show_brief_editor(meeting_id, brief_container)).props("flat dense size=sm")


def _show_brief_editor(meeting_id: int, brief_container: list) -> None:
    m = db.get_meeting(meeting_id)
    brief_container[0].clear()
    with brief_container[0]:
        ta = ui.textarea(value=m["prep_brief"] or "").props("rows=5 outlined").classes("w-full")

        def _save():
            db.update_meeting(meeting_id, prep_brief=ta.value or None)
            _render_brief_display(meeting_id, brief_container)
            ui.notify("Prep brief saved.")

        with ui.row().classes("gap-2 q-mt-xs"):
            ui.button("Save", on_click=_save).props("color=primary dense size=sm")
            ui.button("Cancel", on_click=lambda: _render_brief_display(meeting_id, brief_container)).props("flat dense size=sm")


def _render_summary_display(meeting_id: int, summary_container: list) -> None:
    m = db.get_meeting(meeting_id)
    summary_container[0].clear()
    with summary_container[0]:
        if m["debrief_summary"]:
            with ui.element("div").classes("outline-2 rounded q-pa-sm w-full q-mb-xs"):
                ui.markdown(m["debrief_summary"]).classes("text-body2")
        else:
            ui.label("Not yet generated — use Debrief session →").classes("text-caption text-grey q-mb-xs")
        ui.button("Edit ✎", on_click=lambda: _show_summary_editor(meeting_id, summary_container)).props("flat dense size=sm")


def _show_summary_editor(meeting_id: int, summary_container: list) -> None:
    m = db.get_meeting(meeting_id)
    summary_container[0].clear()
    with summary_container[0]:
        ta = ui.textarea(value=m["debrief_summary"] or "").props("rows=5 outlined").classes("w-full")

        def _save():
            db.update_meeting(meeting_id, debrief_summary=ta.value or None)
            _render_summary_display(meeting_id, summary_container)
            ui.notify("Debrief summary saved.")

        with ui.row().classes("gap-2 q-mt-xs"):
            ui.button("Save", on_click=_save).props("color=primary dense size=sm")
            ui.button("Cancel", on_click=lambda: _render_summary_display(meeting_id, summary_container)).props("flat dense size=sm")


# ---------------------------------------------------------------------------
# Session tab renderers
# ---------------------------------------------------------------------------

async def _do_prep_with_save(meeting_id: int, panel: list, notes_ta) -> None:
    db.update_meeting(meeting_id, prep_context=notes_ta.value or None)
    m = db.get_meeting(meeting_id)
    if panel[0]:
        await panel[0].inject(_build_prep_prompt(m))


async def _do_debrief_with_save(meeting_id: int, panel: list, notes_ta) -> None:
    db.update_meeting(meeting_id, debrief_notes=notes_ta.value or None)
    m = db.get_meeting(meeting_id)
    if panel[0]:
        await panel[0].inject(_build_debrief_prompt(m))


def _save_as_brief(meeting_id: int, panel: list, brief_container: list) -> None:
    p = panel[0]
    if not p or not p.messages:
        ui.notify("No chat output to save.", type="warning")
        return
    last_reply = next((msg["content"] for msg in reversed(p.messages) if msg["role"] == "assistant"), None)
    if last_reply is None:
        ui.notify("No assistant reply yet.", type="warning")
        return
    existing = db.get_meeting(meeting_id)["prep_brief"]
    if existing:
        _confirm_overwrite(lambda: _do_save_brief(meeting_id, last_reply, brief_container))
    else:
        _do_save_brief(meeting_id, last_reply, brief_container)


def _do_save_brief(meeting_id: int, content: str, brief_container: list) -> None:
    db.update_meeting(meeting_id, prep_brief=content)
    _render_brief_display(meeting_id, brief_container)
    ui.notify("Prep brief saved.")


def _save_as_summary(meeting_id: int, panel: list, summary_container: list) -> None:
    p = panel[0]
    if not p or not p.messages:
        ui.notify("No chat output to save.", type="warning")
        return
    last_reply = next((msg["content"] for msg in reversed(p.messages) if msg["role"] == "assistant"), None)
    if last_reply is None:
        ui.notify("No assistant reply yet.", type="warning")
        return
    existing = db.get_meeting(meeting_id)["debrief_summary"]
    if existing:
        _confirm_overwrite(lambda: _do_save_summary(meeting_id, last_reply, summary_container))
    else:
        _do_save_summary(meeting_id, last_reply, summary_container)


def _do_save_summary(meeting_id: int, content: str, summary_container: list) -> None:
    db.update_meeting(meeting_id, debrief_summary=content)
    _render_summary_display(meeting_id, summary_container)
    ui.notify("Debrief summary saved.")


def _render_prep_tab(meeting_id: int, prep_panel: list, brief_container: list) -> None:
    m = db.get_meeting(meeting_id)
    coach_fn = coach.stub_fn("CHAT") if coach.is_stubbed("CHAT") else coach.conversation

    ui.label("Pre-meeting notes").classes("text-caption text-grey")
    notes_ta = ui.textarea(value=m["prep_context"] or "").props("rows=3 outlined").classes("w-full")

    with ui.row().classes("w-full justify-end"):
        ui.button(
            "Save notes ↑",
            on_click=lambda: (db.update_meeting(meeting_id, prep_context=notes_ta.value or None), ui.notify("Notes saved.")),
        ).props("flat dense")

    ui.separator().classes("q-my-xs")

    with ui.row().classes("gap-2 items-center flex-wrap"):
        ui.button(
            "Generate Prep Brief",
            on_click=lambda: asyncio.ensure_future(_do_prep_with_save(meeting_id, prep_panel, notes_ta)),
        ).props("flat dense color=primary")
        ui.button(
            "Save as Prep Brief ↓",
            on_click=lambda: _save_as_brief(meeting_id, prep_panel, brief_container),
        ).props("flat dense")

    ui.separator().classes("q-my-xs")

    with ui.column().classes("w-full").style("flex: 1; min-height: 0"):
        prep_panel[0] = ChatPanel(
            placeholder="Follow up on prep...",
            coach_fn=coach_fn,
            thread_key=f"meeting-{meeting_id}-prep",
        )


def _render_debrief_tab(meeting_id: int, debrief_panel: list, summary_container: list) -> None:
    m = db.get_meeting(meeting_id)
    coach_fn = coach.stub_fn("CHAT") if coach.is_stubbed("CHAT") else coach.conversation

    ui.label("Meeting notes").classes("text-caption text-grey")
    notes_ta = ui.textarea(value=m["debrief_notes"] or "").props("rows=3 outlined").classes("w-full")

    with ui.row().classes("w-full justify-end"):
        ui.button(
            "Save notes ↑",
            on_click=lambda: (db.update_meeting(meeting_id, debrief_notes=notes_ta.value or None), ui.notify("Notes saved.")),
        ).props("flat dense")

    ui.separator().classes("q-my-xs")

    with ui.row().classes("gap-2 items-center flex-wrap"):
        ui.button(
            "Generate Debrief Summary",
            on_click=lambda: asyncio.ensure_future(_do_debrief_with_save(meeting_id, debrief_panel, notes_ta)),
        ).props("flat dense color=secondary")
        ui.button(
            "Save as Debrief Summary ↓",
            on_click=lambda: _save_as_summary(meeting_id, debrief_panel, summary_container),
        ).props("flat dense")

    ui.separator().classes("q-my-xs")

    with ui.column().classes("w-full").style("flex: 1; min-height: 0"):
        debrief_panel[0] = ChatPanel(
            placeholder="Follow up on debrief...",
            coach_fn=coach_fn,
            thread_key=f"meeting-{meeting_id}-debrief",
        )


def _render_session_panel(
    meeting_id: int,
    initial_tab: str,
    tabs_ref: list,
    brief_container: list,
    summary_container: list,
) -> None:
    prep_panel: list[ChatPanel | None] = [None]
    debrief_panel: list[ChatPanel | None] = [None]

    with ui.tabs().classes("w-full").style("flex-shrink: 0") as tabs:
        ui.tab("prep", label="Prep session")
        ui.tab("debrief", label="Debrief session")
    tabs_ref[0] = tabs

    with ui.tab_panels(tabs, value=initial_tab).classes("w-full").style("flex: 1; min-height: 0; overflow: hidden"):
        with ui.tab_panel("prep").classes("h-full q-pa-sm").style("display: flex; flex-direction: column"):
            _render_prep_tab(meeting_id, prep_panel, brief_container)
        with ui.tab_panel("debrief").classes("h-full q-pa-sm").style("display: flex; flex-direction: column"):
            _render_debrief_tab(meeting_id, debrief_panel, summary_container)


# ---------------------------------------------------------------------------
# Detail view — left panel
# ---------------------------------------------------------------------------

def _render_detail_left(
    meeting_id: int,
    tabs_ref: list,
    brief_container: list,
    summary_container: list,
    main_container: list,
) -> None:
    m = db.get_meeting(meeting_id)
    if m is None:
        ui.label("Meeting not found.").classes("text-caption text-negative")
        return

    all_series = db.list_meeting_series()
    series_opts = _series_dict(all_series)
    current_series = m["series_id"] if m["series_id"] is not None else _NO_SERIES

    def _go_back():
        main_container[0].style("overflow-y: auto")
        main_container[0].clear()
        with main_container[0]:
            _render_list(main_container)

    ui.button("← Back", on_click=_go_back).props("flat dense").classes("q-mb-sm")

    # --- Meeting Setup ---
    title_in = [None]
    date_in = [None]
    attendees_in = [None]
    series_in = [None]

    with ui.expansion("Meeting Setup", value=True).classes("w-full"):
        title_in[0] = ui.input(label="Title", value=m["title"]).classes("w-full")
        date_in[0] = ui.input(label="Date (YYYY-MM-DD)", value=m["date"]).classes("w-full")
        attendees_in[0] = ui.input(label="Attendees", value=m["attendees"] or "").classes("w-full")
        series_in[0] = ui.select(
            label="Series", options=series_opts, value=current_series
        ).classes("w-full")
        ui.button(
            "+ New series",
            on_click=lambda: _open_new_series_dialog(series_in[0]),
        ).props("flat dense size=sm").classes("text-caption q-mt-xs")

        def _save_setup():
            series_key = series_in[0].value
            db.update_meeting(
                meeting_id,
                title=title_in[0].value or m["title"],
                date=date_in[0].value or m["date"],
                attendees=attendees_in[0].value or None,
                series_id=None if series_key == _NO_SERIES else series_key,
            )
            ui.notify("Meeting saved.")

        ui.button("Save meeting", on_click=_save_setup).props("color=primary dense").classes("q-mt-sm")

    # --- Prep ---
    with ui.expansion("Prep", value=True).classes("w-full"):
        brief_container[0] = ui.column().classes("w-full bordered rounded q-pa-sm")
        _render_brief_display(meeting_id, brief_container)

    # --- Debrief ---
    with ui.expansion("Debrief", value=True).classes("w-full"):
        summary_container[0] = ui.column().classes("w-full bordered rounded q-pa-sm")
        _render_summary_display(meeting_id, summary_container)


# ---------------------------------------------------------------------------
# Open detail (switches page layout from list → two-column)
# ---------------------------------------------------------------------------

def _open_detail(meeting_id: int, initial_tab: str, main_container: list) -> None:
    main_container[0].style("overflow: hidden")
    main_container[0].clear()

    tabs_ref: list = [None]
    brief_container: list = [None]
    summary_container: list = [None]

    with main_container[0]:
        with ui.row().classes("w-full gap-0").style("height: 100%; overflow: hidden"):
            with ui.column().style(
                "width: 40%; height: 100%; overflow-y: auto; flex-shrink: 0"
            ).classes("q-pa-md gap-1"):
                _render_detail_left(meeting_id, tabs_ref, brief_container, summary_container, main_container)

            with ui.column().classes("flex-1 h-full gap-0 q-pa-sm").style("display: flex; flex-direction: column"):
                _render_session_panel(meeting_id, initial_tab, tabs_ref, brief_container, summary_container)


# ---------------------------------------------------------------------------
# New meeting dialog
# ---------------------------------------------------------------------------

def _open_new_meeting_dialog(main_container: list) -> None:
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
        ui.button(
            "+ New series",
            on_click=lambda: _open_new_series_dialog(series_in),
        ).props("flat dense size=sm").classes("text-caption q-mt-xs")

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
            def _refresh():
                main_container[0].style("overflow-y: auto")
                main_container[0].clear()
                with main_container[0]:
                    _render_list(main_container)
            ui.timer(0, _refresh, once=True)

        with ui.row().classes("w-full justify-end gap-2 q-mt-sm"):
            ui.button("Cancel", on_click=dlg.close).props("flat dense")
            ui.button("Create", on_click=_create).props("color=primary dense")

    dlg.open()


# ---------------------------------------------------------------------------
# List view (full-width table)
# ---------------------------------------------------------------------------

def _prep_debrief_indicator(has_content: bool) -> str:
    return "●" if has_content else "○"


def _render_group_table(
    meetings: list,
    main_container: list,
) -> None:
    """Render one table for a group of meetings (a series or one-offs)."""
    if not meetings:
        return

    with ui.element("table").classes("w-full").style(
        "border-collapse: collapse; table-layout: fixed;"
        "border: 1px solid rgba(0,0,0,0.15); border-radius: 4px"
    ):
        with ui.element("thead"):
            with ui.element("tr").style(
                "border-bottom: 2px solid rgba(0,0,0,0.2);"
                "background: rgba(0,0,0,0.05)"
            ):
                for label, width in [
                    ("Meeting", "32%"),
                    ("Date", "13%"),
                    ("Attendees", "27%"),
                    ("Prep", "9%"),
                    ("Debrief", "9%"),
                    ("", "10%"),
                ]:
                    with ui.element("th").classes("text-caption text-grey text-left q-pa-xs").style(
                        f"width: {width}; font-weight: 500"
                    ):
                        ui.label(label)

        with ui.element("tbody"):
            for m in meetings:
                has_prep = bool(m["prep_brief"])
                has_debrief = bool(m["debrief_summary"])
                mid = m["id"]

                with ui.element("tr").classes("cursor-pointer").style(
                    "border-bottom: 1px solid rgba(0,0,0,0.1)"
                ):
                    # Meeting name — click opens detail
                    with ui.element("td").classes("q-pa-xs").on(
                        "click", lambda _mid=mid: _open_detail(_mid, "prep", main_container)
                    ):
                        ui.label(m["title"]).classes("text-body2 text-bold cursor-pointer")

                    # Date
                    with ui.element("td").classes("q-pa-xs").on(
                        "click", lambda _mid=mid: _open_detail(_mid, "prep", main_container)
                    ):
                        ui.label(m["date"]).classes("text-caption text-grey")

                    # Attendees
                    with ui.element("td").classes("q-pa-xs").on(
                        "click", lambda _mid=mid: _open_detail(_mid, "prep", main_container)
                    ):
                        ui.label(m["attendees"] or "—").classes("text-caption")

                    # Prep column
                    with ui.element("td").classes("q-pa-xs text-center"):
                        with ui.row().classes("gap-1 items-center justify-center no-wrap"):
                            ui.label(_prep_debrief_indicator(has_prep)).classes(
                                "text-body2 " + ("text-positive" if has_prep else "text-grey-6")
                            )
                            ui.button(
                                "→",
                                on_click=lambda _mid=mid: _open_detail(_mid, "prep", main_container),
                            ).props("flat dense size=xs")

                    # Debrief column
                    with ui.element("td").classes("q-pa-xs text-center"):
                        with ui.row().classes("gap-1 items-center justify-center no-wrap"):
                            ui.label(_prep_debrief_indicator(has_debrief)).classes(
                                "text-body2 " + ("text-positive" if has_debrief else "text-grey-6")
                            )
                            ui.button(
                                "→",
                                on_click=lambda _mid=mid: _open_detail(_mid, "debrief", main_container),
                            ).props("flat dense size=xs")

                    # Delete column
                    with ui.element("td").classes("q-pa-xs text-center"):
                        ui.button(
                            "✕",
                            on_click=lambda _mid=mid, _title=m["title"]: _confirm_delete_meeting(
                                _mid, _title, main_container
                            ),
                        ).props("flat dense size=xs color=negative")


def _render_list(main_container: list) -> None:
    meetings = db.list_meetings(limit=50)
    all_series = {s["id"]: s for s in db.list_meeting_series()}

    # Group by series_id
    buckets: dict = {}
    for m in meetings:
        sid = m["series_id"]
        buckets.setdefault(sid, []).append(m)

    named_sids = sorted(
        [sid for sid in buckets if sid is not None],
        key=lambda sid: all_series[sid]["name"].lower(),
    )

    with ui.row().classes("w-full items-center justify-between q-pb-sm").style("flex-shrink: 0"):
        ui.label("Meetings").classes("text-h5")
        ui.button(
            "+ New Meeting",
            on_click=lambda: _open_new_meeting_dialog(main_container),
        ).props("flat dense")

    if not meetings:
        ui.label("No meetings yet.").classes("text-caption text-grey q-mt-sm")
        return

    with ui.scroll_area().classes("w-full").style("flex: 1"):
        for sid in named_sids:
            series_name = all_series[sid]["name"]
            ui.label(series_name).classes("text-overline text-bold q-mt-md q-mb-xs")
            _render_group_table(buckets[sid], main_container)

        if None in buckets:
            ui.label("One-off meetings").classes("text-overline text-bold q-mt-md q-mb-xs")
            _render_group_table(buckets[None], main_container)


# ---------------------------------------------------------------------------
# Page entry point
# ---------------------------------------------------------------------------

@ui.page("/meetings")
def meetings_page() -> None:
    create_nav("/meetings")

    with ui.column().classes("w-full q-pa-md").style(
        "height: calc(100vh - 56px); overflow-y: auto; display: flex; flex-direction: column"
    ) as outer:
        main_container: list = [outer]
        _render_list(main_container)
