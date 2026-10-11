"""Offline conversion only; runtime needs Qt, not FFmpeg or the DSH host.

Usage: WorkBuddy-python assets/dsh-deepseek/convert.py SOURCE_DIR FFMPEG
SOURCE_DIR contains the nine pinned public WebMs documented in SOURCE.md.
"""
import hashlib
import json
import subprocess
import sys
import struct
import zlib
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


def write_runtime_png(path, image):
    """RGBA PNG, filter zero, stored deflate. Avoid inflate/unfilter CPU at load.

    PNG chunks/CRC are the standard file format, not additional cache metadata.
    """
    rgba = image.convertToFormat(QImage.Format_RGBA8888)
    data, stride = bytes(rgba.constBits()), rgba.bytesPerLine()
    raw = b"".join(b"\0" + data[y * stride:y * stride + rgba.width() * 4]
                   for y in range(rgba.height()))
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR",struct.pack(">IIBBBBB",rgba.width(),rgba.height(),8,6,0,0,0))
                     + chunk(b"IDAT",zlib.compress(raw,0)) + chunk(b"IEND",b""))
    if QImage(str(path)).convertToFormat(QImage.Format_RGBA8888) != rgba:
        raise RuntimeError("runtime PNG pixels changed")


def maimai_cache():
    directory = Path(__file__).resolve().parent.parent / "longniang"
    image = QImage(str(directory / "spritesheet.webp"))
    if image.isNull() or not image.hasAlphaChannel():
        raise RuntimeError("invalid original maimai atlas")
    write_runtime_png(directory / "spritesheet-runtime.png", image)
    print(json.dumps({"same_pixels": True, "bytes": (directory / "spritesheet-runtime.png").stat().st_size}))


def write_pages(destination, state, atlas, count):
    """Lossless fixed rows, no resampling or individual frame trimming."""
    pages = []
    for page in range((count + COLUMNS - 1) // COLUMNS):
        filename = f"{state}-{page:03}.png"
        image = atlas.copy(0, page * SIZE, COLUMNS * SIZE, SIZE)
        if not image.save(str(destination / filename), "PNG"):
            raise RuntimeError("PNG page encoding failed")
        decoded = QImage(str(destination / filename))
        if decoded != image:
            raise RuntimeError("page pixels changed during lossless encoding")
        pages.append(filename)
    return pages


def repack():
    """Repack our existing pinned cache; no WebM, FFmpeg or network required.

    Retain the old atlases in the explicitly supplied evidence directory first.
    Every used frame is compared to its original before updating the manifest.
    """
    import shutil
    destination = Path(__file__).resolve().parent
    evidence = Path(sys.argv[2])
    evidence.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    if any(not entry["file"].endswith(".webp") for entry in manifest["animations"].values()):
        raise RuntimeError("repack requires the old full WebP atlases, not already paged assets")
    shutil.copyfile(destination / "manifest.json", evidence / "manifest-before.json")
    audit = []
    for state, entry in manifest["animations"].items():
        old_path = destination / entry["file"]
        shutil.copyfile(old_path, evidence / old_path.name)
        image = QImage(str(old_path))
        if image.isNull():
            raise RuntimeError("original cache cannot be decoded")
        pages = write_pages(destination, state, image, entry["frames"])
        for page, filename in enumerate(pages):
            decoded = QImage(str(destination / filename))
            for column in range(min(COLUMNS, entry["frames"] - page * COLUMNS)):
                original = image.copy(column * SIZE, page * SIZE, SIZE, SIZE)
                if decoded.copy(column * SIZE, 0, SIZE, SIZE) != original:
                    raise RuntimeError("fixed frame changed")
        if state == "idle":
            preview = image.copy(0, 0, SIZE, SIZE)
            if not preview.save(str(destination / "preview.png"), "PNG") or QImage(str(destination / "preview.png")) != preview:
                raise RuntimeError("preview pixels changed")
        entry["pages"], entry["file"] = pages, pages[0]
        audit.append({"state":state,"frames_compared":entry["frames"],"pages":len(pages),
                      "bytes":sum((destination/name).stat().st_size for name in pages)})
    manifest["preview"] = "preview.png"
    (destination / "manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (evidence / "pixel-audit.json").write_text(json.dumps(audit,indent=2),encoding="utf-8")
    # Only originals just backed up and verified above are removed.
    for row in audit:
        (destination / (row["state"] + ".webp")).unlink()
    print(json.dumps(audit),flush=True)


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
        pages = write_pages(destination, state, atlas, len(frames))
        if state == "idle":
            if not frames[0].save(str(destination / "preview.png"), "PNG"):
                raise RuntimeError("preview encoding failed")
        bounds = audits[state]
        manifest["animations"][state] = {"file": pages[0], "pages": pages, "frames": len(frames),
            "source": name + ".webm", "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "native_frames": len(bounds), "native_bottom_range": max(b[3] for b in bounds) - min(b[3] for b in bounds),
            "native_center_range": max((b[0]+b[2])/2 for b in bounds) - min((b[0]+b[2])/2 for b in bounds),
            "native_first_bounds": bounds[0], "native_last_bounds": bounds[-1]}
        print(state, len(frames), sum((destination / page).stat().st_size for page in pages), flush=True)
    manifest["preview"] = "preview.png"
    (destination / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--maimai"]:
        maimai_cache()
    elif sys.argv[1:2] == ["--repack"]:
        repack()
    else:
        main()
