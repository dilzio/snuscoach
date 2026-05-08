"""Playwright integration tests for the UI foundation pass.

Verifies: all 6 routes load, left nav is present on each page, nav links
exist, and the header shows "snuscoach".
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.ui


ROUTES = [
    ("/", "Home"),
    ("/meetings", "Meetings"),
    ("/stakeholders", "Stakeholders"),
    ("/wins-posts", "Wins & Posts"),
    ("/journal", "Journal"),
    ("/admin", "Admin"),
]

NAV_LABELS = ["Home", "Meetings", "Stakeholders", "Wins & Posts", "Journal", "Admin"]


@pytest.mark.parametrize("path,title", ROUTES)
def test_page_loads(page: Page, ui_base_url: str, path: str, title: str) -> None:
    page.goto(f"{ui_base_url}{path}")
    expect(page.locator(f"text={title}").first).to_be_visible()


@pytest.mark.parametrize("path,_", ROUTES)
def test_header_shows_app_name(page: Page, ui_base_url: str, path: str, _: str) -> None:
    page.goto(f"{ui_base_url}{path}")
    expect(page.locator("text=snuscoach").first).to_be_visible()


@pytest.mark.parametrize("path,_", ROUTES)
def test_nav_links_present(page: Page, ui_base_url: str, path: str, _: str) -> None:
    page.goto(f"{ui_base_url}{path}")
    for label in NAV_LABELS:
        expect(page.locator(f"a:has-text('{label}')").first).to_be_visible()


@pytest.mark.parametrize("path,_", ROUTES)
def test_no_profile_chip_shown(page: Page, ui_base_url: str, path: str, _: str) -> None:
    """With an empty DB, the header should show 'No profile'."""
    page.goto(f"{ui_base_url}{path}")
    expect(page.locator("text=No profile").first).to_be_visible()


def test_nav_home_link_navigates(page: Page, ui_base_url: str) -> None:
    page.goto(f"{ui_base_url}/meetings")
    page.locator("a:has-text('Home')").first.click()
    page.wait_for_url(f"{ui_base_url}/")
    expect(page.locator("text=Home").first).to_be_visible()


def test_nav_admin_link_navigates(page: Page, ui_base_url: str) -> None:
    page.goto(f"{ui_base_url}/")
    page.locator("a:has-text('Admin')").first.click()
    page.wait_for_url(f"{ui_base_url}/admin")
    expect(page.locator("text=Admin").first).to_be_visible()
