import pytest


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


@pytest.fixture
def temp_db(temp_db_path):
    """Initialized temp DB. Most tests use this."""
    from snuscoach import db

    db.init_db()
    yield temp_db_path
