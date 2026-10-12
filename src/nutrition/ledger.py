"""每日营养台账。

数据来源是麦当劳 MCP 的 list-nutrition-foods（真实调用），本地只做累加和留存。
台账存在 ~/.mcpet/nutrition.json，含个人饮食数据，已被 .gitignore 排除。

注意：本项目只做记录与提醒，不做任何医疗或营养建议——CONTEST_DECLARATION.md
里也有同样声明。
"""

from __future__ import annotations

import json
import os
import stat
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from .. import config
from ..mcd_mcp.brain import NutritionFact


@dataclass
class LedgerEntry:
    date: str
    meal_name: str
    energy_kcal: float = 0.0
    protein_g: float = 0.0
    fat_g: float = 0.0
    carb_g: float = 0.0
    sodium_mg: float = 0.0
    calcium_mg: float = 0.0
    note: str = ""
    quantity: float = 1.0

    @classmethod
    def from_fact(cls, fact: NutritionFact, date: str | None = None, *, quantity: float = 1) -> "LedgerEntry":
        if isinstance(quantity, bool):
            raise ValueError("quantity must be finite and positive")
        quantity = float(quantity)
        if not math.isfinite(quantity) or quantity <= 0:
            raise ValueError("quantity must be finite and positive")
        return cls(
            date=date or datetime.now().date().isoformat(),
            meal_name=fact.name,
            energy_kcal=fact.energy_kcal * quantity,
            protein_g=fact.protein_g * quantity,
            fat_g=fact.fat_g * quantity,
            carb_g=fact.carb_g * quantity,
            sodium_mg=fact.sodium_mg * quantity,
            calcium_mg=fact.calcium_mg * quantity,
            note=fact.note,
            quantity=quantity,
        )


class NutritionLedger:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else config.data_dir() / "nutrition.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: list[LedgerEntry] = self._load()

    def _load(self) -> list[LedgerEntry]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        entries = []
        for item in raw if isinstance(raw, list) else []:
            try:
                entries.append(LedgerEntry(**item))
            except TypeError:
                continue
        return entries

    def _save(self) -> None:
        temporary = self.path.with_suffix(".tmp")
        try:
            temporary.write_text(
                json.dumps([asdict(e) for e in self._entries], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
        try:
            os.chmod(self.path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass

    @property
    def entries(self) -> list[LedgerEntry]:
        return list(self._entries)

    def add(self, entry: LedgerEntry) -> LedgerEntry:
        self._entries.append(entry)
        try:
            self._save()
        except OSError:
            self._entries.pop()
            raise
        return entry

    def add_fact(self, fact: NutritionFact, date: str | None = None, *, quantity: float = 1) -> LedgerEntry:
        return self.add(LedgerEntry.from_fact(fact, date, quantity=quantity))

    def day(self, date: str | None = None) -> list[LedgerEntry]:
        target = date or datetime.now().date().isoformat()
        return [e for e in self._entries if e.date == target]

    def totals(self, date: str | None = None) -> dict[str, float]:
        entries = self.day(date)
        return {
            "energy_kcal": round(sum(e.energy_kcal for e in entries), 1),
            "protein_g": round(sum(e.protein_g for e in entries), 1),
            "fat_g": round(sum(e.fat_g for e in entries), 1),
            "carb_g": round(sum(e.carb_g for e in entries), 1),
            "sodium_mg": round(sum(e.sodium_mg for e in entries), 1),
            "calcium_mg": round(sum(e.calcium_mg for e in entries), 1),
            "items": len(entries),
        }

    def summary(self, date: str | None = None) -> str:
        totals = self.totals(date)
        if not totals["items"]:
            return "今天还没记账"
        return (
            f"今天记了 {int(totals['items'])} 项："
            f"约 {totals['energy_kcal']:.0f} kcal，"
            f"蛋白 {totals['protein_g']:.0f} g，"
            f"脂肪 {totals['fat_g']:.0f} g，"
            f"碳水 {totals['carb_g']:.0f} g，"
            f"钠 {totals['sodium_mg']:.0f} mg"
        )
