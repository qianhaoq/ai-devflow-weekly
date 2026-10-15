#!/usr/bin/env python3
"""按 sources.yml 抓取启用源，生成 data/items/YYYY/MM/<id>.json 条目。

- rss：requests（带 UA）抓取 + feedparser 解析
- github_releases：优先 GitHub API（JSON，可用 GITHUB_TOKEN 提额），失败回退 .atom（feedparser）
- page_diff：抓 HTML、提取正文文本取 sha256，与 data/state/<source id>.json 中
  上次快照比对；哈希变化才生成一条条目（source_url = 页面 URL + '#' + 日期）。
  首次抓取只记录基线，不生成条目。
"""
from __future__ import annotations

import argparse
import calendar
import hashlib
import html as html_lib
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import feedparser
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common

SHANGHAI = ZoneInfo("Asia/Shanghai")
REQUEST_TIMEOUT = 30

# 默认关键词过滤（源未声明 include_keywords 时按源 id 取默认值）；
# 机制本身是通用的：任一源可在 sources.yml 里写 include_keywords 覆盖。
DEFAULT_INCLUDE_KEYWORDS = {
    # GitHub 全量 changelog 只保留 Actions/Copilot/Codespaces 相关
    "github-actions-changelog": [
        "copilot",
        "actions",
        "code review",
        "agent",
        "codespaces",
    ],
}


def http_get(url: str, headers: dict | None = None):
    headers = dict(headers or {})
    headers.setdefault("User-Agent", common.USER_AGENT)
    return requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)


def include_keywords(source: dict) -> list[str]:
    keywords = source.get("include_keywords")
    if keywords is None:
        keywords = DEFAULT_INCLUDE_KEYWORDS.get(source.get("id"), [])
    return [str(k).lower() for k in keywords or []]


def matches_keywords(text: str, keywords: list[str]) -> bool:
    haystack = (text or "").lower()
    return any(k in haystack for k in keywords)


def iso_to_sh_date(value) -> str | None:
    """ISO 时间字符串 -> Asia/Shanghai 日期（YYYY-MM-DD）；解析失败返回 None。"""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(SHANGHAI).date().isoformat()


def entry_date_str(entry) -> str | None:
    """feedparser 条目 -> Asia/Shanghai 日期；无日期返回 None。"""
    st = entry.get("published_parsed") or entry.get("updated_parsed")
    if st:
        ts = calendar.timegm(st)
        return datetime.fromtimestamp(ts, SHANGHAI).date().isoformat()
    return None


def build_item(
    source: dict, *, title: str, link: str, date_str: str | None, signal_type: str
) -> dict:
    """规范化为符合 schema 的条目：summary_zh 为空、verified=false、fetched_at 为当前 UTC。"""
    vendor = str(source.get("vendor") or source.get("id") or "unknown")
    state_key = str(source.get("id") or vendor)
    return {
        "id": common.item_id(vendor, link),
        "date": date_str or datetime.now(SHANGHAI).date().isoformat(),
        "vendor": vendor,
        "category": common.CATEGORY_MAP.get(
            source.get("category"), source.get("category")
        ),
        "source_id": source.get("id"),
        "title": title,
        "summary_zh": "",
        "source_url": link,
        "verified": False,
        "signal_type": signal_type,
        "fetched_at": common.utc_now_iso(),
    }


def fetch_feed(source: dict, limit: int, cutoff: str, signal_type: str) -> list[dict]:
    """RSS/Atom 通用抓取：requests + feedparser，可选关键词过滤、按日期裁剪、限流条数。"""
    resp = http_get(source["url"])
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)
    keywords = include_keywords(source)
    items = []
    for entry in feed.entries:
        title = (entry.get("title") or "").strip()
        summary = (entry.get("summary") or entry.get("description") or "").strip()
        link = (entry.get("link") or "").strip()
        if not link.startswith(("http://", "https://")):
            continue
        if keywords and not matches_keywords(f"{title} {summary}", keywords):
            continue
        date_str = entry_date_str(entry)
        if date_str and date_str < cutoff:
            continue
        items.append(
            build_item(
                source,
                title=title or link,
                link=link,
                date_str=date_str,
                signal_type=signal_type,
            )
        )
        if len(items) >= limit:
            break
    return items


def parse_atom_repo(url: str):
    """从 https://github.com/<owner>/<repo>/releases.atom 提取 (owner, repo)。"""
    m = re.search(r"github\.com/([^/]+)/([^/]+)/releases", url or "")
    return (m.group(1), m.group(2)) if m else (None, None)


