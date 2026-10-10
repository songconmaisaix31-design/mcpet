"""上下文窗口上限推断 —— 与 provider 无关的共享逻辑。

从 LLMPET 的 `transcript.contextLimit()` 提炼。核心难点：**1M 上下文是靠 beta
header 开的，模型名里不一定带 `1m`**，所以不能只读名字。

LLMPET 的启发式（保留）：
    单次请求的 input 不可能超过上下文窗口 → 观测到的用量一旦顶穿 200k，
    这个会话必然跑在 1M 窗口上。

但 LLMPET 还依赖一张从 LiteLLM 同步来的精确表，我们没有同步链路，所以加了
一层「显式声明」：模型名里出现 `1m` / `[1m]` 就直接判 1M，这是各厂商约定俗成的写法。
"""

from __future__ import annotations

import re

DEFAULT_LIMIT = 200_000
LARGE_LIMIT = 1_000_000

# 模型名里显式写了 1M 窗口的常见写法：claude-sonnet-4-5-1m / xxx[1m] / xxx-1m-2025
_EXPLICIT_1M = re.compile(r"(^|[^a-z0-9])1m([^a-z0-9]|$)", re.IGNORECASE)

# 已知模型的默认窗口。键是归一化后的前缀，命中即用。
_KNOWN_LIMITS: tuple[tuple[str, int], ...] = (
    ("gpt-5", 400_000),
    ("gpt-4.1", 1_000_000),
    ("o3", 200_000),
    ("o4", 200_000),
    ("gemini-2.5", 1_000_000),
    ("gemini-1.5", 1_000_000),
    ("deepseek", 128_000),
    ("qwen", 131_072),
    ("glm", 128_000),
    ("step-", 65_536),
    ("moonshot", 128_000),
)


def context_limit(model: str, used: int = 0) -> int:
    """推断某模型的上下文窗口上限。"""
    name = (model or "").lower()

    if _EXPLICIT_1M.search(name):
        return LARGE_LIMIT

    for prefix, limit in _KNOWN_LIMITS:
        if prefix in name:
            return limit

    # 兜底启发式：用量已经顶穿 200k，说明真实窗口更大（否则这次请求根本发不出去）
    if used > DEFAULT_LIMIT:
        return LARGE_LIMIT
    return DEFAULT_LIMIT


def context_percent(used: int, limit: int) -> int:
    if limit <= 0:
        return 0
    return max(0, min(100, round(used / limit * 100)))
