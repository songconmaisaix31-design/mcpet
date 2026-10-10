"""每日定时调度。

为什么自己写：CeTaPet 只有「固定周期待机轮转」（240s/30s/30s），那是相对计时，
不是真实时钟；longniang 和 LLMPET 也都没有按钟点触发的能力。11:30 提醒必须
按真实时间触发，所以这一层是新写的。

休眠/唤醒处理：不做「精确补发历史」，而是每次 tick 重新求值——机器睡过了 11:30，
醒来后第一次 tick 会触发，并带 late=True 让 UI 改口说「刚才该吃饭了」。
超过 grace_minutes 就放弃补触发（否则第二天开机被一堆过期提醒轰炸）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from PySide6.QtCore import QObject, QTimer, Signal


@dataclass
class DailyTask:
    name: str
    hour: int
    minute: int
    callback: Callable[[bool], None] | None = None
    grace_minutes: int = 120
    late_after_minutes: int = 5
    last_fired: str | None = field(default=None)

    def target(self, now: datetime) -> datetime:
        return now.replace(hour=self.hour, minute=self.minute, second=0, microsecond=0)


class DailySchedule:
    """纯逻辑，不依赖 Qt，可直接单测。"""

    def __init__(self, tasks: list[DailyTask] | None = None):
        self.tasks: list[DailyTask] = tasks or []

    def add(self, task: DailyTask) -> DailyTask:
        self.tasks.append(task)
        return task

    def due(self, now: datetime) -> list[tuple[DailyTask, bool]]:
        """返回 [(任务, 是否迟到)]。会顺带把「太晚以至于放弃」的任务标记为已触发。"""
        today = now.date().isoformat()
        result: list[tuple[DailyTask, bool]] = []
        for task in self.tasks:
            if task.last_fired == today:
                continue
            target = task.target(now)
            if now < target:
                continue
            delta_minutes = (now - target).total_seconds() / 60.0
            if delta_minutes > task.grace_minutes:
                task.last_fired = today
                continue
            result.append((task, delta_minutes > task.late_after_minutes))
        return result

    def mark_fired(self, task: DailyTask, now: datetime) -> None:
        task.last_fired = now.date().isoformat()

    def fire(self, now: datetime) -> list[tuple[DailyTask, bool]]:
        fired: list[tuple[DailyTask, bool]] = []
        for task, late in self.due(now):
            self.mark_fired(task, now)
            if task.callback:
                task.callback(late)
            fired.append((task, late))
        return fired


class QtDailyScheduler(QObject):
    """Qt 适配器：用 QTimer 驱动 DailySchedule。"""

    fired = Signal(str, bool)  # task.name, late

    def __init__(self, schedule: DailySchedule, interval_ms: int = 30_000, parent: QObject | None = None):
        super().__init__(parent)
        self.schedule = schedule
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._tick)
        self._now_fn: Callable[[], datetime] = datetime.now

    def start(self) -> None:
        self._tick()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        for task, late in self.schedule.fire(self._now_fn()):
            self.fired.emit(task.name, late)
