"""Playwright integration tests for the Journal section (§4.5 / §6.7).

List view: table of journal entries (date, type badge, content preview).
Detail view: two-column entry form + contextual chat.
"""

import sqlite3
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.ui

JOURNAL = "/journal"
_CHAT_PLACEHOLDER = "Reflect on your day..."


def _goto(page: Page, url: str) -> None:
    page.goto(url, wait_until="networkidle")


# ---------------------------------------------------------------------------
# DB seeding helpers
# ---------------------------------------------------------------------------

def _seed_entries(db_path: Path) -> dict:
    conn = sqlite3.connect(str(db_path))
    try:
        existing = {r[0] for r in conn.execute("SELECT content FROM journal_entries").fetchall()}

        entry1_id = entry2_id = None
        content1 = "coach: What's on your mind today?\n\nyou: Had a tough 1:1 with my manager."

        if content1 not in existing:
            cur = conn.execute(
                "INSERT INTO journal_entries (content, coach_prompt, entry_type, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (content1, "Opening prompt for day", "journal", "2026-05-15T09:00:00", "2026-05-15T09:00:00"),
            )
            entry1_id = cur.lastrowid
        else:
            entry1_id = conn.execute(
                "SELECT id FROM journal_entries WHERE content=?", (content1,)
            ).fetchone()[0]

        content2 = "Nudge report: 3 stakeholders have gone quiet."
        if content2 not in existing:
            cur = conn.execute(
                "INSERT INTO journal_entries (content, coach_prompt, entry_type, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (content2, None, "nudge", "2026-05-13T08:00:00", "2026-05-13T08:00:00"),
            )
            entry2_id = cur.lastrowid
        else:
            entry2_id = conn.execute(
                "SELECT id FROM journal_entries WHERE content=?", (content2,)
            ).fetchone()[0]

        conn.commit()
    finally:
        conn.close()

    return {"entry1_id": entry1_id, "entry2_id": entry2_id}


# ---------------------------------------------------------------------------
# Page structure
# ---------------------------------------------------------------------------

