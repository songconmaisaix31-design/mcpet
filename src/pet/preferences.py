"""Independent machine-local pet preferences; never reads credentials or ledgers."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from .skins import settle_action


class PetPreferences:
    def __init__(self, path: Path | None = None):
        self.path = path or (Path(os.environ.get("MCPET_DATA_DIR") or Path.home() / ".mcpet") / "pet-preferences.json")
        self.error: str | None = None

    def load(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return settle_action(data) if isinstance(data, dict) else {}
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            self.error = "无法读取桌宠偏好，使用默认值"
            return {}

    def save(self, data: dict) -> bool:
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                             prefix="pet-", suffix=".tmp", delete=False) as stream:
                temporary = stream.name
                json.dump(data, stream, ensure_ascii=False)
            os.replace(temporary, self.path)
            self.error = None
            return True
        except OSError:
            self.error = "无法保存桌宠偏好"
            return False
        finally:
            if temporary and Path(temporary).exists():
                try:
                    Path(temporary).unlink(missing_ok=True)
                except OSError:
                    pass
