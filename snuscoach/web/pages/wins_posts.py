from datetime import date

from nicegui import ui

from snuscoach import coach, db
from snuscoach.web.components.chat import ChatPanel
from snuscoach.web.components.nav import create_nav


def _truncate(text: str, n: int = 60) -> str:
    return text[:n] + "…" if len(text) > n else text


# ---------------------------------------------------------------------------
# Post expand / edit dialog
# ---------------------------------------------------------------------------

def _open_post_expand_dialog(post: dict, refresh_fn=None) -> None:
    with ui.dialog() as dlg, ui.card().style("min-width: 500px; max-width: 720px"):
        with ui.row().classes("w-full items-center justify-between q-mb-xs"):
            ui.label(post["channel"]).classes("text-subtitle1 text-bold")
            ui.label(post["posted_at"]).classes("text-caption text-grey")
        if post["audience"]:
            ui.label(f"Audience: {post['audience']}").classes(
                "text-caption text-grey q-mb-xs"
            )
        ui.separator().classes("q-mb-sm")

        edit_container: list = [None]
        edit_container[0] = ui.column().classes("w-full")
        _render_post_display(post, edit_container, dlg, refresh_fn)

        with ui.row().classes("w-full justify-end q-mt-sm"):
            ui.button("Close", on_click=dlg.close).props("flat dense")

    dlg.open()


def _render_post_display(post: dict, edit_container: list, dlg, refresh_fn) -> None:
    edit_container[0].clear()
    with edit_container[0]:
        with ui.scroll_area().style("max-height: 50vh"):
            ui.markdown(post["content"]).classes("text-body2")
        with ui.row().classes("gap-2 q-mt-sm"):
            ui.button(
                "Edit",
                on_click=lambda: _render_post_editor(post, edit_container, dlg, refresh_fn),
            ).props("flat dense size=sm")


def _render_post_editor(post: dict, edit_container: list, dlg, refresh_fn) -> None:
    edit_container[0].clear()
    with edit_container[0]:
        ta = ui.textarea(value=post["content"]).props("rows=6 outlined").classes("w-full")
        channel_in = ui.input(label="Channel", value=post["channel"]).classes("w-full")
        audience_in = ui.input(
            label="Audience", value=post["audience"] or ""
        ).classes("w-full")
        date_in = ui.input(
            label="Posted at (YYYY-MM-DD)", value=post["posted_at"]
        ).classes("w-full")

        def _save_edit():
            content = ta.value.strip()
            channel = channel_in.value.strip()
            if not content:
                ui.notify("Content is required.", type="warning")
                return
            if not channel:
                ui.notify("Channel is required.", type="warning")
                return
            db.update_post(
                post["id"],
                content,
                channel,
                audience_in.value.strip() or None,
                date_in.value.strip() or post["posted_at"],
            )
            dlg.close()
            ui.notify("Post updated.")
            if refresh_fn:
                ui.timer(0, refresh_fn, once=True)

        with ui.row().classes("gap-2 q-mt-xs"):
            ui.button("Save", on_click=_save_edit).props("color=primary dense size=sm")
            ui.button(
                "Cancel",
                on_click=lambda: _render_post_display(post, edit_container, dlg, refresh_fn),
            ).props("flat dense size=sm")


# ---------------------------------------------------------------------------
# Save Post dialog
# ---------------------------------------------------------------------------

