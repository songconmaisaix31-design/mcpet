"""Qt adapter for the shared headless daily schedule."""
from datetime import datetime
from typing import Callable
from PySide6.QtCore import QObject, QTimer, Signal
from .core import DailySchedule, DailyTask


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
