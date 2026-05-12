"""Playwright integration tests for the Stakeholders section (§6.7).

List view: full-width table grouped by tier. Detail view: left panel with
Profile + Notes + Delete; right panel with persistent chat.

AI calls are expected to fail (fake API key in conftest) — tests assert on
UI structure and DB mutations, not on AI replies.
"""

import sqlite3
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.ui

STAKEHOLDERS = "/stakeholders"


def _goto(page: Page, url: str) -> None:
    page.goto(url, wait_until="networkidle")


# ---------------------------------------------------------------------------
# DB seeding helper — idempotent
# ---------------------------------------------------------------------------

def _seed_stakeholders(db_path: Path) -> dict:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        def _get_or_insert(name, role, rel, comm, reward, notes):
            row = conn.execute(
                "SELECT id FROM stakeholders WHERE name=?", (name,)
            ).fetchone()
            if row:
                return row[0]
            conn.execute(
                "INSERT INTO stakeholders"
                " (name, role, relationship, communication_style, what_they_reward, notes, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (name, role, rel, comm, reward, notes,
                 "2026-05-01T10:00:00", "2026-05-01T10:00:00"),
            )
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        alice_id = _get_or_insert(
            "Alice", "VP Engineering", "manager",
            "Direct and data-driven", "Outcomes and visibility",
            "[2026-05-01] Seemed stressed about Q3 goals",
        )
        bob_id = _get_or_insert(
            "Bob", "CTO", "skip",
            "Big picture", "Long-term strategy",
            None,
        )
        carol_id = _get_or_insert(
            "Carol", "Staff Engineer", "peer",
            "Collaborative", "Technical excellence",
            None,
        )
        conn.commit()
    finally:
        conn.close()

    return {"alice_id": alice_id, "bob_id": bob_id, "carol_id": carol_id}


def _open_alice(page: Page, ui_db_path: Path, ui_base_url: str) -> None:
    _seed_stakeholders(ui_db_path)
    _goto(page, f"{ui_base_url}{STAKEHOLDERS}")
    page.locator("text=Alice").first.click()
    page.wait_for_timeout(500)


# ---------------------------------------------------------------------------
# Basic page load
# ---------------------------------------------------------------------------

