from datetime import date

from nicegui import ui

from snuscoach import coach, db
from snuscoach.web.components.chat import ChatPanel
from snuscoach.web.components.nav import create_nav


def _truncate(text: str, n: int = 60) -> str:
    return text[:n] + "…" if len(text) > n else text


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _adopt_ai_draft(panel_ref: list, target_ta: list, notify_msg: str) -> None:
    p = panel_ref[0]
    if not p or not p.messages:
        ui.notify("No chat output yet.", type="warning")
        return
    last_reply = next(
        (msg["content"] for msg in reversed(p.messages) if msg["role"] == "assistant"),
        None,
    )
    if last_reply is None:
        ui.notify("No assistant reply yet.", type="warning")
        return
    if target_ta[0] is not None:
        target_ta[0].value = last_reply
        ui.notify(notify_msg)


# ---------------------------------------------------------------------------
# Post detail view
# ---------------------------------------------------------------------------

def _build_post_seed_prompt(post: dict | None, win: dict | None) -> str:
    if post is None and win is not None:
        desc = f" — {win['description']}" if win["description"] else ""
        return (
            f"I want to draft a visibility post for this win: **{win['title']}**{desc}. "
            "Please draft a compelling post I can share on a professional channel."
        )
    elif post is not None:
        audience_str = f", audience: {post['audience']}" if post["audience"] else ""
        return (
            f"I'd like to improve this visibility post (channel: {post['channel']}{audience_str}):\n\n"
            f"{post['content']}\n\n"
            "What improvements would you suggest to make it more compelling and impactful?"
        )
    else:
        return "Help me draft a visibility post. I'll share what I want to highlight."


def _open_post_detail(
    post: dict | None,
    win_id: int | None,
    go_back_fn,
    main_container: list,
) -> None:
    main_container[0].style("height: calc(100vh - 56px); overflow: hidden")
    main_container[0].clear()

    content_ta: list = [None]
    panel_ref: list[ChatPanel | None] = [None]

    win = db.get_win(win_id) if win_id else None
    seed_prompt = _build_post_seed_prompt(post, win)
    thread_key = f"post-{post['id']}" if post else None

    with main_container[0]:
        with ui.row().classes("w-full gap-0").style("height: 100%; overflow: hidden"):
            with ui.column().style(
                "width: 40%; height: 100%; overflow-y: auto; flex-shrink: 0;"
                "background: #fafafa; border-right: 1px solid var(--sc-border)"
            ).classes("q-pa-md gap-1"):
                _render_post_detail_left(post, win_id, win, content_ta, panel_ref, go_back_fn)
            with ui.column().classes("flex-1 h-full q-pa-sm gap-0").style(
                "display: flex; flex-direction: column"
            ):
                _render_post_detail_right(post, content_ta, panel_ref, thread_key, seed_prompt)


def _render_post_detail_left(
    post: dict | None,
    win_id: int | None,
    win: dict | None,
    content_ta: list,
    panel_ref: list,
    go_back_fn,
) -> None:
    ui.button("Back", on_click=go_back_fn).props("flat dense icon=chevron_left").classes("q-mb-sm text-grey")

    ui.label("Post Details").classes("text-subtitle2 text-bold q-mb-xs")

    today = date.today().isoformat()
    ui.label("Content").classes("text-caption text-grey q-mt-xs")
    content_ta[0] = ui.textarea(
        value=post["content"] if post else ""
    ).props("rows=6 outlined").classes("w-full")

    channel_in = ui.input(
        label="Channel *",
        value=post["channel"] if post else "",
        placeholder="e.g. slack-eng, email-skip",
    ).classes("w-full")
    audience_in = ui.input(
        label="Audience (optional)",
        value=(post["audience"] or "") if post else "",
    ).classes("w-full")
    date_in = ui.input(
        label="Posted at (YYYY-MM-DD)",
        value=post["posted_at"] if post else today,
    ).classes("w-full")

    if win:
        ui.label(f"Win: {win['title']}").classes("text-caption text-grey q-mt-xs")

    def _save():
        content = content_ta[0].value.strip()
        channel = channel_in.value.strip()
        if not content:
            ui.notify("Content is required.", type="warning")
            return
        if not channel:
            ui.notify("Channel is required.", type="warning")
            return
        if post:
            db.update_post(
                post["id"],
                content,
                channel,
                audience_in.value.strip() or None,
                date_in.value.strip() or post["posted_at"],
            )
            ui.notify("Post saved.")
        else:
            db.add_post(
                content=content,
                channel=channel,
                audience=audience_in.value.strip() or None,
                posted_at=date_in.value.strip() or today,
                win_id=win_id,
            )
            go_back_fn()

    ui.button("Save Post", on_click=_save).props("unelevated dense color=primary size=sm").classes("q-mt-xs")


