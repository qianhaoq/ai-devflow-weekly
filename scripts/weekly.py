#!/usr/bin/env python3
"""生成周刊 Markdown：_weekly/YYYY-Www.md。

- 仅收录 verified=true 的条目（docs/editorial.md 第 4 条）。
- 按分类分组（中文标题），每条附原始链接与发布日期（Asia/Shanghai）。
- 标题含 beta/preview/预览 的条目加「beta/预览」标注（editorial 第 5 条）。
- Jekyll front matter：layout: default + title。

用法：python scripts/weekly.py [--week 2026-W42]（默认当前 ISO 周，Asia/Shanghai）。
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date as date_cls
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common

SHANGHAI = ZoneInfo("Asia/Shanghai")
WEEK_RE = re.compile(r"^(\d{4})-W(\d{2})$")


def is_beta(title: str) -> bool:
    """标题是否标注 beta/预览（英文不区分大小写）。"""
    title = title or ""
    lowered = title.lower()
    return "beta" in lowered or "preview" in lowered or "预览" in title


def current_week_label(now: datetime | None = None) -> str:
    """当前 ISO 周标签（Asia/Shanghai 时区），如 2026-W42。"""
    now = now or datetime.now(SHANGHAI)
    iso_year, iso_week, _ = now.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def parse_week(label: str) -> tuple[int, int]:
    m = WEEK_RE.match(label or "")
    if not m:
        raise ValueError(f"周标签格式应为 YYYY-Www（如 2026-W42），收到：{label!r}")
    return int(m.group(1)), int(m.group(2))


def items_in_week(
    items: list[dict], iso_year: int, iso_week: int, *, verified_only: bool = True
) -> list[dict]:
    """筛选落在指定 ISO 周的条目（默认仅 verified）。"""
    out = []
    for item in items:
        if verified_only and not item.get("verified"):
            continue
        try:
            day = date_cls.fromisoformat(str(item.get("date") or ""))
        except ValueError:
            continue
        if (day.isocalendar()[0], day.isocalendar()[1]) == (iso_year, iso_week):
            out.append(item)
    return out


def render_week(items: list[dict], week_label: str) -> str:
    """渲染周刊 Markdown（防御性：即使传入未核实条目也只输出 verified）。"""
    verified = [it for it in items if it.get("verified")]
    lines = [
        "---",
        "layout: default",
        f'title: "AI 研发工作流周刊 {week_label}"',
        "---",
        "",
        f"# AI 研发工作流周刊 {week_label}",
        "",
    ]
    if not verified:
        lines += ["本周暂无已核实条目。", ""]

    grouped: dict[str, list[dict]] = {}
    for item in verified:
        grouped.setdefault(str(item.get("category", "")), []).append(item)

    for category in common.CATEGORIES:
        entries = sorted(
            grouped.get(category, []),
            key=lambda it: (str(it.get("date") or ""), str(it.get("id") or "")),
            reverse=True,
        )
        if not entries:
            continue
        lines += [f"## {common.CATEGORY_ZH.get(category, category)}", ""]
        for item in entries:
            title = str(item.get("title") or "").strip() or item.get("source_url", "")
            badge = "（beta/预览）" if is_beta(str(item.get("title") or "")) else ""
            meta = " · ".join(
                part for part in (item.get("vendor", ""), item.get("date", "")) if part
            )
            lines.append(f"- **[{title}]({item.get('source_url', '')})**{badge} — {meta}")
            summary = str(item.get("summary_zh") or "").strip()
            if summary:
                lines.append(f"  {summary}")
        lines.append("")

    for category in grouped:  # schema 之外的分类（理论上不会出现）
        if category not in common.CATEGORIES:
            lines += [f"## {category}", "", f"共 {len(grouped[category])} 条", ""]

    return "\n".join(lines).rstrip() + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="生成周刊 Markdown（仅 verified 条目）")
    ap.add_argument(
        "--week",
        default=None,
        help="周标签，如 2026-W42（默认当前 ISO 周，Asia/Shanghai）",
    )
    ap.add_argument(
        "--all",
        action="store_true",
        help="重建所有含已核实条目的周（部署时使用，使编辑审核后置 verified 的条目进入当周周刊）",
    )
    args = ap.parse_args(argv)

    if args.all:
        items = common.load_items()
        weeks = set()
        for item in items:
            if not item.get("verified"):
                continue
            try:
                y, w, _ = date_cls.fromisoformat(str(item.get("date") or "")).isocalendar()
            except ValueError:
                continue
            weeks.add(f"{y}-W{w:02d}")
        for label in sorted(weeks):
            main(["--week", label])
        # 已有周刊但其中已无 verified 条目（编辑把最后一条改回 false）：删除，避免发布过期内容
        for path in sorted(common.WEEKLY_DIR.glob("*-W*.md")) if common.WEEKLY_DIR.exists() else []:
            if WEEK_RE.match(path.stem) and path.stem not in weeks:
                path.unlink()
                print(f"已删除 {path.name}：该周已无已核实条目")
        return 0

    label = args.week or current_week_label()
    iso_year, iso_week = parse_week(label)
    items = items_in_week(common.load_items(), iso_year, iso_week)

    common.WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
    out_path = common.WEEKLY_DIR / f"{label}.md"
    out_path.write_text(render_week(items, label), encoding="utf-8")
    print(f"已写入 {out_path.relative_to(common.ROOT)}：{len(items)} 条已核实条目")
    return 0


if __name__ == "__main__":
    sys.exit(main())
