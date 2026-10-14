"""把鲸鲸已装载的所有动作录成透明 GIF，按套装与动作名整理。"""
from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image, ImageChops, ImageSequence
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from src.pet.characters import load_character
from src.pet.cetapet import ACTIONS as POSES
from src.pet.recordings import SIZES
from src.pet.skins import SKINS
from src.pet.spritesheet import ScaledAnimationFrames
from src.pet.window import resolve_frame_delay, resolve_frame_hold

LABELS = {"idle": "待机", "run-left": "向左跑", "run-right": "向右跑", "working": "忙碌工作",
          "thinking": "思考泡泡", "greet": "元气挥手", "happy": "开心庆祝", "error": "垂头叹气",
          "sleeping": "睡觉", "eating": "吃饭", "remind": "饭点提醒", "coupon": "领券",
          "balance": "余额", "progress": "任务进度", "waiting": "等待", "failed": "失败",
          "frying": "炸薯条", "outfit": "换上麦麦套装", "outfit-default": "换回默认套装",
          **{key: "早期·" + row["label"] for key, row in POSES.items()}}


def frame_image(pixmap) -> Image.Image:
    image = pixmap.toImage().convertToFormat(QImage.Format_RGBA8888)
    return Image.frombytes("RGBA", (image.width(), image.height()), bytes(image.constBits()),
                           "raw", "RGBA", image.bytesPerLine())


def clip_key(sheet, action):
    """同一组原页与方向只编码一次；工装中的复用也会被识别。"""
    row = sheet.row_for(action)
    if row not in sheet._paths:
        return clip_key(sheet._base_sheet, action)
    return sheet._paths[row], row == sheet._mirrored_row, sheet.frame_count(action)


def cadence(sheet, action) -> list[int]:
    delay = resolve_frame_delay(sheet, action)
    durations = [delay] * sheet.frame_count(action)
    durations[0] += resolve_frame_hold(sheet, action)
    return durations


def gif_cadence(durations) -> list[int]:
    # GIF 的单位是 10ms；累计取整，避免逐帧取整导致长动作加速或拖慢。
    elapsed, encoded, result = 0, 0, []
    for duration in durations:
        elapsed += duration
        end = int(elapsed / 10 + 0.5) * 10
        value = max(10, end - encoded)
        result.append(value)
        encoded += value
    return result


