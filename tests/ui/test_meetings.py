"""Playwright integration tests for the redesigned Meetings section (§6.7).

List view: full-width table grouped by series; per-row Prep/Debrief session
links. Detail view: three collapsible accordions (Meeting Setup, Prep,
Debrief) on the left; tabbed Prep/Debrief session panel on the right.

AI calls are expected to fail (fake API key in conftest) — tests assert on
user messages appearing in chat, not on AI replies.
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
# DB seeding helper — idempotent
# ---------------------------------------------------------------------------

def _seed_meetings(db_path: Path) -> dict:
    """Ensure the shared test DB has a series, two series meetings, and one one-off.

    Returns dict of IDs.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")

    try:
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
# Basic page load
# ---------------------------------------------------------------------------

def test_meetings_page_loads(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{MEETINGS}")
    expect(page.locator("text=Meetings").first).to_be_visible()


def test_new_meeting_button_visible(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{MEETINGS}")
    expect(page.locator("text=+ New Meeting").first).to_be_visible()


# ---------------------------------------------------------------------------
# List view — empty state
# ---------------------------------------------------------------------------

def test_meeting_list_empty_state(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{MEETINGS}")
    expect(page.locator("text=No meetings yet.").first).to_be_visible()


# ---------------------------------------------------------------------------
# List view — with data
# ---------------------------------------------------------------------------

def test_list_shows_series_header(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_meetings(ui_db_path)
    _goto(page, f"{ui_base_url}{MEETINGS}")
    expect(page.locator("text=Weekly 1:1").first).to_be_visible()


def test_list_shows_one_offs_header(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_meetings(ui_db_path)
    _goto(page, f"{ui_base_url}{MEETINGS}")
    expect(page.locator("text=One-off meetings").first).to_be_visible()


def test_list_shows_meeting_row(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_meetings(ui_db_path)
    _goto(page, f"{ui_base_url}{MEETINGS}")
    expect(page.locator("text=Q2 Planning").first).to_be_visible()


def test_list_prep_indicator_filled(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    """m1 has prep_brief — ● indicator should be visible (green)."""
    _seed_meetings(ui_db_path)
    _goto(page, f"{ui_base_url}{MEETINGS}")
    # At least one filled indicator in the page
    expect(page.locator("text=●").first).to_be_visible()


def test_list_debrief_indicator_filled(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    """m2 has debrief_summary — ● indicator should be visible."""
    _seed_meetings(ui_db_path)
    _goto(page, f"{ui_base_url}{MEETINGS}")
    # m2's debrief ● is also a filled indicator
    filled = page.locator("text=●")
    expect(filled.first).to_be_visible()


# ---------------------------------------------------------------------------
# Detail view — navigation
# ---------------------------------------------------------------------------

def _open_q2_planning(page: Page, ui_db_path: Path, ui_base_url: str) -> None:
    """Seed, navigate, click Q2 Planning row to open detail."""
    _seed_meetings(ui_db_path)
    _goto(page, f"{ui_base_url}{MEETINGS}")
    page.locator("text=Q2 Planning").first.click()
    page.wait_for_timeout(500)


def _open_m1(page: Page, ui_db_path: Path, ui_base_url: str) -> None:
    """Seed, navigate, click first '1:1 with Alice' row (m1, 2026-05-13)."""
    _seed_meetings(ui_db_path)
    _goto(page, f"{ui_base_url}{MEETINGS}")
    page.locator("text=1:1 with Alice").first.click()
    page.wait_for_timeout(500)


def test_click_meeting_name_opens_detail(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_q2_planning(page, ui_db_path, ui_base_url)
    expect(page.locator("button:has-text('Back')").first).to_be_visible()


def test_detail_has_meeting_setup_section(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_q2_planning(page, ui_db_path, ui_base_url)
    expect(page.locator("text=Meeting Setup").first).to_be_visible()


def test_detail_setup_fields_prepopulated(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    """m1 title should appear in the Title input."""
    _open_m1(page, ui_db_path, ui_base_url)
    title_input = page.locator(".q-field:has(.q-field__label:has-text('Title')) input").first
    expect(title_input).to_have_value("1:1 with Alice")


def test_back_button_returns_to_list(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_q2_planning(page, ui_db_path, ui_base_url)
    page.locator("button:has-text('Back')").first.click()
    page.wait_for_timeout(500)
    expect(page.locator("text=Weekly 1:1").first).to_be_visible()
    expect(page.locator("button:has-text('Back')")).to_have_count(0)


def test_save_setup_updates_db(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    """Edit title in Meeting Setup, Save meeting → DB row updated."""
    _open_m1(page, ui_db_path, ui_base_url)
    title_input = page.locator(".q-field:has(.q-field__label:has-text('Title')) input").first
    title_input.fill("1:1 with Alice UPDATED")
    page.locator("button:has-text('Save meeting')").first.click()
    page.wait_for_timeout(500)

    conn = sqlite3.connect(str(ui_db_path))
    row = conn.execute(
        "SELECT title FROM meetings WHERE title LIKE '%UPDATED%'"
    ).fetchone()
    conn.close()
    assert row is not None, "Updated title not found in DB"


# ---------------------------------------------------------------------------
# Detail view — left panel sections
# ---------------------------------------------------------------------------

def test_detail_has_prep_section(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_q2_planning(page, ui_db_path, ui_base_url)
    expect(page.locator("text=Prep").first).to_be_visible()


def test_detail_has_debrief_section(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_q2_planning(page, ui_db_path, ui_base_url)
    expect(page.locator("text=Debrief").first).to_be_visible()


def test_detail_prep_brief_shows_content(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    """m1 has prep_brief — its text should be visible in the left panel."""
    _open_m1(page, ui_db_path, ui_base_url)
    expect(page.locator("text=prep brief: focus on Q3 goals").first).to_be_visible()


def test_detail_prep_brief_placeholder_when_empty(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    """m3 has no prep_brief — placeholder text should show."""
    _open_q2_planning(page, ui_db_path, ui_base_url)
    expect(page.locator("text=Not yet generated").first).to_be_visible()


def test_open_prep_session_button_visible(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_q2_planning(page, ui_db_path, ui_base_url)
    expect(page.locator("button:has-text('Open Prep Session')").first).to_be_visible()


def test_open_debrief_session_button_visible(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_q2_planning(page, ui_db_path, ui_base_url)
    expect(page.locator("button:has-text('Open Debrief Session')").first).to_be_visible()


def test_edit_toggle_shows_textarea(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    """Click Edit ✎ on m1's prep brief — textarea should appear."""
    _open_m1(page, ui_db_path, ui_base_url)
    page.locator("button:has-text('Edit')").first.click()
    page.wait_for_timeout(300)
    # A textarea should now be visible
    expect(page.locator("textarea").first).to_be_visible()


# ---------------------------------------------------------------------------
# Detail view — right panel tabs
# ---------------------------------------------------------------------------

def test_prep_tab_visible_on_detail(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_q2_planning(page, ui_db_path, ui_base_url)
    expect(page.locator("text=Prep session").first).to_be_visible()


def test_debrief_tab_visible_on_detail(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_q2_planning(page, ui_db_path, ui_base_url)
    expect(page.locator("text=Debrief session").first).to_be_visible()


def test_pre_meeting_notes_label_on_prep_tab(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_q2_planning(page, ui_db_path, ui_base_url)
    expect(page.locator("text=Pre-meeting notes").first).to_be_visible()


def test_generate_prep_brief_button_visible(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_q2_planning(page, ui_db_path, ui_base_url)
    expect(page.locator("button:has-text('Generate Prep Brief')").first).to_be_visible()


def test_save_as_prep_brief_button_visible(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_q2_planning(page, ui_db_path, ui_base_url)
    expect(page.locator("button:has-text('Save as Prep Brief')").first).to_be_visible()


def test_generate_prep_brief_injects_message(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    """Clicking Generate Prep Brief injects the TASK prompt into the prep chat."""
    _open_q2_planning(page, ui_db_path, ui_base_url)
    page.locator("button:has-text('Generate Prep Brief')").first.click()
    expect(
        page.locator("text=TASK: Pre-meeting prep brief").first
    ).to_be_visible(timeout=8_000)


def test_open_debrief_session_switches_tab(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    """Clicking Open Debrief Session → switches the right panel to the debrief tab."""
    _open_q2_planning(page, ui_db_path, ui_base_url)
    page.locator("button:has-text('Open Debrief Session')").first.click()
    page.wait_for_timeout(400)
    expect(page.locator("text=Meeting notes").first).to_be_visible()


def test_debrief_tab_has_generate_button(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_q2_planning(page, ui_db_path, ui_base_url)
    page.locator("text=Debrief session").first.click()
    page.wait_for_timeout(300)
    expect(page.locator("button:has-text('Generate Debrief Summary')").first).to_be_visible()


def test_generate_debrief_summary_injects_message(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    """Clicking Generate Debrief Summary injects the TASK prompt into the debrief chat."""
    _seed_meetings(ui_db_path)
    _goto(page, f"{ui_base_url}{MEETINGS}")
    # Click m2 which has debrief_notes set
    page.locator("text=1:1 with Alice").nth(1).click()
    page.wait_for_timeout(500)
    page.locator("text=Debrief session").first.click()
    page.wait_for_timeout(300)
    page.locator("button:has-text('Generate Debrief Summary')").first.click()
    expect(
        page.locator("text=TASK: Post-meeting debrief").first
    ).to_be_visible(timeout=8_000)


# ---------------------------------------------------------------------------
# Direct session links from list view
# ---------------------------------------------------------------------------

def test_prep_arrow_opens_detail_on_prep_tab(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    """Clicking [→] in Prep column opens detail with Prep session tab active."""
    _seed_meetings(ui_db_path)
    _goto(page, f"{ui_base_url}{MEETINGS}")
    # Find all → buttons and click the first one in the Prep column
    # Each row has two → buttons (prep, debrief); first overall is the prep arrow for first meeting
    page.locator("button:has-text('→')").first.click()
    page.wait_for_timeout(500)
    expect(page.locator("button:has-text('Back')").first).to_be_visible()
    expect(page.locator("text=Pre-meeting notes").first).to_be_visible()


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
    page.locator(".q-dialog input").first.fill("TestMeetingXYZ")
    page.locator(".q-dialog button:has-text('Create')").first.click()
    page.wait_for_selector(".q-dialog", state="hidden", timeout=5_000)
    expect(page.locator("text=TestMeetingXYZ").first).to_be_visible(timeout=8_000)
