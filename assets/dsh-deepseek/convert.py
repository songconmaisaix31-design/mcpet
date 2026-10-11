"""Offline conversion only; runtime needs Qt, not FFmpeg or the DSH host.

Usage: WorkBuddy-python assets/dsh-deepseek/convert.py SOURCE_DIR FFMPEG
SOURCE_DIR contains the nine pinned public WebMs documented in SOURCE.md.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter

CLIPS = {
    "idle": "待机呼吸休闲", "run-left": "原地左转奔跑",
    "working": "工作状态-忙碌点按", "thinking": "工作状态-思考冒泡",
    "greet": "点击回应-元气挥手", "happy": "工作状态-雀跃庆祝",
    "error": "工作状态-垂头叹气冒汗", "sleeping": "原地小憩沉眠",
    "eating": "吃白饭",
}
UPSTREAM_SHA = "92662190cdd4dee05e38a5151584cc6254cd7a43"
SIZE = 192
COLUMNS = 12


def alpha_bounds(image):
    image = image.convertToFormat(QImage.Format_RGBA8888)
    data = bytes(image.constBits())
    table = bytes(255 if i > 32 else 0 for i in range(256))
    left, top, right, bottom = image.width(), image.height(), -1, -1
    for y in range(image.height()):
        alpha = data[y * image.bytesPerLine() + 3:(y + 1) * image.bytesPerLine():4].translate(table)
        start = alpha.find(b"\xff")
        if start >= 0:
            left, top = min(left, start), min(top, y)
            right, bottom = max(right, alpha.rfind(b"\xff")), y
    return None if right < 0 else [left, top, right, bottom]


def decode(ffmpeg, source, filters, width, height):
    process = subprocess.Popen([ffmpeg, "-v", "error", "-c:v", "libvpx-vp9", "-i", str(source),
                                "-an", "-vf", filters, "-pix_fmt", "rgba", "-f", "rawvideo", "-"],
                               stdout=subprocess.PIPE)
    try:
        while True:
            raw = process.stdout.read(width * height * 4)
            if not raw:
                break
            if len(raw) != width * height * 4:
                raise RuntimeError("partial decoded frame")
            yield QImage(raw, width, height, width * 4, QImage.Format_RGBA8888).copy()
    finally:
        process.stdout.close()
        if process.wait() != 0:
            raise RuntimeError("FFmpeg decode failed")


def main():
    source_dir, ffmpeg = Path(sys.argv[1]), sys.argv[2]
    destination = Path(__file__).resolve().parent
    audits = {}
    for state, name in CLIPS.items():
        bounds = [alpha_bounds(frame) for frame in decode(ffmpeg, source_dir / (name + ".webm"),
                                                        "format=rgba", 640, 360)]
        if any(bound is None for bound in bounds):
            raise RuntimeError(f"{state}: transparent source frame")
        audits[state] = bounds
        print(state, len(bounds), flush=True)
    # One global crop for every frame and action. Never normalize individual poses.
    union = [min(b[0] for seq in audits.values() for b in seq),
             min(b[1] for seq in audits.values() for b in seq),
             max(b[2] for seq in audits.values() for b in seq),
             max(b[3] for seq in audits.values() for b in seq)]
    side = max(360, union[2] - union[0] + 17)
    side += side % 2
    x = max(0, min(640 - side, (union[0] + union[2] - side) // 2))
    crop = [x, 0, side, 360]
    manifest = {"upstream_sha": UPSTREAM_SHA, "cell_size": SIZE, "columns": COLUMNS,
                "frame_delay_ms": 80, "source_union_alpha32": union, "fixed_crop": crop,
                "animations": {}}
    for state, name in CLIPS.items():
        source = source_dir / (name + ".webm")
        filters = f"fps=25/2,crop={side}:360:{x}:0,scale={SIZE}:{SIZE}:force_original_aspect_ratio=decrease:flags=lanczos,pad={SIZE}:{SIZE}:(ow-iw)/2:(oh-ih):color=black@0,format=rgba"
        frames = list(decode(ffmpeg, source, filters, SIZE, SIZE))
        atlas = QImage(COLUMNS * SIZE, ((len(frames) + COLUMNS - 1) // COLUMNS) * SIZE,
                       QImage.Format_RGBA8888)
        atlas.fill(Qt.transparent)
        painter = QPainter(atlas)
        for index, frame in enumerate(frames):
            painter.drawImage((index % COLUMNS) * SIZE, (index // COLUMNS) * SIZE, frame)
        painter.end()
        if not atlas.save(str(destination / (state + ".webp")), "WEBP", 100):
            raise RuntimeError("lossless WebP encoding failed")
        bounds = audits[state]
        manifest["animations"][state] = {"file": state + ".webp", "frames": len(frames),
            "source": name + ".webm", "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "native_frames": len(bounds), "native_bottom_range": max(b[3] for b in bounds) - min(b[3] for b in bounds),
            "native_center_range": max((b[0]+b[2])/2 for b in bounds) - min((b[0]+b[2])/2 for b in bounds),
            "native_first_bounds": bounds[0], "native_last_bounds": bounds[-1]}
        print(state, len(frames), (destination / (state + ".webp")).stat().st_size, flush=True)
    (destination / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
