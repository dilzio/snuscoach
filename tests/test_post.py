"""Integration tests for the visibility post draft flow.

Drives `cli.cmd_post_draft` directly. Real SQLite for persistence, only the
LLM call (`coach.conversation`) is mocked. Covers the multi-turn iteration
and the publish/save path.
"""
import pytest

from snuscoach import cli, db


def _stub_inputs(monkeypatch, answers):
    it = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(it))


def test_post_draft_saves_last_iterated_draft(monkeypatch, temp_db):
    """User iterates with the coach; the saved post starts from the LAST reply."""
    _stub_inputs(
        monkeypatch,
        [
            "team-broadcast",  # audience
            "",  # follow-up 1: empty → end loop after first reply
            "y",  # publish? yes
            "Slack #engineering",  # channel
            "2026-05-01",  # posted_at
        ],
    )

    # First call: returns the work description
    # Second call (after stream): returns the finalized content from $EDITOR
    multiline_calls = iter(["I shipped the migration.", "Final post text."])
    multiline_initials: list[str] = []

    def _multi(_label, initial=""):
        multiline_initials.append(initial)
        return next(multiline_calls)

    monkeypatch.setattr(cli, "_input_multiline", _multi)

    replies = iter(["FIRST draft", "SECOND refined draft"])
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: next(replies))

    cli.cmd_post_draft(None)

    rows = db.list_posts()
    assert len(rows) == 1
    row = rows[0]
    assert row["channel"] == "Slack #engineering"
    assert row["audience"] == "team-broadcast"
    assert row["posted_at"] == "2026-05-01"
    assert row["content"] == "Final post text."

    # The editor for finalization was seeded with the FIRST (and only) coach
    # reply since the user ended the loop immediately. The work description
    # call has no `initial`.
    assert multiline_initials[0] == ""  # work description prompt
    assert multiline_initials[1] == "FIRST draft"


def test_post_draft_iterated_seed_uses_last_reply(monkeypatch, temp_db):
    """When the user iterates with the coach, the editor seed is the LAST reply."""
    _stub_inputs(
        monkeypatch,
        [
            "manager",
            "Make it sharper",  # follow-up 1
            "Drop the bullet about timing",  # follow-up 2
            "",  # end loop
            "y",  # publish
            "email to manager",
            "2026-05-01",
        ],
    )

    multiline_calls = iter(["Work description.", "Final content."])
    multiline_initials: list[str] = []

    def _multi(_label, initial=""):
        multiline_initials.append(initial)
        return next(multiline_calls)

    monkeypatch.setattr(cli, "_input_multiline", _multi)

    replies = iter(["FIRST", "SECOND", "THIRD final"])
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: next(replies))

    cli.cmd_post_draft(None)

    # Editor for finalization should be seeded with the LAST coach reply
    assert multiline_initials[1] == "THIRD final"


def test_post_draft_skips_save_when_user_declines_to_publish(monkeypatch, temp_db):
    _stub_inputs(
        monkeypatch,
        [
            "team-broadcast",
            "",  # end loop
            "n",  # publish? no
        ],
    )
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "Work.")
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: "draft")

    cli.cmd_post_draft(None)

    assert db.list_posts() == []


def test_post_draft_rejects_empty_work_description(monkeypatch, temp_db):
    _stub_inputs(monkeypatch, ["team-broadcast"])
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "")

    with pytest.raises(SystemExit):
        cli.cmd_post_draft(None)


def test_post_draft_rejects_invalid_date(monkeypatch, temp_db):
    _stub_inputs(
        monkeypatch,
        [
            "team-broadcast",
            "",  # end loop
            "y",  # publish
            "Slack #foo",  # channel
            "garbage-date",  # bad date
        ],
    )
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "content")
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: "draft")

    with pytest.raises(SystemExit):
        cli.cmd_post_draft(None)
    assert db.list_posts() == []


def test_post_draft_rejects_empty_finalized_content(monkeypatch, temp_db):
    _stub_inputs(
        monkeypatch,
        [
            "team-broadcast",
            "",  # end loop
            "y",  # publish
        ],
    )
    # work description first, then editor returns empty for finalize
    multi = iter(["Work description.", ""])
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: next(multi))
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: "draft")

    cli.cmd_post_draft(None)
    assert db.list_posts() == []