def _render_post_detail_right(
    post: dict | None,
    content_ta: list,
    panel_ref: list,
    thread_key: str | None,
    seed_prompt: str,
) -> None:
    coach_fn = coach.stub_fn("POST_DRAFT") if coach.is_stubbed("POST_DRAFT") else coach.draft

    chat_label = f"Chat: {post['channel']} post" if post else "Chat: New post"

    with ui.row().classes("w-full items-center justify-between q-mb-xs").style(
        "flex-shrink: 0"
    ):
        ui.label(chat_label).classes("text-overline text-grey")
        ui.button(
            "Adopt AI draft ↓",
            on_click=lambda: _adopt_ai_draft(
                panel_ref, content_ta, "Content updated — click Save Post to persist."
            ),
        ).props("flat dense size=sm")

    with ui.column().classes("w-full").style("flex: 1; min-height: 0"):
        panel_ref[0] = ChatPanel(
            placeholder="Ask the coach to help draft or improve this post...",
            coach_fn=coach_fn,
            thread_key=thread_key,
        )
        if not panel_ref[0].messages:
            panel_ref[0].input.value = seed_prompt


# ---------------------------------------------------------------------------
# Add Win dialog
# ---------------------------------------------------------------------------

def _open_add_win_dialog(main_container: list) -> None:
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
            win_id = db.add_win(title, desc_in.value.strip() or None)
            new_win = db.get_win(win_id)
            seed = f"I just logged a new win: **{new_win['title']}**."
            if new_win["description"]:
                seed += f" {new_win['description']}."
            seed += " Help me write a compelling description that clearly communicates the impact."
            _open_detail(new_win, main_container, seed_prompt=seed)
            dlg.close()

        with ui.row().classes("w-full justify-end gap-2 q-mt-sm"):
            ui.button("Cancel", on_click=dlg.close).props("flat dense")
            ui.button("Add", on_click=_save).props("color=primary dense")

    dlg.open()


# ---------------------------------------------------------------------------
# List view helpers
# ---------------------------------------------------------------------------

def _wins_with_posts() -> set[int]:
    try:
        return {p["win_id"] for p in db.list_posts() if p["win_id"] is not None}
    except Exception:
        return set()


def _refresh_list(main_container: list) -> None:
    main_container[0].style("overflow-y: auto")
    main_container[0].clear()
    with main_container[0]:
        _render_list(main_container)


def _render_wins_table(main_container: list) -> None:
    wins = db.list_wins()
    wins_with_posts_set = _wins_with_posts()

    if not wins:
        ui.label("No wins yet.").classes("text-caption text-grey q-px-md q-py-sm")
        return

    with ui.element("table").classes("sc-table w-full"):
        with ui.element("thead"):
            with ui.element("tr"):
                for label, width in [("Title", "22%"), ("Description", "43%"), ("Date", "13%"), ("Posted", "22%")]:
                    with ui.element("th").style(f"width: {width}"):
                        ui.label(label)
        with ui.element("tbody"):
            for win in wins:
                wid = win["id"]
                has_post = wid in wins_with_posts_set
                with ui.element("tr").classes("sc-tr-click cursor-pointer"):
                    with ui.element("td").on("click", lambda _w=win: _open_detail(_w, main_container)):
                        ui.label(win["title"]).classes("text-bold")
                    with ui.element("td").on("click", lambda _w=win: _open_detail(_w, main_container)):
                        ui.label(_truncate(win["description"] or "—")).classes("text-caption text-grey")
                    with ui.element("td").on("click", lambda _w=win: _open_detail(_w, main_container)):
                        ui.label(win["created_at"][:10]).classes("text-caption text-grey")
                    with ui.element("td"):
                        with ui.row().classes("gap-1 items-center no-wrap"):
                            if has_post:
                                ui.label("✓").classes("text-positive text-body2")
                            ui.button(
                                "↗ New Post",
                                on_click=lambda _wid=wid: _open_post_detail(
                                    None, _wid, lambda: _refresh_list(main_container), main_container,
                                ),
                            ).props("flat dense size=xs")


