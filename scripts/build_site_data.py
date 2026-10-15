#!/usr/bin/env python3
"""把 data/items 下全部条目合并为 _data/items.json（按日期倒序），供 Jekyll
site.data.items 使用（index.html 列表页）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common


def main() -> int:
    items = common.load_items()
    items.sort(
        key=lambda it: (str(it.get("date") or ""), str(it.get("id") or "")),
        reverse=True,
    )
    common.SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = common.SITE_DATA_DIR / "items.json"
    out.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已写入 {out.relative_to(common.ROOT)}（{len(items)} 条）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
