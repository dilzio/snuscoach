import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests


def _wait_for_server(url: str, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if requests.get(url, timeout=1).status_code < 500:
                return
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(0.3)
    raise RuntimeError(f"snuscoach UI server did not start at {url} within {timeout}s")


@pytest.fixture(scope="session")
def ui_server(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("ui_db") / "snuscoach_test.db"
    log_path = tmp_path_factory.mktemp("ui_logs") / "server.log"
    port = 18080
    env = {
        **os.environ,
        "SNUSCOACH_DB": str(db_path),
        "SNUSCOACH_PORT": str(port),
        "SNUSCOACH_LOG": "false",
        # Fake key so AI calls fail fast and hit error handlers rather than
        # making real API calls or blocking indefinitely.
        "ANTHROPIC_API_KEY": "test-fake-key-ui-tests",
    }
    # NiceGUI 3.x detects pytest via PYTEST_CURRENT_TEST and enters a screen-test
    # mode that requires NICEGUI_SCREEN_TEST_PORT. We use Playwright instead of
    # NiceGUI's native test client, so strip that marker from the subprocess env.
    env.pop("PYTEST_CURRENT_TEST", None)

    subprocess.run(
        [sys.executable, "-m", "snuscoach", "init"],
        env=env,
        check=True,
        capture_output=True,
    )

    log_fh = log_path.open("w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "snuscoach.web.main"],
        env=env,
        stdout=log_fh,
        stderr=log_fh,
    )

    base_url = f"http://localhost:{port}"
    try:
        _wait_for_server(base_url)
    except RuntimeError:
        log_fh.close()
        proc.terminate()
        print(f"\nServer log:\n{log_path.read_text()}")
        raise

    yield base_url

    proc.terminate()
    proc.wait(timeout=5)
    log_fh.close()


@pytest.fixture
def ui_base_url(ui_server):
    return ui_server
