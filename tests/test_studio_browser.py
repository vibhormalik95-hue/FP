"""Rendered-browser test of the Studio page with the mock provider.

Skipped unless Playwright and an installed Chrome/Chromium are available.
"""
import socket
import threading
import time

import pytest

playwright = pytest.importorskip("playwright.sync_api")
import uvicorn  # noqa: E402

from studio.providers import MockProvider  # noqa: E402
from studio.server import create_app  # noqa: E402

KEY = "sk-ant-BROWSER-TEST-KEY-000000000000000000"


@pytest.fixture(scope="module")
def base_url():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(port=port, provider=MockProvider()), host="127.0.0.1",
                                           port=port, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    while not server.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    t.join(5)


@pytest.fixture(scope="module")
def page(base_url):
    with playwright.sync_playwright() as p:
        browser = None
        for kwargs in ({"channel": "chrome"}, {"channel": "msedge"}, {}):
            try:
                browser = p.chromium.launch(headless=True, **kwargs)
                break
            except Exception:
                continue
        if browser is None:
            pytest.skip("No Chromium-based browser available")
        pg = browser.new_page(viewport={"width": 1920, "height": 1080})
        pg.goto(base_url + "/")
        pg.wait_for_selector("#feed li")
        yield pg
        browser.close()


def test_manual_preview_apply_undo(page):
    page.click("#tab-manual")
    page.select_option("#manual-kind", "category")
    page.select_option("#manual-value", "Gaming")
    page.select_option("#manual-action", "hide")
    page.click("#manual-preview")
    page.wait_for_selector("#review-body .counts")
    assert "40 → 36" in page.inner_text("#review-body")
    assert page.locator("#feed li").count() == 12
    page.click("#apply-btn")
    page.wait_for_selector("text=Applied.")
    assert "36 eligible" in page.inner_text("#feed-count")
    page.click("#undo-btn")
    page.wait_for_selector("text=Undone.")
    assert "40 eligible" in page.inner_text("#feed-count")


def test_key_field_is_masked_and_cleared(page):
    page.select_option("#provider-kind", "anthropic")
    page.fill("#api-key", KEY)
    assert page.get_attribute("#api-key", "type") == "password"
    page.click("#save-provider")
    page.wait_for_selector("#provider-msg.ok")
    assert page.input_value("#api-key") == ""
    assert KEY not in page.content()
    assert "key pasted (memory only)" in page.inner_text("#provider-line")
    page.select_option("#provider-kind", "mock")
    page.click("#save-provider")
    page.wait_for_selector("text=mock provider (no AI)")


def test_new_category_flow(page):
    page.click("#tab-category")
    page.fill("#category-text", "videos that teach a skill step by step")
    page.click("#category-define")
    page.wait_for_selector("#definition-box:not([hidden])")
    assert page.input_value("#def-label")
    page.select_option("#category-action", "only")
    page.click("#category-classify")
    page.wait_for_selector("th:has-text('Independent check')")
    page.click("#apply-btn")
    page.wait_for_selector("text=Applied.")
    page.click("#undo-btn")
    page.wait_for_selector("text=Undone.")


def test_add_video_flow(page):
    page.click("#tab-items")
    page.fill("#item-title-0", "Retro speedrun practice")
    page.fill("#item-desc-0", "A player practises a speedrun route in a retro game.")
    page.click("#items-preview")
    page.wait_for_selector("text=How the model classified the new videos")
    page.click("#apply-btn")
    page.wait_for_selector("text=Applied.")
    assert "41 in catalogue" in page.inner_text("#feed-count")
    page.click("#undo-btn")
    page.wait_for_selector("text=Undone.")
