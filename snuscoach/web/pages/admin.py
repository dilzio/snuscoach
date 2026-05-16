from nicegui import ui

from snuscoach.web.components.nav import create_nav


@ui.page("/admin")
def admin_page() -> None:
    create_nav("/admin")
    with ui.column().classes("w-full q-pa-md").style(
        "height: calc(100vh - 56px); background: #fff"
    ):
        with ui.row().classes("items-center gap-2 q-mb-md"):
            ui.icon("settings", size="sm").style("color: var(--sc-text-muted)")
            ui.label("Admin").classes("text-h6")
        ui.label("Profile and voice samples — coming soon.").classes("text-body2 text-grey")
