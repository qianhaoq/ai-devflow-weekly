#!/usr/bin/env python3
"""校验 data/items 下全部条目。

检查项：JSON Schema、id/source_url 唯一、source_url 为官方域名（任一源的
official_domain，host+可选路径前缀；github.com 仅限 sources.yml 中官方 org/repo 路径）、
文件路径与 date/id 一致、pricing 条目必须带 price_snapshot。

定价规则：signal_type=pricing_change 且带 price_snapshot 的条目与同 vendor+plan
的上一条定价条目比对；若价格与币种相同、仅计费周期不同（月付/年付），输出
WARNING（billing switch, not a price increase），不算错误。

用法：python scripts/validate.py，发现错误时退出码 1。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common

FORMAT_CHECKER = Draft202012Validator.FORMAT_CHECKER


def validate_item(item, schema: dict | None = None) -> list[str]:
    """返回单条条目的 schema 错误列表（含 pricing 必须带 price_snapshot 的规则）。"""
    validator = Draft202012Validator(schema or common.load_schema(), format_checker=FORMAT_CHECKER)
    errors = []
    for err in validator.iter_errors(item):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        errors.append(f"schema: {loc}: {err.message}")
    return errors


def github_repo_paths(sources: list[dict]) -> set[str]:
    """sources.yml 中 github.com 源的官方 /org/repo 路径（小写）：取自源 url，
    外加显式列出的 official_github_repos（如仓库迁移后的新 org/repo）。"""
    paths: set[str] = set()
    for source in sources or []:
        for repo in source.get("official_github_repos") or []:
            parts = [p for p in str(repo).split("/") if p]
            if len(parts) == 2:
                paths.add(("/" + "/".join(parts)).lower())
        url = source.get("url") or ""
        if common.url_host(url) != "github.com":
            continue
        parts = [p for p in urlparse(url).path.split("/") if p][:2]
        if len(parts) == 2:
            paths.add(("/" + "/".join(parts)).lower())
    return paths


def url_is_official(url: str, sources: list[dict]) -> bool:
    """source_url 是否官方。github.com 只接受 sources.yml 列出的 /org/repo 路径
    （避免 github.com/anthropics/<任意仓库> 或任意 github 仓库被当作官方）。"""
    host = (common.url_host(url) or "").lower().rstrip(".")
    if host == "github.com" or host.endswith(".github.com"):
        if host != "github.com":
            return False  # www.github.com 等非规范 host 一律拒绝
        path = urlparse(url).path.lower()
        return any(path == p or path.startswith(p + "/") for p in github_repo_paths(sources))
    return common.is_official_url(url, sources)


def _price_equal(a, b) -> bool:
    """价格相等：可数字化则按数值比，否则按字符串比。"""
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return str(a).strip() == str(b).strip()


def _snapshot(obj) -> dict:
    """接受条目 dict 或 price_snapshot dict，统一取出快照。"""
    if not isinstance(obj, dict):
        return {}
    snap = obj.get("price_snapshot")
    return snap if isinstance(snap, dict) else obj


def is_billing_switch(prev, cur) -> bool:
    """是否「仅计费周期变化」：价格、币种相同而 billing_period 不同（如月付 -> 年付）。

    prev/cur 可以是定价条目（含 price_snapshot）或快照 dict 本身。
    价格或币种有变即为真实价格变化，返回 False。
    """
    prev_snap, cur_snap = _snapshot(prev), _snapshot(cur)
    if not prev_snap or not cur_snap:
        return False
    if not prev_snap.get("billing_period") or not cur_snap.get("billing_period"):
        return False
    if prev_snap.get("billing_period") == cur_snap.get("billing_period"):
        return False
    if not _price_equal(prev_snap.get("price"), cur_snap.get("price")):
        return False
    prev_ccy = str(prev_snap.get("currency") or "").strip().lower()
    cur_ccy = str(cur_snap.get("currency") or "").strip().lower()
    return prev_ccy == cur_ccy


def collect_items() -> list[tuple[Path, dict]]:
    """(路径, 条目) 列表；JSON 解析失败的文件以 (路径, {}) 记录，由调用方报错。"""
    pairs = []
    for path in common.iter_item_files():
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            item = None
        pairs.append((path, item))
    return pairs


def check_all(items_dir: Path | None = None) -> tuple[list[str], list[str]]:
    """全量校验，返回 (errors, warnings)。"""
    sources = common.load_sources()
    errors: list[str] = []
    warnings: list[str] = []

    seen_ids: dict[str, str] = {}
    seen_urls: dict[str, str] = {}
    pricing_items: list[tuple[str, dict]] = []

    for path, item in collect_items():
        rel = str(path.relative_to(common.ROOT))
        if not isinstance(item, dict):
            errors.append(f"{rel}: JSON 解析失败或不是对象")
            continue

        for msg in validate_item(item):
            errors.append(f"{rel}: {msg}")

        # 文件路径必须与 date/id 一致（date/id 缺失或非法时 schema 已报错）
        if item.get("date") and item.get("id"):
            expected = common.item_path(item["id"], item["date"])
            if expected != path:
                errors.append(
                    f"{rel}: 路径与 date/id 不符，应为 data/items/{item['date'][:4]}/"
                    f"{item['date'][5:7]}/{item['id']}.json"
                )

        # source_url 必须是官方域名
        url = item.get("source_url")
        if url and not url_is_official(url, sources):
            errors.append(f"{rel}: source_url 非官方域名: {url}")

        # id 与 source_url 唯一
        if item.get("id"):
            if item["id"] in seen_ids:
                errors.append(f"{rel}: id 重复 {item['id']}（首见 {seen_ids[item['id']]}）")
            else:
                seen_ids[item["id"]] = rel
        if url:
            if url in seen_urls:
                errors.append(f"{rel}: source_url 重复: {url}（首见 {seen_urls[url]}）")
            else:
                seen_urls[url] = rel

        if item.get("signal_type") == "pricing_change" and isinstance(
            item.get("price_snapshot"), dict
        ):
            pricing_items.append((rel, item))

    # 定价规则：同 vendor+plan 的前后快照对比，仅周期不同 -> WARNING 而非错误
    pricing_items.sort(key=lambda pair: (pair[1].get("date") or "", pair[1].get("id") or ""))
    last_seen: dict[tuple[str, str], dict] = {}
    for rel, item in pricing_items:
        snap = item["price_snapshot"]
        key = (item.get("vendor") or "", snap.get("plan") or "")
        prev = last_seen.get(key)
        if prev is not None and is_billing_switch(prev, item):
            warnings.append(
                f"{rel}: billing switch, not a price increase"
                f"（{key[0]}/{key[1]}: "
                f"{_snapshot(prev).get('billing_period')} -> {snap.get('billing_period')}）"
            )
        last_seen[key] = item

    return errors, warnings


def main(argv=None) -> int:
    errors, warnings = check_all()
    for msg in warnings:
        print(f"WARNING {msg}")
    for msg in errors:
        print(f"ERROR {msg}")
    total = len(common.iter_item_files())
    print(f"校验完成：{total} 条，错误 {len(errors)}，警告 {len(warnings)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
