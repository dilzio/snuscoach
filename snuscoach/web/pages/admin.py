from nicegui import ui

from snuscoach.web.components.nav import create_nav


@ui.page("/admin")
def admin_page() -> None:
    create_nav("/admin")
    with ui.column().classes("q-pa-md"):
        ui.label("Admin").classes("text-h5")
        ui.label("Profile and voice samples — coming soon.")
