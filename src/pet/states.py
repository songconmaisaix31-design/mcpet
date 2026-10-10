"""状态词表、优先级与 oneshot 衰减。

思路移植自 LLMPET 的 shared/states.js：多个事件源同时往宠物身上打状态时，
用「优先级高的赢」做聚合；一次性状态（提醒、报错）给一个 TTL，时间到了自己
衰减回 idle，不会永久占着表情。
"""

from __future__ import annotations

import time

# 优先级：数字大的赢
STATE_PRIORITY: dict[str, int] = {
    "error": 8,
    "remind": 7,      # 11:30 该吃饭了
    "coupon": 6,      # 领券汇报
    "waiting": 5,     # 等你点确认
    "eating": 4,
    "working": 3,
    "thinking": 2,
    "happy": 2,
    "greet": 2,
    "idle": 1,
    "sleeping": 0,
}

# 一次性状态及其存活时长（毫秒）。waiting 不在里面——它是「等你」，必须常驻。
ONESHOT_TTL_MS: dict[str, int] = {
    "remind": 90_000,
    "coupon": 60_000,
    "error": 45_000,
    "happy": 8_000,
    "greet": 6_000,
}

# 我们自己的目标图集行定义（麦当劳原创素材按此规格生产）
TARGET_ROWS: tuple[str, ...] = (
    "idle",
    "working",
    "thinking",
    "eating",
    "happy",
    "greet",
    "remind",
    "coupon",
    "waiting",
    "failed",
    "run-right",
    "run-left",
)

# 占位素材（龙娘图集）只有 11 行，且没有 eating / coupon 这类动作。
# 这里列出「我们的状态 → 占位图集里的哪一行」，等原创素材做好后直接换成 1:1 映射。
LONGNIANG_ROW_ALIAS: dict[str, int] = {
    "idle": 0,
    "working": 7,      # running: active task work
    "thinking": 8,     # review
    "eating": 0,       # 占位图集没有吃饭动作，退回待机
    "happy": 4,        # jumping
    "greet": 3,        # waving
    "remind": 3,       # waving
    "coupon": 8,       # review
    "waiting": 6,
    "failed": 5,
    "error": 5,
    "sleeping": 0,
    "run-right": 1,
    "run-left": 2,
}


def pick_state(current: str | None, incoming: str) -> str:
    """两个状态撞车时谁赢。未知状态一律按 0 处理，不会把宠物卡死。"""
    if not current:
        return incoming
    if STATE_PRIORITY.get(incoming, 0) >= STATE_PRIORITY.get(current, 0):
        return incoming
    return current


class PetStateMachine:
    """带 TTL 衰减的状态机。tick() 由 UI 定时器驱动。"""

    def __init__(self, initial: str = "idle"):
        self.state = initial
        self._expires_at: float | None = None
        self.state_changed_at = time.monotonic()

    def set(self, state: str, ttl_ms: int | None = None) -> str:
        now = time.monotonic()
        if state == self.state and self._expires_at and self._expires_at > now:
            self._expires_at = now + (ttl_ms if ttl_ms is not None else ONESHOT_TTL_MS.get(state, 0)) / 1000
            return self.state
        resolved = pick_state(self.state, state)
        if resolved != self.state:
            self.state = resolved
            self.state_changed_at = now
        ttl = ttl_ms if ttl_ms is not None else ONESHOT_TTL_MS.get(self.state)
        self._expires_at = now + ttl / 1000 if ttl else None
        return self.state

    def clear(self, state: str) -> None:
        """显式结束某个一次性状态（例如用户点掉了提醒气泡）。"""
        if self.state == state:
            self.state = "idle"
            self._expires_at = None
            self.state_changed_at = time.monotonic()

    def tick(self) -> str | None:
        """到期衰减。返回新状态，没变化返回 None。"""
        if self._expires_at is None:
            return None
        if time.monotonic() < self._expires_at:
            return None
        previous = self.state
        self.state = "idle"
        self._expires_at = None
        self.state_changed_at = time.monotonic()
        return None if previous == "idle" else self.state
