from nicegui import ui

from snuscoach.web.components.nav import create_nav


@ui.page("/wins-posts")
def wins_posts_page() -> None:
    create_nav("/wins-posts")
    with ui.column().classes("q-pa-md"):
        ui.label("Wins & Posts").classes("text-h5")
        ui.label("Wins ledger and visibility drafting — coming soon.")
