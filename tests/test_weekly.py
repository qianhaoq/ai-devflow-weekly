"""weekly.py：仅收录 verified 条目、beta 标注、周筛选与渲染格式。"""
from datetime import date, timedelta

import common
import weekly


def make_item(**overrides):
    item = {
        "id": "cursor-0123456789",
        "date": "2026-10-12",
        "vendor": "Cursor",
        "category": "code",
        "title": "Cursor 2.0 发布",
        "summary_zh": "官方 changelog 发布 2.0 版本。",
        "source_url": "https://cursor.com/changelog",
        "verified": True,
        "signal_type": "changelog",
        "fetched_at": "2026-10-12T08:00:00Z",
    }
    item.update(overrides)
    return item


# 选一个周一，保证周一与周三同属一个 ISO 周、下周一属于下一周
MONDAY = date(2026, 10, 12) - timedelta(days=date(2026, 10, 12).weekday())
_iso = MONDAY.isocalendar()
WEEK_LABEL = f"{_iso[0]}-W{_iso[1]:02d}"


def test_render_week_only_includes_verified():
    items = [
        make_item(date=MONDAY.isoformat()),
        make_item(
            id="windsurf-0123456789",
            vendor="Windsurf",
            title="Windsurf 1.0 未核实条目",
            source_url="https://windsurf.com/changelog",
            verified=False,
        ),
    ]
    md = weekly.render_week(items, WEEK_LABEL)
    assert "Cursor 2.0 发布" in md
    assert "Windsurf 1.0 未核实条目" not in md


def test_items_in_week_excludes_unverified_by_default():
    items = [make_item(date=MONDAY.isoformat(), verified=False)]
    iso_year, iso_week = weekly.parse_week(WEEK_LABEL)
    assert weekly.items_in_week(items, iso_year, iso_week) == []


def test_items_in_week_filters_by_date():
    items = [
        make_item(date=MONDAY.isoformat()),
        make_item(
            id="cursor-1111111111", date=(MONDAY + timedelta(days=2)).isoformat()
        ),
        make_item(
            id="cursor-2222222222", date=(MONDAY + timedelta(days=7)).isoformat()
        ),
    ]
    iso_year, iso_week = weekly.parse_week(WEEK_LABEL)
    got = weekly.items_in_week(items, iso_year, iso_week)
    assert [it["id"] for it in got] == ["cursor-0123456789", "cursor-1111111111"]


def test_render_week_marks_beta():
    md = weekly.render_week(
        [make_item(title="Claude Code 2.5 (beta) 可用")], WEEK_LABEL
    )
    assert "（beta/预览）" in md
    assert weekly.is_beta("Foo Preview 更新") is True
    assert weekly.is_beta("新功能预览上线") is True
    assert weekly.is_beta("Regular Release 1.2") is False


def test_render_week_front_matter_and_grouping():
    md = weekly.render_week(
        [make_item(date=MONDAY.isoformat())], WEEK_LABEL
    )
    assert md.startswith("---\n")
    assert "layout: default" in md
    assert f'title: "AI 研发工作流周刊 {WEEK_LABEL}"' in md
    assert f"## {common.CATEGORY_ZH['code']}" in md
    # 原始链接 + 发布日期 + vendor 均需出现（editorial 第 5 条）
    assert "https://cursor.com/changelog" in md
    assert MONDAY.isoformat() in md
    assert "Cursor" in md


def test_render_week_pricing_group():
    md = weekly.render_week(
        [
            make_item(
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
        ],
        WEEK_LABEL,
    )
    assert f"## {common.CATEGORY_ZH['pricing']}" in md


def test_current_week_label_format():
    assert weekly.WEEK_RE.fullmatch(weekly.current_week_label())


def test_weekly_all_rebuilds_verified_weeks(monkeypatch, tmp_path):
    import common
    import weekly as w
    items = [{"date": "2026-10-14", "verified": True}, {"date": "2026-09-01", "verified": False}]
    calls = []
    monkeypatch.setattr(common, "load_items", lambda: items)
    real = w.main
    monkeypatch.setattr(w, "main", lambda argv=None: calls.append(argv) or 0)
    assert real(["--all"]) == 0
    assert calls == [["--week", "2026-W42"]]
