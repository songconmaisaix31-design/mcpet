"""用量台账 —— 「账号余额提醒」的数据底座。

从 LLMPET 的 `metering.js` 移植的机制，逐条对应：

| LLMPET 机制 | 这里 | 为什么必须有 |
|---|---|---|
| 字节偏移增量扫描 | `cursors[path]` | 日志动辄 GB，每次全扫会拖死桌宠 |
| `message.id` 去重 | `records[key]` | 流式响应会把同一条消息写多行 |
| 逐分量取最大值 + 只记正增量 | `_absorb()` | 第一行 output 不完整，直接累加会少算 |
| 5 小时滚动窗口 | `window_totals()` | 对应厂商的限流窗口，是「余额」的本体 |
| 日 / 时 / 终生三级聚合 | `daily` / `hourly` / `carried` | 终生 = 已滚出窗口的日 + 保留的日，不会漂移 |
| 原子写 | `_save()` | 断电写坏状态等于丢掉全部历史 |
| 首次回填 | `backfill_days` | 装完就能看到近 95 天，而不是从今天开始 |

**与 LLMPET 的关键差异**：数据来源不是写死的 `~/.claude/projects`，而是
`agentbridge` 交来的 provider 列表。换一个 Agent，只换 provider，这一层不动。
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from ..agentbridge.providers.base import Provider
from ..agentbridge.records import UsageRecord, UsageTotals
from .pricing import PricingTable, cost_usd, load_pricing

STATE_SCHEMA = 1
DEFAULT_WINDOW_HOURS = 5.0          # 厂商限流主窗口
DAILY_KEEP_DAYS = 95                # 与 LLMPET 一致
# 去重记录保留期。只服务「同一轮内的流式修正」，跨天就没有意义了；
# 保留 3 天是给跨天仍在跑的长任务留余量。
RECORD_KEEP_DAYS = 3


def _now() -> float:
    return time.time()


def day_key(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def hour_of(ts: float) -> int:
    return datetime.fromtimestamp(ts).hour


def _empty_totals() -> dict[str, float]:
    return {
        "tokens": 0,
        "cost": 0.0,
        "calls": 0,
        "input": 0,
        "output": 0,
        "cacheWrite": 0,
        "cacheRead": 0,
    }


@dataclass
class ScanResult:
    files: int = 0
    records: int = 0
    corrections: int = 0
    truncated: int = 0
    elapsed_ms: int = 0
    providers: list[str] = field(default_factory=list)

    def describe(self) -> str:
        if not self.providers:
            return "没有可用的数据源"
        return (
            f"扫描 {self.files} 个文件 / 新增 {self.records} 条用量"
            f"（流式修正 {self.corrections} 次，文件重置 {self.truncated} 个）"
            f"，耗时 {self.elapsed_ms} ms"
        )


@dataclass
class UsageSnapshot:
    """一次读取的全部口径。展示层只依赖这个，不碰内部状态。"""

    window: UsageTotals = field(default_factory=UsageTotals)
    today: UsageTotals = field(default_factory=UsageTotals)
    lifetime: UsageTotals = field(default_factory=UsageTotals)
    window_hours: float = DEFAULT_WINDOW_HOURS
    window_started: float = 0.0
    hourly_today: list[float] = field(default_factory=list)
    hourly_tokens_today: list[int] = field(default_factory=list)
    daily: dict[str, dict[str, float]] = field(default_factory=dict)
    estimated_models: list[str] = field(default_factory=list)
    unknown_models: list[str] = field(default_factory=list)
    pricing_source: str = "内置"
    sources: list[str] = field(default_factory=list)

    @property
    def has_data(self) -> bool:
        return self.lifetime.tokens > 0


class UsageMeter:
    """增量用量台账。线程内使用，不做并发保护（桌宠是单线程定时器驱动）。"""

    def __init__(
        self,
        providers: Iterable[Provider],
        *,
        state_path: Path,
        pricing: PricingTable | None = None,
        pricing_override: Path | None = None,
        window_hours: float = DEFAULT_WINDOW_HOURS,
        backfill_days: int = DAILY_KEEP_DAYS,
    ) -> None:
        self.providers = list(providers)
        self.state_path = Path(state_path)
        self.pricing = pricing or load_pricing(pricing_override)
        self.window_hours = float(window_hours)
        self.backfill_days = int(backfill_days)

        self.cursors: dict[str, int] = {}
        self.records: dict[str, dict[str, float]] = {}
        self.daily: dict[str, dict[str, float]] = {}
        self.by_model_by_day: dict[str, dict[str, dict[str, float]]] = {}
        self.hourly: dict[str, list[float]] = {}
        self.hourly_tokens: dict[str, list[int]] = {}
        self.recent: list[list[float]] = []
        self.carried: dict[str, float] = _empty_totals()
        self.diagnostics: dict[str, object] = {"scans": 0, "lastScanTs": 0.0}
        # 计价可信度分两档，报告里分开说，不含糊成一句「估算」：
        #   estimated —— 命中家族单价（如 gpt-5.5 → gpt-5 家族），量级对、尾数不准
        #   unknown   —— 连家族都没命中，落到 default，只能当数量级参考
        self._estimated: set[str] = set()
        self._unknown: set[str] = set()

        self._load()

    # ------------------------------------------------------------ 持久化
    def _load(self) -> None:
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(raw, dict) or raw.get("schemaVersion") != STATE_SCHEMA:
            return
        self.cursors = _int_map(raw.get("cursors"))
        self.records = _record_map(raw.get("records"))
        self.daily = _day_map(raw.get("daily"))
        self.by_model_by_day = _nested_map(raw.get("byModelByDay"))
        self.hourly = _hour_map(raw.get("hourly"), float)
        self.hourly_tokens = _hour_map(raw.get("hourlyTokens"), int)
        recent = raw.get("recent")
        if isinstance(recent, list):
            self.recent = [
                [float(row[0]), float(row[1]), float(row[2])]
                for row in recent
                if isinstance(row, list) and len(row) >= 3
            ]
        carried = raw.get("carried")
        if isinstance(carried, dict):
            self.carried = {**_empty_totals(), **{k: float(v) for k, v in carried.items() if isinstance(v, (int, float))}}
        diag = raw.get("diagnostics")
        if isinstance(diag, dict):
            self.diagnostics.update(diag)

    def _save(self) -> None:
        payload = {
            "schemaVersion": STATE_SCHEMA,
            "cursors": self.cursors,
            "records": self.records,
            "daily": self.daily,
            "byModelByDay": self.by_model_by_day,
            "hourly": self.hourly,
            "hourlyTokens": self.hourly_tokens,
            "recent": self.recent,
            "carried": self.carried,
            "diagnostics": self.diagnostics,
        }
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self.state_path)
        except OSError:
            try:
                tmp.unlink()
            except OSError:
                pass

    # ------------------------------------------------------------ 扫描
    def scan(self, *, persist: bool = True) -> ScanResult:
        started = time.perf_counter()
        result = ScanResult()
        now = _now()

        for provider in self.providers:
            result.providers.append(provider.id)
            try:
                batches = list(provider.iter_usage(self.cursors))
            except Exception:  # provider 崩了不该拖垮整个台账
                continue
            for batch in batches:
                result.files += 1
                if batch.truncated:
                    result.truncated += 1
                    self._drop_records_for_file(batch.path)
                for record in batch.records:
                    delta, corrected = self._absorb(record, now)
                    if corrected:
                        result.corrections += 1
                    # 注意用 any(delta.values()) 而不是 `if not delta`：
                    # delta 是固定四个键的字典，全零时它仍然「非空」，
                    # 用 `not delta` 会把没增长的记录也计进 records。
                    if not any(delta.values()):
                        continue
                    result.records += 1
                    self._accumulate(record, delta, now)
                # 偏移最后写：先记账再推进，中途崩溃最多重放，不会漏
                self.cursors[batch.path] = batch.offset

        self._prune(now)
        result.elapsed_ms = int((time.perf_counter() - started) * 1000)
        self.diagnostics["scans"] = int(self.diagnostics.get("scans", 0)) + 1
        self.diagnostics["lastScanTs"] = now
        if persist:
            self._save()
        return result

    def _absorb(self, record: UsageRecord, now: float) -> tuple[dict[str, int], bool]:
        """去重 + 流式修正。返回 (本次应记的正增量, 是否发生了修正)。"""
        components = record.components()
        previous = self.records.get(record.key)
        if previous is None:
            self.records[record.key] = {
                **{k: float(v) for k, v in components.items()},
                "_ts": record.ts,
            }
            return dict(components), False

        delta: dict[str, int] = {}
        corrected = False
        for name, value in components.items():
            prior = int(previous.get(name, 0))
            if value > prior:
                delta[name] = value - prior
                previous[name] = float(value)
                corrected = True
            else:
                delta[name] = 0
        return delta, corrected

    def _accumulate(self, record: UsageRecord, delta: dict[str, int], now: float) -> None:
        row, exact = self.pricing.row_for(record.model)
        if not exact and record.model:
            # 精确行没命中，再看是「家族估算」还是「完全未知」
            from .pricing import family_for

            if family_for(record.model) == "default":
                self._unknown.add(record.model)
            else:
                self._estimated.add(record.model)

        cost = cost_usd(
            row,
            input_tokens=delta["input"],
            output_tokens=delta["output"],
            cache_write_tokens=delta["cacheWrite"],
            cache_read_tokens=delta["cacheRead"],
        )
        tokens = sum(delta.values())
        if tokens <= 0:
            return

        key = day_key(record.ts)
        bucket = self.daily.setdefault(key, _empty_totals())
        bucket["tokens"] += tokens
        bucket["cost"] += cost
        bucket["calls"] += 1
        for name in ("input", "output", "cacheWrite", "cacheRead"):
            bucket[name] += delta[name]

        model_key = record.model or "unknown"
        model_bucket = self.by_model_by_day.setdefault(key, {}).setdefault(
            model_key, {"tokens": 0.0, "cost": 0.0}
        )
        model_bucket["tokens"] += tokens
        model_bucket["cost"] += cost

        hours = self.hourly.setdefault(key, [0.0] * 24)
        hour_tokens = self.hourly_tokens.setdefault(key, [0] * 24)
        hour = hour_of(record.ts)
        hours[hour] += cost
        hour_tokens[hour] += tokens

        self.recent.append([record.ts, float(tokens), cost])

    def _drop_records_for_file(self, path_key: str) -> None:
        """文件被重置时清掉它的去重记录，否则重读会被当成「无增量」而漏记。"""
        prefix_codex = f"codex:{path_key}:"
        prefix_generic = f"generic:{path_key}:"
        for key in [k for k in self.records if k.startswith(prefix_codex) or k.startswith(prefix_generic)]:
            self.records.pop(key, None)

    def _prune(self, now: float) -> None:
        window_start = now - self.window_hours * 3600
        self.recent = [row for row in self.recent if row[0] >= window_start]

        record_cutoff = now - RECORD_KEEP_DAYS * 86400
        for key in [k for k, v in self.records.items() if float(v.get("_ts", 0)) < record_cutoff]:
            self.records.pop(key, None)

        # 日粒度超期 → 滚进 carried，终生口径因此不会因为清理而变小
        cutoff_day = day_key(now - DAILY_KEEP_DAYS * 86400)
        for key in sorted(k for k in self.daily if k < cutoff_day):
            row = self.daily.pop(key)
            for name in self.carried:
                self.carried[name] += float(row.get(name, 0))
            self.by_model_by_day.pop(key, None)
            self.hourly.pop(key, None)
            self.hourly_tokens.pop(key, None)

    # ------------------------------------------------------------ 读取
    def snapshot(self) -> UsageSnapshot:
        now = _now()
        window_start = now - self.window_hours * 3600

        window = UsageTotals()
        oldest = 0.0
        for ts, tokens, cost in self.recent:
            if ts < window_start:
                continue
            window.tokens += int(tokens)
            window.cost_usd += cost
            window.calls += 1
            if oldest == 0.0 or ts < oldest:
                oldest = ts

        today_key = day_key(now)
        today = _totals_from_row(self.daily.get(today_key, {}))

        lifetime = _totals_from_row(self.carried)
        for row in self.daily.values():
            lifetime.add(_totals_from_row(row))

        return UsageSnapshot(
            window=window,
            today=today,
            lifetime=lifetime,
            window_hours=self.window_hours,
            # 窗口起点取「窗口内最早那条记录」，不是 `now − 5h`。
            # 后者恒定等于整窗，会让外推永远算出「剩余 0 分钟」。
            window_started=oldest or now,
            hourly_today=list(self.hourly.get(today_key, [0.0] * 24)),
            hourly_tokens_today=list(self.hourly_tokens.get(today_key, [0] * 24)),
            daily={k: dict(v) for k, v in self.daily.items()},
            estimated_models=sorted(self._estimated),
            unknown_models=sorted(self._unknown),
            pricing_source=self.pricing.source,
            sources=[p.id for p in self.providers],
        )

    # 外推的最小观测时长。只有 1 分钟数据就线性外推到 5 小时，会得到
    # 一个吓人的假数字（1 分钟 3k → 5 小时 900k）。宁可标「样本不足」。
    MIN_PROJECTION_SECONDS = 600.0

    def window_projection(self, snapshot: UsageSnapshot) -> tuple[float, float, bool]:
        """按窗口内速率外推。

        返回 (预计窗口总量 token, 距离窗口最老记录滚出的秒数, 样本是否充足)。

        这是「余额提醒」真正有用的部分——不是告诉你已经花了多少，
        而是告诉你**照这个速度烧下去，这个窗口大概会到多少**。
        这是本项目的加工，不是厂商口径，所以返回值里带一个「样本是否充足」的诚实标记。
        """
        now = _now()
        elapsed = max(0.0, now - snapshot.window_started)
        window_seconds = self.window_hours * 3600
        sample_ok = elapsed >= self.MIN_PROJECTION_SECONDS
        basis = max(self.MIN_PROJECTION_SECONDS, elapsed)
        rate = snapshot.window.tokens / basis
        projected = rate * window_seconds
        remaining = max(0.0, window_seconds - elapsed)
        return projected, remaining, sample_ok


# ---------------------------------------------------------------- 反序列化
def _int_map(raw: object) -> dict[str, int]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, int] = {}
    for key, value in raw.items():
        try:
            out[str(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return out


def _record_map(raw: object) -> dict[str, dict[str, float]]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, float]] = {}
    for key, value in raw.items():
        if isinstance(value, dict):
            out[str(key)] = {
                k: float(v) for k, v in value.items() if isinstance(v, (int, float))
            }
    return out


def _day_map(raw: object) -> dict[str, dict[str, float]]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, float]] = {}
    for key, value in raw.items():
        if isinstance(value, dict):
            out[str(key)] = {**_empty_totals(), **{
                k: float(v) for k, v in value.items() if isinstance(v, (int, float))
            }}
    return out


def _nested_map(raw: object) -> dict[str, dict[str, dict[str, float]]]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, dict[str, float]]] = {}
    for day, models in raw.items():
        if not isinstance(models, dict):
            continue
        out[str(day)] = {
            str(model): {k: float(v) for k, v in row.items() if isinstance(v, (int, float))}
            for model, row in models.items()
            if isinstance(row, dict)
        }
    return out


def _hour_map(raw: object, cast) -> dict[str, list]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, list] = {}
    for key, value in raw.items():
        if isinstance(value, list) and len(value) == 24:
            out[str(key)] = [cast(v) for v in value]
    return out


def _totals_from_row(row: dict) -> UsageTotals:
    return UsageTotals(
        tokens=int(row.get("tokens", 0)),
        cost_usd=float(row.get("cost", 0.0)),
        calls=int(row.get("calls", 0)),
        input_tokens=int(row.get("input", 0)),
        output_tokens=int(row.get("output", 0)),
        cache_write_tokens=int(row.get("cacheWrite", 0)),
        cache_read_tokens=int(row.get("cacheRead", 0)),
    )


def recent_days(snapshot: UsageSnapshot, days: int = 7) -> list[tuple[str, dict]]:
    """最近 N 天（含今天），按日期升序。缺的日期补零，趋势图才不会跳。"""
    today = datetime.now().date()
    out: list[tuple[str, dict]] = []
    for offset in range(days - 1, -1, -1):
        key = (today - timedelta(days=offset)).strftime("%Y-%m-%d")
        out.append((key, snapshot.daily.get(key, _empty_totals())))
    return out