def releases_via_api(
    source: dict, owner: str, repo: str, limit: int, cutoff: str
) -> list[dict]:
    api = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page={limit}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = http_get(api, headers=headers)
    resp.raise_for_status()
    items = []
    for rel in resp.json():
        if rel.get("draft"):
            continue
        tag = rel.get("tag_name") or ""
        link = (
            rel.get("html_url")
            or f"https://github.com/{owner}/{repo}/releases/tag/{tag}"
        )
        title = (rel.get("name") or tag or link).strip()
        date_str = iso_to_sh_date(rel.get("published_at") or rel.get("created_at"))
        if date_str and date_str < cutoff:
            continue
        items.append(
            build_item(
                source,
                title=title,
                link=link,
                date_str=date_str,
                signal_type="release",
            )
        )
        if len(items) >= limit:
            break
    return items


def fetch_github_releases(source: dict, limit: int, cutoff: str) -> list[dict]:
    """github_releases 源：优先 JSON API（可用 GITHUB_TOKEN），失败回退 .atom。"""
    owner, repo = parse_atom_repo(source.get("url"))
    if owner and repo:
        try:
            return releases_via_api(source, owner, repo, limit, cutoff)
        except Exception as exc:  # API 限流/失败时退回 .atom
            logging.warning(
                "[%s] GitHub API 失败，回退 Atom：%s", source.get("id"), exc
            )
    return fetch_feed(source, limit, cutoff, signal_type="release")


def extract_text(html: str) -> str:
    """去掉 script/style 与标签，保留可见文本（作为 diff 基线，避免标记噪声误报）。"""
    html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_page_diff(source: dict, today: str) -> list[dict]:
    url = source["url"]
    resp = http_get(url)
    resp.raise_for_status()
    if resp.encoding is None or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding or "utf-8"
    digest = hashlib.sha256(extract_text(resp.text).encode("utf-8")).hexdigest()

    vendor = str(source.get("vendor") or source.get("id") or "unknown")
    state_key = str(source.get("id") or vendor)
    state = common.load_state(state_key) or {}
    if state.get("url") != url or not state.get("hash"):
        logging.info("[%s] 首次抓取（或 URL 变更），仅记录基线", source.get("id"))
        common.save_state(
            state_key, {"url": url, "hash": digest, "last_checked": common.utc_now_iso()}
        )
        return []
    if state.get("hash") == digest:
        state["last_checked"] = common.utc_now_iso()
        common.save_state(state_key, state)
        return []

    state.update(
        {
            "url": url,
            "hash": digest,
            "last_checked": common.utc_now_iso(),
            "last_changed": common.utc_now_iso(),
        }
    )
    common.save_state(state_key, state)
    link = f"{url}#{today}"
    return [
        build_item(
            source,
            title=f"{source.get('vendor')} 页面更新（{today}）",
            link=link,
            date_str=today,
            signal_type="changelog",
        )
    ]


def fetch_source(source: dict, limit: int, cutoff: str, today: str) -> list[dict]:
    stype = source.get("type")
    if stype == "rss":
        return fetch_feed(source, limit, cutoff, signal_type="changelog")
    if stype == "github_releases":
        return fetch_github_releases(source, limit, cutoff)
    if stype == "page_diff":
        return fetch_page_diff(source, today)
    raise ValueError(f"未知源类型：{stype!r}")


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="抓取 sources.yml 中的启用源")
    ap.add_argument(
        "--limit", type=int, default=5, help="每个源最多保留的条目数（默认 5）"
    )
    ap.add_argument(
        "--since-days",
        type=int,
        default=30,
        help="只保留最近 N 天内的条目（默认 30）",
    )
    return ap.parse_args(argv)


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args(argv)
    today = datetime.now(SHANGHAI).date().isoformat()
    cutoff = (
        datetime.now(SHANGHAI).date() - timedelta(days=args.since_days)
    ).isoformat()

    sources = common.enabled_sources()
    known_urls = set(common.load_existing_index())
    print(f"启用源 {len(sources)} 个（since {cutoff}，limit {args.limit}）")

    new_total = 0
    failures = []
    for source in sources:
        sid, stype = source.get("id"), source.get("type")
        try:
            items = fetch_source(source, args.limit, cutoff, today)
        except Exception as exc:  # 单个源失败不影响其他源
            logging.warning("源 %s 抓取失败：%s", sid, exc)
            failures.append(sid)
            continue
        new_count = 0
        for item in items:
            url = item["source_url"]
            if url in known_urls:  # 与既有数据及本轮内去重
                continue
            known_urls.add(url)
            if common.item_path(item["id"], item["date"]).exists():
                continue
            common.write_item(item)
            new_count += 1
        new_total += new_count
        print(f"  {sid} ({stype}): 命中 {len(items)}，新增 {new_count}")

    print(f"抓取完成：新增 {new_total} 条，失败源 {len(failures)} 个")
    if failures:
        print("  失败：" + ", ".join(failures))
    return 0


if __name__ == "__main__":
    sys.exit(main())
