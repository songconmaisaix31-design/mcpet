"""配置与凭证管理。

原则：真实 Token 只从环境变量 / 项目根目录 .env 读取，绝不写进仓库里任何文件；
所有对外输出（日志、README 截图、气泡文案）在落地前必须经过 redact()。
"""

from __future__ import annotations

import os
import re
import json
import stat
from pathlib import Path

from dotenv import load_dotenv, dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MCP_URL = "https://mcp.mcd.cn"

# 麦当劳 MCP 限流：每个 Token 每分钟 600 次。留 10% 余量。
DEFAULT_RATE_LIMIT_PER_MINUTE = 540


def load_env() -> None:
    """环境变量 > 本机用户配置 > 项目配置；不向输出暴露文件内容。"""
    load_dotenv(data_dir() / ".env", override=False, interpolate=False)
    load_dotenv(PROJECT_ROOT / ".env", override=False, interpolate=False)


SETTINGS_KEYS = ("MCD_MCP_TOKEN", "STEPFUN_API_KEY", "DEEPSEEK_API_KEY", "MCPET_CITY", "MCPET_LUNCH_TIME",
                 "MCPET_AGENT_ROOT_CLAUDE", "MCPET_AGENT_ROOT_CODEX",
                 "MCPET_AGENT_ROOT_GENERIC")


def save_settings(values: dict[str, str]) -> None:
    """只写用户数据目录；保留其他配置。凭证不进入 JSON 或聊天记录。"""
    if set(values) - set(SETTINGS_KEYS):
        raise ValueError("未知设置字段")
    if any("\n" in v or "\r" in v or "\x00" in v for v in values.values()):
        raise ValueError("设置不能包含换行或空字符")
    path = data_dir() / ".env"
    previous = dict(dotenv_values(path, interpolate=False)) if path.exists() else {}
    previous.update(values)
    # dotenv 双引号支持反斜杠与引号转义。先收临时文件权限再原子替换。
    content = "\n".join(f"{k}={json.dumps(v or '', ensure_ascii=False)}" for k, v in previous.items())
    temporary = path.with_suffix(".env.tmp")
    temporary.write_text(content + "\n", encoding="utf-8")
    os.chmod(temporary, stat.S_IRUSR | stat.S_IWUSR)
    temporary.replace(path)
    os.environ.update(values)


def root_warnings(values: dict[str, str]) -> list[str]:
    warnings = []
    for key in SETTINGS_KEYS:
        if "AGENT_ROOT" in key and values.get(key):
            try:
                exists = Path(os.path.expandvars(values[key])).expanduser().is_dir()
            except (OSError, ValueError):
                exists = False
            if not exists:
                warnings.append(f"{key.removeprefix('MCPET_AGENT_ROOT_')}: 目录不存在，不会读取")
    if os.environ.get("MCPET_AGENT_ROOTS"):
        warnings.append("环境变量 MCPET_AGENT_ROOTS 覆盖单独目录配置；修改后请重启")
    return warnings


def _is_placeholder(value: str) -> bool:
    """识别 .env.example 里留下的占位值，别把它当成真 Token 发出去。"""
    text = value.strip()
    return text.upper().startswith(("YOUR_", "CHANGEME", "XXX")) or text in {"", "none", "null"}


def mcp_token() -> str | None:
    value = os.environ.get("MCD_MCP_TOKEN") or ""
    return None if _is_placeholder(value) else value.strip()


def mcp_url() -> str:
    return os.environ.get("MCD_MCP_URL") or DEFAULT_MCP_URL


def stepfun_api_key() -> str | None:
    value = os.environ.get("STEPFUN_API_KEY") or ""
    return None if _is_placeholder(value) else value.strip()


def stepfun_model() -> str:
    return os.environ.get("STEPFUN_MODEL") or "step-3.5-flash"


def deepseek_api_key() -> str:
    """仅用于余额只读查询；占位值等同未配置。"""
    value = os.environ.get("DEEPSEEK_API_KEY") or ""
    return "" if _is_placeholder(value) else value.strip()


