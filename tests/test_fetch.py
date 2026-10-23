"""page_diff 的错误页、日期门禁与基线回归。"""
import hashlib

import pytest
import requests

import common
import fetch


TODAY = "2026-10-23"
SOURCE = {"id": "example", "url": "https://example.com/releases", "vendor": "Example", "category": "coding"}


@pytest.fixture
def page(monkeypatch, tmp_path):
    monkeypatch.setattr(common, "STATE_DIR", tmp_path)

    def set_page(html):
        response = requests.Response()
        response.status_code = 200
        response.encoding = "utf-8"
        response._content = html.encode("utf-8")
        monkeypatch.setattr(fetch, "http_get", lambda url: response)

    return set_page


@pytest.mark.parametrize("html", [
    "<title>404错误页-阿里云帮助中心</title>",
    "<title>404 Not Found</title>",
    "<title>Release notes</title><body>页面不存在</body>",
])
@pytest.mark.parametrize("existing", [False, True])
def test_soft404_never_sets_or_overwrites_baseline(page, html, existing):
    original = {"url": SOURCE["url"], "hash": "valid-baseline", "last_changed": "previous"}
    if existing:
        common.save_state(SOURCE["id"], original)
    page(html + f"<footer>{TODAY}</footer>")
    assert fetch.fetch_page_diff(SOURCE, TODAY) == []
    state = common.load_state(SOURCE["id"])
    assert state.get("hash") == (original["hash"] if existing else None)
    assert state.get("last_changed") == ("previous" if existing else None)
    assert state["last_checked"]


def test_missing_date_updates_baseline_without_item(page):
    common.save_state(SOURCE["id"], {"url": SOURCE["url"], "hash": "old"})
    html = "<body>Release notes 2026-10-22</body><script>2026-10-23</script>"
    page(html)
    assert fetch.fetch_page_diff(SOURCE, TODAY) == []
    state = common.load_state(SOURCE["id"])
    assert state["hash"] == hashlib.sha256(fetch.extract_text(html).encode()).hexdigest()
    assert fetch.fetch_page_diff(SOURCE, TODAY) == []


def test_dated_change_produces_unverified_item(page):
    page("<body>Old release</body>")
    assert fetch.fetch_page_diff(SOURCE, TODAY) == []
    page(f"<body>{TODAY} New release</body>")
    items = fetch.fetch_page_diff(SOURCE, TODAY)
    assert len(items) == 1
    assert items[0]["source_url"] == f"{SOURCE['url']}#{TODAY}"
    assert items[0]["date"] == TODAY
    assert items[0]["verified"] is False
    assert fetch.fetch_page_diff(SOURCE, TODAY) == []
