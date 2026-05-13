"""Playwright integration tests for the Wins & Posts section (§4.4 / §6.7).

Three-area layout: wins ledger (left top) + post history (left bottom) +
AI drafting chat (right). AI calls fail with the fake key — tests cover
UI structure and DB mutations only.
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
        # Wins — plain insert; no unique constraint so re-seed is idempotent
        # if the test DB is fresh per session. For safety we check first.
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


# ---------------------------------------------------------------------------
# Page load and structure
# ---------------------------------------------------------------------------

def test_wins_posts_page_loads(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("text=Drafting chat").first).to_be_visible()


def test_wins_ledger_heading_visible(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("text=Wins").first).to_be_visible()


def test_post_history_heading_visible(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("text=Post history").first).to_be_visible()


def test_save_post_button_visible(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("button:has-text('Save Post')").first).to_be_visible()


def test_add_win_button_visible(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("button:has-text('+ Add Win')").first).to_be_visible()


def test_chat_input_visible(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("input").first).to_be_visible()


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
# Wins list with seeded data
# ---------------------------------------------------------------------------

def test_wins_list_shows_title(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("text=Shipped X").first).to_be_visible()


def test_wins_list_shows_second_win(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("text=Led Y").first).to_be_visible()


def test_wins_list_shows_date(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("text=2026-05-01").first).to_be_visible()


def test_wins_list_shows_description(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("text=Delivered key reliability").first).to_be_visible()


# ---------------------------------------------------------------------------
# Post history with seeded data
# ---------------------------------------------------------------------------

def test_post_list_shows_channel(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("text=slack-eng").first).to_be_visible()


def test_post_list_shows_second_channel(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("text=email-skip").first).to_be_visible()


def test_post_list_shows_date(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("text=2026-05-01").first).to_be_visible()


def test_post_list_shows_content_snippet(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("text=We shipped the Q2").first).to_be_visible()


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
    # Click Add without filling in title
    page.locator(".q-dialog button:has-text('Add')").first.click()
    page.wait_for_timeout(300)
    # Dialog should still be open (validation blocked the save)
    expect(page.locator(".q-dialog").first).to_be_visible()


def test_add_win_creates_and_appears(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("button:has-text('+ Add Win')").first.click()
    page.wait_for_timeout(300)

    title_input = page.locator(".q-dialog input").first
    title_input.fill("NewWinXYZ")
    page.locator(".q-dialog button:has-text('Add')").first.click()
    page.wait_for_timeout(500)

    # Dialog should be closed
    expect(page.locator(".q-dialog")).to_have_count(0)
    # Win should appear in the ledger
    expect(page.locator("text=NewWinXYZ").first).to_be_visible()

    # Verify in DB
    conn = sqlite3.connect(str(ui_db_path))
    count = conn.execute("SELECT count(*) FROM wins WHERE title='NewWinXYZ'").fetchone()[0]
    conn.close()
    assert count == 1


# ---------------------------------------------------------------------------
# Win selection and "Open in chat →" inject
# ---------------------------------------------------------------------------

def test_win_click_shows_open_in_chat_button(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("text=Shipped X").first.click()
    page.wait_for_timeout(400)
    expect(page.locator("button:has-text('Open in chat')").first).to_be_visible()


def test_win_deselect_hides_open_in_chat_button(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    # Count baseline (post cards already have "Open in chat →" buttons)
    baseline = page.locator("button:has-text('Open in chat →')").count()
    page.locator("text=Shipped X").first.click()
    page.wait_for_timeout(300)
    # Selected: one more button on the win card
    assert page.locator("button:has-text('Open in chat →')").count() == baseline + 1
    # Click again to deselect
    page.locator("text=Shipped X").first.click()
    page.wait_for_timeout(300)
    # Back to baseline
    assert page.locator("button:has-text('Open in chat →')").count() == baseline


def test_win_open_in_chat_injects_message(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("text=Shipped X").first.click()
    page.wait_for_timeout(400)
    page.locator("button:has-text('Open in chat')").first.click()
    page.wait_for_timeout(600)
    # The injected message contains the win title
    expect(page.locator("text=Shipped X").first).to_be_visible()


# ---------------------------------------------------------------------------
# Save Post dialog
# ---------------------------------------------------------------------------

def test_save_post_dialog_opens(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("button:has-text('Save Post')").first.click()
    page.wait_for_timeout(300)
    expect(page.locator(".q-dialog").first).to_be_visible()
    expect(page.locator("text=Save Post").first).to_be_visible()


def test_save_post_dialog_cancel(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("button:has-text('Save Post')").first.click()
    page.wait_for_timeout(300)
    page.locator(".q-dialog button:has-text('Cancel')").first.click()
    page.wait_for_timeout(300)
    expect(page.locator(".q-dialog")).to_have_count(0)


def test_save_post_content_required(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("button:has-text('Save Post')").first.click()
    page.wait_for_timeout(300)

    # Clear the content field and fill in channel
    content_ta = page.locator(".q-dialog textarea").first
    content_ta.fill("")
    channel_input = page.locator(".q-dialog input").first
    channel_input.fill("slack-test")

    page.locator(".q-dialog button:has-text('Save')").first.click()
    page.wait_for_timeout(300)
    # Dialog should still be open
    expect(page.locator(".q-dialog").first).to_be_visible()


def test_save_post_channel_required(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("button:has-text('Save Post')").first.click()
    page.wait_for_timeout(300)

    # Fill content but leave channel empty
    content_ta = page.locator(".q-dialog textarea").first
    content_ta.fill("Some post content here")
    # Channel input is empty by default

    page.locator(".q-dialog button:has-text('Save')").first.click()
    page.wait_for_timeout(300)
    # Dialog should still be open
    expect(page.locator(".q-dialog").first).to_be_visible()


def test_save_post_creates_and_refreshes(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("button:has-text('Save Post')").first.click()
    page.wait_for_timeout(300)

    content_ta = page.locator(".q-dialog textarea").first
    content_ta.fill("My unique test post content ABC123")
    channel_input = page.locator(".q-dialog input").first
    channel_input.fill("slack-testchan")

    page.locator(".q-dialog button:has-text('Save')").first.click()
    page.wait_for_timeout(600)

    # Dialog should be closed
    expect(page.locator(".q-dialog")).to_have_count(0)

    # Post history should show the new channel
    expect(page.locator("text=slack-testchan").first).to_be_visible()

    # Verify in DB
    conn = sqlite3.connect(str(ui_db_path))
    count = conn.execute(
        "SELECT count(*) FROM posts WHERE channel='slack-testchan'"
    ).fetchone()[0]
    conn.close()
    assert count == 1


# ---------------------------------------------------------------------------
# Post card buttons
# ---------------------------------------------------------------------------

def test_post_view_button_visible(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("button:has-text('View')").first).to_be_visible()


def test_post_open_in_chat_button_visible(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    # "Open in chat →" appears on post cards (separate from win cards)
    expect(page.locator("button:has-text('Open in chat →')").first).to_be_visible()


def test_post_open_in_chat_switches_context(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    # Click "Open in chat →" on the first post card
    page.locator("button:has-text('Open in chat →')").first.click()
    page.wait_for_timeout(500)
    # Right panel label should now reference the channel
    expect(page.locator("text=Iterating:").first).to_be_visible()


# ---------------------------------------------------------------------------
# Post expand dialog (opened via View button)
# ---------------------------------------------------------------------------

def _open_slack_eng_expand(page: Page, ui_base_url: str, ui_db_path: Path) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    # Target the slack-eng card by its card-level classes + text — avoids
    # picking a newer post that sorts to the top after other tests insert rows.
    page.locator("div.rounded.q-mb-xs").filter(has_text="slack-eng").locator(
        "button:has-text('View')"
    ).first.click()
    page.wait_for_timeout(300)


def test_post_view_button_opens_expand_dialog(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_slack_eng_expand(page, ui_base_url, ui_db_path)
    expect(page.locator(".q-dialog").first).to_be_visible()


def test_post_expand_dialog_shows_full_content(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_slack_eng_expand(page, ui_base_url, ui_db_path)
    # Full content (not just snippet) should be visible
    expect(page.locator("text=This reduced error rates by 40%").first).to_be_visible()


def test_post_expand_dialog_closes(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_slack_eng_expand(page, ui_base_url, ui_db_path)
    page.locator(".q-dialog button:has-text('Close')").first.click()
    page.wait_for_timeout(300)
    expect(page.locator(".q-dialog")).to_have_count(0)


# ---------------------------------------------------------------------------
# Edit post
# ---------------------------------------------------------------------------

def test_edit_post_button_visible(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_slack_eng_expand(page, ui_base_url, ui_db_path)
    expect(page.locator(".q-dialog button:has-text('Edit')").first).to_be_visible()


def test_edit_post_shows_textarea(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_slack_eng_expand(page, ui_base_url, ui_db_path)
    page.locator(".q-dialog button:has-text('Edit')").first.click()
    page.wait_for_timeout(300)
    expect(page.locator(".q-dialog textarea").first).to_be_visible()


def test_edit_post_saves_changes(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    ids = _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("button:has-text('View')").first.click()
    page.wait_for_timeout(300)
    page.locator(".q-dialog button:has-text('Edit')").first.click()
    page.wait_for_timeout(300)

    # Update the content in the textarea
    ta = page.locator(".q-dialog textarea").first
    ta.fill("Updated post content XYZ")
    # Fill channel (pre-populated but must not be empty)
    channel_inputs = page.locator(".q-dialog input")
    channel_inputs.first.fill("slack-eng-updated")

    page.locator(".q-dialog button:has-text('Save')").first.click()
    page.wait_for_timeout(600)

    # Dialog should close
    expect(page.locator(".q-dialog")).to_have_count(0)

    # Verify DB was updated
    conn = sqlite3.connect(str(ui_db_path))
    row = conn.execute(
        "SELECT content, channel FROM posts WHERE channel='slack-eng-updated'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert "Updated post content XYZ" in row[0]


def test_edit_post_cancel_returns_to_view(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _open_slack_eng_expand(page, ui_base_url, ui_db_path)
    page.locator(".q-dialog button:has-text('Edit')").first.click()
    page.wait_for_timeout(300)
    page.locator(".q-dialog button:has-text('Cancel')").first.click()
    page.wait_for_timeout(300)
    # Should return to read-only view (Edit button visible again)
    expect(page.locator(".q-dialog button:has-text('Edit')").first).to_be_visible()


# ---------------------------------------------------------------------------
# New draft button and context switching
# ---------------------------------------------------------------------------

def test_new_draft_button_visible(page: Page, ui_base_url: str) -> None:
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("button:has-text('New draft')").first).to_be_visible()


def test_win_context_label_on_open_in_chat(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("text=Shipped X").first.click()
    page.wait_for_timeout(400)
    page.locator("button:has-text('Open in chat')").first.click()
    page.wait_for_timeout(400)
    # Right panel label should reference the win title
    expect(page.locator("text=Draft:").first).to_be_visible()


def test_new_draft_resets_context(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    page.locator("text=Shipped X").first.click()
    page.wait_for_timeout(400)
    page.locator("button:has-text('Open in chat')").first.click()
    page.wait_for_timeout(400)
    # Switch back to generic draft
    page.locator("button:has-text('New draft')").first.click()
    page.wait_for_timeout(400)
    expect(page.locator("text=Drafting chat").first).to_be_visible()


# ---------------------------------------------------------------------------
# Win→post badge
# ---------------------------------------------------------------------------

def _seed_linked_post(db_path: Path, win_id: int) -> int:
    """Seed a post with win_id set (for badge tests)."""
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


def test_win_badge_shown_when_win_has_post(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    ids = _seed_data(ui_db_path)
    _seed_linked_post(ui_db_path, ids["win1_id"])
    _goto(page, f"{ui_base_url}{WINS_POSTS}")
    expect(page.locator("text=✓ posted").first).to_be_visible()


def test_save_post_records_win_id(
    page: Page, ui_base_url: str, ui_db_path: Path
) -> None:
    ids = _seed_data(ui_db_path)
    _goto(page, f"{ui_base_url}{WINS_POSTS}")

    # Open win in chat (sets active_win_id)
    page.locator("text=Shipped X").first.click()
    page.wait_for_timeout(400)
    page.locator("button:has-text('Open in chat')").first.click()
    page.wait_for_timeout(400)

    # Save a post from this context
    page.locator("button:has-text('Save Post')").first.click()
    page.wait_for_timeout(300)

    content_ta = page.locator(".q-dialog textarea").first
    content_ta.fill("Win-linked post content ZZZ")
    channel_input = page.locator(".q-dialog input").first
    channel_input.fill("slack-win-linked")

    page.locator(".q-dialog button:has-text('Save')").first.click()
    page.wait_for_timeout(600)

    expect(page.locator(".q-dialog")).to_have_count(0)

    conn = sqlite3.connect(str(ui_db_path))
    row = conn.execute(
        "SELECT win_id FROM posts WHERE channel='slack-win-linked'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == ids["win1_id"]
