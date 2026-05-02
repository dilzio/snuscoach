"""Integration tests for the LLM call logger.

Real filesystem (per-test tmp dir via conftest fixture). No I/O mocks.
"""
import json
import re
from pathlib import Path

from snuscoach import logger


def _read_records(log_root: Path) -> list[dict]:
    """Find every .jsonl file under log_root and parse all lines."""
    records = []
    for f in log_root.rglob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            records.append(json.loads(line))
    return records


def _log_dir(monkeypatch) -> Path:
    """Return the configured SNUSCOACH_LOG_DIR for assertions."""
    import os
    return Path(os.environ["SNUSCOACH_LOG_DIR"])


def _call(**overrides):
    """Convenience to fire one log_call with defaults."""
    args = dict(
        system=[{"type": "text", "text": "you are a coach"}],
        messages=[{"role": "user", "content": "hi"}],
        response="hello",
        usage=None,
        latency_ms=42,
        model="claude-opus-4-7",
    )
    args.update(overrides)
    logger.log_call(**args)


# ---- on/off ----


def test_logging_disabled_writes_nothing(monkeypatch):
    monkeypatch.setenv("SNUSCOACH_LOG", "false")
    _call()
    assert _read_records(_log_dir(monkeypatch)) == []
    # No directory should be created either
    assert not _log_dir(monkeypatch).exists()


def test_logging_default_is_on(monkeypatch):
    # SNUSCOACH_LOG unset (default) → enabled
    _call()
    assert len(_read_records(_log_dir(monkeypatch))) == 1


def test_falsy_values_disable(monkeypatch):
    for val in ["false", "FALSE", "0", "no", "off", " "]:
        logger._reset_for_tests()
        monkeypatch.setenv("SNUSCOACH_LOG", val)
        _call()
        assert (
            _read_records(_log_dir(monkeypatch)) == []
        ), f"expected disabled for SNUSCOACH_LOG={val!r}"


def test_truthy_values_enable(monkeypatch):
    for val in ["true", "TRUE", "1", "yes", "on"]:
        logger._reset_for_tests()
        monkeypatch.setenv("SNUSCOACH_LOG", val)
        _call()
        assert (
            len(_read_records(_log_dir(monkeypatch))) >= 1
        ), f"expected enabled for SNUSCOACH_LOG={val!r}"


# ---- file layout ----


def test_session_file_under_daily_dir(monkeypatch):
    _call()
    log_root = _log_dir(monkeypatch)
    files = list(log_root.rglob("*.jsonl"))
    assert len(files) == 1
    # Path: <log_root>/YYYY-MM-DD/HHMMSS.jsonl
    rel = files[0].relative_to(log_root)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}/\d{6}\.jsonl", str(rel))


def test_log_dir_auto_created(monkeypatch, tmp_path):
    nested = tmp_path / "deep" / "logs"
    monkeypatch.setenv("SNUSCOACH_LOG_DIR", str(nested))
    logger._reset_for_tests()
    _call()
    assert nested.exists()
    assert list(nested.rglob("*.jsonl"))


def test_default_log_dir(monkeypatch):
    """Unset env → falls back to ~/.snuscoach/logs."""
    monkeypatch.delenv("SNUSCOACH_LOG_DIR", raising=False)
    fake_home = Path("/tmp/pytest-fake-home-xyz123")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    # Re-evaluate logger.log_dir() — should use the new home
    assert logger.log_dir() == fake_home / ".snuscoach" / "logs"


# ---- record shape ----


def test_log_record_shape(monkeypatch):
    logger.set_command("meeting prep")
    _call(
        system=[{"type": "text", "text": "system here"}],
        messages=[{"role": "user", "content": "user msg"}],
        response="assistant reply",
        latency_ms=1234,
    )
    records = _read_records(_log_dir(monkeypatch))
    assert len(records) == 1
    r = records[0]

    assert r["command"] == "meeting prep"
    assert r["model"] == "claude-opus-4-7"
    assert r["system"] == [{"type": "text", "text": "system here"}]
    assert r["messages"] == [{"role": "user", "content": "user msg"}]
    assert r["response"] == "assistant reply"
    assert r["latency_ms"] == 1234
    # Timestamp parses as ISO
    from datetime import datetime
    datetime.fromisoformat(r["timestamp"])


def test_set_command_stamps_record(monkeypatch):
    logger.set_command("chat")
    _call()
    r = _read_records(_log_dir(monkeypatch))[0]
    assert r["command"] == "chat"


def test_command_unset_records_null(monkeypatch):
    _call()
    r = _read_records(_log_dir(monkeypatch))[0]
    assert r["command"] is None


# ---- multiple calls ----


def test_multiple_calls_append_to_same_file(monkeypatch):
    _call(response="first")
    _call(response="second")
    _call(response="third")
    log_root = _log_dir(monkeypatch)
    files = list(log_root.rglob("*.jsonl"))
    assert len(files) == 1, f"expected one file, got {files}"
    records = _read_records(log_root)
    assert [r["response"] for r in records] == ["first", "second", "third"]


# ---- usage serialization ----


def test_usage_object_with_attributes_serializes(monkeypatch):
    class FakeUsage:
        input_tokens = 100
        output_tokens = 50
        cache_read_input_tokens = 200
        cache_creation_input_tokens = 0

    _call(usage=FakeUsage())
    r = _read_records(_log_dir(monkeypatch))[0]
    assert r["usage"] == {
        "input_tokens": 100,
        "output_tokens": 50,
        "cache_read_input_tokens": 200,
        "cache_creation_input_tokens": 0,
    }


def test_usage_dict_serializes(monkeypatch):
    _call(usage={"input_tokens": 5, "output_tokens": 7})
    r = _read_records(_log_dir(monkeypatch))[0]
    assert r["usage"]["input_tokens"] == 5
    assert r["usage"]["output_tokens"] == 7
    # missing fields default to None
    assert r["usage"]["cache_read_input_tokens"] is None


def test_usage_none_serializes_to_empty(monkeypatch):
    _call(usage=None)
    r = _read_records(_log_dir(monkeypatch))[0]
    assert r["usage"] == {}


# ---- error handling ----


def test_log_call_swallows_io_errors(monkeypatch, tmp_path, capsys):
    """If the log dir can't be created (e.g. parent is a regular file),
    log_call must not raise."""
    blocker = tmp_path / "blocker"
    blocker.write_text("i am a file, not a directory")
    monkeypatch.setenv("SNUSCOACH_LOG_DIR", str(blocker / "subdir"))
    logger._reset_for_tests()

    # Should not raise
    _call()

    err = capsys.readouterr().err
    assert "log write failed" in err
