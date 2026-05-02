"""LLM call logging.

Each CLI invocation produces one JSONL file under `<log_dir>/YYYY-MM-DD/HHMMSS.jsonl`,
appended to once per `coach.conversation()` call. The point: be able to look
back at exactly what was sent to Claude and what came back, including usage
and prompt-cache hit rates.

Configured via `.env`:
- `SNUSCOACH_LOG`: "true"/"false"/"0"/"off" (default true).
- `SNUSCOACH_LOG_DIR`: absolute path (default `~/.snuscoach/logs`).
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_FALSY = {"false", "0", "no", "off", ""}

# Process-scoped state. Reset between tests via _reset_for_tests().
_command: str | None = None
_session_file: Path | None = None


def is_enabled() -> bool:
    raw = os.environ.get("SNUSCOACH_LOG", "true").strip().lower()
    return raw not in _FALSY


def log_dir() -> Path:
    override = os.environ.get("SNUSCOACH_LOG_DIR")
    if override:
        return Path(override)
    return Path.home() / ".snuscoach" / "logs"


def set_command(name: str) -> None:
    global _command
    _command = name


def _ensure_session_file() -> Path:
    global _session_file
    if _session_file is not None:
        return _session_file
    now = datetime.now()
    daily_dir = log_dir() / now.strftime("%Y-%m-%d")
    daily_dir.mkdir(parents=True, exist_ok=True)
    _session_file = daily_dir / f"{now.strftime('%H%M%S')}.jsonl"
    return _session_file


def _serialize_usage(usage: Any) -> dict:
    """Pull the relevant fields from an SDK Usage object or dict.

    Unknown attributes are ignored. Missing fields default to None.
    """
    if usage is None:
        return {}
    if isinstance(usage, dict):
        src = usage
        get = src.get
    else:
        src = usage
        def get(k, default=None):
            return getattr(src, k, default)
    return {
        "input_tokens": get("input_tokens"),
        "output_tokens": get("output_tokens"),
        "cache_read_input_tokens": get("cache_read_input_tokens"),
        "cache_creation_input_tokens": get("cache_creation_input_tokens"),
    }


def log_call(
    *,
    system: list,
    messages: list,
    response: str,
    usage: Any,
    latency_ms: int,
    model: str | None = None,
) -> None:
    """Append one record to the current session log file.

    No-op when logging is disabled. Errors are caught and reported to stderr
    so logging never breaks the user-facing flow.
    """
    if not is_enabled():
        return
    try:
        path = _ensure_session_file()
        record = {
            "timestamp": datetime.now().isoformat(timespec="milliseconds"),
            "command": _command,
            "model": model,
            "system": system,
            "messages": messages,
            "response": response,
            "usage": _serialize_usage(usage),
            "latency_ms": latency_ms,
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str))
            f.write("\n")
    except Exception as e:
        print(f"[snuscoach] log write failed: {e}", file=sys.stderr)


def _reset_for_tests() -> None:
    """Clear process-scoped state. For test fixtures only."""
    global _command, _session_file
    _command = None
    _session_file = None
