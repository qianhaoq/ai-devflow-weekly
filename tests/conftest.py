"""把 scripts/ 与仓库根目录加入 sys.path，便于测试直接 import。"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
for p in (str(REPO_ROOT / "scripts"), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)
