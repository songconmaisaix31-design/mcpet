"""下单护栏。

设计原则：护栏是默认路径的一部分，不是可以一键跳过的选项。
每次真实下单前必须：①展示摘要并拿到显式确认；②通过金额上限；③通过每日次数上限。
所有下单（含演练）都写本机审计日志，出问题可追溯、可一键撤单。
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from .. import config

DEFAULT_MAX_AMOUNT_CENTS = 10_000  # 单笔 100 元
DEFAULT_MAX_ORDERS_PER_DAY = 3


class GuardViolation(RuntimeError):
    """护栏拒绝。UI 必须把原因原样展示给用户，不能吞掉。"""


@dataclass
class GuardLimits:
    max_amount_cents: int = DEFAULT_MAX_AMOUNT_CENTS
    max_orders_per_day: int = DEFAULT_MAX_ORDERS_PER_DAY


@dataclass
class OrderAuditEntry:
    created_at: str
    tool: str
    store: str
    items: str
    amount_cents: int
    order_no: str = ""
    pay_url: str = ""
    dry_run: bool = False
    status: str = "placed"
    note: str = ""


def format_amount(cents: int) -> str:
    return f"{cents / 100:.2f}"


def to_cents(value: object) -> int:
    """把 MCP 返回的价格归一到「分」。

    2026-10-10 实测：calculate-price 返回的价格字段单位是**分**——
    中杯冰美式 `originalPrice: 1900` 就是 19.00 元，`price: 990` 是 9.90 元。
    所以整数直接当分用。

    为兼容其它工具可能返回「元」的情况：带小数点的数字或字符串按元换算。
    """
    if value is None or isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value)) if value.is_integer() else int(round(value * 100))
    text = str(value).strip().replace("¥", "").replace("元", "").replace(",", "")
    if not text:
        return 0
    try:
        number = float(text)
    except ValueError:
        return 0
    return int(round(number)) if number.is_integer() else int(round(number * 100))


class OrderGuard:
    """下单护栏 + 本机审计台账。"""

    def __init__(self, limits: GuardLimits | None = None, audit_path: Path | None = None):
        self.limits = limits or GuardLimits()
        self.audit_path = Path(audit_path) if audit_path else config.data_dir() / "order-audit.json"
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: list[OrderAuditEntry] = self._load()

    # ---------- 审计台账 ----------

    def _load(self) -> list[OrderAuditEntry]:
        if not self.audit_path.exists():
            return []
        try:
            raw = json.loads(self.audit_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        entries = []
        for item in raw if isinstance(raw, list) else []:
            try:
                entries.append(OrderAuditEntry(**item))
            except TypeError:
                continue
        return entries

    def _save(self) -> None:
        payload = [asdict(entry) for entry in self._entries]
        self.audit_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        try:
            os.chmod(self.audit_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
        except OSError:
            pass  # Windows 上 chmod 支持有限，失败不影响功能

    @property
    def entries(self) -> list[OrderAuditEntry]:
        return list(self._entries)

    def orders_today(self) -> list[OrderAuditEntry]:
        today = datetime.now().date().isoformat()
        return [
            entry
            for entry in self._entries
            if entry.created_at[:10] == today and entry.status in {"placed", "dry_run_skipped"}
        ]

    # ---------- 校验 ----------

    def check(self, amount_cents: int) -> None:
        if amount_cents <= 0:
            raise GuardViolation("金额无效（≤0），拒绝下单。")
        if amount_cents > self.limits.max_amount_cents:
            raise GuardViolation(
                f"单笔金额 {format_amount(amount_cents)} 元超过上限 "
                f"{format_amount(self.limits.max_amount_cents)} 元，已拒绝。"
            )
        placed = [e for e in self.orders_today() if e.status == "placed"]
        if len(placed) >= self.limits.max_orders_per_day:
            raise GuardViolation(
                f"今日已下单 {len(placed)} 次，达到上限 "
                f"{self.limits.max_orders_per_day} 次，已拒绝。"
            )

    def record(self, entry: OrderAuditEntry) -> None:
        self._entries.append(entry)
        self._save()

    def mark_cancelled(self, order_no: str) -> bool:
        for entry in self._entries:
            if entry.order_no and entry.order_no == order_no:
                entry.status = "cancelled"
                entry.note = f"于 {datetime.now().isoformat(timespec='seconds')} 撤单"
                self._save()
                return True
        return False
