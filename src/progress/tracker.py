"""进度追踪 —— 「项目进度汇报」的数据底座。

从 LLMPET 移植的机制：

| LLMPET | 这里 | 说明 |
|---|---|---|
| `transcript.contextUsage()` | `ProgressRecord.context_used/limit` | 上下文占用百分比，进度最直观的一格 |
| 1M 窗口启发式 | `agentbridge/context.py` | 顶穿 200k 即判 1M，否则长会话会卡在 100% |
| `runtime-monitor.js` 采样本机进程 | `ProcessSampler`（可选） | 判断 Agent 是真在跑还是日志停在半路 |
| hook 报 `background_tasks_count` | `ProgressRecord.background_tasks` | 后台任务数 |

**与 LLMPET 的差异**：LLMPET 的进度来自 Claude Code 的 hook 实时推送，
我们拿不到别的 Agent 的 hook。所以这里的进度是**日志推导**的，天生带一点滞后
（取决于 Agent 多久落一次盘）。这个滞后是设计约束，不是 bug，报告里会说明。

进程采样默认关闭：一个纯日志驱动的桌宠不需要读系统进程表也能工作，
开着会多读一份本机信息，得让用户自己选。
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from ..agentbridge.providers.base import Provider
from ..agentbridge.records import ProgressRecord

# 进程名特征 -> provider id。只在开启进程采样时用。
PROCESS_HINTS: dict[str, tuple[str, ...]] = {
    "claude": ("claude",),
    "codex": ("codex",),
    "generic": (),
}

# 明显是宿主自身或无关的进程，采到了也不认
_PROCESS_IGNORE = (
    "runtime-monitor",
    "maimai-monster",
    "explorer.exe",
    "chrome_crashpad",
)


@dataclass
class SessionProgress:
    """一个会话的进度视图（在 ProgressRecord 之上补了「新鲜度」判断）。"""

    record: ProgressRecord
    stale: bool = False
    age_seconds: float = 0.0

    @property
    def label(self) -> str:
        return self.record.title or self.record.project or self.record.session_id[:8]

    @property
    def context_percent(self) -> int | None:
        return self.record.context_percent


@dataclass
class ProgressSnapshot:
    sessions: list[SessionProgress] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    stale_minutes: int = 30
    live_processes: dict[str, int] = field(default_factory=dict)
    sampled_at: float = 0.0
    process_sampling: bool = False

    @property
    def active(self) -> list[SessionProgress]:
        return [s for s in self.sessions if not s.stale]

    @property
    def stale(self) -> list[SessionProgress]:
        return [s for s in self.sessions if s.stale]

    @property
    def background_tasks(self) -> int:
        return sum(s.record.background_tasks for s in self.active)

    @property
    def has_data(self) -> bool:
        return bool(self.sessions)


class ProcessSampler:
    """可选的本机进程采样。依赖 psutil，装不上就静默降级为「不采样」。"""

    def __init__(self) -> None:
        self.available = False
        try:
            import psutil  # noqa: F401

            self.available = True
        except ImportError:
            self.available = False

    def sample(self) -> dict[str, int]:
        if not self.available:
            return {}
        import psutil

        counts: dict[str, int] = {}
        try:
            for proc in psutil.process_iter(["name", "cmdline"]):
                try:
                    name = (proc.info.get("name") or "").lower()
                    cmdline = " ".join(proc.info.get("cmdline") or []).lower()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                haystack = f"{name} {cmdline}"
                if any(marker in haystack for marker in _PROCESS_IGNORE):
                    continue
                for provider_id, hints in PROCESS_HINTS.items():
                    if hints and any(hint in haystack for hint in hints):
                        counts[provider_id] = counts.get(provider_id, 0) + 1
                        break
        except Exception:
            return counts
        return counts


class ProgressTracker:
    """把各 provider 的进度快照合并成一份「现在谁在跑什么」。"""

    def __init__(
        self,
        providers: Iterable[Provider],
        *,
        stale_minutes: int = 30,
        max_sessions: int = 12,
        sampler: ProcessSampler | None = None,
        watch_processes: bool = False,
    ) -> None:
        self.providers = list(providers)
        self.stale_minutes = int(stale_minutes)
        self.max_sessions = int(max_sessions)
        self.sampler = sampler or ProcessSampler()
        self.watch_processes = bool(watch_processes) and self.sampler.available

    def snapshot(self, *, now: float | None = None) -> ProgressSnapshot:
        moment = now if now is not None else time.time()
        cutoff = self.stale_minutes * 60

        by_session: dict[tuple[str, str], ProgressRecord] = {}
        sources: list[str] = []
        for provider in self.providers:
            sources.append(provider.id)
            try:
                records = list(provider.iter_progress())
            except Exception:
                continue
            for record in records:
                key = (record.source, record.session_id)
                previous = by_session.get(key)
                if previous is None or record.updated_at >= previous.updated_at:
                    by_session[key] = record

        sessions: list[SessionProgress] = []
        for record in by_session.values():
            age = max(0.0, moment - record.updated_at) if record.updated_at else float("inf")
            sessions.append(
                SessionProgress(record=record, stale=age > cutoff, age_seconds=age)
            )
        # 活跃的在前，同组按更新时间倒序
        sessions.sort(key=lambda s: (s.stale, -s.record.updated_at))
        sessions = sessions[: self.max_sessions]

        live: dict[str, int] = {}
        if self.watch_processes:
            live = self.sampler.sample()

        return ProgressSnapshot(
            sessions=sessions,
            sources=sources,
            stale_minutes=self.stale_minutes,
            live_processes=live,
            sampled_at=moment,
            process_sampling=self.watch_processes,
        )