def _open_save_post_dialog(
    win_id: int | None,
    panel_ref: list,
    refresh_fn=None,
) -> None:
    p = panel_ref[0] if panel_ref else None
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
            label="Content *", value=last_reply
        ).props("rows=6 outlined").classes("w-full")
        channel_in = ui.input(
            label="Channel *", placeholder="e.g. slack-eng, email-skip"
        ).classes("w-full")
        audience_in = ui.input(
            label="Audience (optional)", placeholder="e.g. eng team, skip"
        ).classes("w-full")
        posted_at_in = ui.input(
            label="Posted at (YYYY-MM-DD)", value=today
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
                win_id=win_id,
            )
            dlg.close()
            ui.notify("Post saved.")
            if refresh_fn:
                ui.timer(0, refresh_fn, once=True)

        with ui.row().classes("w-full justify-end gap-2 q-mt-sm"):
            ui.button("Cancel", on_click=dlg.close).props("flat dense")
            ui.button("Save", on_click=_save).props("color=primary dense")

    dlg.open()


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
            db.add_win(title, desc_in.value.strip() or None)
            dlg.close()
            ui.notify("Win added.")
            ui.timer(0, lambda: _refresh_list(main_container), once=True)

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

    with ui.row().classes("w-full items-center justify-between q-pb-xs").style(
        "flex-shrink: 0"
    ):
        ui.label("Wins").classes("text-h6")
        ui.button(
            "+ Add Win",
            on_click=lambda: _open_add_win_dialog(main_container),
        ).props("flat dense")

    if not wins:
        ui.label("No wins yet.").classes("text-caption text-grey q-mt-xs q-mb-md")
        return

    with ui.element("table").classes("w-full q-mb-md").style(
        "border-collapse: collapse; table-layout: fixed;"
        "border: 1px solid rgba(255,255,255,0.15); border-radius: 4px"
    ):
        with ui.element("thead"):
            with ui.element("tr").style(
                "border-bottom: 1px solid rgba(255,255,255,0.2)"
            ):
                for label, width in [
                    ("Title", "22%"),
                    ("Description", "43%"),
                    ("Date", "13%"),
                    ("Posted", "22%"),
                ]:
                    with ui.element("th").classes(
                        "text-caption text-grey text-left q-pa-xs"
                    ).style(f"width: {width}; font-weight: 500"):
                        ui.label(label)

        with ui.element("tbody"):
            for win in wins:
                wid = win["id"]
                has_post = wid in wins_with_posts_set

                with ui.element("tr").classes("cursor-pointer").style(
                    "border-bottom: 1px solid rgba(255,255,255,0.08)"
                ):
                    with ui.element("td").classes("q-pa-xs").on(
                        "click", lambda _w=win: _open_detail(_w, main_container)
                    ):
                        ui.label(win["title"]).classes("text-body2 text-bold")

                    with ui.element("td").classes("q-pa-xs").on(
                        "click", lambda _w=win: _open_detail(_w, main_container)
                    ):
                        ui.label(_truncate(win["description"] or "—")).classes(
                            "text-caption text-grey"
                        )

                    with ui.element("td").classes("q-pa-xs").on(
                        "click", lambda _w=win: _open_detail(_w, main_container)
                    ):
                        ui.label(win["created_at"][:10]).classes("text-caption text-grey")

                    with ui.element("td").classes("q-pa-xs"):
                        with ui.row().classes("gap-1 items-center no-wrap"):
                            if has_post:
                                ui.label("✓").classes("text-positive text-body2")
                            ui.button(
                                "↗ New Post",
                                on_click=lambda _wid=wid: _open_save_post_dialog(
                                    win_id=_wid,
                                    panel_ref=[None],
                                    refresh_fn=lambda: _refresh_list(main_container),
                                ),
                            ).props("flat dense size=xs")


def _render_posts_table(main_container: list) -> None:
    posts = db.list_posts()
    wins_by_id = {w["id"]: w["title"] for w in db.list_wins()}

    with ui.row().classes("w-full items-center justify-between q-pb-xs").style(
        "flex-shrink: 0"
    ):
        ui.label("Posts").classes("text-h6")
        ui.button(
            "+ New Post",
            on_click=lambda: _open_save_post_dialog(
                win_id=None,
                panel_ref=[None],
                refresh_fn=lambda: _refresh_list(main_container),
            ),
        ).props("flat dense")

    if not posts:
        ui.label("No posts yet.").classes("text-caption text-grey q-mt-xs")
        return

    with ui.element("table").classes("w-full").style(
        "border-collapse: collapse; table-layout: fixed;"
        "border: 1px solid rgba(255,255,255,0.15); border-radius: 4px"
    ):
        with ui.element("thead"):
            with ui.element("tr").style(
                "border-bottom: 1px solid rgba(255,255,255,0.2)"
            ):
                for label, width in [
                    ("Channel", "22%"),
                    ("Date", "13%"),
                    ("Audience", "25%"),
                    ("Win", "40%"),
                ]:
                    with ui.element("th").classes(
                        "text-caption text-grey text-left q-pa-xs"
                    ).style(f"width: {width}; font-weight: 500"):
                        ui.label(label)

        with ui.element("tbody"):
            for post in posts:
                linked_win = (
                    wins_by_id.get(post["win_id"], "—") if post["win_id"] else "—"
                )
                with ui.element("tr").classes("cursor-pointer").style(
                    "border-bottom: 1px solid rgba(255,255,255,0.08)"
                ).on(
                    "click",
                    lambda _p=post: _open_post_expand_dialog(
                        _p,
                        refresh_fn=lambda: _refresh_list(main_container),
                    ),
                ):
                    with ui.element("td").classes("q-pa-xs"):
                        ui.label(post["channel"]).classes("text-body2 text-bold")
                    with ui.element("td").classes("q-pa-xs"):
                        ui.label(post["posted_at"]).classes("text-caption text-grey")
                    with ui.element("td").classes("q-pa-xs"):
                        ui.label(post["audience"] or "—").classes("text-caption text-grey")
                    with ui.element("td").classes("q-pa-xs"):
                        ui.label(_truncate(linked_win, 50)).classes("text-caption text-grey")


