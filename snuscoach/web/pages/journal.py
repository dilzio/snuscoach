from nicegui import ui

from snuscoach.web.components.nav import create_nav


@ui.page("/journal")
def journal_page() -> None:
    create_nav("/journal")
    with ui.column().classes("q-pa-md"):
        ui.label("Journal").classes("text-h5")
        ui.label("Daily check-in and entry history — coming soon.")
