import os
import sys
import time

from anthropic import Anthropic

from snuscoach import db, logger, prompts

OPUS_MODEL   = "claude-opus-4-7"
SONNET_MODEL = "claude-sonnet-4-6"


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
    with client.messages.stream(**kwargs) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            parts.append(text)
        print()
        try:
            final_message = stream.get_final_message()
        except Exception:
            final_message = None
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
