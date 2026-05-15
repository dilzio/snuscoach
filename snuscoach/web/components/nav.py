from nicegui import ui

_NAV_LINKS = [
    ("Home", "/", "home"),
    ("Meetings", "/meetings", "groups"),
    ("Stakeholders", "/stakeholders", "person"),
    ("Wins & Posts", "/wins-posts", "workspace_premium"),
    ("Journal", "/journal", "book"),
    ("Admin", "/admin", "settings"),
]


def _profile_label() -> str:
    try:
        from snuscoach import db

        profile = db.get_default_profile()
        return profile["name"] if profile else "No profile"
    except Exception:
        return "No profile"


def create_nav(current_path: str = "/") -> None:
    with ui.header().classes("items-center justify-between q-px-md q-py-sm bg-dark"):
        ui.label("snuscoach").classes("text-h6 font-bold").style("letter-spacing: -0.5px")
        ui.badge(_profile_label(), color="grey-7").classes("text-caption")

    with ui.left_drawer(fixed=True).style("background: var(--sc-sidebar-bg)").classes("q-pa-sm"):
        for label, path, icon in _NAV_LINKS:
            active = current_path == path
            extra = " bg-primary text-white" if active else ""
            with (
                ui.row()
                .classes(f"sc-nav-item{extra}")
                .on("click", lambda p=path: ui.navigate.to(p))
            ):
                ui.icon(icon).classes("text-sm")
                ui.label(label)
