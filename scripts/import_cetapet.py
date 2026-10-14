"""把早期鲸鲸姿态装进本地仓库，并按动作名字整理到指定文件夹。"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.pet.cetapet import CATALOG, ACTIONS  # noqa: E402


def import_assets(source, destination, export=None):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    revision = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"], check=True,
                              capture_output=True, text=True).stdout.strip()
    if revision != CATALOG["commit"]:
        raise ValueError("请提供早期固定版本，不会覆盖其他参考仓库")
    subprocess.run(["git", "-C", str(source), "diff", "--quiet", "HEAD", "--",
                    "CetaPet/asset_library/move", "LICENSE", "README.md"], check=True)
    originals = source / "CetaPet" / "asset_library"
    paths = {row["file"] for row in CATALOG["actions"]}
    if {p.relative_to(originals).as_posix() for p in (originals / "move").rglob("*.png")} != paths:
        raise ValueError("动作清单与早期参考不一致")
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QPainter
    images = {}
    for key, row in ACTIONS.items():
        image = QImage(str(originals / row["file"]))
        if image.isNull() or not image.hasAlphaChannel() or image.width() > 192 or image.height() > 192:
            raise ValueError("姿态图无法按原像素装入固定画布")
        images[key] = image
    for row in CATALOG["actions"]:
        target = destination / "original" / "asset_library" / row["file"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(originals / row["file"], target)
    original_root = destination / "original"
    for name in ("LICENSE", "README.md"):
        shutil.copyfile(source / name, original_root / name)
    runtime = destination / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    entries = {}
    for key, image in images.items():
        # 共用 192×192 画布；不缩放、不按透明边逐帧裁切，原像素完整保留。
        page = QImage(192 * 12, 192, QImage.Format_RGBA8888)
        page.fill(Qt.transparent)
        painter = QPainter(page)
        painter.drawImage((192 - image.width()) // 2, 192 - image.height(), image)
        painter.end()
        filename = key + "-000.png"
        if not page.save(str(runtime / filename), "PNG"):
            raise OSError("鲸鲸姿态保存失败")
        entries[key] = {"frames": 1, "pages": [filename], "kind": "pose"}
    (runtime / "manifest.json").write_text(json.dumps({"cell_size": 192, "columns": 12,
        "frame_delay_ms": 80, "animations": entries}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if export is not None:
        export = Path(export).resolve()
        export.mkdir(parents=True, exist_ok=True)
        lines = ["# DeepSeek 娘早期姿态素材", "", "来源：" + CATALOG["repository"],
                 "固定版本：`" + CATALOG["commit"] + "`", "", "原始九张姿态 PNG，非序列动画。", "",
                 "| 动作 | 原始文件 | McPet 调用 |", "|---|---|---|"]
        for key, row in ACTIONS.items():
            folder = export / row["label"]
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / Path(row["file"]).name
            if target.exists() and target.read_bytes() != (originals / row["file"]).read_bytes():
                raise FileExistsError("分类文件夹已有不同素材，不覆盖：" + row["label"])
            shutil.copyfile(originals / row["file"], target)
            lines.append(f"| {row['label']} | {row['label']}/{target.name} | `{key}` |")
        (export / "动作索引.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        shutil.copyfile(source / "LICENSE", export / "LICENSE")
        shutil.copyfile(source / "README.md", export / "原仓库说明.md")
    return len(images)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / ".tmp-test-data/references/cetapet")
    parser.add_argument("--export", type=Path, help="按动作名分类的输出文件夹")
    args = parser.parse_args()
    count = import_assets(args.source, ROOT / "assets/cetapet", args.export)
    print(f"鲸鲸的 {count} 种姿态已经装好啦" + ("，分类文件夹也整理好了" if args.export else ""))


if __name__ == "__main__":
    main()