def city() -> str:
    return os.environ.get("MCPET_CITY", "北京").strip()


def dry_run() -> bool:
    """演练模式：仍真实调用全部查询与算价，但不提交 create-order。

    注意：这不是 mock。链路、参数、返回值都是真实的，只有「落单」这一步被跳过。
    """
    return os.environ.get("MCD_DRY_RUN", "").strip().lower() in {"1", "true", "yes", "on"}


def data_dir() -> Path:
    """本机运行数据目录（营养台账、订单审计、用量台账）。含个人信息，已被 .gitignore 排除。"""
    override = os.environ.get("MCPET_DATA_DIR")
    path = Path(override) if override else Path.home() / ".mcpet"
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------- Agent 桥接
# 这一组配置决定「从哪读别的 Agent 的用量与进度」。默认值只是候选，
# 详见 src/agentbridge/paths.py —— 目录不存在就跳过，不会报错。


def agent_config_path() -> Path:
    """agentbridge 的配置文件路径（可覆盖根目录、计价表等）。"""
    override = os.environ.get("MCPET_CONFIG_PATH")
    return Path(override) if override else Path.home() / ".mcpet" / "config.json"


def usage_window_hours() -> float:
    """滚动窗口长度（小时）。默认 5，对齐 Claude 的限流主窗口。

    注意：这是**我们自己划的观测窗口**，不是从厂商读来的配额。
    """
    raw = os.environ.get("MCPET_USAGE_WINDOW_HOURS", "").strip()
    try:
        value = float(raw)
    except ValueError:
        return 5.0
    return value if value > 0 else 5.0


def progress_stale_minutes() -> int:
    """会话多久没更新就算「不活跃」。用于进度汇报里区分在跑的和挂着的。"""
    raw = os.environ.get("MCPET_PROGRESS_STALE_MINUTES", "").strip()
    try:
        value = int(raw)
    except ValueError:
        return 30
    return value if value > 0 else 30


def watch_processes() -> bool:
    """是否采样本机进程表来识别「真的在跑」的 Agent。

    默认关。原因：进程表采样要读系统信息、各平台口径不一，而且一个纯日志
    驱动的桌宠不需要它也能工作。开了会更准，但要在文档里说清它读了什么。
    """
    return os.environ.get("MCPET_WATCH_PROCESSES", "").strip().lower() in {
        "1", "true", "yes", "on",
    }



_TOKEN_PATTERNS = (
    re.compile(r"\b(Bearer\s+)[A-Za-z0-9._\-]{8,}", re.IGNORECASE),
    re.compile(r"\b(sk-|mcp_)[A-Za-z0-9._\-]{8,}"),
)
_PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_ID_CARD_RE = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")


def redact(text: str, token: str | None = None, *, personal: bool = True) -> str:
    """脱敏：盖掉 Token、手机号、邮箱、身份证号。

    地址类信息（门店名、收货地址）没有可靠的通用模式，redact 不做处理——
    对外发布截图时这部分需要人工核对。
    """
    if not text:
        return text
    out = text
    for key in ("MCD_MCP_TOKEN", "STEPFUN_API_KEY", "DEEPSEEK_API_KEY"):
        secret = os.environ.get(key, "")
        if secret and not _is_placeholder(secret):
            out = out.replace(secret, "***")
    if token:
        out = out.replace(token, "***")
    for pattern in _TOKEN_PATTERNS:
        out = pattern.sub(lambda m: (m.group(1) if m.lastindex else "") + "***", out)
    if personal:
        out = _PHONE_RE.sub(lambda m: m.group(0)[:3] + "****" + m.group(0)[-4:], out)
        out = _EMAIL_RE.sub("***@***", out)
        out = _ID_CARD_RE.sub(lambda m: m.group(0)[:4] + "*" * 10 + m.group(0)[-4:], out)
    return out