def indexed_frames(frames: list[Image.Image]) -> list[Image.Image]:
    # 每段共用调色板，避免每帧重新选色产生闪烁；0 留给透明。
    samples = Image.new("RGB", (64 * 10, 64 * ((len(frames) + 9) // 10)))
    for index, frame in enumerate(frames):
        sample = frame.copy()
        sample.thumbnail((64, 64))
        samples.paste(sample.convert("RGB"), ((index % 10) * 64, (index // 10) * 64))
    palette = samples.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    shifted_palette = [0, 0, 0] + palette.getpalette()[:255 * 3]
    result = []
    for frame in frames:
        indexed = frame.convert("RGB").quantize(palette=palette, dither=Image.Dither.NONE)
        # 默认未使用的 255 号色映射到可见黑色，防止 +1 溢出。
        indexed = indexed.point([i + 1 for i in range(255)] + [1])
        indexed.putpalette(shifted_palette)
        indexed.paste(0, mask=frame.getchannel("A").point(lambda a: 255 if a < 128 else 0))
        indexed.info["transparency"] = 0
        result.append(indexed)
    return result


def audit(path: Path, expected_duration: int, *, animated: bool) -> dict:
    with Image.open(path) as gif:
        duration, count, changed, transparent = 0, 0, False, False
        first = None
        for frame in ImageSequence.Iterator(gif):
            rgba = frame.convert("RGBA")
            if first is None:
                first = rgba.copy()
            else:
                changed |= ImageChops.difference(first, rgba).convert("RGB").getbbox() is not None
            transparent |= rgba.getchannel("A").getextrema()[0] == 0
            duration += frame.info.get("duration", 0)
            count += 1
        if duration != expected_duration or not transparent or gif.info.get("loop") != 0:
            raise ValueError("GIF 的时长、透明或循环没有对上：" + path.name)
        if animated and not changed:
            raise ValueError("多帧动作导出后没有实际变化：" + path.name)
        return {"encoded_frames": count, "changed": changed, "duration_ms": duration}


def encode(frames, durations, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    indexed = indexed_frames(frames)
    descriptor, raw = tempfile.mkstemp(suffix=".gif", dir=target.parent)
    os.close(descriptor)
    temporary = Path(raw)
    try:
        indexed[0].save(temporary, format="GIF", save_all=True, append_images=indexed[1:],
                        duration=durations, loop=0, disposal=2, transparency=0, optimize=False)
        result = audit(temporary, sum(durations), animated=len(frames) > 1)
        temporary.replace(target)
        return result
    finally:
        temporary.unlink(missing_ok=True)


def gallery(rows, path, *, desktop=False):
    cards = []
    for row in rows:
        folder = f"{SKINS[row['skin']]}/{row['label']}_{row['action']}" if desktop else f"{row['skin']}/{row['action']}"
        file = "放大显示512.gif" if desktop else "512.gif"
        kind = "静态姿态" if row["kind"] == "pose" else "循环动画"
        reuse = " · 复用 " + row["alias_of"] if row.get("alias_of") else ""
        note = " · " + row["note"] if row.get("note") else ""
        cards.append(f'<article><h2>{html.escape(SKINS[row["skin"]] + " · " + row["label"])}</h2>'
                     f'<img loading="lazy" width="256" height="256" src="{html.escape(folder + "/" + file)}">'
                     f'<p>{html.escape(row["action"])} · {kind} · {row["duration_ms"] / 1000:.2f} 秒{html.escape(reuse + note)}</p></article>')
    path.write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>鲸鲸的 GIF 小相册</title>'
                   '<style>body{background:#0d1117;color:#eee;font-family:Microsoft YaHei,sans-serif;margin:30px}'
                   'main{display:flex;flex-wrap:wrap;gap:18px}article{background:#20252b;padding:18px;width:280px}'
                   'h2{font-size:17px}p{font-size:13px}img{background:repeating-conic-gradient(#333 0% 25%,#444 0% 50%) 0/24px 24px}</style>'
                   '<h1>鲸鲸的 GIF 小相册 🐳</h1><p>原帧 192 像素，另备 512 像素放大显示版。早期姿态是静态图；复用项保留实际素材。'
                   'GIF 的颜色和透明度有限，原 PNG 图集不变。</p><main>' + "".join(cards) + '</main></html>\n', encoding="utf-8")


def export_folder(destination, output, rows):
    destination.mkdir(parents=True, exist_ok=True)
    pairs = []
    for row in rows:
        folder = destination / SKINS[row["skin"]] / f"{row['label']}_{row['action']}"
        for size in SIZES:
            source = output / row["skin"] / row["action"] / f"{size}.gif"
            target = folder / ("原尺寸192.gif" if size == 192 else "放大显示512.gif")
            if target.exists() and target.read_bytes() != source.read_bytes():
                raise FileExistsError("分类文件夹已有不同素材，不覆盖：" + row["label"])
            pairs.append((source, target))
    for source, target in pairs:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    shutil.copyfile(output / "index.json", destination / "index.json")
    note = (output / "SOURCE.md").read_text(encoding="utf-8")
    note = note.replace("../dsh-deepseek/SOURCE.md", "DSH-素材来源.md").replace("../cetapet/SOURCE.md", "CeTaPet-素材来源.md").replace("../CREDITS.md", "素材权利说明.md")
    (destination / "SOURCE.md").write_text(note, encoding="utf-8")
    gallery(rows, destination / "打开动作预览.html", desktop=True)
    lines = ["# 鲸鲸的全部 GIF 动作", "", "两套衣服各自分类；同名动作可能复用同一动画。原尺寸 192，512 为平滑放大。", "",
             "| 套装 | 动作 | 类型 | 一轮秒数 | 复用 |", "|---|---|---|---:|---|"]
    for row in rows:
        lines.append(f"| {SKINS[row['skin']]} | {row['label']} / `{row['action']}` | {'静态' if row['kind'] == 'pose' else '动画'} | {row['duration_ms'] / 1000:.2f} | {row.get('alias_of') or '独立'} {row.get('note', '')} |")
    (destination / "动作索引.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    sources = {"DSH-素材来源.md": ROOT / "assets/dsh-deepseek/SOURCE.md",
               "DSH-LICENSE": ROOT / "assets/dsh-deepseek/LICENSE",
               "额外动作-素材来源.md": ROOT / "assets/deepseek-actions/SOURCE.md",
               "素材权利说明.md": ROOT / "assets/CREDITS.md",
               "CeTaPet-素材来源.md": ROOT / "assets/cetapet/SOURCE.md",
               "CeTaPet-LICENSE": ROOT / "assets/cetapet/original/LICENSE",
               "CeTaPet-原仓库说明.md": ROOT / "assets/cetapet/original/README.md"}
    for name, source in sources.items():
        if source.is_file():
            shutil.copyfile(source, destination / name)


def record(output=ROOT / "assets/deepseek-recordings", export=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    source_note = ROOT / "assets/deepseek-recordings/SOURCE.md"
    if output.resolve() != source_note.parent.resolve():
        shutil.copyfile(source_note, output / "SOURCE.md")
    app = QApplication.instance() or QApplication([])
    rows, encoded = [], {}
    for skin in SKINS:
        sheet = load_character("deepseek", skin)
        for action in sheet.row_of:
            source_durations = cadence(sheet, action)
            durations = gif_cadence(source_durations)
            key = clip_key(sheet, action), tuple(durations)
            label = LABELS[action]
            row = {"skin": skin, "action": action, "label": label,
                   "kind": "pose" if sheet.frame_count(action) == 1 else "animation",
                   "source_frames": sheet.frame_count(action), "source_duration_ms": sum(source_durations),
                   "duration_ms": sum(durations), "native_size": 192, "sizes": list(SIZES),
                   "alias_of": encoded[key][0] if key in encoded else None, "files": {}}
            source_key, idle_key = clip_key(sheet, action), clip_key(sheet, "idle")
            if skin == "maimai" and action != "idle" and source_key[0] == idle_key[0]:
                row["note"] = "此套装复用穿装待机" + ("，左右镜像" if source_key[1] != idle_key[1] else "")
            for size in SIZES:
                target = output / skin / action / f"{size}.gif"
                if key in encoded:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    source, checks = encoded[key][1][size]
                    shutil.copyfile(source, target)
                else:
                    frames = [frame_image(frame) for frame in ScaledAnimationFrames(sheet, action, size, 1)]
                    checks = encode(frames, durations, target)
                    del frames
                row["files"][str(size)] = {**checks, "path": f"{skin}/{action}/{size}.gif"}
            if key not in encoded:
                encoded[key] = (f"{skin}/{action}", {size: (output / skin / action / f"{size}.gif", row["files"][str(size)]) for size in SIZES})
            rows.append(row)
            print(f"录好啦：{SKINS[skin]} / {label} ({row['source_frames']} 帧)", flush=True)
    result = {"character_id": "deepseek", "installed": True, "capture": "Qt rendered frames, complete cycle",
              "native_size": 192, "display_size": 512, "frame_delay_override_ms": os.environ.get("MCPET_FRAME_DELAY_MS"),
              "unique_clips": len(encoded), "actions": rows}
    (output / "index.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    gallery(rows, output / "index.html")
    if export is not None:
        export_folder(Path(export), output, rows)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path, help="按套装和动作中文名分类的文件夹")
    args = parser.parse_args()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    result = record(export=args.export)
    print(f"鲸鲸的 {len(result['actions'])} 项动作记录、{result['unique_clips']} 段独立素材已装进小相册啦")


if __name__ == "__main__":
    main()
