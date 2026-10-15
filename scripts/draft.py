#!/usr/bin/env python3
"""为 summary_zh 为空的条目生成中文摘要（OpenAI 兼容 /chat/completions）。

- 环境变量：LLM_API_KEY（必需，缺省则提示并退出 0，条目保持原样）、
  LLM_BASE_URL（默认 https://api.openai.com/v1）、LLM_MODEL（默认 gpt-4o-mini）。
- 摘要成功且 source_url 命中官方域名时才置 verified=true。
- 永远不打印 API Key。
"""
from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common

REQUEST_TIMEOUT = 60
MAX_SUMMARY_CHARS = 600

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


def build_messages(item: dict) -> list[dict]:
    system = "你是《AI 研发工作流周刊》的中文编辑，只依据给定条目写简洁、准确的事实性摘要。"
    user = f"""请为下面这条动态写一段 2-3 句的中文摘要。直接输出正文，不要标题、列表或任何前后缀。

编辑口径（必须遵守）：
{editorial_rules()}

条目信息：
- vendor: {item.get('vendor', '')}
- title: {item.get('title', '')}
- category: {item.get('category', '')}
- signal_type: {item.get('signal_type', '')}
- date: {item.get('date', '')}
- source_url: {item.get('source_url', '')}"""
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


def summarize(item: dict, base_url: str, api_key: str, model: str) -> str:
    """调用 /chat/completions 生成摘要；失败抛异常，由调用方处理。"""
    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": build_messages(item),
            "temperature": 0.2,
        },
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
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

    base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    sources = common.load_sources()

    summarized = verified = failed = 0
    for item in pending:
        try:
            summary = summarize(item, base_url, api_key, model)
        except Exception as exc:
            logging.warning("摘要失败 %s：%s", item.get("id"), exc)
            failed += 1
            continue
        if not summary:
            logging.warning("摘要为空 %s", item.get("id"))
            failed += 1
            continue
        item["summary_zh"] = summary
        summarized += 1
        if common.is_official_url(item.get("source_url") or "", sources):
            item["verified"] = True
            verified += 1
        else:
            logging.warning("域名非官方，verified 保持 false：%s", item.get("source_url"))
        common.write_item(item)

    print(
        f"摘要完成：共 {len(pending)} 条，成功 {summarized}"
        f"（其中已核实 {verified}），失败 {failed}。模型：{model}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
