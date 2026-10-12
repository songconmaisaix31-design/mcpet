"""Trim existing video-derived RGBA pages; preserve the original import."""
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/maimai-actions"
DEST = ROOT / "assets/deepseek-actions"


def frames(state, start, stop):
    result = []
    for index in range(start, stop):
        with Image.open(SOURCE / f"{state}-{index // 12:03}.png") as page:
            frame = page.crop(((index % 12) * 192, 0, (index % 12 + 1) * 192, 192))
            # One fixed transform aligns the default dress's body/feet with the
            # existing DeepSeek atlas. No per-frame fitting or pose correction.
            cell = Image.new("RGBA", (192, 192))
            cell.paste(frame.resize((172, 172), Image.Resampling.LANCZOS), (22, 18))
            result.append(cell)
    return result


def pages(directory, name, sequence):
    directory.mkdir(parents=True, exist_ok=True)
    names = []
    for offset in range(0, len(sequence), 12):
        page = Image.new("RGBA", (2304, 192))
        for column, frame in enumerate(sequence[offset:offset + 12]):
            page.paste(frame, (column * 192, 0))
        filename = f"{name}-{offset // 12:03}.png"
        page.save(directory / filename)
        names.append(filename)
    return {"frames": len(sequence), "pages": names}


def gif(directory, name, sequence, loop=False):
    indexed = []
    for frame in sequence:
        image = frame.quantize(colors=255, method=Image.Quantize.FASTOCTREE)
        image.paste(255, mask=frame.getchannel("A").point(lambda a: 255 if a < 96 else 0))
        image.info["transparency"] = 255
        indexed.append(image)
    indexed[0].save(directory / f"{name}.gif", save_all=True, append_images=indexed[1:],
                    duration=80, disposal=2, transparency=255, optimize=False,
                    **({"loop": 0} if loop else {}))


def main():
    frying = frames("frying", 96, 126)  # 7.68–10.08s, stable basket after the faulty early motion.
    outfit = frames("outfit", 6, 54)  # 0.48–4.32s, remove empty lead and tail.
    idle = frames("outfit", 58, 71)   # 4.64–5.68s, clean front-facing blink, no effects/tail.
    animations = {}
    for name, sequence in (("frying", frying), ("outfit", outfit), ("outfit-default", outfit[::-1])):
        animations[name] = pages(DEST, name, sequence)
        gif(DEST, name, sequence, loop=name == "frying")
    manifest = {"cell_size": 192, "columns": 12, "frame_delay_ms": 80,
                "animations": animations, "character_id": "deepseek",
                "clips": {"frying": [7.68, 10.08], "outfit": [0.48, 4.32]},
                "fixed_transform": {"size": [172, 172], "offset": [22, 18]}}
    (DEST / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    skin = ROOT / "assets/deepseek-skins/maimai"
    entry = pages(skin, "idle", idle)
    idle[0].save(skin / "preview.png")
    gif(skin, "idle", idle, loop=True)
    states = ("idle", "run-left", "working", "thinking", "greet", "happy", "error", "sleeping", "eating")
    (skin / "manifest.json").write_text(json.dumps({"cell_size": 192, "columns": 12,
        "frame_delay_ms": 80, "preview": "preview.png", "skin_id": "maimai",
        "clip": [4.64, 5.68],
        "animations": {state: entry for state in states},
        "fallback": "All logical states reuse the dressed idle; separate dressed poses are unavailable."},
        indent=2) + "\n", encoding="utf-8")
    print({name: entry["frames"] for name, entry in animations.items()})


if __name__ == "__main__":
    main()
