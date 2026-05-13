import asyncio
from datetime import date

from nicegui import ui

from snuscoach import coach, db
from snuscoach.web.components.chat import ChatPanel
from snuscoach.web.components.nav import create_nav


def _truncate(text: str, n: int = 80) -> str:
    return text[:n] + "…" if len(text) > n else text


# ---------------------------------------------------------------------------
# Wins ledger
# ---------------------------------------------------------------------------

def _build_win_inject(win) -> str:
    lines = [f"Let's focus on this win: {win['title']}."]
    if win["description"]:
        lines.append(win["description"])
    lines.append("\nPlease draft a visibility post for it.")
    return "\n".join(lines)


def _render_win_card(win, selected_ids: set, wins_container: list, panel_ref: list) -> None:
    wid = win["id"]
    is_selected = wid in selected_ids

    highlight = (
        "background: rgba(25, 118, 210, 0.15); border: 1px solid rgba(25, 118, 210, 0.4);"
        if is_selected
        else "border: 1px solid rgba(255,255,255,0.15);"
    )

    def _toggle_select():
        if wid in selected_ids:
            selected_ids.discard(wid)
        else:
            selected_ids.clear()
            selected_ids.add(wid)
        _render_wins_section(selected_ids, wins_container, panel_ref)

    with ui.element("div").classes(
        "w-full rounded q-pa-sm q-mb-xs cursor-pointer"
    ).style(highlight).on("click", _toggle_select):
        with ui.row().classes("w-full items-start justify-between gap-1"):
            ui.label(win["title"]).classes("text-body2 text-bold")
            ui.label(win["created_at"][:10]).classes("text-caption text-grey-5")
        if win["description"]:
            ui.label(_truncate(win["description"])).classes("text-caption text-grey q-mt-xs")
        if is_selected:
            def _open_in_chat(_win=win):
                if panel_ref[0] is not None:
                    asyncio.ensure_future(panel_ref[0].inject(_build_win_inject(_win)))

            ui.button("Open in chat →", on_click=_open_in_chat).props(
                "flat dense size=sm color=primary"
            ).classes("q-mt-xs")


def _render_wins_section(selected_ids: set, wins_container: list, panel_ref: list) -> None:
    wins_container[0].clear()
    with wins_container[0]:
        with ui.row().classes("w-full items-center justify-between q-mb-xs").style("flex-shrink: 0"):
            ui.label("Wins").classes("text-overline text-bold")
            ui.button(
                "+ Add Win",
                on_click=lambda: _open_add_win_dialog(selected_ids, wins_container, panel_ref),
            ).props("flat dense size=sm")

        wins = db.list_wins()
        if not wins:
            ui.label("No wins yet.").classes("text-caption text-grey q-mt-xs")
            return

        with ui.scroll_area().classes("w-full").style("flex: 1; min-height: 0"):
            for win in wins:
                _render_win_card(win, selected_ids, wins_container, panel_ref)


def _open_add_win_dialog(selected_ids: set, wins_container: list, panel_ref: list) -> None:
    with ui.dialog() as dlg, ui.card().classes("w-96"):
        ui.label("Add Win").classes("text-subtitle1 text-bold q-mb-sm")
        title_in = ui.input(label="Title *").classes("w-full")
        desc_in = ui.textarea(label="Description (optional)").props(
            "rows=3 outlined"
        ).classes("w-full")

        def _save():
            title = title_in.value.strip()
            if not title:
                ui.notify("Title is required.", type="warning")
                return
            db.add_win(title, desc_in.value.strip() or None)
            dlg.close()
            ui.notify("Win added.")

            def _refresh():
                _render_wins_section(selected_ids, wins_container, panel_ref)

            ui.timer(0, _refresh, once=True)

        with ui.row().classes("w-full justify-end gap-2 q-mt-sm"):
            ui.button("Cancel", on_click=dlg.close).props("flat dense")
            ui.button("Add", on_click=_save).props("color=primary dense")

    dlg.open()


# ---------------------------------------------------------------------------
# Post history
# ---------------------------------------------------------------------------

def _open_post_expand_dialog(post) -> None:
    audience_label = f" / {post['audience']}" if post["audience"] else ""
    with ui.dialog() as dlg, ui.card().style("min-width: 500px; max-width: 720px"):
        with ui.row().classes("w-full items-center justify-between q-mb-xs"):
            ui.label(post["channel"]).classes("text-subtitle1 text-bold")
            ui.label(post["posted_at"]).classes("text-caption text-grey")
        if post["audience"]:
            ui.label(f"Audience: {post['audience']}").classes("text-caption text-grey q-mb-xs")
        ui.separator().classes("q-mb-sm")
        with ui.scroll_area().style("max-height: 60vh"):
            ui.markdown(post["content"]).classes("text-body2")
        with ui.row().classes("w-full justify-end q-mt-sm"):
            ui.button("Close", on_click=dlg.close).props("flat dense")
    dlg.open()


