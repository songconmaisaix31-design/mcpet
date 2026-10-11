"""归一化记录 —— 所有 provider 说同一种语言。

关键区分（这是整个可移植设计的核心）：

    UsageRecord     —— 一次模型调用的用量。可累加、可计价。
    ProgressRecord  —— 一个会话在某一刻的进度快照。不累加，只取最新。

LLMPET 里这两件事是混在 transcript 解析里的（一个文件同时喂状态机和计量）。
这里拆开，因为「余额」需要历史累加、「进度」只需要当前值——混在一起会导致
读进度时被迫扫全量历史。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class UsageRecord:
    """一次模型调用的用量。

    字段名刻意保持 provider 中立：不叫 `input_tokens` 之外的任何厂商私有名。
    各 provider 负责把自己的私有字段翻译过来。
    """

    key: str            # 全局去重键。同一逻辑调用的多次快照必须产出同一个 key。
    ts: float           # Unix 秒（float）。用于分日 / 分时 / 滑动窗口。
    model: str          # 原始模型名（未归一化，归一化在计价层做）
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    source: str = ""    # provider id
    session_id: str = ""

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_write_tokens
            + self.cache_read_tokens
        )

    def components(self) -> dict[str, int]:
        return {
            "input": self.input_tokens,
            "output": self.output_tokens,
            "cacheWrite": self.cache_write_tokens,
            "cacheRead": self.cache_read_tokens,
        }


@dataclass
class ProgressRecord:
    """一个会话的进度快照。后写覆盖先写（按 updated_at 取新）。"""

    source: str
    session_id: str
    state: str = "UNKNOWN"
    project: str = ""
    cwd: str = ""
    title: str = ""
    model: str = ""
    context_used: int = 0
    context_limit: int = 0
    background_tasks: int = 0
    detail: str = ""
    updated_at: float = 0.0
    completed_at: float = 0.0
    completion_id: str = ""
    context_limit_estimated: bool = False

    @property
    def context_percent(self) -> int | None:
        if self.context_limit <= 0:
            return None
        pct = round(self.context_used / self.context_limit * 100)
        return max(0, min(100, pct))


@dataclass
class UsageTotals:
    """一份可加总的用量小计。"""

    tokens: int = 0
    cost_usd: float = 0.0
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    by_model: dict[str, dict[str, float]] = field(default_factory=dict)

    def add(self, other: "UsageTotals") -> "UsageTotals":
        self.tokens += other.tokens
        self.cost_usd += other.cost_usd
        self.calls += other.calls
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_write_tokens += other.cache_write_tokens
        self.cache_read_tokens += other.cache_read_tokens
        for model, row in other.by_model.items():
            bucket = self.by_model.setdefault(model, {"tokens": 0, "cost": 0.0})
            bucket["tokens"] += row.get("tokens", 0)
            bucket["cost"] += row.get("cost", 0.0)
        return self

    def to_dict(self) -> dict:
        return {
            "tokens": self.tokens,
            "costUsd": round(self.cost_usd, 6),
            "calls": self.calls,
            "input": self.input_tokens,
            "output": self.output_tokens,
            "cacheWrite": self.cache_write_tokens,
            "cacheRead": self.cache_read_tokens,
            "byModel": self.by_model,
        }
