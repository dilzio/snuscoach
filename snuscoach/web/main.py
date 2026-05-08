import os

from nicegui import ui

import snuscoach.web.pages  # noqa: F401 — registers all @ui.page routes


def run(port: int | None = None, show: bool = True) -> None:
    ui.run(
        title="snuscoach",
        port=port or int(os.getenv("SNUSCOACH_PORT", "8080")),
        show=show,
        reload=False,
        storage_secret="snuscoach-local",
    )


if __name__ in {"__main__", "__mp_main__"}:
    run()
