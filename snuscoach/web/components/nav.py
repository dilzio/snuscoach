from nicegui import app, ui

_NAV_LINKS = [
    ("Home", "/"),
    ("Meetings", "/meetings"),
    ("Stakeholders", "/stakeholders"),
    ("Wins & Posts", "/wins-posts"),
    ("Journal", "/journal"),
    ("Admin", "/admin"),
]


def _profile_label() -> str:
    try:
        from snuscoach import db

        profile = db.get_default_profile()
        return profile["name"] if profile else "No profile"
    except Exception:
        return "No profile"


def create_nav(current_path: str = "/") -> None:
    with ui.header().classes("items-center justify-between px-4 py-2 bg-dark"):
        ui.label("snuscoach").classes("text-h6 font-bold")
        ui.badge(_profile_label(), color="grey-7").classes("text-caption")

    with ui.left_drawer(fixed=True).classes("bg-grey-10 q-pa-md"):
        for label, path in _NAV_LINKS:
            active = current_path == path
            classes = "w-full text-left q-py-xs q-px-sm rounded"
            if active:
                classes += " bg-primary text-white"
            ui.link(label, path).classes(classes)
