"""validate.py：schema、定价快照、计费周期切换、官方域名校验的最小测试集。"""
import re

import common
import validate as v

SOURCES = [
    {"id": "cursor-changelog", "vendor": "Cursor", "official_domain": "cursor.com"},
    {
        "id": "claude-code-releases",
        "vendor": "Anthropic Claude Code",
        "official_domain": "github.com/anthropics",
    },
]


def make_item(**overrides):
    item = {
        "id": "cursor-0123456789",
        "date": "2026-10-01",
        "vendor": "Cursor",
        "category": "code",
        "source_id": "cursor-changelog",
        "title": "Cursor 2.0 发布",
        "summary_zh": "",
        "source_url": "https://cursor.com/changelog",
        "verified": False,
        "signal_type": "changelog",
        "fetched_at": "2026-10-01T08:00:00Z",
    }
    item.update(overrides)
    return item


# ---------- schema ----------


def test_schema_accepts_valid_item():
    assert v.validate_item(make_item()) == []


def test_schema_rejects_missing_required_field():
    item = make_item()
    del item["id"]
    assert v.validate_item(item) != []


def test_schema_rejects_unknown_category():
    assert v.validate_item(make_item(category="news")) != []


def test_schema_rejects_malformed_date():
    assert v.validate_item(make_item(date="2026/10/01")) != []


def test_schema_rejects_unknown_property():
    assert v.validate_item(make_item(extra_field="x")) != []


def test_schema_rejects_bad_verified_type():
    assert v.validate_item(make_item(verified="yes")) != []


# ---------- id ----------


def test_item_id_is_vendor_slug_plus_sha1_prefix():
    item_id = common.item_id("Cursor", "https://cursor.com/changelog")
    assert re.fullmatch(r"cursor-[0-9a-f]{10}", item_id)


def test_slugify_strips_non_ascii():
    assert common.slugify("智谱 GLM") == "glm"
    assert common.slugify("Anthropic Claude Code") == "anthropic-claude-code"


# ---------- pricing ----------


def test_pricing_requires_price_snapshot():
    errors = v.validate_item(
        make_item(category="pricing", signal_type="pricing_change")
    )
    assert any("price_snapshot" in msg for msg in errors)


def test_pricing_with_snapshot_accepted():
    item = make_item(
        category="pricing",
        signal_type="pricing_change",
        price_snapshot={
            "plan": "Pro",
            "price": 20,
            "currency": "USD",
            "billing_period": "monthly",
            "captured_at": "2026-10-01T00:00:00Z",
        },
    )
    assert v.validate_item(item) == []


def test_snapshot_requires_captured_at():
    item = make_item(
        category="pricing",
        price_snapshot={
            "plan": "Pro",
            "price": 20,
            "currency": "USD",
            "billing_period": "monthly",
        },
    )
    assert v.validate_item(item) != []


# ---------- 计费周期切换 ----------


def test_billing_switch_detected():
    prev = {
        "price_snapshot": {
            "plan": "Pro",
            "price": 20,
            "currency": "USD",
            "billing_period": "monthly",
        }
    }
    cur = {
        "price_snapshot": {
            "plan": "Pro",
            "price": 20,
            "currency": "USD",
            "billing_period": "annual",
        }
    }
    assert v.is_billing_switch(prev, cur) is True


def test_price_change_is_not_billing_switch():
    prev = {"price": 20, "currency": "USD", "billing_period": "monthly"}
    cur = {"price": 25, "currency": "USD", "billing_period": "annual"}
    assert v.is_billing_switch(prev, cur) is False


def test_same_period_is_not_billing_switch():
    prev = {"price": 20, "currency": "USD", "billing_period": "monthly"}
    cur = {"price": 20, "currency": "USD", "billing_period": "monthly"}
    assert v.is_billing_switch(prev, cur) is False


def test_currency_change_is_not_billing_switch():
    prev = {"price": 20, "currency": "USD", "billing_period": "monthly"}
    cur = {"price": 20, "currency": "CNY", "billing_period": "annual"}
    assert v.is_billing_switch(prev, cur) is False


# ---------- 官方域名 ----------


def test_official_host_accepted():
    assert common.is_official_url("https://cursor.com/changelog", SOURCES) is True


def test_official_subdomain_accepted():
    assert common.is_official_url("https://docs.cursor.com/changelog", SOURCES) is True


def test_unofficial_host_rejected():
    assert common.is_official_url("https://cursor.example.com/x", SOURCES) is False
    assert common.is_official_url("https://evil.example.com/news", SOURCES) is False


def test_official_domain_path_prefix():
    assert (
        common.is_official_url(
            "https://github.com/anthropics/claude-code/releases/tag/v1.0.0", SOURCES
        )
        is True
    )
    assert common.is_official_url("https://github.com/other/repo", SOURCES) is False


def test_github_only_official_repo_paths_in_validate():
    srcs = SOURCES + [{"id": "x", "url": "https://github.com/anthropics/claude-code/releases.atom",
                       "official_domain": "github.com/anthropics"}]
    assert v.url_is_official("https://github.com/anthropics/claude-code/releases/tag/v1", srcs) is True
    assert v.url_is_official("https://github.com/anthropics/other-repo/releases", srcs) is False
    assert v.url_is_official("https://github.com/anthropics/claude-code-evil", srcs) is False
    assert v.url_is_official("https://github.com/any/repo/releases", srcs) is False
    assert v.url_is_official("https://github.com/any/repo/releases", []) is False
    assert v.url_is_official("https://example.com/page", []) is False


def test_enabled_sources_skip_unverified(tmp_path):
    path = tmp_path / "sources.yml"
    path.write_text(
        "sources:\n"
        "  - {id: keep, verified: true}\n"
        "  - {id: drop, verified: false}\n",
        encoding="utf-8",
    )
    assert [s["id"] for s in common.enabled_sources(path)] == ["keep"]
