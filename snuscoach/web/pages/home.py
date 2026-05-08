from nicegui import ui

from snuscoach.web.components.nav import create_nav


@ui.page("/")
def home_page() -> None:
    create_nav("/")
    with ui.column().classes("q-pa-md"):
        ui.label("Home").classes("text-h5")
        ui.label("Dashboard — coming soon.")