def _render_list(main_container: list) -> None:
    with ui.scroll_area().classes("w-full").style("flex: 1"):
        with ui.column().classes("w-full q-pa-md gap-2"):
            _render_wins_table(main_container)
            ui.separator().classes("q-my-sm")
            _render_posts_table(main_container)


# ---------------------------------------------------------------------------
# Detail view
# ---------------------------------------------------------------------------

def _open_detail(win: dict, main_container: list) -> None:
    main_container[0].style("overflow: hidden")
    main_container[0].clear()

    desc_ta: list = [None]
    panel_ref: list[ChatPanel | None] = [None]

    with main_container[0]:
        with ui.row().classes("w-full gap-0").style("height: 100%; overflow: hidden"):
            with ui.column().style(
                "width: 40%; height: 100%; overflow-y: auto; flex-shrink: 0"
            ).classes("q-pa-md gap-1"):
                _render_detail_left(win, desc_ta, panel_ref, main_container)

            with ui.column().classes("flex-1 h-full q-pa-sm gap-0").style(
                "display: flex; flex-direction: column"
            ):
                _render_detail_right(win, desc_ta, panel_ref)


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

    ui.button("← Back", on_click=_go_back).props("flat dense").classes("q-mb-sm")

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

    ui.button("Save Win", on_click=_save_win).props("color=primary dense").classes(
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
                lambda _p=post: _open_post_expand_dialog(
                    _p,
                    refresh_fn=lambda: _refresh_detail(win["id"], main_container),
                ),
            )
    else:
        ui.label("No posts linked to this win yet.").classes("text-caption text-grey")

    ui.button(
        "+ New Post for Win",
        on_click=lambda: _open_save_post_dialog(
            win_id=win["id"],
            panel_ref=panel_ref,
            refresh_fn=lambda: _refresh_detail(win["id"], main_container),
        ),
    ).props("flat dense size=sm").classes("q-mt-xs")


def _refresh_detail(win_id: int, main_container: list) -> None:
    wins = db.list_wins()
    win = next((w for w in wins if w["id"] == win_id), None)
    if win:
        _open_detail(win, main_container)


def _render_detail_right(
    win: dict,
    desc_ta: list,
    panel_ref: list,
) -> None:
    coach_fn = coach.stub_fn("POST_DRAFT") if coach.is_stubbed("POST_DRAFT") else coach.draft

    with ui.row().classes("w-full items-center justify-between q-mb-xs").style(
        "flex-shrink: 0"
    ):
        ui.label(f"Chat: {win['title']}").classes("text-overline text-grey")
        ui.button(
            "Adopt AI draft ↓",
            on_click=lambda: _adopt_ai_draft(panel_ref, desc_ta),
        ).props("flat dense size=sm")

    with ui.column().classes("w-full").style("flex: 1; min-height: 0"):
        panel_ref[0] = ChatPanel(
            placeholder="Ask the coach to help refine this win or draft a visibility post...",
            coach_fn=coach_fn,
            thread_key=f"win-{win['id']}",
        )


def _adopt_ai_draft(panel_ref: list, desc_ta: list) -> None:
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
    if desc_ta[0] is not None:
        desc_ta[0].value = last_reply
        ui.notify("Description updated — click Save Win to persist.")


# ---------------------------------------------------------------------------
# Page entry point
# ---------------------------------------------------------------------------

@ui.page("/wins-posts")
def wins_posts_page() -> None:
    create_nav("/wins-posts")

    with ui.column().classes("w-full q-pa-md").style(
        "height: calc(100vh - 56px); overflow-y: auto; display: flex; flex-direction: column"
    ) as outer:
        main_container: list = [outer]
        _render_list(main_container)
