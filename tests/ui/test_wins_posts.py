"""Playwright integration tests for the Wins & Posts section (§4.4 / §6.7).

List view: two tables (wins top, posts bottom). No chat panel in list view.
Detail view (per win): two-column edit form + contextual chat.
"""

import sqlite3
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.ui

WINS_POSTS = "/wins-posts"


def _goto(page: Page, url: str) -> None:
    page.goto(url, wait_until="networkidle")


# ---------------------------------------------------------------------------
# DB seeding helpers
# ---------------------------------------------------------------------------

def _seed_data(db_path: Path) -> dict:
    conn = sqlite3.connect(str(db_path))
    try:
        existing_wins = conn.execute("SELECT title FROM wins").fetchall()
        existing_win_titles = {r[0] for r in existing_wins}

        win1_id = win2_id = None
        if "Shipped X" not in existing_win_titles:
            cur = conn.execute(
                "INSERT INTO wins (title, description, created_at) VALUES (?, ?, ?)",
                ("Shipped X", "Delivered key reliability improvement for Q2.", "2026-05-01T10:00:00"),
            )
            win1_id = cur.lastrowid
        else:
            win1_id = conn.execute("SELECT id FROM wins WHERE title='Shipped X'").fetchone()[0]

        if "Led Y" not in existing_win_titles:
            cur = conn.execute(
                "INSERT INTO wins (title, description, created_at) VALUES (?, ?, ?)",
                ("Led Y", None, "2026-04-20T10:00:00"),
            )
            win2_id = cur.lastrowid
        else:
            win2_id = conn.execute("SELECT id FROM wins WHERE title='Led Y'").fetchone()[0]

        existing_posts = conn.execute("SELECT channel FROM posts").fetchall()
        existing_channels = {r[0] for r in existing_posts}

        post1_id = post2_id = None
        if "slack-eng" not in existing_channels:
            cur = conn.execute(
                "INSERT INTO posts (content, channel, audience, posted_at, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    "We shipped the Q2 reliability push.\n\nThis reduced error rates by 40%.",
                    "slack-eng",
                    "eng team",
                    "2026-05-01",
                    "2026-05-01T10:00:00",
                ),
            )
            post1_id = cur.lastrowid
        else:
            post1_id = conn.execute("SELECT id FROM posts WHERE channel='slack-eng'").fetchone()[0]

        if "email-skip" not in existing_channels:
            cur = conn.execute(
                "INSERT INTO posts (content, channel, audience, posted_at, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    "Following up on the auth migration progress.",
                    "email-skip",
                    None,
                    "2026-04-25",
                    "2026-04-25T10:00:00",
                ),
            )
            post2_id = cur.lastrowid
        else:
            post2_id = conn.execute("SELECT id FROM posts WHERE channel='email-skip'").fetchone()[0]

        conn.commit()
    finally:
        conn.close()

    return {
        "win1_id": win1_id,
        "win2_id": win2_id,
        "post1_id": post1_id,
        "post2_id": post2_id,
    }


def _seed_linked_post(db_path: Path, win_id: int) -> int:
    """Seed a post with win_id set (for badge / linkage tests)."""
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute(
            "INSERT INTO posts (content, channel, audience, posted_at, created_at, win_id)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                "Post linked to a specific win.",
                "slack-linked",
                None,
                "2026-05-10",
                "2026-05-10T10:00:00",
                win_id,
            ),
        )
        post_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return post_id


# ---------------------------------------------------------------------------
# Page load and structure — list view
# ---------------------------------------------------------------------------

def test_page_loads(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("text=Wins").first).to_be_visible()


def test_wins_heading_visible(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("text=Wins").first).to_be_visible()


def test_posts_heading_visible(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("text=Posts").first).to_be_visible()


def test_add_win_button_visible(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("button:has-text('+ Add Win')").first).to_be_visible()


def test_new_post_button_visible(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("button:has-text('+ New Post')").first).to_be_visible()


# ---------------------------------------------------------------------------
# Empty states
# ---------------------------------------------------------------------------

def test_wins_empty_state(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("text=No wins yet.").first).to_be_visible()


def test_posts_empty_state(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("text=No posts yet.").first).to_be_visible()


# ---------------------------------------------------------------------------
# Wins table with seeded data
# ---------------------------------------------------------------------------

def test_wins_table_shows_title(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("text=Shipped X").first).to_be_visible()


def test_wins_table_shows_second_win(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("text=Led Y").first).to_be_visible()


