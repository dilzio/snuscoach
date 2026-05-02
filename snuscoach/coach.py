import os
import sys
import time

from anthropic import Anthropic

from snuscoach import db, logger, prompts

MODEL = "claude-opus-4-7"


def _client() -> Anthropic:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit(
            "ERROR: ANTHROPIC_API_KEY is not set. Export it in your shell or "
            "put it in a .env file in the project directory."
        )
    return Anthropic()


def _system_blocks() -> list[dict]:
    stakeholders = db.list_stakeholders()
    wins = db.list_wins()
    posts = db.list_posts()
    meetings = db.list_meetings()
    meeting_series = db.list_meeting_series()
    return [
        {"type": "text", "text": prompts.SYSTEM},
        {
            "type": "text",
            "text": prompts.context_block(
                stakeholders, wins, posts, meetings, meeting_series
            ),
            "cache_control": {"type": "ephemeral"},
        },
    ]


def _stream(messages: list[dict]) -> str:
    client = _client()
    system = _system_blocks()
    parts: list[str] = []
    started = time.monotonic()
    final_message = None
    with client.messages.stream(
        model=MODEL,
        max_tokens=32000,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        system=system,
        messages=messages,
    ) as stream:
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
        model=MODEL,
    )
    return response_text


def one_shot(user_message: str) -> str:
    return _stream([{"role": "user", "content": user_message}])


def conversation(messages: list[dict]) -> str:
    return _stream(messages)
