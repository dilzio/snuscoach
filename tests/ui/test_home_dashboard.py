"""Playwright integration tests for the Home dashboard (§6.7).

Verifies: two-column layout, all three widget cards render, chat panel is
functional. AI calls are expected to fail (fake API key in conftest) so the
nudge card's error fallback is what we assert against.
"""

import os
import sqlite3
from datetime import date
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.ui

HOME = "/"


def _goto(page: Page, url: str) -> None:
    """Navigate and wait for NiceGUI WebSocket content to settle."""
    page.goto(url, wait_until="networkidle")


def test_home_page_loads(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{HOME}")
    expect(page.locator("text=Home").first).to_be_visible()


def test_nudge_card_heading_visible(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{HOME}")
    expect(page.locator("text=Coach nudge").first).to_be_visible()


def test_nudge_card_resolves(page: Page, ui_base_url: str) -> None:
    """Spinner should disappear and content (or error text) should appear."""
    _goto(page, f"{ui_base_url}{HOME}")
    # Wait for spinner to go away (AI call completes or hits error handler)
    page.wait_for_selector(".q-spinner", state="hidden", timeout=20_000)
    # Either the report markdown or the error fallback label should be present
    content = page.locator("text=Nudge unavailable").or_(page.locator(".q-markdown"))
    expect(content.first).to_be_visible()


def test_upcoming_meetings_card_renders(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{HOME}")
    expect(page.locator("text=Upcoming meetings").first).to_be_visible()
    expect(page.locator("text=No upcoming meetings.").first).to_be_visible()


def test_wins_gap_card_renders(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{HOME}")
    expect(page.locator("text=Wins without a post").first).to_be_visible()
    wins_label = page.locator("text=All wins have posts.").or_(
        page.locator("text=wins with no visibility post")
    )
    expect(wins_label.first).to_be_visible()


def test_chat_panel_renders(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{HOME}")
    expect(page.locator("input[placeholder*='mind']").first).to_be_visible()
    expect(page.locator("button:has-text('Send')").first).to_be_visible()


def test_chat_panel_accepts_input(page: Page, ui_base_url: str) -> None:
    """User message should appear in the chat after sending."""
    _goto(page, f"{ui_base_url}{HOME}")
    chat_input = page.locator("input[placeholder*='mind']").first
    chat_input.fill("Hello coach")
    page.locator("button:has-text('Send')").first.click()
    expect(page.locator("text=Hello coach").first).to_be_visible()


def test_all_three_card_headings_simultaneously_visible(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    """All three sidebar card headings must be in-viewport even with a long nudge."""
    today = date.today().isoformat()
    long_nudge = ("This is a very long nudge paragraph. " * 40).strip()

    conn = sqlite3.connect(str(ui_db_path))
    conn.execute(
        "INSERT INTO nudges (date, report, gaps_json, created_at) VALUES (?, ?, ?, ?)",
        (today, long_nudge, "{}", today + "T00:00:00"),
    )
    conn.commit()
    conn.close()

    _goto(page, f"{ui_base_url}{HOME}")
    page.wait_for_selector(".q-spinner", state="hidden", timeout=20_000)

    for heading in ("Coach nudge", "Upcoming meetings", "Wins without a post"):
        assert page.locator(f"text={heading}").first.is_visible(), (
            f'"{heading}" heading is not visible in the viewport'
        )


def test_nudge_card_serves_cached_report(page: Page, ui_base_url: str, ui_db_path: Path) -> None:
    """Nudge card shows cached report without making an LLM call."""
    today = date.today().isoformat()
    cached_text = "Cached nudge report: you are doing great."

    # Seed today's nudge directly into the test DB
    conn = sqlite3.connect(str(ui_db_path))
    conn.execute(
        "INSERT INTO nudges (date, report, gaps_json, created_at) VALUES (?, ?, ?, ?)",
        (today, cached_text, "{}", today + "T00:00:00"),
    )
    conn.commit()
    conn.close()

    _goto(page, f"{ui_base_url}{HOME}")
    page.wait_for_selector(".q-spinner", state="hidden", timeout=20_000)
    expect(page.locator(f"text={cached_text}").first).to_be_visible()


def _seed_nudge_and_thread(db_path: Path, nudge_text: str) -> None:
    """Insert a nudge row and the matching chat thread+messages into the test DB.

    Uses INSERT OR IGNORE / INSERT OR REPLACE to be idempotent — the UI server
    may have already created the thread or a nudge row for today.
    """
    today = date.today().isoformat()
    thread_key = f"home-nudge-{today}"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            "INSERT OR REPLACE INTO nudges (date, report, gaps_json, created_at) VALUES (?, ?, ?, ?)",
            (today, nudge_text, "{}", today + "T00:00:00"),
        )
        # Thread may already exist if the server visited the home page first
        conn.execute(
            "INSERT OR IGNORE INTO chat_threads (key, created_at, updated_at) VALUES (?, ?, ?)",
            (thread_key, today + "T00:00:00", today + "T00:00:00"),
        )
        row = conn.execute(
            "SELECT id FROM chat_threads WHERE key = ?", (thread_key,)
        ).fetchone()
        thread_id = row[0]
        # Clear any existing messages for this thread so we control the state
        conn.execute("DELETE FROM chat_messages WHERE thread_id = ?", (thread_id,))
        conn.execute(
            "INSERT INTO chat_messages (thread_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (thread_id, "user", nudge_text, today + "T00:00:01"),
        )
        conn.execute(
            "INSERT INTO chat_messages (thread_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (thread_id, "assistant", "Great work! Keep it up.", today + "T00:00:02"),
        )
        conn.commit()
    finally:
        conn.close()


def test_chat_history_survives_navigation(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    """Chat messages persisted to DB should still be visible after navigating away and back."""
    nudge_text = "Navigation persistence nudge: unique marker xq9z."
    _seed_nudge_and_thread(ui_db_path, nudge_text)

    _goto(page, f"{ui_base_url}{HOME}")
    page.wait_for_selector(".q-spinner", state="hidden", timeout=20_000)
    # History loaded from DB — user message should be visible immediately
    expect(page.locator(f"text={nudge_text}").first).to_be_visible()

    # Navigate away then back
    _goto(page, f"{ui_base_url}/meetings")
    _goto(page, f"{ui_base_url}{HOME}")
    page.wait_for_selector(".q-spinner", state="hidden", timeout=20_000)

    # Message should still be visible after re-render
    expect(page.locator(f"text={nudge_text}").first).to_be_visible()


def test_open_in_chat_does_not_reseed_on_repeat(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    """Pressing 'Open in chat' a second time should not duplicate the nudge text."""
    today = date.today().isoformat()
    cached_text = "Reseed guard nudge: unique marker ab7y."

    conn = sqlite3.connect(str(ui_db_path))
    try:
        conn.execute(
            "INSERT OR REPLACE INTO nudges (date, report, gaps_json, created_at) VALUES (?, ?, ?, ?)",
            (today, cached_text, "{}", today + "T00:00:00"),
        )
        conn.commit()
    finally:
        conn.close()

    _goto(page, f"{ui_base_url}{HOME}")
    page.wait_for_selector(".q-spinner", state="hidden", timeout=20_000)

    # Click once — nudge text seeds into chat
    page.locator("button:has-text('Open in chat')").first.click()
    page.wait_for_timeout(500)  # let the async seed() complete

    # Click again — should be a no-op (seed() guard fires)
    page.locator("button:has-text('Open in chat')").first.click()
    page.wait_for_timeout(500)

    # Nudge text should appear exactly once in the chat
    count = page.locator(f"text={cached_text}").count()
    assert count == 1, f"Expected nudge text to appear once, got {count}"
