import pytest


@pytest.fixture(autouse=True)
def temp_db(monkeypatch, tmp_path):
    """Point SNUSCOACH_DB at a per-test temp file and init schema fresh.

    Auto-applied to every test so nothing can touch the user's real DB at
    ~/.snuscoach/snuscoach.db.
    """
    db_path = tmp_path / "snuscoach.db"
    monkeypatch.setenv("SNUSCOACH_DB", str(db_path))

    from snuscoach import db

    db.init_db()
    yield db_path