def _render_posts_table(main_container: list) -> None:
    posts = db.list_posts()
    wins_by_id = {w["id"]: w["title"] for w in db.list_wins()}

    if not posts:
        ui.label("No posts yet.").classes("text-caption text-grey q-px-md q-py-sm")
        return

    with ui.element("table").classes("sc-table w-full"):
        with ui.element("thead"):
            with ui.element("tr"):
                for label, width in [("Channel", "22%"), ("Date", "13%"), ("Audience", "25%"), ("Win", "40%")]:
                    with ui.element("th").style(f"width: {width}"):
                        ui.label(label)
        with ui.element("tbody"):
            for post in posts:
                linked_win = wins_by_id.get(post["win_id"], "—") if post["win_id"] else "—"
                with ui.element("tr").classes("sc-tr-click cursor-pointer"):
                    with ui.element("td").on("click", lambda _p=post: _open_post_detail(_p, _p["win_id"], lambda: _refresh_list(main_container), main_container)):
                        ui.label(post["channel"]).classes("text-bold")
                    with ui.element("td").on("click", lambda _p=post: _open_post_detail(_p, _p["win_id"], lambda: _refresh_list(main_container), main_container)):
                        ui.label(post["posted_at"]).classes("text-caption text-grey")
                    with ui.element("td").on("click", lambda _p=post: _open_post_detail(_p, _p["win_id"], lambda: _refresh_list(main_container), main_container)):
                        ui.label(post["audience"] or "—").classes("text-caption text-grey")
                    with ui.element("td").on("click", lambda _p=post: _open_post_detail(_p, _p["win_id"], lambda: _refresh_list(main_container), main_container)):
                        ui.label(_truncate(linked_win, 50)).classes("text-caption text-grey")


