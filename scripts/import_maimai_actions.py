"""Offline conversion of the two user-supplied MP4s to existing PNG pages.

Usage: python scripts/import_maimai_actions.py FRIES_MP4 OUTFIT_MP4 FFMPEG
Conversion only: requires numpy, opencv-python and Pillow. Runtime uses Qt only.
"""
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

SIZE, COLUMNS = 192, 12
DESTINATION = Path(__file__).resolve().parents[1] / "assets" / "maimai-actions"


def remove_background(rgb):
    """Remove border-connected neutral backdrop, retaining enclosed whites.

    Both supplied clips have a neutral, vertically graded backdrop. Estimate
    that gradient from the two margins; dark clothing and saturated hair/effects
    remain foreground. The source canvas is fixed throughout both animations.
    """
    pixels = rgb.astype(np.float32)
    backdrop = np.median(np.concatenate((pixels[:, :16], pixels[:, -16:]), axis=1), axis=1)
    distance = np.max(np.abs(pixels - backdrop[:, None]), axis=2)
    saturation = pixels.max(axis=2) - pixels.min(axis=2)
    candidate = ((saturation < 36) & ((distance < 48) | (pixels.min(axis=2) >= 75))).astype(np.uint8)
    # Padding connects every border, including areas isolated by special effects.
    connected = np.pad(candidate, 1, constant_values=1)
    cv2.floodFill(connected, None, (0, 0), 2)
    alpha = np.where(connected[1:-1, 1:-1] == 2, 0, 255).astype(np.uint8)
    # Soften only the foreground boundary before the single fixed downscale.
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0.6)
    return Image.fromarray(np.dstack((rgb, alpha)))


def convert(source, state, ffmpeg):
    process = subprocess.Popen(
        [ffmpeg, "-v", "error", "-i", str(source), "-an", "-vf", "fps=25/2",
         "-pix_fmt", "rgb24", "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
    pages, count, page = [], 0, Image.new("RGBA", (SIZE * COLUMNS, SIZE))
    try:
        while True:
            data = process.stdout.read(720 * 720 * 3)
            if not data:
                break
            if len(data) != 720 * 720 * 3:
                raise RuntimeError("Incomplete decoded frame")
            rgb = np.frombuffer(data, np.uint8).reshape(720, 720, 3)
            frame = remove_background(rgb).resize((SIZE, SIZE), Image.Resampling.LANCZOS)
            if not frame.getchannel("A").getbbox():
                raise RuntimeError("Empty foreground frame")
            page.paste(frame, ((count % COLUMNS) * SIZE, 0))
            count += 1
            if count % COLUMNS == 0:
                name = f"{state}-{len(pages):03}.png"
                page.save(DESTINATION / name)
                pages.append(name)
                page = Image.new("RGBA", (SIZE * COLUMNS, SIZE))
        if process.wait() != 0 or not count:
            raise RuntimeError("Video decode failed")
        if count % COLUMNS:
            name = f"{state}-{len(pages):03}.png"
            page.save(DESTINATION / name)
            pages.append(name)
    finally:
        process.stdout.close()
        if process.poll() is None:
            process.kill()
            process.wait()
    return {"source": source.name, "frames": count, "pages": pages}


def main():
    fries, outfit, ffmpeg = sys.argv[1:]
    cv2.setNumThreads(1)
    DESTINATION.mkdir(parents=True, exist_ok=True)
    animations = {state: convert(Path(source), state, ffmpeg)
                  for state, source in (("frying", fries), ("outfit", outfit))}
    manifest = {"cell_size": SIZE, "columns": COLUMNS, "frame_delay_ms": 80,
                "animations": animations}
    (DESTINATION / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({state: entry["frames"] for state, entry in animations.items()}))


if __name__ == "__main__":
    main()
