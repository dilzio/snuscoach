import os
import sys
import time

from anthropic import Anthropic

from snuscoach import db, logger, prompts

OPUS_MODEL   = "claude-opus-4-7"
SONNET_MODEL = "claude-sonnet-4-6"

CANNED_MARKER = "[CANNED RESPONSE]"

_CANNED_BODIES: dict[str, str] = {
    "CHAT": (
        "You're navigating this well. The key tension is between being visible on the "
        "initiative without over-claiming credit. Keep your language tied to outcomes "
        "the team achieved, with you as the enabler.\n\n"
        "What specific relationship or dynamic do you want to work through next?"
    ),
    "POST_DRAFT": (
        "Here's a draft:\n\n---\n"
        "Just wrapped the Q2 reliability push — latency down 40%, zero SEV-1s for six "
        "weeks straight. Huge credit to the SRE and backend teams who moved fast once "
        "the framing was clear.\n\n"
        "Next up: the auth migration kicks off Thursday. Scope's tight, timeline's "
        "tighter. Should be interesting.\n---\n\n"
        "**Coda:** Tag your skip in the thread — they've been asking for this signal "
        "for two quarters. Tighten the first sentence for leadership; they need the "
        "outcome and the next move, not the details."
    ),
    "MEETING_PREP": (
        "**Top 3 outcomes, ranked:**\n"
        "1. Alignment on Q3 scope — leave with a written list of what's in and out.\n"
        "2. Surface the budget dependency early so it doesn't become a blocker in week 6.\n"
        "3. Make your read of the political landscape visible to your manager in the room.\n\n"
        "**Talking points:** Frame the ask as removing ambiguity. Name the constraint "
        "before someone else does — it signals control.\n\n"
        "**Pre-align:** Get Sarah onside before the meeting or neutralise the objection.\n\n"
        "**Risks:** Don't let the conversation drift to roadmap; stay on scope decisions.\n\n"
        "**Listen-fors:** Who defers to whom on timeline calls? That's the power centre.\n\n"
        "**Coda:** Be the one who made the ambiguity visible and resolved it."
    ),
    "MEETING_DEBRIEF": (
        "**Follow-ups:**\n"
        "1. Send the scope doc to Sarah by EOD Thursday.\n"
        "2. Sync with ops on the migration timeline — you said 'Thursday' in the room; lock it.\n\n"
        "**Political signals:** James pushed back on timeline twice — that's about resourcing "
        "he doesn't control, not timeline. The VP deferred to you on technical calls twice.\n\n"
        "**Credit & thanks:** Public shout-out to Marcus in Slack. Private email to "
        "Jordan's manager noting how they handled the Q3 escalation.\n\n"
        "**Escalate:** Budget dependency needs to go to your manager before Thursday's sync.\n\n"
        "**What you missed:** The CFO's silence wasn't neutrality — she was waiting to see "
        "who'd own the cost side. No one did.\n\n"
        "**Coda:** Get the scope doc done before anyone asks. Changes you from reactive to driving."
    ),
    "JOURNAL": (
        "What's weighing on you most from the past week — something you're still "
        "turning over in your head, even if you're not sure why?\n\n"
        "Also: where did you feel most in control of your own narrative versus "
        "shaped by someone else's framing?"
    ),
    "REFLECT": (
        "**Recurring avoidances:** You consistently delay direct feedback to James. "
        "It shows up after every 1:1 and in three debriefs over the last 60 days.\n\n"
        "**Stalled relationships:** The platform team lead relationship is frozen — "
        "no real interaction in 45 days, yet your wins all landed in their domain.\n\n"
        "**Visibility gaps:** Six wins in the ledger, two posts. The auth migration is "
        "the most under-documented high-impact thing you've done this quarter.\n\n"
        "**What's working:** Meeting prep discipline is noticeably better — debrief "
        "quality is up, political signals are being caught earlier. Keep that."
    ),
    "NUDGE_INTERACTIVE": (
        "Let's do a quick check-in across the gaps I'm seeing.\n\n"
        "You've got two meetings from last week with no debrief logged. What's your "
        "read on what actually happened in those meetings, politically? Not the agenda "
        "— what was actually being decided?\n\n"
        "Also: four wins in the ledger with no visibility post. What's the block — "
        "is it time, or is there something more uncomfortable about claiming credit publicly?"
    ),
    "NUDGE_REPORT": (
        "## Coach nudge\n\n"
        "**Gaps detected:**\n\n"
        "1. **2 meetings without debriefs** — Architecture Review, Q3 Planning\n"
        "   > Action: `make debrief`\n\n"
        "2. **4 wins with no visibility post this month**\n"
        "   > Action: `make post`\n\n"
        "3. **Stakeholder 'James' — no note in 38 days**\n"
        "   > Action: `snuscoach stakeholder note \"James\"`\n\n"
        "4. **No journal entry in 5 days**\n"
        "   > Action: `make journal`\n\n"
        "Highest-leverage: clear the debrief backlog first."
    ),
}


