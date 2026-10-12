"""Qt-free costume IDs shared by desktop and MCP; actions do not own identity."""
import math
import time

SKINS = {"default": "默认套装", "maimai": "麦麦套装"}


def validate_skin(character_id, skin_id):
    if skin_id not in SKINS or (character_id != "deepseek" and skin_id != "default"):
        raise ValueError("此角色不支持该皮肤")
    return skin_id


def settle_action(preferences):
    """A persisted deadline/target survives Agent and desktop restarts."""
    deadline = preferences.get("action_until", 0)
    if isinstance(deadline, (int, float)) and math.isfinite(deadline) and 0 < deadline <= time.time():
        target = preferences.pop("pending_skin_id", None)
        if preferences.get("character_id") == "deepseek" and target in SKINS:
            preferences.update(skin_id=target, deepseek_skin_id=target)
        preferences["action"] = "idle"
        preferences.pop("action_until", None)
        preferences.pop("action_animation", None)
    return preferences
