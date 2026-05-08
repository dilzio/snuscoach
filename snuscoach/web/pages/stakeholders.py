from nicegui import ui

from snuscoach.web.components.nav import create_nav


@ui.page("/stakeholders")
def stakeholders_page() -> None:
    create_nav("/stakeholders")
    with ui.column().classes("q-pa-md"):
        ui.label("Stakeholders").classes("text-h5")
        ui.label("Stakeholder graph — coming soon.")
