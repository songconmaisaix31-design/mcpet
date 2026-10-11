"""Local companionship only: elapsed-time walking, short rests and screen bounds."""
from __future__ import annotations

import random
from PySide6.QtCore import QPoint, QRect, QSize


def clamp_position(point: QPoint, size: QSize, areas: list[QRect]) -> QPoint:
    """Qt global coordinates are logical pixels, including negative monitor origins."""
    if not areas:
        return point
    candidates = [QPoint(min(max(point.x(), a.left()), max(a.left(), a.right() - size.width() + 1)),
                         min(max(point.y(), a.top()), max(a.top(), a.bottom() - size.height() + 1)))
                  for a in areas]
    return min(candidates, key=lambda p: (p.x() - point.x()) ** 2 + (p.y() - point.y()) ** 2)


class RoamingBehavior:
    """Pause/resume retains phase; long event-loop stalls never teleport the pet."""
    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.phase = "idle"
        self.remaining = 8.0
        self.direction = 1
        self.speed = 28.0  # logical pixels / second, independent of timer frequency

    def advance(self, elapsed: float, *, paused: bool = False) -> tuple[float, str]:
        if paused:
            return 0.0, "idle"
        elapsed = min(max(elapsed, 0.0), 0.1)
        self.remaining -= elapsed
        if self.remaining <= 0:
            if self.phase == "walking":
                self.phase = "resting"
                self.remaining = self.rng.uniform(5, 10)
            else:
                self.phase = "walking"
                self.direction = self.rng.choice((-1, 1))
                self.remaining = self.rng.uniform(3, 6)
        if self.phase == "walking":
            return self.direction * self.speed * elapsed, "run-right" if self.direction > 0 else "run-left"
        return 0.0, "sleeping" if self.phase == "resting" else "idle"

    def turn(self) -> None:
        self.direction *= -1
