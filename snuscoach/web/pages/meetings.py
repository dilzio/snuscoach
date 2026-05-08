from nicegui import ui

from snuscoach.web.components.nav import create_nav


@ui.page("/meetings")
def meetings_page() -> None:
    create_nav("/meetings")
    with ui.column().classes("q-pa-md"):
        ui.label("Meetings").classes("text-h5")
        ui.label("Meeting list — coming soon.")
