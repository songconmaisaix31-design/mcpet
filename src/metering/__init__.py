"""用量与余额提醒。

对外只暴露一个入口 `build_meter()`——把「根目录解析 → provider 构建 → 台账」
这一串串好。调用方不需要知道 provider 的存在。
"""

from __future__ import annotations

from pathlib import Path

from ..agentbridge import AgentRoots, build_providers, resolve_roots
from .pricing import PricingTable, load_pricing, norm_model
from .report import (
    bubble,
    format_tokens,
    format_usd,
    proportional_bar,
    reminder_level,
    report,
    sparkline,
)
from .usage import (
    DEFAULT_WINDOW_HOURS,
    ScanResult,
    UsageMeter,
    UsageSnapshot,
    recent_days,
)

__all__ = [
    "DEFAULT_WINDOW_HOURS",
    "PricingTable",
    "ScanResult",
    "UsageMeter",
    "UsageSnapshot",
    "bubble",
    "build_meter",
    "format_tokens",
    "format_usd",
    "load_pricing",
    "norm_model",
    "proportional_bar",
    "recent_days",
    "reminder_level",
    "report",
    "sparkline",
]


def default_state_path() -> Path:
    """台账落盘位置。跟着 data_dir()，可被 MCPET_DATA_DIR 覆盖。"""
    from ..config import data_dir

    return data_dir() / "usage.json"


def default_pricing_override() -> Path:
    from ..config import data_dir

    return data_dir() / "pricing.json"


def build_meter(
    *,
    roots: AgentRoots | None = None,
    state_path: Path | None = None,
    pricing_override: Path | None = None,
    window_hours: float | None = None,
) -> UsageMeter:
    """组装一个可用的用量台账。

    这台机器上一个 provider 都不可用时，返回一个 provider 为空的台账——
    调用方拿到的 snapshot 会如实显示「无可用数据源」，而不是抛异常。
    """
    from ..config import usage_window_hours

    resolved = roots or resolve_roots()
    providers = build_providers(resolved)
    override = pricing_override if pricing_override is not None else default_pricing_override()
    return UsageMeter(
        providers,
        state_path=state_path or default_state_path(),
        pricing=load_pricing(override),
        window_hours=window_hours if window_hours is not None else usage_window_hours(),
    )
