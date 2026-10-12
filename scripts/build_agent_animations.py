"""Offline export of existing fixed frames as Agent-readable animated resources."""
import json
from pathlib import Path
from PIL import Image


def main():
    directory = Path(__file__).resolve().parents[1] / "assets/maimai-actions"
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    for state, entry in manifest["animations"].items():
        frames = []
        for index in range(entry["frames"]):
            with Image.open(directory / entry["pages"][index // 12]) as page:
                frame = page.crop(((index % 12) * 192, 0, (index % 12 + 1) * 192, 192)).convert("RGBA")
            indexed = frame.quantize(colors=255, method=Image.Quantize.FASTOCTREE)
            indexed.paste(255, mask=frame.getchannel("A").point(lambda value: 255 if value < 96 else 0))
            indexed.info["transparency"] = 255
            frames.append(indexed)
        options = {"loop": 0} if state == "frying" else {}
        frames[0].save(directory / f"{state}.gif", save_all=True, append_images=frames[1:],
                       duration=80, disposal=2, transparency=255, optimize=False, **options)
        with Image.open(directory / f"{state}.gif") as decoded:
            # GIF encoders merge visually identical frames and add their time.
            duration = 0
            for index in range(decoded.n_frames):
                decoded.seek(index)
                duration += decoded.info["duration"]
            assert duration == entry["frames"] * 80
            print(state, "source_frames", len(frames), "gif_frames", decoded.n_frames,
                  "duration_ms", duration)


if __name__ == "__main__":
    main()