def test_page_loads(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{JOURNAL}")
    expect(page.locator("text=Journal").first).to_be_visible()


def test_new_entry_button_visible(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{JOURNAL}")
    expect(page.locator("button:has-text('+ New Entry')").first).to_be_visible()


# ---------------------------------------------------------------------------
# List view — empty state
# ---------------------------------------------------------------------------

def test_list_empty_state(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{JOURNAL}")
    expect(page.locator("text=No entries yet.").first).to_be_visible()


# ---------------------------------------------------------------------------
# List view — with seeded data
# ---------------------------------------------------------------------------

def test_list_shows_entry_date(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_entries(ui_db_path)
    _goto(page, f"{ui_base_url}{JOURNAL}")
    expect(page.locator("text=2026-05-15").first).to_be_visible()


def test_list_shows_type_badge_journal(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_entries(ui_db_path)
    _goto(page, f"{ui_base_url}{JOURNAL}")
    expect(page.locator("text=journal").first).to_be_visible()


def test_list_shows_type_badge_nudge(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_entries(ui_db_path)
    _goto(page, f"{ui_base_url}{JOURNAL}")
    expect(page.locator("text=nudge").first).to_be_visible()


def test_list_shows_content_preview(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_entries(ui_db_path)
    _goto(page, f"{ui_base_url}{JOURNAL}")
    expect(page.locator("text=coach: What's on your mind today").first).to_be_visible()


def test_list_newest_first(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_entries(ui_db_path)
    _goto(page, f"{ui_base_url}{JOURNAL}")
    dates = page.locator("td").filter(has_text="2026-05").all_text_contents()
    assert dates[0] == "2026-05-15"


# ---------------------------------------------------------------------------
# Add entry flow
# ---------------------------------------------------------------------------

def test_add_entry_opens_detail_view(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{JOURNAL}")
    page.locator("button:has-text('+ New Entry')").first.click()
    page.wait_for_timeout(400)
    expect(page.locator("text=Entry Details").first).to_be_visible()


def test_add_entry_back_returns_to_list(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{JOURNAL}")
    page.locator("button:has-text('+ New Entry')").first.click()
    page.wait_for_timeout(400)
    page.locator("button:has-text('Back')").first.click()
    page.wait_for_timeout(400)
    expect(page.locator("button:has-text('+ New Entry')").first).to_be_visible()


def test_add_entry_save_persists_to_db(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _goto(page, f"{ui_base_url}{JOURNAL}")
    page.locator("button:has-text('+ New Entry')").first.click()
    page.wait_for_timeout(400)
    page.locator("textarea").first.fill("Reflected on a hard week with stakeholders.")
    page.locator("button:has-text('Save Entry')").first.click()
    page.wait_for_timeout(600)

    conn = sqlite3.connect(str(ui_db_path))
    count = conn.execute(
        "SELECT count(*) FROM journal_entries WHERE content LIKE ?",
        ("%Reflected on a hard week%",),
    ).fetchone()[0]
    conn.close()
    assert count >= 1


def test_add_entry_save_refreshes_list(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _goto(page, f"{ui_base_url}{JOURNAL}")
    page.locator("button:has-text('+ New Entry')").first.click()
    page.wait_for_timeout(400)
    page.locator("textarea").first.fill("New entry for list refresh test.")
    page.locator("button:has-text('Save Entry')").first.click()
    page.wait_for_timeout(600)
    expect(page.locator("button:has-text('+ New Entry')").first).to_be_visible()
    expect(page.locator("text=New entry for list refresh test.").first).to_be_visible()


def test_save_entry_no_content_warns(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{JOURNAL}")
    page.locator("button:has-text('+ New Entry')").first.click()
    page.wait_for_timeout(400)
    page.locator("button:has-text('Save Entry')").first.click()
    page.wait_for_timeout(300)
    expect(page.locator("text=Content is required.").first).to_be_visible()


# ---------------------------------------------------------------------------
# Existing entry detail view
# ---------------------------------------------------------------------------

def test_click_entry_opens_detail(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_entries(ui_db_path)
    _goto(page, f"{ui_base_url}{JOURNAL}")
    page.locator("td").filter(has_text="coach: What's on your mind today").first.click()
    page.wait_for_timeout(400)
    expect(page.locator("text=Entry Details").first).to_be_visible()


def test_detail_shows_content(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_entries(ui_db_path)
    _goto(page, f"{ui_base_url}{JOURNAL}")
    page.locator("td").filter(has_text="coach: What's on your mind today").first.click()
    page.wait_for_timeout(400)
    ta_value = page.locator("textarea").first.input_value()
    assert "tough 1:1" in ta_value


def test_detail_shows_date(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_entries(ui_db_path)
    _goto(page, f"{ui_base_url}{JOURNAL}")
    page.locator("td").filter(has_text="coach: What's on your mind today").first.click()
    page.wait_for_timeout(400)
    expect(page.locator("text=2026-05-15").first).to_be_visible()


def test_detail_back_returns_to_list(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_entries(ui_db_path)
    _goto(page, f"{ui_base_url}{JOURNAL}")
    page.locator("td").filter(has_text="coach: What's on your mind today").first.click()
    page.wait_for_timeout(400)
    page.locator("button:has-text('Back')").first.click()
    page.wait_for_timeout(400)
    expect(page.locator("button:has-text('+ New Entry')").first).to_be_visible()


def test_detail_save_updates_db(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    ids = _seed_entries(ui_db_path)
    _goto(page, f"{ui_base_url}{JOURNAL}")
    page.locator("td").filter(has_text="coach: What's on your mind today").first.click()
    page.wait_for_timeout(400)
    page.locator("textarea").first.fill("Updated reflection content for test.")
    page.locator("button:has-text('Save Entry')").first.click()
    page.wait_for_timeout(600)

    conn = sqlite3.connect(str(ui_db_path))
    row = conn.execute(
        "SELECT content FROM journal_entries WHERE id=?", (ids["entry1_id"],)
    ).fetchone()
    conn.close()
    assert "Updated reflection content for test." in row[0]


# ---------------------------------------------------------------------------
# Chat panel
# ---------------------------------------------------------------------------

def test_detail_chat_panel_exists(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{JOURNAL}")
    page.locator("button:has-text('+ New Entry')").first.click()
    page.wait_for_timeout(400)
    expect(
        page.locator(f"input[placeholder='{_CHAT_PLACEHOLDER}']").first
    ).to_be_visible()


def test_adopt_transcript_no_messages_warns(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    # Existing entry → thread is empty (no auto-seed) → Adopt transcript warns
    _seed_entries(ui_db_path)
    _goto(page, f"{ui_base_url}{JOURNAL}")
    page.locator("td").filter(has_text="coach: What's on your mind today").first.click()
    page.wait_for_timeout(400)
    page.locator("button:has-text('Adopt transcript')").first.click()
    page.wait_for_timeout(300)
    expect(page.locator("text=Start a conversation first.").first).to_be_visible()
