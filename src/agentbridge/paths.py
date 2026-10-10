"""数据源根目录解析 —— 绝不硬编码任何本机路径。

设计原则（对应 DaV1d 对「不绑死本机环境」的要求）：

1. 平台默认值（`~/.claude/projects` 之类）**只是候选**，不是事实。候选不存在
   就跳过，不报错——别的机器上可能根本没装那个 Agent。
2. 解析顺序固定：**环境变量 > 配置文件 > 平台默认候选**。
3. 所有路径都做 `~` 展开与绝对化，Windows / macOS / Linux 同一套代码。
4. 配置来源全部可被外部注入（`config_path` 参数），便于测试与嵌入式使用。

配置文件默认在 `~/.maimai-monster/config.json`，形状：

    {
      "agentRoots": {
        "claude": "~/my/custom/claude/projects",
        "generic": "/srv/agent-inbox"
      }
    }
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

# provider id -> 平台默认候选目录（可能不存在；不存在即跳过）
_PLATFORM_DEFAULTS: dict[str, tuple[str, ...]] = {
    "claude": ("~/.claude/projects",),
    "codex": ("~/.codex/sessions",),
    # 通用收件箱：任何 Agent 按 docs/AGENT_BRIDGE.md 的规范往这里写就能被读到
    "generic": ("~/.maimai-monster/inbox",),
}

# provider id -> 专属环境变量（最高优先级）
_ENV_OVERRIDES: dict[str, str] = {
    "claude": "MAIMAI_AGENT_ROOT_CLAUDE",
    "codex": "MAIMAI_AGENT_ROOT_CODEX",
    "generic": "MAIMAI_AGENT_ROOT_GENERIC",
}

# 批量覆盖：MAIMAI_AGENT_ROOTS="claude=/a/b,generic=/c/d"
_ENV_ROOTS = "MAIMAI_AGENT_ROOTS"

DEFAULT_CONFIG_PATH = Path.home() / ".maimai-monster" / "config.json"


def _expand(raw: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(raw.strip()))).resolve()


@dataclass
class AgentRoots:
    """解析后的根目录集合。

    `roots` 只放**真实存在**的目录；`declared` 放所有被声明过的（含不存在的），
    供 `agents` 命令如实汇报「你配了但目录不存在」这类问题。
    """

    roots: dict[str, list[Path]] = field(default_factory=dict)
    declared: dict[str, list[Path]] = field(default_factory=dict)
    config_path: Path | None = None
    sources: dict[str, str] = field(default_factory=dict)  # id -> 值来自哪一层

    def for_provider(self, provider_id: str) -> list[Path]:
        return self.roots.get(provider_id, [])

    def active_ids(self) -> list[str]:
        return [pid for pid, paths in self.roots.items() if paths]

    def describe(self) -> list[str]:
        lines: list[str] = []
        for pid in sorted(self.declared):
            origin = self.sources.get(pid, "默认")
            live = self.roots.get(pid, [])
            if live:
                for path in live:
                    lines.append(f"{pid:<8} {path}  [{origin}]")
            else:
                for path in self.declared[pid]:
                    lines.append(f"{pid:<8} {path}  [{origin}]  (不存在，已跳过)")
        return lines


def _load_config(config_path: Path | None) -> dict:
    path = config_path or DEFAULT_CONFIG_PATH
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _parse_env_roots(value: str) -> dict[str, list[str]]:
    """解析 MAIMAI_AGENT_ROOTS：`id=path` 用逗号或换行分隔。

    逗号与换行都支持，是因为 Windows 路径里 `;` 是 PATH 分隔符，用 `;` 会和
    其它工具的习惯打架；`,` 在路径里罕见，够用。
    """
    out: dict[str, list[str]] = {}
    for chunk in value.replace("\n", ",").split(","):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            continue
        pid, _, path = chunk.partition("=")
        pid = pid.strip()
        path = path.strip()
        if pid and path:
            out.setdefault(pid, []).append(path)
    return out


def resolve_roots(
    *,
    config_path: Path | None = None,
    env: dict[str, str] | None = None,
    provider_ids: list[str] | None = None,
) -> AgentRoots:
    """解析全部 provider 的根目录。

    `env` 与 `config_path` 可注入，便于测试；生产环境用 os.environ 与默认路径。
    """
    environ = env if env is not None else dict(os.environ)
    ids = provider_ids or list(_PLATFORM_DEFAULTS)

    batch = _parse_env_roots(environ.get(_ENV_ROOTS, ""))
    config = _load_config(config_path)
    config_roots = config.get("agentRoots")
    config_roots = config_roots if isinstance(config_roots, dict) else {}

    result = AgentRoots(config_path=config_path or DEFAULT_CONFIG_PATH)

    for pid in ids:
        declared_raw: list[str] = []
        origin = "默认"

        if pid in batch:
            declared_raw = batch[pid]
            origin = _ENV_ROOTS
        elif _ENV_OVERRIDES.get(pid) and environ.get(_ENV_OVERRIDES[pid], "").strip():
            declared_raw = [environ[_ENV_OVERRIDES[pid]]]
            origin = _ENV_OVERRIDES[pid]
        elif pid in config_roots and str(config_roots[pid]).strip():
            raw_value = config_roots[pid]
            if isinstance(raw_value, list):
                declared_raw = [str(v) for v in raw_value]
            else:
                declared_raw = [str(raw_value)]
            origin = "配置文件"
        else:
            declared_raw = list(_PLATFORM_DEFAULTS.get(pid, ()))

        paths: list[Path] = []
        for raw in declared_raw:
            try:
                paths.append(_expand(raw))
            except (OSError, RuntimeError, ValueError):
                continue
        if not paths:
            continue

        result.declared[pid] = paths
        result.sources[pid] = origin
        live = [p for p in paths if p.is_dir()]
        if live:
            result.roots[pid] = live

    return result
