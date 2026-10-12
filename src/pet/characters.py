"""Bundled characters. No downloads, host, model calls or account access."""
from pathlib import Path

from .spritesheet import AnimationSheet, SpriteLoadError, SpriteSheet

CHARACTER_IDS = ("maimai", "deepseek")
ASSETS = Path(__file__).resolve().parents[2] / "assets"


def character_name(character_id: str) -> str:
    try:
        return {"maimai": "麦麦", "deepseek": "DeepSeek 娘"}[character_id]
    except (KeyError, TypeError) as exc:
        raise SpriteLoadError("未知桌宠角色") from exc


def load_character(character_id: str) -> SpriteSheet:
    character_name(character_id)
    if character_id == "deepseek":
        return AnimationSheet(ASSETS / "dsh-deepseek")
    directory = ASSETS / "longniang"
    try:
        runtime = directory / "spritesheet-runtime.png"
        sheet = SpriteSheet.load(runtime if runtime.exists() else directory / "spritesheet.webp", pet_json=directory / "pet.json",
                                 rows_json=directory / "sprite-rows.json")
        if getattr(sheet, "validation_issues", None):
            raise SpriteLoadError("麦麦图集校验失败")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise SpriteLoadError("无法加载麦麦素材") from exc
    sheet.meta["character_id"] = "maimai"
    return AnimationSheet(ASSETS / "maimai-actions", base_sheet=sheet)
