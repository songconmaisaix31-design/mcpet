"""配置与凭证管理。

原则：真实 Token 只从环境变量 / 项目根目录 .env 读取，绝不写进仓库里任何文件；
所有对外输出（日志、README 截图、气泡文案）在落地前必须经过 redact()。
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MCP_URL = "https://mcp.mcd.cn"

# 麦当劳 MCP 限流：每个 Token 每分钟 600 次。留 10% 余量。
DEFAULT_RATE_LIMIT_PER_MINUTE = 540


def load_env() -> None:
    """加载项目根目录 .env（如存在）。已存在的环境变量优先，不被覆盖。"""
    load_dotenv(PROJECT_ROOT / ".env", override=False)


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
    return os.environ.get("STEPFUN_API_KEY") or None


def stepfun_model() -> str:
    return os.environ.get("STEPFUN_MODEL") or "step-3.5-flash"


def city() -> str:
    return os.environ.get("MAIMAI_CITY", "北京").strip()


def dry_run() -> bool:
    """演练模式：仍真实调用全部查询与算价，但不提交 create-order。

    注意：这不是 mock。链路、参数、返回值都是真实的，只有「落单」这一步被跳过。
    """
    return os.environ.get("MCD_DRY_RUN", "").strip().lower() in {"1", "true", "yes", "on"}


def data_dir() -> Path:
    """本机运行数据目录（营养台账、订单审计）。含个人信息，已被 .gitignore 排除。"""
    override = os.environ.get("MAIMAI_DATA_DIR")
    path = Path(override) if override else Path.home() / ".maimai-monster"
    path.mkdir(parents=True, exist_ok=True)
    return path


_TOKEN_PATTERNS = (
    re.compile(r"\b(Bearer\s+)[A-Za-z0-9._\-]{8,}", re.IGNORECASE),
    re.compile(r"\b(sk-|mcp_)[A-Za-z0-9._\-]{8,}"),
)
_PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_ID_CARD_RE = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")


def redact(text: str, token: str | None = None) -> str:
    """脱敏：盖掉 Token、手机号、邮箱、身份证号。

    地址类信息（门店名、收货地址）没有可靠的通用模式，redact 不做处理——
    对外发布截图时这部分需要人工核对。
    """
    if not text:
        return text
    out = text
    if token:
        out = out.replace(token, "***")
    for pattern in _TOKEN_PATTERNS:
        out = pattern.sub(lambda m: (m.group(1) if m.lastindex else "") + "***", out)
    out = _PHONE_RE.sub(lambda m: m.group(0)[:3] + "****" + m.group(0)[-4:], out)
    out = _EMAIL_RE.sub("***@***", out)
    out = _ID_CARD_RE.sub(lambda m: m.group(0)[:4] + "*" * 10 + m.group(0)[-4:], out)
    return out
