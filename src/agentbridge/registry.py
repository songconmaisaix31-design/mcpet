"""Provider 注册表 —— 把「有哪些 provider」和「这台机器上哪些可用」分开。

`available_providers()` 报的是**代码里实现了几种**（稳定，不随机器变）；
`build_providers()` 报的是**这台机器上真的能用几种**（取决于根目录是否存在）。
两者分开，是为了让 `agents` 命令能如实告诉用户：
「支持 3 种，你这里配了 1 种，另外 2 种因为目录不存在被跳过」。
"""

from __future__ import annotations

from .paths import AgentRoots, resolve_roots
from .providers.base import Provider
from .providers.claude import ClaudeProvider
from .providers.codex import CodexProvider
from .providers.generic import GenericProvider

# id -> 实现类。顺序即默认展示顺序：先通用，再具体厂商。
PROVIDER_TYPES: dict[str, type] = {
    "generic": GenericProvider,
    "claude": ClaudeProvider,
    "codex": CodexProvider,
}

PROVIDER_LABELS: dict[str, str] = {
    "generic": "通用收件箱（任何 Agent 按规范写入）",
    "claude": "Claude Code transcript",
    "codex": "OpenAI Codex rollout",
}


def available_providers() -> list[str]:
    """代码里实现了几种 provider。"""
    return list(PROVIDER_TYPES)


def build_providers(
    roots: AgentRoots | None = None,
    *,
    only: list[str] | None = None,
) -> list[Provider]:
    """构建**本机可用**的 provider 列表。

    根目录不存在的 provider 直接不构建——别的机器上没装 Claude Code 是常态，
    不该因此报错，也不该在菜单里显示一个永远没数据的项。
    """
    roots = roots or resolve_roots()
    ids = only if only is not None else list(PROVIDER_TYPES)
    out: list[Provider] = []
    for pid in ids:
        cls = PROVIDER_TYPES.get(pid)
        if cls is None:
            continue
        live = roots.for_provider(pid)
        if not live:
            continue
        out.append(cls(live))
    return out
