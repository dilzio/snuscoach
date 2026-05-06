"""Tests for model routing: correct model selected per task type.

Patches coach._stream to capture the model argument without hitting the API.
"""
from unittest.mock import patch

import pytest

from snuscoach import coach
from snuscoach.cli import _iterate_with_followups


# ---- coach module routing ----

def test_conversation_uses_opus():
    with patch.object(coach, "_stream", return_value="ok") as m:
        coach.conversation([{"role": "user", "content": "hi"}])
    m.assert_called_once()
    _, model = m.call_args[0]
    assert model == coach.OPUS_MODEL


def test_draft_uses_sonnet():
    with patch.object(coach, "_stream", return_value="ok") as m:
        coach.draft([{"role": "user", "content": "hi"}])
    m.assert_called_once()
    _, model = m.call_args[0]
    assert model == coach.SONNET_MODEL


# ---- _stream kwargs by model ----

def _capture_stream_kwargs(model):
    """Call _stream with a patched Anthropic client and return the kwargs."""
    captured = {}

    class FakeStream:
        text_stream = iter([])
        def get_final_message(self): return None
        def __enter__(self): return self
        def __exit__(self, *a): pass

    def fake_messages_stream(**kwargs):
        captured.update(kwargs)
        return FakeStream()

    class FakeClient:
        class messages:
            stream = staticmethod(fake_messages_stream)

    import os
    with patch.object(coach, "_client", return_value=FakeClient()), \
         patch.object(coach, "_system_blocks", return_value=[]):
        coach._stream([{"role": "user", "content": "x"}], model)

    return captured


def test_opus_stream_includes_thinking_and_effort():
    kwargs = _capture_stream_kwargs(coach.OPUS_MODEL)
    assert kwargs["model"] == coach.OPUS_MODEL
    assert kwargs["max_tokens"] == 32000
    assert "thinking" in kwargs
    assert "output_config" in kwargs


def test_sonnet_stream_excludes_thinking_and_effort():
    kwargs = _capture_stream_kwargs(coach.SONNET_MODEL)
    assert kwargs["model"] == coach.SONNET_MODEL
    assert kwargs["max_tokens"] == 8096
    assert "thinking" not in kwargs
    assert "output_config" not in kwargs


# ---- _iterate_with_followups routing ----

def test_iterate_defaults_to_conversation(monkeypatch):
    with patch.object(coach, "conversation", return_value="reply") as m, \
         patch("builtins.input", return_value=""):
        _iterate_with_followups("hello")
    m.assert_called()


def test_iterate_respects_custom_coach_fn(monkeypatch):
    calls = []

    def my_fn(messages):
        calls.append(messages)
        return "reply"

    monkeypatch.setattr("builtins.input", lambda _: "")
    _iterate_with_followups("hello", coach_fn=my_fn)
    assert len(calls) == 1


def test_iterate_uses_same_fn_for_followups(monkeypatch):
    """All turns in a session — initial + follow-ups — use the same coach_fn."""
    calls = []

    def my_fn(messages):
        calls.append(len(messages))
        return "reply"

    answers = iter(["follow up", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    _iterate_with_followups("hello", coach_fn=my_fn)
    # first call: 1 message; second call: 3 messages (user, assistant, followup)
    assert calls == [1, 3]


# ---- cmd_post_draft routes to draft ----

def test_cmd_post_draft_calls_draft_not_conversation(monkeypatch, temp_db):
    from snuscoach import cli

    answers = iter(["team-broadcast", "", "n"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "some work done")

    with patch.object(coach, "draft", return_value="a draft") as mock_draft, \
         patch.object(coach, "conversation") as mock_conv:
        cli.cmd_post_draft(None)

    mock_draft.assert_called()
    mock_conv.assert_not_called()


# ---- coaching commands route to conversation ----

def test_cmd_meeting_prep_calls_conversation_not_draft(monkeypatch, temp_db):
    from snuscoach import cli, db

    db.add_meeting(title="Standup", date="2026-05-06")
    answers = iter(["", "n"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "agenda context")

    with patch.object(coach, "conversation", return_value="brief") as mock_conv, \
         patch.object(coach, "draft") as mock_draft:
        try:
            cli.cmd_meeting_prep(type("A", (), {"id": 1})())
        except SystemExit:
            pass  # "not saved" exit is fine

    mock_conv.assert_called()
    mock_draft.assert_not_called()
