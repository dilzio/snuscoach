import asyncio
import json
from datetime import date

from nicegui import ui

from snuscoach import coach, db, prompts
from snuscoach.cli import _compute_nudge_gaps
from snuscoach.web.components.chat import ChatPanel
from snuscoach.web.components.nav import create_nav


def _nudge_card(panel_ref: list) -> None:
    with ui.card().classes("w-full").style(
        "max-height: 45vh; display: flex; flex-direction: column"
    ):
        ui.label("Coach nudge").classes("text-subtitle2 text-bold")
        content_col = ui.column().classes("w-full").style(
            "overflow-y: auto; flex: 1; min-height: 0"
        )
        with content_col:
            spinner = ui.spinner("dots")

    async def _load() -> None:
        today = date.today().isoformat()
        report: str | None = None
        gaps: dict | None = None

        # Today's nudge: exact date match, no LLM call needed
        cached = db.get_nudge_for_date(today)
        if cached:
            report = cached["report"]
        else:
            # No nudge for today — try generating one via LLM
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
                    pass  # caching failed; nudge still displays from in-memory report

            # LLM unavailable and no today's nudge: fall back to the most recent
            # nudge from any prior date rather than showing an error
            if report is None:
                prior = db.get_latest_nudge()
                if prior:
                    report = prior["report"]

        spinner.delete()
        with content_col:
            if report is None:
                ui.label("Nudge unavailable — check ANTHROPIC_API_KEY").classes("text-body2 text-grey")
            else:
                ui.markdown(report).classes("text-body2")
            ui.button(
                "Open in chat ▸",
                on_click=lambda: asyncio.ensure_future(panel_ref[0].seed(report or "")),
            ).props("flat dense")

    ui.timer(0, _load, once=True)


def _upcoming_meetings_card() -> None:
    today = date.today().isoformat()
    all_meetings = db.list_meetings()
    upcoming = sorted(
        [m for m in all_meetings if m["date"] >= today],
        key=lambda m: m["date"],
    )[:3]

    with ui.card().classes("w-full"):
        ui.label("Upcoming meetings").classes("text-subtitle2 text-bold")
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
    label = (
        f"{count} win{'s' if count != 1 else ''} with no visibility post"
        if count
        else "All wins have posts."
    )

    with ui.card().classes("w-full cursor-pointer").on(
        "click", lambda: ui.navigate.to("/wins-posts")
    ):
        ui.label("Wins without a post").classes("text-subtitle2 text-bold")
        ui.label(label).classes("text-body2")


@ui.page("/")
def home_page() -> None:
    create_nav("/")
    panel: list[ChatPanel | None] = [None]

    with ui.row().classes("w-full gap-0").style(
        "height: calc(100vh - 56px); overflow: hidden"
    ):
        with ui.column().classes("q-pa-md gap-4").style(
            "width: 360px; height: 100%; overflow-y: auto; flex-shrink: 0"
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
            )
