"""本机 GIF 小相册；只读资源，不加载 Qt、不启动界面。"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re

ROOT = Path(os.environ.get("MCPET_RECORDINGS_DIR", Path(__file__).resolve().parents[2] / "assets/deepseek-recordings"))
SIZES = (192, 512)


def catalog() -> dict:
    path = ROOT / "index.json"
    if not path.is_file():
        return {"character_id": "deepseek", "actions": [], "installed": False}
    return json.loads(path.read_text(encoding="utf-8"))


def entry(skin: str, action: str) -> dict | None:
    if skin not in {"default", "maimai"} or not re.fullmatch(r"[a-z0-9_-]+", action):
        raise ValueError("鲸鲸的小相册里没有这个动作哦")
    return next((row for row in catalog()["actions"] if row["skin"] == skin and row["action"] == action), None)


def image_path(skin: str, action: str, size: int = 512) -> Path:
    if size not in SIZES or entry(skin, action) is None:
        raise ValueError("这张 GIF 还没有录好哦")
    path = ROOT / skin / action / f"{size}.gif"
    if not path.is_file():
        raise FileNotFoundError("鲸鲸的 GIF 文件不见啦，请重新运行录制命令")
    return path


def info(skin: str, action: str) -> dict | None:
    row = entry(skin, action)
    if row is None or not (ROOT / skin / action / "512.gif").is_file():
        return None
    return {"uri": f"mcpet://recording/deepseek/{skin}/{action}/512", "mime_type": "image/gif",
            "kind": row["kind"], "label": row["label"], "duration_seconds": row["duration_ms"] / 1000,
            "native_size": 192, "display_size": 512, "alias_of": row.get("alias_of"),
            "note": row.get("note", ""),
            "rendering": "鲸鲸的 GIF 小相册；512 像素由原帧放大，宿主支持图像资源时可展示"}
