"""Integration tests for LLM stub configuration and purge-stubs command."""
import pytest

from snuscoach import cli, coach, db


class _ReflectArgs:
    def __init__(self, since=None):
        self.since = since


def _stub_inputs(monkeypatch, answers):
    it = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(it))


# ---------------------------------------------------------------------------
# coach module: is_stubbed / canned_response / stub_fn
# ---------------------------------------------------------------------------


def test_is_stubbed_false_by_default(monkeypatch):
    monkeypatch.delenv("SNUSCOACH_STUB_CHAT", raising=False)
    assert not coach.is_stubbed("CHAT")


@pytest.mark.parametrize("value", ["true", "True", "TRUE", "1", "yes", "on"])
def test_is_stubbed_truthy_values(monkeypatch, value):
    monkeypatch.setenv("SNUSCOACH_STUB_CHAT", value)
    assert coach.is_stubbed("CHAT")


def test_is_stubbed_false_values(monkeypatch):
    monkeypatch.setenv("SNUSCOACH_STUB_CHAT", "false")
    assert not coach.is_stubbed("CHAT")


def test_canned_response_contains_marker():
    resp = coach.canned_response("MEETING_PREP")
    assert coach.CANNED_MARKER in resp


def test_canned_response_includes_use_case_label():
    resp = coach.canned_response("REFLECT")
    assert "REFLECT" in resp


def test_stub_fn_returns_and_prints_canned(capsys):
    fn = coach.stub_fn("JOURNAL")
    result = fn([{"role": "user", "content": "hello"}])
    assert coach.CANNED_MARKER in result
    assert "JOURNAL" in result
    captured = capsys.readouterr()
    assert coach.CANNED_MARKER in captured.out


def test_canned_bodies_defined_for_all_use_cases():
    use_cases = [
        "CHAT", "POST_DRAFT", "MEETING_PREP", "MEETING_DEBRIEF",
        "JOURNAL", "REFLECT", "NUDGE_INTERACTIVE", "NUDGE_REPORT",
    ]
    for uc in use_cases:
        resp = coach.canned_response(uc)
        assert coach.CANNED_MARKER in resp
        assert len(resp) > len(coach.CANNED_MARKER) + 20, f"Canned body too short for {uc}"


# ---------------------------------------------------------------------------
# cli.py: stub env vars route to canned responses (no real API call)
# ---------------------------------------------------------------------------


def test_reflect_stub_saves_canned_response(monkeypatch, temp_db):
    monkeypatch.setenv("SNUSCOACH_STUB_REFLECT", "true")
    _stub_inputs(monkeypatch, ["y"])

    cli.cmd_reflect(_ReflectArgs())

    rows = db.get_reflections()
    assert len(rows) == 1
    assert coach.CANNED_MARKER in rows[0]["content"]


def test_reflect_stub_off_still_calls_real_coach(monkeypatch, temp_db):
    monkeypatch.delenv("SNUSCOACH_STUB_REFLECT", raising=False)
    _stub_inputs(monkeypatch, ["y"])
    called = []
    monkeypatch.setattr(cli.coach, "conversation", lambda msgs: called.append(msgs) or "Real.")

    cli.cmd_reflect(_ReflectArgs())

    assert len(called) == 1
    rows = db.get_reflections()
    assert "Real." in rows[0]["content"]


def test_nudge_report_stub_saves_canned(monkeypatch, temp_db):
    monkeypatch.setenv("SNUSCOACH_STUB_NUDGE_REPORT", "true")
    monkeypatch.setenv("SNUSCOACH_NUDGE_MODE", "report")
    _stub_inputs(monkeypatch, [""])  # skip action selection

    cli.cmd_nudge(None)

    nudge = db.get_latest_nudge()
    assert nudge is not None
    assert coach.CANNED_MARKER in nudge["report"]


def test_meeting_prep_stub_saves_canned(monkeypatch, temp_db):
    monkeypatch.setenv("SNUSCOACH_STUB_MEETING_PREP", "true")
    mid = db.add_meeting("Q3 planning", "2026-05-15")
    _stub_inputs(monkeypatch, ["", "y"])  # empty = end follow-ups, y = save
    monkeypatch.setattr(cli, "_input_multiline", lambda *_a, **_kw: "some context")

    args = type("A", (), {"id": mid})()
    cli.cmd_meeting_prep(args)

    m = db.get_meeting(mid)
    assert m["prep_brief"] is not None
    assert coach.CANNED_MARKER in m["prep_brief"]


def test_meeting_debrief_stub_saves_canned(monkeypatch, temp_db):
    monkeypatch.setenv("SNUSCOACH_STUB_MEETING_DEBRIEF", "true")
    mid = db.add_meeting("Design review", "2026-05-10")
    monkeypatch.setattr(cli, "_input_multiline", lambda *_a, **_kw: "raw meeting notes")
    _stub_inputs(monkeypatch, ["", "y"])  # empty = end follow-ups, y = save

    args = type("A", (), {"id": mid})()
    cli.cmd_meeting_debrief(args)

    m = db.get_meeting(mid)
    assert m["debrief_summary"] is not None
    assert coach.CANNED_MARKER in m["debrief_summary"]


