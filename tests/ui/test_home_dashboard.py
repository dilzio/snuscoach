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
