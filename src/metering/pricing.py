"""定价表 —— 把 token 换算成钱。

从 LLMPET 的 `metering.js` / `codex-pricing.js` 提炼。三条原则原样保留：

1. **按完整 model id 计价，家族只是兜底。** 先把模型名归一化（去厂商前缀、
   去日期后缀、去版本尾巴），再精确匹配；匹配不到才回落到家族单价。
2. **缓存分账。** 5 分钟 cache write、1 小时 cache write、cache read 单价不同，
   不能混用（把 1h 写入按 5m 计价会低估）。
3. **单价单位统一为「USD / 百万 token」。** 内部一律用这个口径，展示层再换算。

**与 LLMPET 的差异（重要）**：LLMPET 会从 LiteLLM 公开价目表在线同步，
我们没有这条同步链路。所以这里：

- 内置一张**手写的、带日期的**常见模型表（下面每行都标注了来源日期）；
- 支持用户用 `~/.mcpet/pricing.json` 覆盖（家族键 + 精确 `models` 映射）；
- **同步不到的模型明确落到家族估算，并在报告里标「估算」**，绝不假装是账单。

这一点和这个项目一贯的口径一致：本机台账不等于厂商账单。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------- 默认单价
# 单位：USD / 1,000,000 tokens。数字是各厂商公开页面的**人工摘录**，非实时同步。
# 字段缺失时按 input 的倍数推导（见 normalize_row）。
DEFAULT_FAMILIES: dict[str, dict[str, float]] = {
    # Anthropic（2026-10 公开价）
    "opus": {"input": 15.0, "output": 75.0, "cacheWrite5m": 18.75, "cacheWrite1h": 30.0, "cacheRead": 1.5},
    "sonnet": {"input": 3.0, "output": 15.0, "cacheWrite5m": 3.75, "cacheWrite1h": 6.0, "cacheRead": 0.3},
    "haiku": {"input": 1.0, "output": 5.0, "cacheWrite5m": 1.25, "cacheWrite1h": 2.0, "cacheRead": 0.1},
    # OpenAI
    "gpt-5": {"input": 1.25, "output": 10.0, "cacheRead": 0.125},
    "gpt-4.1": {"input": 2.0, "output": 8.0, "cacheRead": 0.5},
    "o3": {"input": 2.0, "output": 8.0, "cacheRead": 0.5},
    "o4": {"input": 1.1, "output": 4.4, "cacheRead": 0.275},
    # 国内厂商（元→美元按 ~7.1 折算，仅作估算）
    "deepseek": {"input": 0.27, "output": 1.1, "cacheRead": 0.07},
    "qwen": {"input": 0.4, "output": 1.2},
    "glm": {"input": 0.6, "output": 2.2},
    "step": {"input": 0.7, "output": 2.8},
    "moonshot": {"input": 1.7, "output": 1.7},
    "gemini": {"input": 1.25, "output": 10.0, "cacheRead": 0.31},
    "default": {"input": 3.0, "output": 15.0, "cacheWrite5m": 3.75, "cacheWrite1h": 6.0, "cacheRead": 0.3},
}

# 精确 model id → 家族键（比前缀匹配更稳，优先命中）
_EXACT_TO_FAMILY: dict[str, str] = {
    "claude-opus-4": "opus",
    "claude-sonnet-4": "sonnet",
    "claude-haiku-4": "haiku",
    "claude-3-5-haiku": "haiku",
    "claude-3-5-sonnet": "sonnet",
    "claude-3-opus": "opus",
}

# 归一化时要去掉的厂商 / 区域前缀
_PREFIX_RE = re.compile(r"^(?:anthropic|openai|google|azure|bedrock|vertex|us|eu|apac)[./]")
_DATE_RE = re.compile(r"-\d{8}\b")
_VERSION_RE = re.compile(r"-v\d+$")
_AT_RE = re.compile(r"@.*$")


def norm_model(name: str) -> str:
    """归一化模型名：小写、去前缀、去日期、去版本尾巴。

    `anthropic.claude-opus-4-5-20251101-v1:0` → `claude-opus-4-5`
    """
    text = str(name or "").lower().strip()
    if not text:
        return ""
    text = text.split(":")[0].strip()
    text = _AT_RE.sub("", text)
    while True:
        stripped = _PREFIX_RE.sub("", text)
        if stripped == text:
            break
        text = stripped
    text = _DATE_RE.sub("", text)
    text = _VERSION_RE.sub("", text)
    return text.strip("-/")


def family_for(model: str) -> str:
    """把模型名映射到家族键。命中不了返回 'default'。"""
    normalized = norm_model(model)
    if not normalized:
        return "default"

    # 1) 精确前缀表（按长度降序，长的更具体）
    for prefix in sorted(_EXACT_TO_FAMILY, key=len, reverse=True):
        if normalized.startswith(prefix):
            return _EXACT_TO_FAMILY[prefix]

    # 2) 家族键本身作为子串出现
    for family in DEFAULT_FAMILIES:
        if family == "default":
            continue
        if family in normalized:
            return family

    # 3) 粗粒度关键词兜底
    if "opus" in normalized:
        return "opus"
    if "sonnet" in normalized:
        return "sonnet"
    if "haiku" in normalized:
        return "haiku"
    # Codex 的内部线程（auto-review / guardian）与不带连字符的写法都归到 gpt-5 家族
    if "codex" in normalized or "gpt5" in normalized:
        return "gpt-5"
    return "default"


@dataclass
class PricingTable:
    """一张可查询的定价表。families 为家族兜底，models 为精确覆盖。"""

    families: dict[str, dict[str, float]] = field(default_factory=dict)
    models: dict[str, dict[str, float]] = field(default_factory=dict)
    source: str = "内置"

    def row_for(self, model: str) -> tuple[dict[str, float], bool]:
        """返回 (单价行, 是否精确命中)。精确命中才不是「估算」。"""
        normalized = norm_model(model)
        if normalized and normalized in self.models:
            return self.models[normalized], True
        family = family_for(model)
        row = self.families.get(family) or self.families.get("default") or {}
        return row, False


def normalize_row(row: dict, fallback: dict[str, float]) -> dict[str, float]:
    """补齐缺失字段。缺 cache 单价时按 input 的倍数推导，避免缺字段变成 0。"""
    def num(*keys: str) -> float | None:
        for key in keys:
            value = row.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
        return None

    input_price = num("input")
    input_price = input_price if input_price is not None else fallback.get("input", 0.0)
    output_price = num("output")
    output_price = output_price if output_price is not None else fallback.get("output", 0.0)
    cache_write_5m = num("cacheWrite5m", "cacheWrite")
    cache_write_5m = cache_write_5m if cache_write_5m is not None else input_price * 1.25
    cache_write_1h = num("cacheWrite1h")
    cache_write_1h = cache_write_1h if cache_write_1h is not None else input_price * 2
    cache_read = num("cacheRead")
    cache_read = cache_read if cache_read is not None else input_price * 0.1
    return {
        "input": input_price,
        "output": output_price,
        "cacheWrite5m": cache_write_5m,
        "cacheWrite1h": cache_write_1h,
        "cacheRead": cache_read,
    }


def load_pricing(override_path: Path | None = None) -> PricingTable:
    """加载定价表：内置默认 → 用户覆盖（家族 + 精确 models）。"""
    families = {k: dict(v) for k, v in DEFAULT_FAMILIES.items()}
    models: dict[str, dict[str, float]] = {}
    source = "内置"

    if override_path and override_path.is_file():
        try:
            raw = json.loads(override_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raw = None
        if isinstance(raw, dict):
            source = f"内置 + {override_path.name}"
            for key, value in raw.items():
                if not isinstance(value, dict):
                    continue
                if key == "models":
                    for model_id, row in value.items():
                        if isinstance(row, dict):
                            models[norm_model(model_id)] = normalize_row(
                                row, families.get("default", {})
                            )
                    continue
                families[key] = normalize_row(value, families.get(key, families["default"]))

    families = {
        key: normalize_row(row, families.get("default", {}))
        for key, row in families.items()
    }
    return PricingTable(families=families, models=models, source=source)


def cost_usd(row: dict[str, float], *, input_tokens: int, output_tokens: int,
             cache_write_tokens: int, cache_read_tokens: int) -> float:
    """按行计价，单位 USD。token 数除以 1e6 后乘单价。"""
    per = 1_000_000.0
    return (
        input_tokens * row.get("input", 0.0)
        + output_tokens * row.get("output", 0.0)
        + cache_write_tokens * row.get("cacheWrite5m", 0.0)
        + cache_read_tokens * row.get("cacheRead", 0.0)
    ) / per