def is_stubbed(use_case: str) -> bool:
    key = f"SNUSCOACH_STUB_{use_case.upper()}"
    return os.environ.get(key, "").lower() in ("1", "true", "yes", "on")


def canned_response(use_case: str) -> str:
    body = _CANNED_BODIES.get(use_case.upper(), "(no canned body defined for this use case)")
    return f"{CANNED_MARKER} {use_case}\n\n{body}"


def stub_fn(use_case: str):
    """Drop-in replacement for coach.draft / coach.conversation when stubbing."""
    def _stub(messages: list[dict]) -> str:
        resp = canned_response(use_case)
        print(resp)
        return resp
    return _stub


def _client() -> Anthropic:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit(
            "ERROR: ANTHROPIC_API_KEY is not set. Export it in your shell or "
            "put it in a .env file in the project directory."
        )
    return Anthropic()


def _system_blocks() -> list[dict]:
    profile = dict(db.get_default_profile() or {})
    stakeholders = db.list_stakeholders()
    wins = db.list_wins()
    posts = db.list_posts()
    meetings = db.list_meetings()
    meeting_series = db.list_meeting_series()
    voice_samples = db.list_voice_samples()
    journal_entries = db.list_journal_entries(limit=7)
    latest_reflection = db.get_latest_reflection()
    return [
        {"type": "text", "text": prompts.system_prompt(profile)},
        {
            "type": "text",
            "text": prompts.context_block(
                stakeholders, wins, posts, meetings, meeting_series, voice_samples,
                journal_entries=journal_entries,
                latest_reflection=latest_reflection,
            ),
            "cache_control": {"type": "ephemeral"},
        },
    ]


def _stream(messages: list[dict], model: str) -> str:
    client = _client()
    system = _system_blocks()
    parts: list[str] = []
    started = time.monotonic()
    final_message = None
    kwargs: dict = dict(
        model=model,
        max_tokens=32000 if model == OPUS_MODEL else 8096,
        system=system,
        messages=messages,
    )
    if model == OPUS_MODEL:
        kwargs["thinking"] = {"type": "adaptive"}
        kwargs["output_config"] = {"effort": "high"}
    try:
        with client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                print(text, end="", flush=True)
                parts.append(text)
            print()
            try:
                final_message = stream.get_final_message()
            except Exception:
                final_message = None
    except Exception as xn:
        parts.append(f"\n\nANTHROPIC API ERROR: {xn.message}")
    elapsed_ms = int((time.monotonic() - started) * 1000)
    response_text = "".join(parts)
    logger.log_call(
        system=system,
        messages=messages,
        response=response_text,
        usage=getattr(final_message, "usage", None),
        latency_ms=elapsed_ms,
        model=model,
    )
    return response_text


def conversation(messages: list[dict]) -> str:
    """Coaching turns — Opus with extended thinking."""
    return _stream(messages, OPUS_MODEL)


def draft(messages: list[dict]) -> str:
    """Drafting turns — Sonnet, no extended thinking."""
    return _stream(messages, SONNET_MODEL)
