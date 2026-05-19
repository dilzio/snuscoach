import asyncio
import json
from datetime import date

from nicegui import ui

from snuscoach import coach, db, prompts
from snuscoach.cli import _compute_nudge_gaps
from snuscoach.web.components.chat import ChatPanel
from snuscoach.web.components.nav import create_nav


def _nudge_card(panel_ref: list) -> None:
    with ui.card().classes("sc-card sc-card--nudge w-full").style(
        "max-height: 45vh; display: flex; flex-direction: column"
    ):
        with ui.row().classes("items-center gap-2 q-mb-xs"):
            ui.icon("tips_and_updates", size="xs").style("color: var(--sc-accent-nudge)")
            ui.label("Coach nudge").classes("sc-label")

        content_col = ui.column().classes("w-full").style(
            "overflow-y: auto; flex: 1; min-height: 0"
        )
        with content_col:
            spinner = ui.spinner("dots")

    async def _load() -> None:
        today = date.today().isoformat()
        report: str | None = None
        gaps: dict | None = None

        cached = db.get_nudge_for_date(today)
        if cached:
            report = cached["report"]
        else:
            try:
                gaps = _compute_nudge_gaps()
                prompt = prompts.nudge_analysis_prompt(gaps, mode="report")
                if coach.is_stubbed("NUDGE_REPORT"):
                    report = coach.canned_response("NUDGE_REPORT")
                else:
                    loop = asyncio.get_running_loop()
                    report = await loop.run_in_executor(
                        None, coach.draft, [{"role": "user", "content": prompt}]
                    )
            except Exception:
                report = None

            if report is not None and gaps is not None:
                try:
                    db.add_nudge(today, report, json.dumps(gaps))
                except Exception:
                    pass

            if report is None:
                prior = db.get_latest_nudge()
                if prior:
                    report = prior["report"]

        spinner.delete()
        with content_col:
            if report is None:
                ui.label("Nudge unavailable — check ANTHROPIC_API_KEY").classes(
                    "text-body2 text-grey"
                )
            else:
                ui.markdown(report).classes("text-body2 sc-nudge-md")
            ui.button(
                "Open in chat ▸",
                on_click=lambda: asyncio.ensure_future(panel_ref[0].seed(report or "")),
            ).props("flat dense").style("color: var(--sc-accent-nudge)")

    ui.timer(0, _load, once=True)


def _upcoming_meetings_card() -> None:
    today = date.today().isoformat()
    all_meetings = db.list_meetings()
    upcoming = sorted(
        [m for m in all_meetings if m["date"] >= today],
        key=lambda m: m["date"],
    )[:3]

    with ui.card().classes("sc-card sc-card--meet w-full cursor-pointer").on("click", lambda: ui.navigate.to("/meetings")):
        with ui.row().classes("items-center gap-2 q-mb-xs"):
            ui.icon("calendar_today", size="xs").style("color: var(--sc-accent-meet)")
            ui.label("Upcoming meetings").classes("sc-label")
        if not upcoming:
            ui.label("No upcoming meetings.").classes("text-caption text-grey")
        else:
            for m in upcoming:
                ui.link(f"{m['date']}  {m['title']}", "/meetings").classes("text-body2 block")


def _wins_gap_card() -> None:
    try:
        gaps = _compute_nudge_gaps()
        count = gaps["wins_without_post"]
    except Exception:
        count = 0

    accent = "var(--sc-accent-wins)" if count else "var(--q-color-positive)"
    card_class = (
        "sc-card sc-card--wins w-full cursor-pointer"
        if count
        else "sc-card sc-card--wins-ok w-full cursor-pointer"
    )

    with ui.card().classes(card_class).on("click", lambda: ui.navigate.to("/wins-posts")):
        with ui.row().classes("items-center gap-2 q-mb-xs"):
            ui.icon("emoji_events", size="xs").style(f"color: {accent}")
            ui.label("Visibility").classes("sc-label")
        if count:
            with ui.row().classes("items-center justify-between"):
                with ui.row().classes("items-baseline gap-1"):
                    ui.label(str(count)).style(
                        f"font-size: 28px; font-weight: 700; color: {accent}; line-height: 1"
                    )
                    ui.label(f"win{'s' if count != 1 else ''} without a post").classes(
                        "text-body2"
                    )
                ui.icon("arrow_forward").style(f"color: {accent}; opacity: 0.5; font-size: 20px")
        else:
            ui.label("All wins have posts.").classes("text-body2 text-grey")


@ui.page("/")
def home_page() -> None:
    create_nav("/")
    panel: list[ChatPanel | None] = [None]

    with ui.row().classes("w-full gap-0").style(
        "height: calc(100vh - 56px); overflow: hidden"
    ):
        with ui.column().classes("q-pa-md").style(
            "width: 360px; height: 100%; overflow: hidden; flex-shrink: 0; "
            "gap: 12px; background: var(--sc-content-bg)"
        ):
            _nudge_card(panel)
            _upcoming_meetings_card()
            _wins_gap_card()

        with ui.column().classes("flex-1 h-full"):
            thread_key = f"home-nudge-{date.today().isoformat()}"
            panel[0] = ChatPanel(
                placeholder="What's on your mind?",
                coach_fn=coach.stub_fn("CHAT") if coach.is_stubbed("CHAT") else coach.conversation,
                thread_key=thread_key,
                empty_state="Ask me anything about your week,\nyour stakeholders, or your next move.",
            )
