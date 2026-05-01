"""Integration tests for the pre-meeting prep flow.

`cmd_prep` doesn't persist anything — these tests verify input handling and
the multi-turn follow-up loop that fixes the original bug (clarifying questions
had nowhere to be answered).
"""
import pytest

from snuscoach import cli


def _stub_inputs(monkeypatch, answers):
    it = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(it))


def test_prep_runs_one_turn_when_followup_empty(monkeypatch, temp_db):
    _stub_inputs(
        monkeypatch,
        [
            "1:1 with Frekus",  # title
            "Matt, Frekus",  # attendees
            "",  # follow-up: empty → end loop after first reply
        ],
    )
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "Architecture buy-in update.")

    calls: list[list[dict]] = []

    def _conv(messages):
        calls.append(list(messages))
        return "Provisional brief — three clarifying questions first."

    monkeypatch.setattr(cli.coach, "conversation", _conv)

    cli.cmd_prep(None)

    # Exactly one model call when the user immediately ends the loop
    assert len(calls) == 1
    # First call has just the seeded user message
    assert len(calls[0]) == 1
    assert calls[0][0]["role"] == "user"
    assert "Pre-meeting prep brief" in calls[0][0]["content"]


def test_prep_iterates_when_user_answers_followup(monkeypatch, temp_db):
    _stub_inputs(
        monkeypatch,
        [
            "1:1 with Frekus",
            "Matt, Frekus",
            "Yes — Frekus has seen designs",  # answers a clarifying question
            "And the architecture connects to acquisition integration",
            "",  # end loop
        ],
    )
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "Architecture update.")

    calls: list[int] = []

    def _conv(messages):
        calls.append(len(messages))
        return f"Reply #{len(calls)}"

    monkeypatch.setattr(cli.coach, "conversation", _conv)

    cli.cmd_prep(None)

    # Three model calls: initial + two follow-ups
    assert len(calls) == 3
    # Message history grows by 2 each turn (user + assistant), starting at 1 user
    assert calls == [1, 3, 5]


def test_prep_rejects_empty_title(monkeypatch, temp_db):
    _stub_inputs(monkeypatch, [""])
    with pytest.raises(SystemExit):
        cli.cmd_prep(None)
