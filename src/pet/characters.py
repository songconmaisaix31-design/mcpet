"""Bundled characters. No downloads, host, model calls or account access."""
from pathlib import Path

from .spritesheet import AnimationSheet, SpriteLoadError, SpriteSheet
from .skins import validate_skin
from .identity import CHARACTER_NAMES

CHARACTER_IDS = tuple(CHARACTER_NAMES)
ASSETS = Path(__file__).resolve().parents[2] / "assets"


def character_name(character_id: str) -> str:
    try:
        return CHARACTER_NAMES[character_id]
    except (KeyError, TypeError) as exc:
        raise SpriteLoadError("未知桌宠角色") from exc


def load_character(character_id: str, skin_id: str = "default") -> SpriteSheet:
    character_name(character_id)
    validate_skin(character_id, skin_id)
    if character_id == "deepseek":
        base = AnimationSheet(ASSETS / ("dsh-deepseek" if skin_id == "default" else "deepseek-skins/maimai"))
        sheet = AnimationSheet(ASSETS / "deepseek-actions", base_sheet=base)
        sheet.meta.update(character_id="deepseek", skin_id=skin_id)
        return sheet
    directory = ASSETS / "longniang"
    try:
        runtime = directory / "spritesheet-runtime.png"
        sheet = SpriteSheet.load(runtime if runtime.exists() else directory / "spritesheet.webp", pet_json=directory / "pet.json",
                                 rows_json=directory / "sprite-rows.json")
        if getattr(sheet, "validation_issues", None):
            raise SpriteLoadError("ChatGPT 娘的图集没对上，先帮我检查一下素材吧。")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise SpriteLoadError("ChatGPT 娘的衣柜打不开啦，请检查素材文件。") from exc
    sheet.meta["character_id"] = "maimai"
    return AnimationSheet(ASSETS / "maimai-actions", base_sheet=sheet)
