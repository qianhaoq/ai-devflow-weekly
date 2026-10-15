#!/usr/bin/env python3
"""为 summary_zh 为空的条目生成中文摘要（OpenAI 兼容 /chat/completions）。

- 环境变量：LLM_API_KEY（必需，缺省则提示并退出 0，条目保持原样）、
  LLM_BASE_URL（默认 https://api.deepseek.com，DeepSeek 按量付费）、LLM_MODEL（默认 deepseek-flash）。
- 只把官方源原文（release note 摘录）喂给模型；取不到原文则跳过该条。
- AI 起草的条目一律保持 verified=false，由编辑审核后人工置 true。
- 关闭 DeepSeek thinking，限制 max_tokens；429/5xx/超时指数退避重试。
- 永远不打印 API Key。
"""
from __future__ import annotations

import html
import logging
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from validate import url_is_official

REQUEST_TIMEOUT = 60
MAX_SUMMARY_CHARS = 600
MAX_TOKENS = 400
MAX_EXCERPT_CHARS = 4000
MAX_ATTEMPTS = 3
BACKOFF_BASE = 2.0  # 秒：2, 4, ...
RETRY_STATUS = {429, 500, 502, 503, 504}

# docs/editorial.md 不可用时使用的口径兜底（与正式口径保持一致）
EDITORIAL_FALLBACK = """1. 只用官方源核实：仅陈述来自官方 changelog/releases/博客的事实。
2. 价格变化：没有前后定价快照对比，不得写“涨价/降价”。
3. 月付/年付切换：仅计费周期变化，标记为“计费周期变化”，不算涨价或降价。
4. beta/预览功能须标注。"""


def editorial_rules() -> str:
    """读取 docs/editorial.md 的编辑口径；读不到时用内置兜底。"""
    try:
        text = (common.ROOT / "docs" / "editorial.md").read_text(encoding="utf-8").strip()
        return text or EDITORIAL_FALLBACK
    except OSError:
        return EDITORIAL_FALLBACK


PROMPT_RULES = """硬性规则：
- 只使用下方「官方原文」中的信息，不得补充原文以外的任何事实、数字或推测。
- 只有同时给出「当前 price_snapshot」和可比的「上一次 price_snapshot」（同 vendor、同 plan、同币种）时，才可依据两者的差异描述价格变化；缺任何一个都绝不能声称涨价、降价或任何价格变化。
- 月付/年付切换只能描述为“计费周期变化”，不得说成涨价或降价。"""


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw or "")
    text = html.unescape(re.sub(r"(?s)<[^>]+>", " ", raw))
    return re.sub(r"\s+", " ", text).strip()


def source_excerpt(item: dict, fetch=None) -> str:
    """官方 release note 原文摘录：优先用条目自带文本，否则抓 source_url。失败返回空串。"""
    text = (item.get("source_excerpt") or "").strip()
    m = re.match(r"https://github\.com/([^/]+)/([^/]+)/releases/tag/([^?#]+?)/?$", item.get("source_url") or "")
    if not text and m:
        # GitHub release：取 API 的 release 正文，而不是带导航/登录控件的整页 HTML
        try:
            api = f"https://api.github.com/repos/{m[1]}/{m[2]}/releases/tags/{quote(m[3], safe='')}"  # tag 可含 /（如 sdk/v1）
            gh_headers = {"User-Agent": common.USER_AGENT, "Accept": "application/vnd.github+json"}
            if os.environ.get("GITHUB_TOKEN"):
                gh_headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
            resp = (fetch or (lambda u: requests.get(u, timeout=REQUEST_TIMEOUT, headers=gh_headers)))(api)
            resp.raise_for_status()
            text = (resp.json().get("body") or "").strip()
        except Exception as exc:
            logging.warning("取 release 正文失败 %s：%s", item.get("id"), exc)
            return ""
    if not text and item.get("source_url") and not m:
        try:
            getter = fetch or (lambda u: requests.get(u, timeout=REQUEST_TIMEOUT, headers={"User-Agent": common.USER_AGENT}))
            resp = getter(item["source_url"])
            resp.raise_for_status()
            raw = resp.text
            body = re.search(r"(?is)<(main|article)[^>]*>(.*?)</\1>", raw)  # 优先正文区，去掉导航
            text = html_to_text(body.group(2) if body else raw)
        except Exception as exc:  # 网络错误：跳过该条，不让模型凭空写
            logging.warning("取原文失败 %s：%s", item.get("id"), exc)
            text = ""
    return text[:MAX_EXCERPT_CHARS]


def _captured(snap: dict) -> str:
    return str((snap or {}).get("captured_at") or "")


def previous_snapshot(item: dict, items: list[dict]) -> dict | None:
    """同 vendor+plan+币种、captured_at 严格早于当前快照的最近一次观测；没有则 None。
    按 price_snapshot.captured_at（采集时间）排序，而不是条目发布日期。"""
    cur = item.get("price_snapshot")
    if not isinstance(cur, dict) or not _captured(cur):
        return None
    key = (item.get("vendor"), cur.get("plan"), str(cur.get("currency") or "").lower())
    best = None
    for other in items:
        snap = other.get("price_snapshot") if isinstance(other, dict) else None
        if other is item or not isinstance(snap, dict) or not _captured(snap):
            continue
        if (other.get("vendor"), snap.get("plan"), str(snap.get("currency") or "").lower()) != key:
            continue
        if _captured(snap) >= _captured(cur):
            continue
        if best is None or _captured(snap) > _captured(best):
            best = snap
    return best