def _render_list(main_container: list) -> None:
    with ui.row().classes("w-full items-center justify-between sc-page-header"):
        with ui.row().classes("items-center gap-2"):
            ui.icon("workspace_premium", size="sm").style("color: var(--sc-accent-wins)")
            ui.label("Wins & Posts").classes("sc-page-title")
        ui.button(
            "+ Add Win",
            on_click=lambda: _open_add_win_dialog(main_container),
        ).props("unelevated dense").classes("bg-primary text-white text-caption")

    with ui.scroll_area().classes("w-full").style("flex: 1"):
        with ui.row().classes("items-center gap-2 q-px-md q-pt-md q-pb-xs"):
            ui.icon("emoji_events", size="xs").style("color: var(--sc-accent-wins)")
            ui.label("Wins").classes("sc-label")
        _render_wins_table(main_container)

        ui.separator()

        with ui.row().classes("items-center justify-between q-px-md q-pt-sm q-pb-xs"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("campaign", size="xs").style("color: var(--sc-accent-meet)")
                ui.label("Posts").classes("sc-label")
            ui.button(
                "+ New Post",
                on_click=lambda: _open_post_detail(
                    None, None, lambda: _refresh_list(main_container), main_container
                ),
            ).props("flat dense size=sm")
        _render_posts_table(main_container)


# ---------------------------------------------------------------------------
# Win detail view
# ---------------------------------------------------------------------------

def _open_detail(win: dict, main_container: list, seed_prompt: str | None = None) -> None:
    main_container[0].style("overflow: hidden")
    main_container[0].clear()

    desc_ta: list = [None]
    panel_ref: list[ChatPanel | None] = [None]

    with main_container[0]:
        with ui.row().classes("w-full gap-0").style("height: 100%; overflow: hidden"):
            with ui.column().style(
                "width: 40%; height: 100%; overflow-y: auto; flex-shrink: 0;"
                "background: #fafafa; border-right: 1px solid var(--sc-border)"
            ).classes("q-pa-md gap-1"):
                _render_detail_left(win, desc_ta, panel_ref, main_container)

            with ui.column().classes("flex-1 h-full q-pa-sm gap-0").style(
                "display: flex; flex-direction: column"
            ):
                _render_detail_right(win, desc_ta, panel_ref, seed_prompt=seed_prompt)


def _render_detail_left(
    win: dict,
    desc_ta: list,
    panel_ref: list,
    main_container: list,
) -> None:
    def _go_back():
        main_container[0].style("overflow-y: auto")
        main_container[0].clear()
        with main_container[0]:
            _render_list(main_container)

    ui.button("Back", on_click=_go_back).props("flat dense icon=chevron_left").classes("q-mb-sm text-grey")

    ui.label("Win Details").classes("text-subtitle2 text-bold q-mb-xs")
    title_in = ui.input(label="Title", value=win["title"]).classes("w-full")
    ui.label("Description").classes("text-caption text-grey q-mt-xs")
    desc_ta[0] = ui.textarea(value=win["description"] or "").props(
        "rows=4 outlined"
    ).classes("w-full")

    def _save_win():
        title = title_in.value.strip()
        if not title:
            ui.notify("Title is required.", type="warning")
            return
        db.update_win(win["id"], title, desc_ta[0].value.strip() or None)
        ui.notify("Win saved.")

    ui.button("Save Win", on_click=_save_win).props("unelevated dense color=primary size=sm").classes(
        "q-mt-xs"
    )
    ui.label(f"Created: {win['created_at'][:10]}").classes(
        "text-caption text-grey q-mt-xs"
    )

    ui.separator().classes("q-my-sm")

    ui.label("Linked posts").classes("text-subtitle2 text-bold q-mb-xs")
    linked_posts = [p for p in db.list_posts() if p["win_id"] == win["id"]]
    if linked_posts:
        for post in linked_posts:
            label_text = f"{post['posted_at']} — {post['channel']}"
            ui.label(label_text).classes("text-caption text-grey cursor-pointer").on(
                "click",
                lambda _p=post: _open_post_detail(
                    _p,
                    win["id"],
                    lambda: _open_detail(win, main_container),
                    main_container,
                ),
            )
    else:
        ui.label("No posts linked to this win yet.").classes("text-caption text-grey")

    ui.button(
        "+ New Post for Win",
        on_click=lambda: _open_post_detail(
            None,
            win["id"],
            lambda: _open_detail(win, main_container),
            main_container,
        ),
    ).props("flat dense size=sm").classes("q-mt-xs")


def _render_detail_right(
    win: dict,
    desc_ta: list,
    panel_ref: list,
    seed_prompt: str | None = None,
) -> None:
    coach_fn = coach.stub_fn("POST_DRAFT") if coach.is_stubbed("POST_DRAFT") else coach.draft

    with ui.row().classes("w-full items-center justify-between q-mb-xs").style(
        "flex-shrink: 0"
    ):
        ui.label(f"Chat: {win['title']}").classes("text-overline text-grey")
        ui.button(
            "Adopt AI draft ↓",
            on_click=lambda: _adopt_ai_draft(
                panel_ref, desc_ta, "Description updated — click Save Win to persist."
            ),
        ).props("flat dense size=sm")

    with ui.column().classes("w-full").style("flex: 1; min-height: 0"):
        panel_ref[0] = ChatPanel(
            placeholder="Ask the coach to help refine this win or draft a visibility post...",
            coach_fn=coach_fn,
            thread_key=f"win-{win['id']}",
        )
        if not panel_ref[0].messages and seed_prompt:
            panel_ref[0].input.value = seed_prompt


# ---------------------------------------------------------------------------
# Page entry point
# ---------------------------------------------------------------------------

@ui.page("/wins-posts")
def wins_posts_page() -> None:
    create_nav("/wins-posts")

    with ui.column().classes("w-full").style(
        "height: calc(100vh - 56px); overflow: hidden; display: flex; flex-direction: column;"
        "background: #fff"
    ) as outer:
        main_container: list = [outer]
        _render_list(main_container)
