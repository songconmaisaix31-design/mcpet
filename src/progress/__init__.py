"""项目进度汇报。

对外入口 `build_tracker()`——和 metering 一样，把根目录解析与 provider
构建封在里面，调用方只管拿快照。
"""

from __future__ import annotations

from ..agentbridge import AgentRoots, build_providers, resolve_roots
from .report import (
    bubble,
    context_bar,
    human_age,
    pet_state_for,
    report,
    state_label,
)
from .tracker import (
    ProcessSampler,
    ProgressSnapshot,
    ProgressTracker,
    SessionProgress,
)

__all__ = [
    "ProcessSampler",
    "ProgressSnapshot",
    "ProgressTracker",
    "SessionProgress",
    "bubble",
    "build_tracker",
    "context_bar",
    "human_age",
    "pet_state_for",
    "report",
    "state_label",
]


def build_tracker(
    *,
    roots: AgentRoots | None = None,
    stale_minutes: int | None = None,
    max_sessions: int = 12,
    watch_processes: bool | None = None,
) -> ProgressTracker:
    """组装进度追踪器。一个 provider 都不可用时返回空追踪器，不抛异常。"""
    from ..config import progress_stale_minutes, watch_processes as cfg_watch

    from ..config import agent_config_path

    resolved = roots or resolve_roots(config_path=agent_config_path())
    return ProgressTracker(
        build_providers(resolved),
        stale_minutes=stale_minutes if stale_minutes is not None else progress_stale_minutes(),
        max_sessions=max_sessions,
        watch_processes=cfg_watch() if watch_processes is None else watch_processes,
    )
