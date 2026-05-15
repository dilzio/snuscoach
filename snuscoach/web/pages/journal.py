import asyncio
from datetime import date

from nicegui import ui

from snuscoach import coach, db, prompts
from snuscoach.web.components.chat import ChatPanel
from snuscoach.web.components.nav import create_nav


def _truncate(text: str, n: int = 80) -> str:
    return text[:n] + "…" if len(text) > n else text


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _format_transcript(messages: list[dict]) -> str:
    parts = []
    for m in messages[1:]:  # skip the first user task prompt
        label = "coach" if m["role"] == "assistant" else "you"
        parts.append(f"{label}: {m['content']}")
    return "\n\n".join(parts)


def _adopt_transcript(panel_ref: list, content_ta: list) -> None:
    p = panel_ref[0]
    if not p or len(p.messages) < 2:
        ui.notify("Start a conversation first.", type="warning")
        return
    content_ta[0].value = _format_transcript(p.messages)
    ui.notify("Transcript adopted — click Save Entry to persist.")


# ---------------------------------------------------------------------------
# Detail view
# ---------------------------------------------------------------------------

def _open_detail(entry: dict | None, main_container: list) -> None:
    main_container[0].style("height: calc(100vh - 56px); overflow: hidden")
    main_container[0].clear()

    content_ta: list = [None]
    panel_ref: list[ChatPanel | None] = [None]

    def _go_back():
        main_container[0].style("overflow-y: auto")
        main_container[0].clear()
        with main_container[0]:
            _render_list(main_container)

    with main_container[0]:
        with ui.row().classes("w-full gap-0").style("height: 100%; overflow: hidden"):
            with ui.column().style(
                "width: 40%; height: 100%; overflow-y: auto; flex-shrink: 0;"
                "background: #fff; border-right: 1px solid var(--sc-border)"
            ).classes("q-pa-md gap-1"):
                _render_detail_left(entry, content_ta, panel_ref, _go_back)

            with ui.column().classes("flex-1 h-full q-pa-sm gap-0").style(
                "display: flex; flex-direction: column"
            ):
                _render_detail_right(entry, content_ta, panel_ref)


def _render_detail_left(
    entry: dict | None,
    content_ta: list,
    panel_ref: list,
    go_back_fn,
) -> None:
    ui.button("← Back", on_click=go_back_fn).props("flat dense").classes("q-mb-sm")
    ui.label("Entry Details").classes("text-subtitle2 text-bold q-mb-xs")

    date_str = entry["created_at"][:10] if entry else date.today().isoformat()
    entry_type = entry["entry_type"] if entry else "journal"
    ui.label(f"Date: {date_str}").classes("text-caption text-grey")
    ui.label(f"Type: {entry_type}").classes("text-caption text-grey q-mb-xs")

    ui.label("Content").classes("text-caption text-grey q-mt-xs")
    content_ta[0] = ui.textarea(
        value=entry["content"] if entry else ""
    ).props("rows=10 outlined").classes("w-full")

    ui.button(
        "Adopt transcript ↓",
        on_click=lambda: _adopt_transcript(panel_ref, content_ta),
    ).props("flat dense size=sm").classes("q-mt-xs")

    def _save():
        content = content_ta[0].value.strip()
        if not content:
            ui.notify("Content is required.", type="warning")
            return
        if entry:
            db.update_journal_entry(entry["id"], content)
            ui.notify("Entry saved.")
        else:
            coach_opening = None
            p = panel_ref[0]
            if p and p.messages:
                coach_opening = next(
                    (m["content"] for m in p.messages if m["role"] == "assistant"),
                    None,
                )
            db.add_journal_entry(content, coach_prompt=coach_opening, entry_type="journal")
            go_back_fn()

    ui.button("Save Entry", on_click=_save).props("color=primary dense").classes("q-mt-xs")


def _render_detail_right(
    entry: dict | None,
    content_ta: list,
    panel_ref: list,
) -> None:
    coach_fn = coach.stub_fn("JOURNAL") if coach.is_stubbed("JOURNAL") else coach.draft
    thread_key = f"journal-{entry['id']}" if entry else None

    with ui.row().classes("w-full items-center justify-between q-mb-xs").style(
        "flex-shrink: 0"
    ):
        ui.label("Chat: Journal check-in").classes("text-overline text-grey")

    with ui.column().classes("w-full").style("flex: 1; min-height: 0"):
        panel_ref[0] = ChatPanel(
            placeholder="Reflect on your day...",
            coach_fn=coach_fn,
            thread_key=thread_key,
        )
        if entry is None:
            async def _auto_seed():
                opening = prompts.journal_opening_prompt()
                await panel_ref[0].seed(opening)
            ui.timer(0, _auto_seed, once=True)


# ---------------------------------------------------------------------------
# List view
# ---------------------------------------------------------------------------

def _refresh_list(main_container: list) -> None:
    main_container[0].style("overflow-y: auto")
    main_container[0].clear()
    with main_container[0]:
        _render_list(main_container)


def _render_list(main_container: list) -> None:
    entries = db.list_journal_entries(limit=50)

    with ui.scroll_area().classes("w-full").style("flex: 1"):
        with ui.column().classes("w-full q-pa-md gap-2"):
            with ui.row().classes("w-full items-center justify-between q-pb-xs").style(
                "flex-shrink: 0"
            ):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("book", size="xs").style("color: var(--sc-accent-nudge)")
                    ui.label("Journal").classes("sc-label q-mt-md q-mb-xs")
                ui.button(
                    "+ New Entry",
                    on_click=lambda: _open_detail(None, main_container),
                ).props("flat dense")

            if not entries:
                ui.label("No entries yet.").classes("text-caption text-grey q-mt-xs")
                return

            with ui.element("table").classes("w-full").style(
                "border-collapse: collapse; table-layout: fixed;"
                "border: 1px solid var(--sc-border); border-radius: 6px; overflow: hidden"
            ):
                with ui.element("thead"):
                    with ui.element("tr").style(
                        "border-bottom: 1px solid var(--sc-border);"
                        "background: var(--sc-border-light)"
                    ):
                        for label, width in [
                            ("Date", "18%"),
                            ("Type", "15%"),
                            ("Preview", "67%"),
                        ]:
                            with ui.element("th").classes(
                                "sc-label text-left q-pa-xs"
                            ).style(f"width: {width}"):
                                ui.label(label)

                with ui.element("tbody"):
                    for entry in entries:
                        with ui.element("tr").classes("cursor-pointer").style(
                            "border-bottom: 1px solid var(--sc-border-light)"
                        ).on("click", lambda _e=entry: _open_detail(_e, main_container)):
                            with ui.element("td").classes("q-pa-xs"):
                                ui.label(entry["created_at"][:10]).classes(
                                    "text-caption text-grey"
                                )
                            with ui.element("td").classes("q-pa-xs"):
                                ui.badge(
                                    entry["entry_type"] or "journal",
                                    color="primary" if (entry["entry_type"] or "journal") == "journal" else "secondary",
                                ).props("outline")
                            with ui.element("td").classes("q-pa-xs"):
                                ui.label(_truncate(entry["content"])).classes(
                                    "text-caption text-grey"
                                )


# ---------------------------------------------------------------------------
# Page entry point
# ---------------------------------------------------------------------------

@ui.page("/journal")
def journal_page() -> None:
    create_nav("/journal")
    with ui.column().classes("w-full").style(
        "height: calc(100vh - 56px); overflow-y: auto; display: flex; flex-direction: column;"
        "background: var(--sc-content-bg)"
    ) as outer:
        main_container: list = [outer]
        _render_list(main_container)