def _render_post_card(post) -> None:
    audience_label = f" / {post['audience']}" if post["audience"] else ""
    first_line = post["content"].splitlines()[0] if post["content"] else ""
    snippet = _truncate(first_line, 60)

    with ui.element("div").classes(
        "w-full rounded q-pa-sm q-mb-xs cursor-pointer"
    ).style(
        "border: 1px solid rgba(255,255,255,0.1);"
    ).on("click", lambda _p=post: _open_post_expand_dialog(_p)):
        with ui.row().classes("w-full items-center justify-between gap-1"):
            ui.label(post["channel"]).classes("text-body2 text-bold")
            ui.label(post["posted_at"]).classes("text-caption text-grey-5")
        if post["audience"]:
            ui.label(post["audience"]).classes("text-caption text-grey")
        ui.label(snippet).classes("text-caption q-mt-xs")


def _render_posts_section(posts_container: list) -> None:
    posts_container[0].clear()
    with posts_container[0]:
        posts = db.list_posts()
        if not posts:
            ui.label("No posts yet.").classes("text-caption text-grey")
            return
        for post in posts:
            _render_post_card(post)


# ---------------------------------------------------------------------------
# Save Post dialog
# ---------------------------------------------------------------------------

def _open_save_post_dialog(panel_ref: list, posts_container: list) -> None:
    p = panel_ref[0]
    last_reply = ""
    if p and p.messages:
        last_reply = next(
            (msg["content"] for msg in reversed(p.messages) if msg["role"] == "assistant"),
            "",
        )
    today = date.today().isoformat()

    with ui.dialog() as dlg, ui.card().style("min-width: 500px; max-width: 720px"):
        ui.label("Save Post").classes("text-subtitle1 text-bold q-mb-sm")
        content_in = ui.textarea(
            label="Content *",
            value=last_reply,
        ).props("rows=6 outlined").classes("w-full")
        channel_in = ui.input(
            label="Channel *",
            placeholder="e.g. slack-eng, email-skip",
        ).classes("w-full")
        audience_in = ui.input(
            label="Audience (optional)",
            placeholder="e.g. eng team, skip",
        ).classes("w-full")
        posted_at_in = ui.input(
            label="Posted at (YYYY-MM-DD)",
            value=today,
        ).classes("w-full")

        def _save():
            content = content_in.value.strip()
            channel = channel_in.value.strip()
            if not content:
                ui.notify("Content is required.", type="warning")
                return
            if not channel:
                ui.notify("Channel is required.", type="warning")
                return
            db.add_post(
                content=content,
                channel=channel,
                audience=audience_in.value.strip() or None,
                posted_at=posted_at_in.value.strip() or today,
            )
            dlg.close()
            ui.notify("Post saved.")

            def _refresh():
                _render_posts_section(posts_container)

            ui.timer(0, _refresh, once=True)

        with ui.row().classes("w-full justify-end gap-2 q-mt-sm"):
            ui.button("Cancel", on_click=dlg.close).props("flat dense")
            ui.button("Save", on_click=_save).props("color=primary dense")

    dlg.open()


# ---------------------------------------------------------------------------
# Page entry point
# ---------------------------------------------------------------------------

@ui.page("/wins-posts")
def wins_posts_page() -> None:
    create_nav("/wins-posts")

    selected_ids: set = set()
    wins_container: list = [None]
    posts_container: list = [None]
    panel_ref: list[ChatPanel | None] = [None]

    coach_fn = coach.stub_fn("POST_DRAFT") if coach.is_stubbed("POST_DRAFT") else coach.draft

    with ui.row().classes("w-full gap-0").style(
        "height: calc(100vh - 56px); overflow: hidden"
    ):
        # --- Left column: wins ledger (top) + post history (bottom) ---
        with ui.column().style(
            "width: 40%; height: 100%; overflow: hidden; flex-shrink: 0;"
            "display: flex; flex-direction: column"
        ).classes("q-pa-md gap-1"):

            # Wins section — grows to fill remaining space
            wins_container[0] = ui.column().classes("w-full").style(
                "flex: 1; min-height: 0; overflow: hidden; display: flex; flex-direction: column"
            )
            with wins_container[0]:
                _render_wins_section(selected_ids, wins_container, panel_ref)

            ui.separator().classes("q-my-xs").style("flex-shrink: 0")

            # Post history section — capped height
            ui.label("Post history").classes("text-overline text-bold").style("flex-shrink: 0")
            posts_container[0] = ui.column().classes("w-full").style(
                "max-height: calc(35vh - 28px); overflow-y: auto; flex-shrink: 0"
            )
            with posts_container[0]:
                _render_posts_section(posts_container)

        # --- Right column: drafting chat ---
        with ui.column().classes("flex-1 h-full gap-0 q-pa-sm").style(
            "display: flex; flex-direction: column"
        ):
            with ui.row().classes("w-full items-center justify-between q-mb-xs").style(
                "flex-shrink: 0"
            ):
                ui.label("Drafting chat").classes("text-overline text-grey")
                ui.button(
                    "Save Post ▾",
                    on_click=lambda: _open_save_post_dialog(panel_ref, posts_container),
                ).props("color=primary dense")

            with ui.column().classes("w-full").style("flex: 1; min-height: 0"):
                panel_ref[0] = ChatPanel(
                    placeholder="Draft a Slack post, email to skip, brag doc entry...",
                    coach_fn=coach_fn,
                    thread_key="wins-posts-draft",
                )
