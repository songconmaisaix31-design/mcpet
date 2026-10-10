"""跨 Agent 数据桥（可移植层）。

这一层的存在意义只有一个：**不要把McPet绑死在某一台机器、某一个 Agent 上。**

LLMPET 的计量与进度模块是直接写死 `~/.claude/projects` 的——那是 Electron 桌面版
在作者本机跑得通的写法，但一个要给别人跑的开源项目不能这么写。所以这里把
「从哪读数据」抽成 provider：

    UsageProvider     —— 产出归一化的 UsageRecord（token 用量）
    ProgressProvider  —— 产出归一化的 ProgressRecord（会话进度 / 上下文占用）

内置三个 provider，覆盖三类现实场景：

    claude   Claude Code 的 transcript JSONL（结构最全，但只在装了它时才有）
    codex    OpenAI Codex 的 rollout JSONL
    generic  一份公开的通用 JSONL / heartbeat 目录规范，**任何 Agent 都能写**

根目录的解析顺序永远是「环境变量 > 配置文件 > 平台默认候选」，
而且平台默认候选**只是候选**：不存在就静默跳过，不会因为本机没装 Claude Code
就让整个程序起不来。
"""

from __future__ import annotations

from .paths import AgentRoots, resolve_roots
from .records import ProgressRecord, UsageRecord
from .registry import available_providers, build_providers

__all__ = [
    "AgentRoots",
    "ProgressRecord",
    "UsageRecord",
    "available_providers",
    "build_providers",
    "resolve_roots",
]
