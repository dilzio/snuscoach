import os
import sys

from anthropic import Anthropic

from snuscoach import db, prompts

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
    prep_briefs = db.list_prep_briefs()
    return [
        {"type": "text", "text": prompts.SYSTEM},
        {
            "type": "text",
            "text": prompts.context_block(
                stakeholders, wins, posts, meetings, prep_briefs
            ),
            "cache_control": {"type": "ephemeral"},
        },
    ]


def _stream(messages: list[dict]) -> str:
    client = _client()
    parts: list[str] = []
    with client.messages.stream(
        model=MODEL,
        max_tokens=32000,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        system=_system_blocks(),
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            parts.append(text)
        print()
    return "".join(parts)


def one_shot(user_message: str) -> str:
    return _stream([{"role": "user", "content": user_message}])


def conversation(messages: list[dict]) -> str:
    return _stream(messages)
