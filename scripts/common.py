"""共享工具：加载 sources.yml、读写条目、生成 id/路径、官方域名校验。"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parent.parent
SOURCES_PATH = ROOT / "sources.yml"
SCHEMA_PATH = ROOT / "schema" / "item.schema.json"
ITEMS_DIR = ROOT / "data" / "items"
STATE_DIR = ROOT / "data" / "state"
WEEKLY_DIR = ROOT / "_weekly"
SITE_DATA_DIR = ROOT / "_data"

USER_AGENT = "ai-devflow-weekly/0.1 (+https://qianhaoq.github.io/ai-devflow-weekly/)"

CATEGORIES = ["code", "review", "test", "ci", "agent-platform", "pricing"]

CATEGORY_ZH = {
    "code": "代码 / IDE",
    "review": "代码评审",
    "test": "测试",
    "ci": "持续集成",
    "agent-platform": "智能体平台",
    "pricing": "定价变化",
}

# sources.yml 中源的 category -> 条目的 category（coding->code、testing->test）
CATEGORY_MAP = {
    "coding": "code",
    "testing": "test",
    "review": "review",
    "ci": "ci",
    "agent-platform": "agent-platform",
}


def utc_now_iso() -> str:
    """当前 UTC 时间，RFC 3339 格式（如 2026-10-15T08:00:00+00:00）。"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slugify(text: str) -> str:
    """vendor -> 文件名友好的 ASCII slug（小写、连字符分隔）。

    匹配 schema 的 id pattern（^[a-z0-9]+(?:-[a-z0-9]+)*-[0-9a-f]{10}$）：
    中文等非 ASCII 字符替换为连字符（"智谱 GLM" -> "glm"），全空时回退 "source"。
    """
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").strip().lower()).strip("-")
    return slug or "source"


def item_id(vendor: str, source_url: str) -> str:
    """条目 id：vendor-slug + '-' + sha1(source_url) 前 10 位十六进制。"""
    digest = hashlib.sha1((source_url or "").encode("utf-8")).hexdigest()[:10]
    return f"{slugify(vendor)}-{digest}"


def load_schema() -> dict:
    """加载 schema/item.schema.json。"""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_sources(path: Path | None = None) -> list[dict]:
    """读取 sources.yml 的全部源（顶层 excluded 一律忽略）；文件不存在时返回空列表。"""
    src = path or SOURCES_PATH
    if not src.exists():
        return []
    with src.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data.get("sources") or []


def enabled_sources(path: Path | None = None) -> list[dict]:
    """仅返回可用的源：`verified: false` 的源一律跳过（verified 缺省视为 true）。

    兼容未来改用 `enabled` 字段的写法（两者都为真才算启用）。
    """
    return [
        s
        for s in load_sources(path)
        if bool(s.get("verified", True)) and bool(s.get("enabled", True))
    ]


def _source_domain_entries(source: dict) -> list[str]:
    """单个源声明的官方域名条目；兼容 official_domain（单值，可带路径前缀）
    与 official_domains（列表）两种写法。"""
    domains: list[str] = []
    od = source.get("official_domain")
    if isinstance(od, str) and od.strip():
        domains.append(od.strip())
    domains.extend(str(d) for d in source.get("official_domains") or [])
    return domains


def all_official_domains(path: Path | None = None) -> set[str]:
    """所有源官方域名的并集（仅 host 部分，路径前缀被去掉）。"""
    domains: set[str] = set()
    for source in load_sources(path):
        for entry in _source_domain_entries(source):
            domains.add(entry.lower().split("/")[0])
    return domains


def official_domains_for_vendor(vendor: str, path: Path | None = None) -> set[str]:
    """按 vendor 名匹配的全部官方域名（大小写不敏感，仅 host 部分）。"""
    domains: set[str] = set()
    for source in load_sources(path):
        if (source.get("vendor") or "").lower() == (vendor or "").lower():
            for entry in _source_domain_entries(source):
                domains.add(entry.lower().split("/")[0])
    return domains


def is_official(host: str, domains: set[str] | list[str]) -> bool:
    """host 等于某域名，或为其子域名（如 docs.cursor.com <- cursor.com）。"""
    if not host:
        return False
    host = host.lower().rstrip(".")
    for domain in domains:
        domain = str(domain).lower().strip()
        if host == domain or host.endswith("." + domain):
            return True
    return False


def is_official_url(url: str, sources: list[dict]) -> bool:
    """source_url 是否命中任一源的官方域名。

    official_domain 形如 "cursor.com"（仅 host，允许子域名）或
    "github.com/anthropics"（host 为 github.com 且路径需以 /anthropics 开头）。
    """
    try:
        parsed = urlparse(url or "")
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    for source in sources or []:
        for entry in _source_domain_entries(source):
            entry = entry.lower().rstrip("/")
            if "/" in entry:
                domain_host, _, prefix = entry.partition("/")
                path_prefix = "/" + prefix.strip("/")
            else:
                domain_host, path_prefix = entry, None
            if not is_official(host, [domain_host]):
                continue
            if path_prefix is None or parsed.path.startswith(path_prefix):
                return True
    return False


def url_host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def iter_item_files(items_dir: Path | None = None) -> list[Path]:
    base = items_dir or ITEMS_DIR
    if not base.exists():
        return []
    return sorted(p for p in base.rglob("*.json") if p.is_file())


def load_items(items_dir: Path | None = None) -> list[dict]:
    """加载 data/items 下全部条目；单个文件损坏时告警并跳过。"""
    items: list[dict] = []
    for path in iter_item_files(items_dir):
        try:
            with path.open("r", encoding="utf-8") as fh:
                items.append(json.load(fh))
        except (OSError, json.JSONDecodeError) as exc:
            logging.warning("条目文件损坏，已跳过：%s（%s）", path, exc)
    return items


def load_existing_index(items_dir: Path | None = None) -> dict[str, str]:
    """source_url -> id 映射，用于与已存数据去重。"""
    return {
        item.get("source_url", ""): item.get("id", "")
        for item in load_items(items_dir)
    }


def item_path(item_id_: str, date: str, root: Path | None = None) -> Path:
    """条目应存放的路径：<root>/data/items/YYYY/MM/<id>.json（YYYY/MM 取自 date）。"""
    year, month = date.split("-")[:2]
    return (root or ROOT) / "data" / "items" / year / month / f"{item_id_}.json"


def write_item(item: dict, items_dir: Path | None = None) -> Path:
    """按规范化路径写入条目，自动创建父目录。"""
    base = items_dir or ITEMS_DIR
    year, month = str(item["date"]).split("-")[:2]
    path = base / year / month / f"{item['id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(item, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return path


def load_state(vendor: str, state_dir: Path | None = None) -> dict | None:
    path = (state_dir or STATE_DIR) / f"{slugify(vendor)}.json"
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def save_state(vendor: str, state: dict, state_dir: Path | None = None) -> None:
    path = (state_dir or STATE_DIR) / f"{slugify(vendor)}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
