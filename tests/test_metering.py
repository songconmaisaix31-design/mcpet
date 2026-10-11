"""metering 的离线测试。

样本形状全部照抄真实返回（Claude transcript 的 usage 字段名、Codex 的
last_token_usage 子集关系），确保测的是真实语义而不是我编的。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from src.agentbridge.providers.base import UsageBatch
from src.agentbridge.records import UsageRecord
from src.metering.pricing import (
    cost_usd,
    family_for,
    load_pricing,
    norm_model,
    normalize_row,
)
from src.metering.report import (
    bubble,
    format_tokens,
    format_usd,
    proportional_bar,
    reminder_level,
    report,
)
from src.metering.usage import UsageMeter, day_key, recent_days


class FakeProvider:
    """喂固定批次的假 provider。用来把聚合逻辑从真实日志里隔离出来测。"""

    id = "fake"
    label = "Fake"

    def __init__(self, batches: list[UsageBatch]) -> None:
        self._batches = batches

    def roots(self) -> list[Path]:
        return []

    def iter_usage(self, cursors):
        return iter(self._batches)

    def iter_progress(self):
        return iter([])


def record(key: str, ts: float, model: str = "claude-sonnet-4-5", **usage) -> UsageRecord:
    return UsageRecord(key=key, ts=ts, model=model, **usage)


def make_meter(tmp_path: Path, batches: list[UsageBatch]) -> UsageMeter:
    return UsageMeter([FakeProvider(batches)], state_path=tmp_path / "usage.json")


# ------------------------------------------------------------------ 去重与流式修正


def test_streaming_correction_counts_only_positive_delta(tmp_path):
    """同一 message.id 写多行，只有增长的部分才该记账。"""
    now = time.time()
    batches = [
        UsageBatch(path="f1", offset=10, records=[record("k1", now, output_tokens=10)]),
        UsageBatch(path="f1", offset=20, records=[record("k1", now, output_tokens=250)]),
        UsageBatch(path="f1", offset=30, records=[record("k1", now, output_tokens=250)]),
    ]
    meter = make_meter(tmp_path, batches)
    result = meter.scan()
    snapshot = meter.snapshot()

    assert result.corrections == 1          # 只有第二行是真正的增长
    assert result.records == 2              # 首次 + 一次增量
    assert snapshot.today.output_tokens == 250   # 不是 10+250+250=510
    assert snapshot.today.calls == 2


def test_shrinking_snapshot_never_subtracts(tmp_path):
    now = time.time()
    batches = [
        UsageBatch(path="f", offset=1, records=[record("k", now, output_tokens=500)]),
        UsageBatch(path="f", offset=2, records=[record("k", now, output_tokens=100)]),
    ]
    meter = make_meter(tmp_path, batches)
    meter.scan()
    assert meter.snapshot().today.output_tokens == 500


def test_cursors_advance_even_without_records(tmp_path):
    """没有新记录的文件也必须推进偏移，否则每轮都从头扫。"""
    meter = make_meter(tmp_path, [UsageBatch(path="f", offset=999, records=[])])
    meter.scan()
    assert meter.cursors["f"] == 999


def test_truncated_file_drops_its_records(tmp_path):
    """文件被轮转重读时，旧去重记录必须清掉，否则新内容会被当成「无增量」。"""
    now = time.time()
    batches = [
        UsageBatch(path="f", offset=100, records=[record("codex:f:0", now, output_tokens=10)]),
        UsageBatch(path="f", offset=50, truncated=True,
                   records=[record("codex:f:0", now, output_tokens=10)]),
    ]
    meter = make_meter(tmp_path, batches)
    result = meter.scan()
    assert result.truncated == 1
    assert meter.snapshot().today.output_tokens == 20   # 两次都记上了


# ------------------------------------------------------------------ 聚合


def test_daily_hourly_and_window(tmp_path):
    now = time.time()
    # 6 小时前那条可能已经跨天（取决于跑测试的时刻），所以按时间戳自己算期望值，
    # 不假设它一定落在「今天」。
    old = now - 6 * 3600
    batches = [
        UsageBatch(path="f", offset=1, records=[
            record("a", now, input_tokens=100, output_tokens=50),
            record("b", old, input_tokens=10, output_tokens=5),
        ]),
    ]
    meter = make_meter(tmp_path, batches)
    meter.scan()
    snapshot = meter.snapshot()

    old_is_today = day_key(old) == day_key(now)
    expected_today = 165 if old_is_today else 150

    assert snapshot.window.calls == 1          # 6 小时前在 5 小时窗口外
    assert snapshot.window.tokens == 150
    assert snapshot.today.tokens == expected_today
    assert sum(snapshot.hourly_tokens_today) == expected_today
    assert snapshot.lifetime.tokens == 165     # 终生不受窗口/分天影响


def test_lifetime_survives_pruning(tmp_path):
    """日粒度超期滚进 carried，终生口径不能因为清理而变小。"""
    meter = make_meter(tmp_path, [])
    meter.daily["2020-01-01"] = {
        "tokens": 1000, "cost": 1.0, "calls": 3,
        "input": 1000, "output": 0, "cacheWrite": 0, "cacheRead": 0,
    }
    before = meter.snapshot().lifetime.tokens
    assert before == 1000
    meter._prune(time.time())
    assert "2020-01-01" not in meter.daily
    assert meter.snapshot().lifetime.tokens == 1000


def test_persistence_round_trip(tmp_path):
    now = time.time()
    state = tmp_path / "usage.json"
    batches = [UsageBatch(path="f", offset=7, records=[record("k", now, output_tokens=42)])]

    first = UsageMeter([FakeProvider(batches)], state_path=state)
    first.scan()

    second = UsageMeter([FakeProvider([])], state_path=state)
    assert second.cursors["f"] == 7
    assert second.snapshot().today.output_tokens == 42


def test_state_written_atomically_no_tmp_left(tmp_path):
    now = time.time()
    state = tmp_path / "usage.json"
    meter = make_meter(tmp_path, [UsageBatch(path="f", offset=1, records=[record("k", now)])])
    meter.scan()
    assert state.is_file()
    assert not state.with_suffix(".tmp").exists()


def test_schema_mismatch_is_reported_without_overwriting(tmp_path):
    state = tmp_path / "usage.json"
    state.write_text(json.dumps({"schemaVersion": 999, "cursors": {"x": 1}}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="版本未知"):
        UsageMeter([], state_path=state)
    assert json.loads(state.read_text())["cursors"] == {"x": 1}


# ------------------------------------------------------------------ 窗口与外推


def test_window_projection_needs_enough_samples(tmp_path):
    now = time.time()
    meter = make_meter(tmp_path, [
        UsageBatch(path="f", offset=1, records=[record("k", now, input_tokens=3000)]),
    ])
    meter.scan()
    snapshot = meter.snapshot()
    projected, remaining, sample_ok = meter.window_projection(snapshot)
    assert sample_ok is False                 # 只有一条刚写入的记录
    assert projected == 3000 / 600 * 5 * 3600  # 按最小观测时长外推，不按 1 秒
    assert remaining <= 5 * 3600


def test_window_projection_uses_oldest_record_as_start(tmp_path):
    now = time.time()
    started = now - 3600
    meter = make_meter(tmp_path, [
        UsageBatch(path="f", offset=1, records=[
            record("old", started, input_tokens=1000),
            record("new", now - 10, input_tokens=1000),
        ]),
    ])
    meter.scan()
    snapshot = meter.snapshot()
    assert snapshot.window_started == pytest.approx(started, abs=1)
    projected, _, sample_ok = meter.window_projection(snapshot)
    assert sample_ok is True
    assert projected == pytest.approx(2000 / 3600 * 5 * 3600, rel=0.01)


# ------------------------------------------------------------------ 计价


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("claude-sonnet-4-5", "claude-sonnet-4-5"),
        ("anthropic.claude-opus-4-5-20251101-v1:0", "claude-opus-4-5"),
        ("us.anthropic.claude-3-5-haiku-20241022", "claude-3-5-haiku"),
        ("gpt-5-codex", "gpt-5-codex"),
        ("", ""),
    ],
)
def test_norm_model(raw, expected):
    assert norm_model(raw) == expected


@pytest.mark.parametrize(
    "model,family",
    [
        ("claude-opus-4-5", "opus"),
        ("claude-sonnet-4-5", "sonnet"),
        ("claude-3-5-haiku", "haiku"),
        ("gpt-5.5", "gpt-5"),
        ("gpt5.5", "gpt-5"),
        ("codex-auto-review", "gpt-5"),
        ("deepseek-v3", "deepseek"),
        ("step-3.5-flash", "step"),
        ("完全没听过的模型", "default"),
    ],
)
def test_family_for(model, family):
    assert family_for(model) == family


def test_normalize_row_derives_cache_prices_from_input():
    row = normalize_row({"input": 10, "output": 50}, {"input": 1, "output": 1})
    assert row["cacheWrite5m"] == pytest.approx(12.5)
    assert row["cacheWrite1h"] == pytest.approx(20.0)
    assert row["cacheRead"] == pytest.approx(1.0)


def test_pricing_override_merges_and_wins(tmp_path):
    override = tmp_path / "pricing.json"
    override.write_text(
        json.dumps({
            "sonnet": {"input": 1.0},
            "models": {"claude-sonnet-4-5": {"input": 0.5, "output": 0.5}},
        }),
        encoding="utf-8",
    )
    table = load_pricing(override)
    row, exact = table.row_for("claude-sonnet-4-5")
    assert exact is True
    assert row["input"] == 0.5
    # 家族被部分覆盖，未给的字段沿用默认，不会变 0
    family_row, family_exact = table.row_for("claude-sonnet-4-9")
    assert family_exact is False
    assert family_row["input"] == 1.0
    assert family_row["output"] > 0


def test_cost_usd_math():
    row = {"input": 3.0, "output": 15.0, "cacheWrite5m": 3.75, "cacheRead": 0.3}
    cost = cost_usd(row, input_tokens=1_000_000, output_tokens=0,
                    cache_write_tokens=0, cache_read_tokens=0)
    assert cost == pytest.approx(3.0)


# ------------------------------------------------------------------ 文案


def test_formatters():
    assert format_tokens(999) == "999"
    assert format_tokens(1_500) == "1.5k"
    assert format_tokens(2_400_000) == "2.40M"
    assert format_tokens(3_000_000_000) == "3.00B"
    assert format_usd(0.5) == "$0.5000"
    assert format_usd(12.345) == "$12.35"
    assert format_usd(1500) == "$1,500"
    assert proportional_bar(50, 100) == "██████"
    assert proportional_bar(0, 100) == ""


def test_bubble_and_report_say_no_data_honestly(tmp_path):
    meter = UsageMeter([], state_path=tmp_path / "usage.json")   # 一个数据源都没有
    snapshot = meter.snapshot()
    projected, remaining, sample_ok = meter.window_projection(snapshot)
    assert "还没读到" in bubble(snapshot, projected, sample_ok)
    assert reminder_level(snapshot, projected) == "unknown"
    text = report(snapshot, projected, remaining, sample_ok)
    assert "无可用数据源" in text
    assert "不等于厂商账单" in text


def test_report_marks_estimated_models(tmp_path):
    now = time.time()
    meter = make_meter(tmp_path, [
        UsageBatch(path="f", offset=1, records=[
            record("a", now, model="gpt-5.5", input_tokens=100),
            record("b", now, model="完全不认识的模型", input_tokens=100),
        ]),
    ])
    meter.scan()
    snapshot = meter.snapshot()
    projected, remaining, sample_ok = meter.window_projection(snapshot)
    text = report(snapshot, projected, remaining, sample_ok)
    assert "gpt-5.5" in text
    assert "按家族估算" in text
    assert "未识别模型" in text
    assert "完全不认识的模型" in text


def test_reminder_levels(tmp_path):
    now = time.time()
    meter = make_meter(tmp_path, [
        UsageBatch(path="f", offset=1, records=[
            record("a", now - 3600, input_tokens=2_000_000),
        ]),
    ])
    meter.scan()
    snapshot = meter.snapshot()
    projected, _, _ = meter.window_projection(snapshot)
    assert reminder_level(snapshot, projected) == "heavy"


def test_recent_days_fills_gaps(tmp_path):
    meter = make_meter(tmp_path, [])
    snapshot = meter.snapshot()
    days = recent_days(snapshot, 5)
    assert len(days) == 5
    assert all(row["tokens"] == 0 for _, row in days)
    assert days[-1][0] == day_key(time.time())


def test_scan_lazy_consumption_and_first_failure(tmp_path):
    now = time.time()
    meter = make_meter(tmp_path, [])
    class Streaming(FakeProvider):
        def iter_usage(self, cursors):
            yield UsageBatch(path="f", offset=1, records=[record("k", now, input_tokens=1)])
            assert cursors["f"] == 1
            raise OSError("first read failure")
    meter.providers = [Streaming([])]
    result = meter.scan()
    assert result.errors == ["fake: OSError: first read failure"]
    assert meter.snapshot().status == "UNKNOWN"
    meter.providers = [FakeProvider([])]
    meter.scan()
    assert meter.diagnostics["firstFailure"] == result.errors[0]
    assert meter.snapshot().lifetime.tokens == 1


def test_pricing_confidence_survives_restart_and_incremental_scan(tmp_path):
    meter = make_meter(tmp_path, [UsageBatch(path="f", offset=10, records=[
        record("k", time.time(), model="gpt-5.5", input_tokens=10),
        record("u", time.time(), model="unknown-model", input_tokens=10),
    ])])
    meter.scan()
    reopened = UsageMeter([], state_path=meter.state_path)
    reopened.scan()
    assert "gpt-5.5" in reopened.snapshot().estimated_models
    assert "unknown-model" in reopened.snapshot().unknown_models


def test_historical_stable_keys_not_counted_twice_after_pruning_restart(tmp_path):
    batch = UsageBatch(path="f", offset=10, records=[
        record("stable", time.time() - 110 * 86400, input_tokens=40),
    ])
    meter = make_meter(tmp_path, [batch])
    meter.scan()
    reopened = UsageMeter([FakeProvider([batch])], state_path=meter.state_path)
    assert reopened.scan().records == 0
    assert reopened.snapshot().lifetime.tokens == 40


def test_failed_persistence_keeps_original(tmp_path, monkeypatch):
    meter = make_meter(tmp_path, [])
    meter.scan()
    previous = meter.state_path.read_bytes()
    def broken(*args):
        raise OSError("disk full")
    monkeypatch.setattr("src.metering.usage.os.replace", broken)
    with pytest.raises(OSError, match="disk full"):
        meter.scan()
    assert meter.state_path.read_bytes() == previous


def test_corrupt_existing_ledger_not_overwritten(tmp_path):
    state = tmp_path / "usage.json"
    state.write_text("broken", encoding="utf-8")
    with pytest.raises(RuntimeError, match="保留原文件"):
        UsageMeter([], state_path=state)
    assert state.read_text() == "broken"


def test_codex_mid_file_model_survives_incremental_scan_and_restart(tmp_path):
    from src.agentbridge.providers.codex import CodexProvider
    root = tmp_path / "logs"
    root.mkdir()
    path = root / "session.jsonl"
    def event():
        return {"type": "event_msg", "timestamp": time.time(), "payload": {"type": "token_count", "info": {
            "last_token_usage": {"input_tokens": 10, "output_tokens": 2}}}}
    entries = [{"type": "turn_context", "payload": {"model": "gpt-5.5"}}, event(),
               {"type": "turn_context", "payload": {"model": "gpt-6"}}, event()]
    path.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    state = tmp_path / "usage.json"
    meter = UsageMeter([CodexProvider([root])], state_path=state)
    meter.scan()
    assert meter.model_hints[str(path)] == "gpt-6"
    with path.open("a", encoding="utf-8") as h:
        h.write(json.dumps(event()) + "\n")
    reopened = UsageMeter([CodexProvider([root])], state_path=state)
    assert reopened.scan().records == 1
    buckets = reopened.by_model_by_day[day_key(time.time())]
    assert buckets["gpt-5.5"]["tokens"] == 12
    assert buckets["gpt-6"]["tokens"] == 24
    assert reopened.scan().records == 0
