import os
import subprocess
import sys
import time

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

    yield base_url, db_path

    proc.terminate()
    proc.wait(timeout=5)
    log_fh.close()


@pytest.fixture
def ui_base_url(ui_server):
    return ui_server[0]


@pytest.fixture
def ui_db_path(ui_server):
    return ui_server[1]


@pytest.fixture(autouse=True)
def temp_db_path(monkeypatch, tmp_path):
    """Always isolate every test to a per-test temp DB.

    Does NOT initialize the schema — tests that want a clean initialized DB
    should request the `temp_db` fixture instead. Tests that exercise the
    migration path use this fixture directly and seed an old-schema DB
    manually before calling init_db().
    """
    db_path = tmp_path / "snuscoach.db"
    monkeypatch.setenv("SNUSCOACH_DB", str(db_path))
    yield db_path


@pytest.fixture(autouse=True)
def isolated_logger(monkeypatch, tmp_path):
    """Always isolate logger state and log dir per-test.

    Points SNUSCOACH_LOG_DIR at a per-test tmp dir and resets the logger's
    process-scoped command + session-file cache before and after each test
    so writes never leak between tests or to ~/.snuscoach/logs.
    """
    monkeypatch.setenv("SNUSCOACH_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.delenv("SNUSCOACH_LOG", raising=False)  # default-on
    from snuscoach import logger

    logger._reset_for_tests()
    yield
    logger._reset_for_tests()


@pytest.fixture(autouse=True)
def isolated_profile_env(monkeypatch):
    """Always clear SNUSCOACH_PROFILE so .env values don't bleed into tests.

    Tests that need a specific profile name can override it via monkeypatch.setenv.
    """
    monkeypatch.delenv("SNUSCOACH_PROFILE", raising=False)


@pytest.fixture(autouse=True)
def isolated_stub_env(monkeypatch):
    """Always clear LLM stub flags so .env values don't bleed into tests.

    Tests that verify stub behavior should opt in with monkeypatch.setenv.
    """
    for name in (
        "SNUSCOACH_STUB_CHAT",
        "SNUSCOACH_STUB_POST_DRAFT",
        "SNUSCOACH_STUB_MEETING_PREP",
        "SNUSCOACH_STUB_MEETING_DEBRIEF",
        "SNUSCOACH_STUB_JOURNAL",
        "SNUSCOACH_STUB_REFLECT",
        "SNUSCOACH_STUB_NUDGE_INTERACTIVE",
        "SNUSCOACH_STUB_NUDGE_REPORT",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def temp_db(temp_db_path):
    """Initialized temp DB. Most tests use this."""
    from snuscoach import db

    db.init_db()
    yield temp_db_path