def build_messages(item: dict, excerpt: str) -> list[dict]:
    system = "你是《AI 研发工作流周刊》的中文编辑，只依据给定的官方原文写简洁、准确的事实性摘要。"
    snapshot = item.get("price_snapshot")
    prev = item.get("_previous_price_snapshot")
    if snapshot and prev:
        price_info = f"当前 {snapshot}；上一次 {prev}（可比，可据此描述价格变化）"
    elif snapshot:
        price_info = f"当前 {snapshot}；无可比的上一次快照（不得写任何价格变化）"
    else:
        price_info = "无（不得写任何价格变化）"
    user = f"""请为下面这条动态写一段 2-3 句的中文摘要。直接输出正文，不要标题、列表或任何前后缀。

{PROMPT_RULES}

编辑口径（必须遵守）：
{editorial_rules()}

条目信息：
- vendor: {item.get('vendor', '')}
- title: {item.get('title', '')}
- category: {item.get('category', '')}
- signal_type: {item.get('signal_type', '')}
- date: {item.get('date', '')}
- source_url: {item.get('source_url', '')}
- price_snapshot: {price_info}

官方原文（摘录，唯一信息来源）：
<<<
{excerpt}
>>>"""
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

# DeepSeek 按量付费（OpenAI 兼容）；空字符串（如未配置的 Actions vars）也回落到默认值
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-flash"  # 2026-10-15 GET /models 实测：deepseek-flash、deepseek-v4-pro；flash 最便宜


def strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


def post_with_retry(url: str, *, post=None, sleep=time.sleep, **kwargs):
    """POST；429/5xx/超时/连接错误按指数退避重试，最多 MAX_ATTEMPTS 次。"""
    post = post or requests.post
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = post(url, **kwargs)
        except (requests.Timeout, requests.ConnectionError) as exc:
            if attempt == MAX_ATTEMPTS:
                raise
            logging.warning("LLM 请求失败（%s），第 %d 次重试", type(exc).__name__, attempt)
        else:
            if resp.status_code not in RETRY_STATUS or attempt == MAX_ATTEMPTS:
                resp.raise_for_status()
                return resp
            logging.warning("LLM 返回 HTTP %s，第 %d 次重试", resp.status_code, attempt)
        sleep(BACKOFF_BASE * (2 ** (attempt - 1)))
    raise RuntimeError("unreachable")


def build_payload(item: dict, excerpt: str, model: str) -> dict:
    return {
        "model": model,
        "messages": build_messages(item, excerpt),
        "temperature": 0.2,
        "max_tokens": MAX_TOKENS,
        "thinking": {"type": "disabled"},  # DeepSeek：默认开启 thinking，摘要不需要
    }


def summarize(item: dict, base_url: str, api_key: str, model: str, excerpt: str, post=None, sleep=time.sleep) -> str:
    """调用 /chat/completions 生成摘要；失败抛异常，由调用方处理。"""
    resp = post_with_retry(
        f"{base_url}/chat/completions",
        post=post,
        sleep=sleep,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=build_payload(item, excerpt, model),
        timeout=REQUEST_TIMEOUT,
    )
    choices = resp.json().get("choices") or [{}]
    content = ((choices[0] or {}).get("message") or {}).get("content") or ""
    return strip_code_fence(content)[:MAX_SUMMARY_CHARS]


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    items = common.load_items()
    pending = [it for it in items if isinstance(it, dict) and not (it.get("summary_zh") or "").strip()]
    if not pending:
        print("没有待起草摘要的条目。")
        return 0

    api_key = os.environ.get("LLM_API_KEY")
    if not api_key:
        print(
            f"提示：未设置 LLM_API_KEY，跳过 {len(pending)} 条摘要"
            "（summary_zh 保持为空，verified 保持 false）。"
        )
        return 0

    base_url = (os.environ.get("LLM_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    model = os.environ.get("LLM_MODEL") or DEFAULT_MODEL
    official = common.enabled_sources()

    summarized = skipped = failed = 0
    for item in pending:
        if not url_is_official(item.get("source_url") or "", official):
            logging.warning("source_url 不属于已启用的官方源，跳过：%s", item.get("source_url"))
            skipped += 1
            continue
        excerpt = source_excerpt(item)
        if not excerpt:
            logging.warning("无官方原文可用，跳过 %s", item.get("id"))
            skipped += 1
            continue
        try:
            ctx = dict(item, _previous_price_snapshot=previous_snapshot(item, items))
            summary = summarize(ctx, base_url, api_key, model, excerpt)
        except Exception as exc:
            logging.warning("摘要失败 %s：%s", item.get("id"), exc)
            failed += 1
            continue
        if not summary:
            logging.warning("摘要为空 %s", item.get("id"))
            failed += 1
            continue
        item["summary_zh"] = summary
        item["verified"] = False  # AI 起草，待编辑审核后人工置 true
        summarized += 1
        common.write_item(item)

    print(
        f"摘要完成：共 {len(pending)} 条，成功 {summarized}"
        f"（verified 均为 false，待编辑审核），跳过 {skipped}，失败 {failed}。模型：{model}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
