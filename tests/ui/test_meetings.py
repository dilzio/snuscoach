"""Playwright integration tests for the Meetings section (§6.7).

Covers: two-column layout, list view (grouped/one-offs/empty), status badges,
detail view navigation and pre-population, Save, chat panel, Prep/Debrief
action buttons, new-meeting dialog.

AI calls are expected to fail (fake API key in conftest) — tests assert on the
user message appearing in chat, not on the AI reply.
"""

import sqlite3
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.ui

MEETINGS = "/meetings"


def _goto(page: Page, url: str) -> None:
    page.goto(url, wait_until="networkidle")


# ---------------------------------------------------------------------------
# DB seeding helper — idempotent (called independently by each test)
# ---------------------------------------------------------------------------

def _seed_meetings(db_path: Path) -> dict:
    """Ensure the shared test DB has a series, two series meetings, and one one-off.

    Uses INSERT OR IGNORE / check-then-insert to be idempotent — the session-
    scoped server may have already seeded these rows in a prior test.
    Returns dict of IDs.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        # Series — unique name constraint; ignore if already exists
        conn.execute(
            "INSERT OR IGNORE INTO meeting_series"
            " (name, description, created_at, updated_at) VALUES (?,?,?,?)",
            ("Weekly 1:1", "Manager sync", "2026-05-01T10:00:00", "2026-05-01T10:00:00"),
        )
        series_id = conn.execute(
            "SELECT id FROM meeting_series WHERE name='Weekly 1:1'"
        ).fetchone()[0]

        def _get_or_insert(title, meeting_date, attendees, prep_ctx, prep_brief,
                           debrief_notes, debrief_sum, sid):
            row = conn.execute(
                "SELECT id FROM meetings WHERE title=? AND date=?", (title, meeting_date)
            ).fetchone()
            if row:
                return row[0]
            conn.execute(
                "INSERT INTO meetings"
                " (series_id, title, attendees, date, prep_context, prep_brief,"
                " debrief_notes, debrief_summary, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (sid, title, attendees, meeting_date, prep_ctx, prep_brief,
                 debrief_notes, debrief_sum,
                 "2026-05-01T10:00:00", "2026-05-01T10:00:00"),
            )
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # m1: in series, has prep_brief, no debrief
        m1_id = _get_or_insert(
            "1:1 with Alice", "2026-05-13", "Alice, Bob",
            "discuss project priorities", "prep brief: focus on Q3 goals",
            None, None, series_id,
        )
        # m2: in series, no prep, has debrief_summary
        m2_id = _get_or_insert(
            "1:1 with Alice", "2026-05-06", "Alice",
            None, None,
            "agreed on timeline", "debrief: timeline locked, needs exec sign-off",
            series_id,
        )
        # m3: one-off, no prep or debrief
        m3_id = _get_or_insert(
            "Q2 Planning", "2026-05-10", "Team",
            None, None, None, None, None,
        )

        conn.commit()
    finally:
        conn.close()

    return {"series_id": series_id, "m1_id": m1_id, "m2_id": m2_id, "m3_id": m3_id}


# ---------------------------------------------------------------------------
# Helper to expand the series group in the list view
# ---------------------------------------------------------------------------

def _expand_series(page: Page) -> None:
    """Click the 'Weekly 1:1' expansion header and wait for it to open."""
    page.locator("text=Weekly 1:1").first.click()
    page.wait_for_timeout(500)


# ---------------------------------------------------------------------------
# Basic page load
# ---------------------------------------------------------------------------

def test_meetings_page_loads(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{MEETINGS}")
    expect(page.locator("text=Meetings").first).to_be_visible()


def test_meetings_page_has_new_meeting_button(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{MEETINGS}")
    expect(page.locator("text=+ New Meeting").first).to_be_visible()


def test_meetings_page_has_chat_panel(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{MEETINGS}")
    expect(page.locator("button:has-text('Send')").first).to_be_visible()


# ---------------------------------------------------------------------------
# List view — empty state
# ---------------------------------------------------------------------------

def test_meeting_list_empty_state(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{MEETINGS}")
    expect(page.locator("text=No meetings yet.").first).to_be_visible()


# ---------------------------------------------------------------------------
# List view — with data
# ---------------------------------------------------------------------------

def test_meeting_list_shows_series_group(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_meetings(ui_db_path)
    _goto(page, f"{ui_base_url}{MEETINGS}")
    expect(page.locator("text=Weekly 1:1").first).to_be_visible()


def test_meeting_list_shows_one_offs_section(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_meetings(ui_db_path)
    _goto(page, f"{ui_base_url}{MEETINGS}")
    expect(page.locator("text=One-off meetings").first).to_be_visible()
    expect(page.locator("text=Q2 Planning").first).to_be_visible()


def test_status_badge_prep_positive(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    """m1 has prep_brief — P badge should be present after expanding the series."""
    _seed_meetings(ui_db_path)
    _goto(page, f"{ui_base_url}{MEETINGS}")
    _expand_series(page)
    expect(page.locator("text=P").first).to_be_visible()


def test_status_badge_debrief_positive(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    """m2 has debrief_summary — D badge should be present after expanding the series."""
    _seed_meetings(ui_db_path)
    _goto(page, f"{ui_base_url}{MEETINGS}")
    _expand_series(page)
    expect(page.locator("text=D").first).to_be_visible()


# ---------------------------------------------------------------------------
# Detail view
# ---------------------------------------------------------------------------

def _open_detail(page: Page, ui_db_path: Path, ui_base_url: str) -> None:
    """Seed data, navigate, expand series, click first meeting card."""
    _seed_meetings(ui_db_path)
    _goto(page, f"{ui_base_url}{MEETINGS}")
    _expand_series(page)
    page.locator("text=1:1 with Alice").first.click()
    page.wait_for_timeout(500)


def test_click_meeting_shows_detail_back_button(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_detail(page, ui_db_path, ui_base_url)
    expect(page.locator("button:has-text('Back')").first).to_be_visible()


def test_click_meeting_shows_title_field(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_detail(page, ui_db_path, ui_base_url)
    # Quasar QInput: label text lives inside .q-field__label
    expect(page.locator(".q-field__label:has-text('Title')").first).to_be_visible()


def test_detail_fields_prepopulated(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    """m1 has prep_brief set; the Prep brief textarea should hold that value."""
    _open_detail(page, ui_db_path, ui_base_url)
    prep_brief_ta = page.locator(
        ".q-field:has(.q-field__label:has-text('Prep brief')) textarea"
    )
    expect(prep_brief_ta.first).to_have_value("prep brief: focus on Q3 goals")


def test_back_button_returns_to_list(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_detail(page, ui_db_path, ui_base_url)
    page.locator("button:has-text('Back')").first.click()
    page.wait_for_timeout(500)
    # Series heading back in view
    expect(page.locator("text=Weekly 1:1").first).to_be_visible()
    # Back button gone
    expect(page.locator("button:has-text('Back')")).to_have_count(0)


def test_save_button_present_in_detail(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_detail(page, ui_db_path, ui_base_url)
    expect(page.locator("button:has-text('Save')").first).to_be_visible()


def test_save_updates_meeting(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    """Edit the title in detail view, save — DB row updated."""
    _open_detail(page, ui_db_path, ui_base_url)

    # Fill the Title QInput — .fill() clears then types
    title_input = page.locator(".q-field:has(.q-field__label:has-text('Title')) input").first
    title_input.fill("1:1 with Alice UPDATED")

    page.locator("button:has-text('Save')").first.click()
    page.wait_for_timeout(500)

    conn = sqlite3.connect(str(ui_db_path))
    row = conn.execute(
        "SELECT title FROM meetings WHERE title LIKE '%UPDATED%'"
    ).fetchone()
    conn.close()
    assert row is not None, "Updated title not found in DB"


# ---------------------------------------------------------------------------
# Chat panel — meeting-contextual
# ---------------------------------------------------------------------------

def test_prep_debrief_buttons_on_selection(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_detail(page, ui_db_path, ui_base_url)
    expect(page.locator("button:has-text('Prep this meeting')").first).to_be_visible()
    expect(page.locator("button:has-text('Debrief this meeting')").first).to_be_visible()


def test_save_brief_button_on_selection(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_detail(page, ui_db_path, ui_base_url)
    expect(page.locator("button:has-text('Save brief')").first).to_be_visible()
    expect(page.locator("button:has-text('Save summary')").first).to_be_visible()


def test_prep_button_injects_user_message(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    """Clicking Prep injects a user message containing the TASK header into the chat."""
    _open_detail(page, ui_db_path, ui_base_url)
    page.locator("button:has-text('Prep this meeting')").first.click()
    expect(
        page.locator("text=TASK: Pre-meeting prep brief").first
    ).to_be_visible(timeout=8_000)


def test_debrief_button_injects_user_message(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    """Clicking Debrief injects a user message with the debrief TASK header."""
    _seed_meetings(ui_db_path)
    _goto(page, f"{ui_base_url}{MEETINGS}")
    _expand_series(page)
    # m2 (2026-05-06) is the second card; both have title "1:1 with Alice"
    page.locator("text=1:1 with Alice").nth(1).click()
    page.wait_for_timeout(500)
    page.locator("button:has-text('Debrief this meeting')").first.click()
    expect(
        page.locator("text=TASK: Post-meeting debrief").first
    ).to_be_visible(timeout=8_000)


def test_chat_panel_renders_no_selection(page: Page, ui_base_url: str) -> None:
    """Generic chat renders when no meeting is selected."""
    _goto(page, f"{ui_base_url}{MEETINGS}")
    expect(page.locator("input[placeholder*='meeting']").first).to_be_visible()
    expect(page.locator("button:has-text('Send')").first).to_be_visible()


# ---------------------------------------------------------------------------
# New meeting dialog
# ---------------------------------------------------------------------------

def test_new_meeting_dialog_opens(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{MEETINGS}")
    page.locator("text=+ New Meeting").first.click()
    page.wait_for_selector(".q-dialog", state="visible", timeout=5_000)
    dialog = page.locator(".q-dialog")
    expect(dialog.locator("text=New Meeting").first).to_be_visible()


def test_new_meeting_dialog_cancel(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{MEETINGS}")
    page.locator("text=+ New Meeting").first.click()
    page.wait_for_selector(".q-dialog", state="visible", timeout=5_000)
    page.locator(".q-dialog button:has-text('Cancel')").first.click()
    page.wait_for_timeout(400)
    expect(page.locator(".q-dialog")).to_have_count(0)


def test_new_meeting_creates_and_appears(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _goto(page, f"{ui_base_url}{MEETINGS}")
    page.locator("text=+ New Meeting").first.click()
    page.wait_for_selector(".q-dialog", state="visible", timeout=5_000)

    # First input in the dialog is the Title field
    page.locator(".q-dialog input").first.fill("TestMeetingXYZ")
    page.locator(".q-dialog button:has-text('Create')").first.click()
    # Wait for dialog to close and list to re-render
    page.wait_for_selector(".q-dialog", state="hidden", timeout=5_000)
    expect(page.locator("text=TestMeetingXYZ").first).to_be_visible(timeout=8_000)