def test_stakeholders_page_loads(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{STAKEHOLDERS}")
    expect(page.locator("text=Stakeholders").first).to_be_visible()


def test_new_stakeholder_button_visible(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{STAKEHOLDERS}")
    expect(page.locator("text=+ New Stakeholder").first).to_be_visible()


# ---------------------------------------------------------------------------
# List view — empty state
# ---------------------------------------------------------------------------

def test_stakeholder_list_empty_state(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{STAKEHOLDERS}")
    expect(page.locator("text=No stakeholders yet.").first).to_be_visible()


# ---------------------------------------------------------------------------
# List view — with data
# ---------------------------------------------------------------------------

def test_list_shows_manager_tier_header(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_stakeholders(ui_db_path)
    _goto(page, f"{ui_base_url}{STAKEHOLDERS}")
    expect(page.locator("text=MANAGER").first).to_be_visible()


def test_list_shows_skip_tier_header(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_stakeholders(ui_db_path)
    _goto(page, f"{ui_base_url}{STAKEHOLDERS}")
    expect(page.locator("text=SKIP").first).to_be_visible()


def test_list_shows_peer_tier_header(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_stakeholders(ui_db_path)
    _goto(page, f"{ui_base_url}{STAKEHOLDERS}")
    expect(page.locator("text=PEER").first).to_be_visible()


def test_list_shows_stakeholder_row(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_stakeholders(ui_db_path)
    _goto(page, f"{ui_base_url}{STAKEHOLDERS}")
    expect(page.locator("text=Alice").first).to_be_visible()


def test_list_shows_role_in_row(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_stakeholders(ui_db_path)
    _goto(page, f"{ui_base_url}{STAKEHOLDERS}")
    expect(page.locator("text=VP Engineering").first).to_be_visible()


def test_list_shows_last_note_date(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    """Alice has a note dated 2026-05-01 — that date should appear in the list."""
    _seed_stakeholders(ui_db_path)
    _goto(page, f"{ui_base_url}{STAKEHOLDERS}")
    expect(page.locator("text=2026-05-01").first).to_be_visible()


def test_list_shows_dash_for_no_notes(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    """Bob and Carol have no notes — at least one — should be visible."""
    _seed_stakeholders(ui_db_path)
    _goto(page, f"{ui_base_url}{STAKEHOLDERS}")
    expect(page.locator("text=—").first).to_be_visible()


# ---------------------------------------------------------------------------
# Detail view — navigation
# ---------------------------------------------------------------------------

def test_click_stakeholder_opens_detail(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_alice(page, ui_db_path, ui_base_url)
    expect(page.locator("button:has-text('Back')").first).to_be_visible()


def test_detail_has_profile_section(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_alice(page, ui_db_path, ui_base_url)
    expect(page.locator("text=Profile").first).to_be_visible()


def test_detail_has_notes_section(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_alice(page, ui_db_path, ui_base_url)
    expect(page.locator("text=Notes").first).to_be_visible()


def test_detail_has_delete_button(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_alice(page, ui_db_path, ui_base_url)
    expect(page.locator("button:has-text('Delete')").first).to_be_visible()


def test_detail_shows_stakeholder_name(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_alice(page, ui_db_path, ui_base_url)
    # Name appears as a bold label (read-only)
    expect(page.locator("text=Alice").first).to_be_visible()


def test_detail_role_field_prepopulated(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_alice(page, ui_db_path, ui_base_url)
    role_input = page.locator(
        ".q-field:has(.q-field__label:has-text('Role')) input"
    ).first
    expect(role_input).to_have_value("VP Engineering")


def test_detail_shows_note_date(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    """Alice's note date 2026-05-01 should appear in the notes log."""
    _open_alice(page, ui_db_path, ui_base_url)
    expect(page.locator("text=2026-05-01").first).to_be_visible()


def test_detail_shows_note_text(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_alice(page, ui_db_path, ui_base_url)
    expect(page.locator("text=Seemed stressed about Q3 goals").first).to_be_visible()


def test_detail_shows_no_notes_placeholder(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    """Bob has no notes — 'No notes yet.' placeholder should appear."""
    _seed_stakeholders(ui_db_path)
    _goto(page, f"{ui_base_url}{STAKEHOLDERS}")
    page.locator("text=Bob").first.click()
    page.wait_for_timeout(500)
    expect(page.locator("text=No notes yet.").first).to_be_visible()


def test_back_button_returns_to_list(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_alice(page, ui_db_path, ui_base_url)
    page.locator("button:has-text('Back')").first.click()
    page.wait_for_timeout(500)
    expect(page.locator("text=MANAGER").first).to_be_visible()
    expect(page.locator("button:has-text('Back')")).to_have_count(0)


# ---------------------------------------------------------------------------
# Detail view — save profile
# ---------------------------------------------------------------------------

def test_save_profile_updates_db(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_alice(page, ui_db_path, ui_base_url)
    role_input = page.locator(
        ".q-field:has(.q-field__label:has-text('Role')) input"
    ).first
    role_input.fill("SVP Engineering")
    page.locator("button:has-text('Save ↑')").first.click()
    page.wait_for_timeout(500)

    conn = sqlite3.connect(str(ui_db_path))
    row = conn.execute(
        "SELECT role FROM stakeholders WHERE name='Alice'"
    ).fetchone()
    conn.close()
    assert row is not None and row[0] == "SVP Engineering", f"Role not updated: {row}"


# ---------------------------------------------------------------------------
# Detail view — add note
# ---------------------------------------------------------------------------

def test_add_note_button_visible(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_alice(page, ui_db_path, ui_base_url)
    expect(page.locator("button:has-text('+ Add')").first).to_be_visible()


def test_add_note_saves_to_db(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_alice(page, ui_db_path, ui_base_url)
    page.locator("button:has-text('+ Add')").first.click()
    page.wait_for_timeout(300)
    page.locator("input[placeholder='New observation...']").first.fill("Test note for playwright")
    page.get_by_role("button", name="Save", exact=True).first.click()
    page.wait_for_timeout(500)

    conn = sqlite3.connect(str(ui_db_path))
    row = conn.execute(
        "SELECT notes FROM stakeholders WHERE name='Alice'"
    ).fetchone()
    conn.close()
    assert row is not None and "Test note for playwright" in (row[0] or ""), \
        f"Note not found in DB: {row}"


def test_add_note_appears_in_notes_log(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_alice(page, ui_db_path, ui_base_url)
    page.locator("button:has-text('+ Add')").first.click()
    page.wait_for_timeout(300)
    page.locator("input[placeholder='New observation...']").first.fill("Visible note content XYZ")
    page.get_by_role("button", name="Save", exact=True).first.click()
    page.wait_for_timeout(500)
    expect(page.locator("text=Visible note content XYZ").first).to_be_visible()


# ---------------------------------------------------------------------------
# Detail view — chat panel
# ---------------------------------------------------------------------------

def test_chat_panel_visible_in_detail(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    """Chat panel header should appear when stakeholder detail is open."""
    _open_alice(page, ui_db_path, ui_base_url)
    expect(page.locator("text=Chat: Alice").first).to_be_visible()


# ---------------------------------------------------------------------------
# New stakeholder dialog
# ---------------------------------------------------------------------------

def test_new_stakeholder_dialog_opens(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{STAKEHOLDERS}")
    page.locator("text=+ New Stakeholder").first.click()
    page.wait_for_selector(".q-dialog", state="visible", timeout=5_000)
    dialog = page.locator(".q-dialog")
    expect(dialog.locator("text=New Stakeholder").first).to_be_visible()


def test_new_stakeholder_dialog_cancel(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{STAKEHOLDERS}")
    page.locator("text=+ New Stakeholder").first.click()
    page.wait_for_selector(".q-dialog", state="visible", timeout=5_000)
    page.locator(".q-dialog button:has-text('Cancel')").first.click()
    page.wait_for_timeout(400)
    expect(page.locator(".q-dialog")).to_have_count(0)


def test_new_stakeholder_name_required(page: Page, ui_base_url: str) -> None:
    """Clicking Create with empty name should show a warning notification."""
    _goto(page, f"{ui_base_url}{STAKEHOLDERS}")
    page.locator("text=+ New Stakeholder").first.click()
    page.wait_for_selector(".q-dialog", state="visible", timeout=5_000)
    page.locator(".q-dialog button:has-text('Create')").first.click()
    page.wait_for_timeout(400)
    # Dialog should still be open (not dismissed on validation failure)
    expect(page.locator(".q-dialog")).not_to_have_count(0)


def test_new_stakeholder_creates_and_appears(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _goto(page, f"{ui_base_url}{STAKEHOLDERS}")
    page.locator("text=+ New Stakeholder").first.click()
    page.wait_for_selector(".q-dialog", state="visible", timeout=5_000)
    page.locator(".q-dialog input").first.fill("TestStakeholderXYZ")
    page.locator(".q-dialog button:has-text('Create')").first.click()
    page.wait_for_selector(".q-dialog", state="hidden", timeout=5_000)
    expect(page.locator("text=TestStakeholderXYZ").first).to_be_visible(timeout=8_000)


def test_new_stakeholder_appears_alongside_existing(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_stakeholders(ui_db_path)
    _goto(page, f"{ui_base_url}{STAKEHOLDERS}")
    page.locator("text=+ New Stakeholder").first.click()
    page.wait_for_selector(".q-dialog", state="visible", timeout=5_000)
    page.locator(".q-dialog input").first.fill("RefreshRegressionStakeholder")
    page.locator(".q-dialog button:has-text('Create')").first.click()
    page.wait_for_selector(".q-dialog", state="hidden", timeout=5_000)
    expect(page.locator("text=RefreshRegressionStakeholder").first).to_be_visible(timeout=8_000)
    # Existing stakeholders still present
    expect(page.locator("text=Alice").first).to_be_visible()


# ---------------------------------------------------------------------------
# Delete stakeholder
# ---------------------------------------------------------------------------

def test_delete_shows_confirmation_dialog(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_alice(page, ui_db_path, ui_base_url)
    page.locator("button:has-text('Delete')").first.click()
    page.wait_for_selector(".q-dialog", state="visible", timeout=5_000)
    expect(page.locator(".q-dialog").locator("text=Delete").first).to_be_visible()


def test_delete_cancel_keeps_stakeholder(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_alice(page, ui_db_path, ui_base_url)
    page.locator("button:has-text('Delete')").first.click()
    page.wait_for_selector(".q-dialog", state="visible", timeout=5_000)
    page.locator(".q-dialog button:has-text('Cancel')").first.click()
    page.wait_for_timeout(400)
    # Still in detail view (Back button still present)
    expect(page.locator("button:has-text('Back')").first).to_be_visible()


def test_delete_confirm_removes_stakeholder(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_alice(page, ui_db_path, ui_base_url)
    page.locator("button:has-text('Delete')").first.click()
    page.wait_for_selector(".q-dialog", state="visible", timeout=5_000)
    page.locator(".q-dialog button:has-text('Delete')").first.click()
    page.wait_for_timeout(800)
    # Returned to list view; Alice is gone
    expect(page.locator("text=Alice")).to_have_count(0)
    # Other stakeholders still present
    expect(page.locator("text=Bob").first).to_be_visible()
