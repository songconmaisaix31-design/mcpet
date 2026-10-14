"""早期鲸鲸姿态小衣柜；只读取明确导入的本地素材，不联网。"""
import json
import os
from pathlib import Path

CATALOG_DIR = Path(__file__).resolve().parents[2] / "assets" / "cetapet"
ROOT = Path(os.environ.get("MCPET_CETAPET_DIR", CATALOG_DIR))
CATALOG = json.loads((CATALOG_DIR / "actions.json").read_text(encoding="utf-8"))
ACTIONS = {"ceta_" + row["id"]: row for row in CATALOG["actions"]}


def pose_path(action):
    if action not in ACTIONS:
        raise ValueError("鲸鲸没有这个姿态哦")
    return ROOT / "original" / "asset_library" / ACTIONS[action]["file"]


def require_pose(action):
    path = pose_path(action)
    if not path.is_file() or not (ROOT / "runtime" / "manifest.json").is_file():
        raise ValueError("这套姿态还没装好，先导入早期鲸鲸素材吧")
    return path
