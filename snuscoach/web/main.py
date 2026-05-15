import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from nicegui import ui

import snuscoach.web.pages  # noqa: F401 — registers all @ui.page routes
from snuscoach.web.theme import apply_theme

apply_theme()  # Quasar colour tokens + CSS custom properties (shared=True → index template)


def run(port: int | None = None, show: bool = True) -> None:
    try:
        ui.run(
            title="snuscoach",
            port=port or int(os.getenv("SNUSCOACH_PORT", "8080")),
            show=show,
            reload=False,
            storage_secret="snuscoach-local",
        )
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ in {"__main__", "__mp_main__"}:
    run()