def test_wins_table_shows_description(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("text=Delivered key reliability").first).to_be_visible()


def test_wins_table_shows_date(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("text=2026-05-01").first).to_be_visible()


def test_wins_table_has_new_post_buttons(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("button:has-text('↗ New Post')").first).to_be_visible()


# ---------------------------------------------------------------------------
# Win posted indicator (✓ badge)
# ---------------------------------------------------------------------------

def test_win_posted_indicator_when_linked(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    ids = _seed_data(ui_db_path)
    _seed_linked_post(ui_db_path, ids["win1_id"])
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("text=✓").first).to_be_visible()


# ---------------------------------------------------------------------------
# Posts table with seeded data
# ---------------------------------------------------------------------------

def test_posts_table_shows_channel(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("text=slack-eng").first).to_be_visible()


def test_posts_table_shows_second_channel(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("text=email-skip").first).to_be_visible()


def test_posts_table_shows_audience(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("text=eng team").first).to_be_visible()


def test_posts_table_linked_win_column(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    ids = _seed_data(ui_db_path)
    _seed_linked_post(ui_db_path, ids["win1_id"])
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    # "Shipped X" should appear in the Win column for the linked post
    expect(page.locator("text=Shipped X").first).to_be_visible()


# ---------------------------------------------------------------------------
# Add Win dialog
# ---------------------------------------------------------------------------

def test_add_win_dialog_opens(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("button:has-text('+ Add Win')").first.click()
    page.wait_for_timeout(300)
    expect(page.locator(".q-dialog").first).to_be_visible()
    expect(page.locator("text=Add Win").first).to_be_visible()


def test_add_win_dialog_cancel(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("button:has-text('+ Add Win')").first.click()
    page.wait_for_timeout(300)
    page.locator("button:has-text('Cancel')").first.click()
    page.wait_for_timeout(300)
    expect(page.locator(".q-dialog")).to_have_count(0)


def test_add_win_title_required(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("button:has-text('+ Add Win')").first.click()
    page.wait_for_timeout(300)
    page.locator(".q-dialog button:has-text('Add')").first.click()
    page.wait_for_timeout(300)
    expect(page.locator(".q-dialog").first).to_be_visible()


def test_add_win_creates_and_appears(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("button:has-text('+ Add Win')").first.click()
    page.wait_for_timeout(300)

    page.locator(".q-dialog input").first.fill("UniqueWinABC")
    page.locator(".q-dialog button:has-text('Add')").first.click()
    page.wait_for_timeout(500)

    expect(page.locator(".q-dialog")).to_have_count(0)
    expect(page.locator("text=UniqueWinABC").first).to_be_visible()

    conn = sqlite3.connect(str(ui_db_path))
    count = conn.execute("SELECT count(*) FROM wins WHERE title='UniqueWinABC'").fetchone()[0]
    conn.close()
    assert count == 1


# ---------------------------------------------------------------------------
# Save Post dialog (from list view)
# ---------------------------------------------------------------------------

def test_new_post_dialog_opens(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("button:has-text('+ New Post')").first.click()
    page.wait_for_timeout(300)
    expect(page.locator(".q-dialog").first).to_be_visible()
    expect(page.locator("text=Save Post").first).to_be_visible()


def test_new_post_dialog_cancel(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("button:has-text('+ New Post')").first.click()
    page.wait_for_timeout(300)
    page.locator(".q-dialog button:has-text('Cancel')").first.click()
    page.wait_for_timeout(300)
    expect(page.locator(".q-dialog")).to_have_count(0)


def test_new_post_content_required(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("button:has-text('+ New Post')").first.click()
    page.wait_for_timeout(300)
    page.locator(".q-dialog textarea").first.fill("")
    page.locator(".q-dialog input").first.fill("slack-test")
    page.locator(".q-dialog button:has-text('Save')").first.click()
    page.wait_for_timeout(300)
    expect(page.locator(".q-dialog").first).to_be_visible()


def test_new_post_channel_required(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("button:has-text('+ New Post')").first.click()
    page.wait_for_timeout(300)
    page.locator(".q-dialog textarea").first.fill("Some content here")
    page.locator(".q-dialog button:has-text('Save')").first.click()
    page.wait_for_timeout(300)
    expect(page.locator(".q-dialog").first).to_be_visible()


def test_new_post_creates_and_appears(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("button:has-text('+ New Post')").first.click()
    page.wait_for_timeout(300)

    page.locator(".q-dialog textarea").first.fill("Standalone post content XYZ")
    page.locator(".q-dialog input").first.fill("slack-standalone")
    page.locator(".q-dialog button:has-text('Save')").first.click()
    page.wait_for_timeout(600)

    expect(page.locator(".q-dialog")).to_have_count(0)
    expect(page.locator("text=slack-standalone").first).to_be_visible()

    conn = sqlite3.connect(str(ui_db_path))
    row = conn.execute(
        "SELECT win_id FROM posts WHERE channel='slack-standalone'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] is None  # no win link


def test_win_row_new_post_button_opens_dialog(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("button:has-text('↗ New Post')").first.click()
    page.wait_for_timeout(300)
    expect(page.locator(".q-dialog").first).to_be_visible()
    expect(page.locator("text=Save Post").first).to_be_visible()


def test_win_row_new_post_records_win_id(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    ids = _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")

    # Target the Shipped X row specifically — earlier tests may have added wins
    # with later timestamps that sort ahead of it.
    page.locator("tr").filter(has_text="Shipped X").locator(
        "button:has-text('↗ New Post')"
    ).first.click()
    page.wait_for_timeout(300)

    page.locator(".q-dialog textarea").first.fill("Win-linked content ZZTEST")
    page.locator(".q-dialog input").first.fill("slack-winlink")
    page.locator(".q-dialog button:has-text('Save')").first.click()
    page.wait_for_timeout(600)

    expect(page.locator(".q-dialog")).to_have_count(0)

    conn = sqlite3.connect(str(ui_db_path))
    row = conn.execute(
        "SELECT win_id FROM posts WHERE channel='slack-winlink'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == ids["win1_id"]


# ---------------------------------------------------------------------------
# Post expand / edit dialog (from posts table row click)
# ---------------------------------------------------------------------------

def test_post_row_click_opens_expand(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    # Click the slack-eng row in posts table
    page.locator("td").filter(has_text="slack-eng").first.click()
    page.wait_for_timeout(300)
    expect(page.locator(".q-dialog").first).to_be_visible()


def test_post_expand_shows_full_content(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("td").filter(has_text="slack-eng").first.click()
    page.wait_for_timeout(300)
    expect(page.locator("text=This reduced error rates by 40%").first).to_be_visible()


def test_post_expand_closes(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("td").filter(has_text="slack-eng").first.click()
    page.wait_for_timeout(300)
    page.locator(".q-dialog button:has-text('Close')").first.click()
    page.wait_for_timeout(300)
    expect(page.locator(".q-dialog")).to_have_count(0)


def test_post_expand_has_edit_button(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("td").filter(has_text="slack-eng").first.click()
    page.wait_for_timeout(300)
    expect(page.locator(".q-dialog button:has-text('Edit')").first).to_be_visible()


def test_post_edit_shows_textarea(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("td").filter(has_text="slack-eng").first.click()
    page.wait_for_timeout(300)
    page.locator(".q-dialog button:has-text('Edit')").first.click()
    page.wait_for_timeout(300)
    expect(page.locator(".q-dialog textarea").first).to_be_visible()


def test_post_edit_saves_changes(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("td").filter(has_text="slack-eng").first.click()
    page.wait_for_timeout(300)
    page.locator(".q-dialog button:has-text('Edit')").first.click()
    page.wait_for_timeout(300)

    page.locator(".q-dialog textarea").first.fill("Updated content EDITEDXYZ")
    page.locator(".q-dialog input").first.fill("slack-edited")
    page.locator(".q-dialog button:has-text('Save')").first.click()
    page.wait_for_timeout(600)

    expect(page.locator(".q-dialog")).to_have_count(0)

    conn = sqlite3.connect(str(ui_db_path))
    row = conn.execute(
        "SELECT content FROM posts WHERE channel='slack-edited'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert "EDITEDXYZ" in row[0]


def test_post_edit_cancel_returns_to_view(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("td").filter(has_text="slack-eng").first.click()
    page.wait_for_timeout(300)
    page.locator(".q-dialog button:has-text('Edit')").first.click()
    page.wait_for_timeout(300)
    page.locator(".q-dialog button:has-text('Cancel')").first.click()
    page.wait_for_timeout(300)
    expect(page.locator(".q-dialog button:has-text('Edit')").first).to_be_visible()


# ---------------------------------------------------------------------------
# Win detail view — navigation
# ---------------------------------------------------------------------------

def test_win_row_click_opens_detail(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("td").filter(has_text="Shipped X").first.click()
    page.wait_for_timeout(400)
    expect(page.locator("text=Win Details").first).to_be_visible()


def test_detail_back_button_returns_to_list(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("td").filter(has_text="Shipped X").first.click()
    page.wait_for_timeout(400)
    page.locator("button:has-text('← Back')").first.click()
    page.wait_for_timeout(400)
    # Back in list view — wins table visible
    expect(page.locator("button:has-text('+ Add Win')").first).to_be_visible()


def test_detail_shows_win_title(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("td").filter(has_text="Shipped X").first.click()
    page.wait_for_timeout(400)
    # Title input pre-populated
    title_input = page.locator("input[aria-label='Title']").first
    expect(title_input).to_have_value("Shipped X")


def test_detail_shows_win_description(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("td").filter(has_text="Shipped X").first.click()
    page.wait_for_timeout(400)
    # Description is in a textarea — must use to_have_value, not text= locator
    expect(page.locator("textarea").first).to_have_value(
        "Delivered key reliability improvement for Q2."
    )


def test_detail_shows_created_date(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("td").filter(has_text="Shipped X").first.click()
    page.wait_for_timeout(400)
    expect(page.locator("text=Created: 2026-05-01").first).to_be_visible()


def test_detail_shows_chat_label(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("td").filter(has_text="Shipped X").first.click()
    page.wait_for_timeout(400)
    expect(page.locator("text=Chat: Shipped X").first).to_be_visible()


def test_detail_has_adopt_ai_draft_button(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("td").filter(has_text="Shipped X").first.click()
    page.wait_for_timeout(400)
    expect(page.locator("button:has-text('Adopt AI draft')").first).to_be_visible()


def test_detail_has_save_win_button(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("td").filter(has_text="Shipped X").first.click()
    page.wait_for_timeout(400)
    expect(page.locator("button:has-text('Save Win')").first).to_be_visible()


def test_detail_has_new_post_for_win_button(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("td").filter(has_text="Shipped X").first.click()
    page.wait_for_timeout(400)
    expect(page.locator("button:has-text('+ New Post for Win')").first).to_be_visible()


# ---------------------------------------------------------------------------
# Win detail view — editing
# ---------------------------------------------------------------------------

def test_detail_save_win_updates_db(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    ids = _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("td").filter(has_text="Shipped X").first.click()
    page.wait_for_timeout(400)

    # Update description
    ta = page.locator("textarea").first
    ta.fill("New description UPDATEDABC")
    page.locator("button:has-text('Save Win')").first.click()
    page.wait_for_timeout(400)

    conn = sqlite3.connect(str(ui_db_path))
    row = conn.execute(
        "SELECT description FROM wins WHERE id=?", (ids["win1_id"],)
    ).fetchone()
    conn.close()
    assert row is not None
    assert "UPDATEDABC" in row[0]


def test_detail_linked_posts_shown(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    ids = _seed_data(ui_db_path)
    _seed_linked_post(ui_db_path, ids["win1_id"])
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("td").filter(has_text="Shipped X").first.click()
    page.wait_for_timeout(400)
    # Linked post (slack-linked) should appear in the left panel
    expect(page.locator("text=slack-linked").first).to_be_visible()


def test_detail_new_post_for_win_dialog_opens(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("td").filter(has_text="Shipped X").first.click()
    page.wait_for_timeout(400)
    page.locator("button:has-text('+ New Post for Win')").first.click()
    page.wait_for_timeout(300)
    expect(page.locator(".q-dialog").first).to_be_visible()
    expect(page.locator("text=Save Post").first).to_be_visible()


def test_detail_new_post_for_win_records_win_id(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    ids = _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("td").filter(has_text="Shipped X").first.click()
    page.wait_for_timeout(400)
    page.locator("button:has-text('+ New Post for Win')").first.click()
    page.wait_for_timeout(300)

    page.locator(".q-dialog textarea").first.fill("Linked post from detail AAABBB")
    page.locator(".q-dialog input").first.fill("slack-detail-linked")
    page.locator(".q-dialog button:has-text('Save')").first.click()
    page.wait_for_timeout(600)

    expect(page.locator(".q-dialog")).to_have_count(0)

    conn = sqlite3.connect(str(ui_db_path))
    row = conn.execute(
        "SELECT win_id FROM posts WHERE channel='slack-detail-linked'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == ids["win1_id"]