# ---------------------------------------------------------------------------
# db.purge_canned_responses
# ---------------------------------------------------------------------------


def test_purge_removes_canned_post(temp_db):
    db.add_post(
        f"{coach.CANNED_MARKER} POST_DRAFT\n\nFake post.",
        channel="slack",
        audience="team",
        posted_at="2026-05-10",
    )
    db.add_post("Real post content.", channel="slack", audience="team", posted_at="2026-05-09")

    counts = db.purge_canned_responses()

    assert counts["posts"] == 1
    posts = db.list_posts()
    assert len(posts) == 1
    assert posts[0]["content"] == "Real post content."


def test_purge_removes_canned_reflection(temp_db):
    db.save_reflection(f"{coach.CANNED_MARKER} REFLECT\n\nFake reflection.")
    db.save_reflection("Real reflection.")

    counts = db.purge_canned_responses()

    assert counts["reflections"] == 1
    rows = db.get_reflections()
    assert len(rows) == 1
    assert rows[0]["content"] == "Real reflection."


def test_purge_removes_canned_journal_entry(temp_db):
    db.add_journal_entry(
        f"{coach.CANNED_MARKER} JOURNAL\n\nFake entry.",
        coach_prompt="prompt",
        entry_type="journal",
    )
    db.add_journal_entry("Real entry.", entry_type="journal")

    counts = db.purge_canned_responses()

    assert counts["journal_entries"] == 1
    rows = db.list_journal_entries(limit=10)
    assert len(rows) == 1
    assert rows[0]["content"] == "Real entry."


def test_purge_removes_canned_nudge(temp_db):
    db.add_nudge("2026-05-10", f"{coach.CANNED_MARKER} NUDGE_REPORT\n\nFake report.", "{}")
    db.add_nudge("2026-05-09", "Real nudge report.", "{}")

    counts = db.purge_canned_responses()

    assert counts["nudges"] == 1
    latest = db.get_latest_nudge()
    assert latest is not None
    assert "Real nudge report." in latest["report"]


def test_purge_nulls_meeting_llm_fields_preserves_row(temp_db):
    mid = db.add_meeting("Planning", "2026-05-10")
    db.update_meeting(
        mid,
        prep_brief=f"{coach.CANNED_MARKER} MEETING_PREP\n\nFake prep.",
        debrief_summary=f"{coach.CANNED_MARKER} MEETING_DEBRIEF\n\nFake debrief.",
    )

    counts = db.purge_canned_responses()

    assert counts["meetings_cleared"] == 1
    m = db.get_meeting(mid)
    assert m is not None  # row preserved
    assert m["prep_brief"] is None
    assert m["debrief_summary"] is None


def test_purge_does_not_affect_real_meeting_data(temp_db):
    mid = db.add_meeting("Real meeting", "2026-05-10")
    db.update_meeting(mid, prep_brief="Legit prep.", debrief_summary="Legit debrief.")

    counts = db.purge_canned_responses()

    assert counts["meetings_cleared"] == 0
    m = db.get_meeting(mid)
    assert m["prep_brief"] == "Legit prep."
    assert m["debrief_summary"] == "Legit debrief."


def test_purge_removes_canned_chat_thread_and_messages(temp_db):
    tid = db.get_or_create_thread("test-thread")
    db.add_chat_message(tid, "user", "Hello")
    db.add_chat_message(tid, "assistant", f"{coach.CANNED_MARKER} CHAT\n\nFake reply.")

    # Real thread should survive
    real_tid = db.get_or_create_thread("real-thread")
    db.add_chat_message(real_tid, "user", "Hi")
    db.add_chat_message(real_tid, "assistant", "Genuine response.")

    counts = db.purge_canned_responses()

    assert counts["chat_threads"] == 1
    # Canned thread gone
    assert db.list_chat_messages(tid) == []
    # Real thread intact
    real_msgs = db.list_chat_messages(real_tid)
    assert len(real_msgs) == 2


def test_purge_returns_zero_counts_when_nothing_to_purge(temp_db):
    db.add_post("Legit post.", channel="slack", audience="team", posted_at="2026-05-10")
    counts = db.purge_canned_responses()
    assert all(v == 0 for v in counts.values())


# ---------------------------------------------------------------------------
# cmd_purge_stubs: CLI command output
# ---------------------------------------------------------------------------


def test_cmd_purge_stubs_prints_counts(monkeypatch, temp_db, capsys):
    db.save_reflection(f"{coach.CANNED_MARKER} REFLECT\n\nFake.")
    db.add_nudge("2026-05-10", f"{coach.CANNED_MARKER} NUDGE_REPORT\n\nFake.", "{}")

    cli.cmd_purge_stubs(None)

    out = capsys.readouterr().out
    assert "reflections" in out
    assert "nudges" in out


def test_cmd_purge_stubs_prints_nothing_to_purge(monkeypatch, temp_db, capsys):
    cli.cmd_purge_stubs(None)
    out = capsys.readouterr().out
    assert "No canned responses found" in out
