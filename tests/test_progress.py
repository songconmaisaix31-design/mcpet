"""progress 的离线测试。"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from src.agentbridge.records import ProgressRecord
from src.progress.report import (
    bubble,
    context_bar,
    human_age,
    pet_state_for,
    report,
    state_label,
)
from src.progress.tracker import ProcessSampler, ProgressTracker


class FakeProvider:
    def __init__(self, provider_id: str, records: list[ProgressRecord]) -> None:
        self.id = provider_id
        self.label = provider_id
        self._records = records

    def roots(self) -> list[Path]:
        return []

    def iter_usage(self, cursors):
        return iter([])

    def iter_progress(self):
        return iter(self._records)


class BrokenProvider(FakeProvider):
    def iter_progress(self):
        raise RuntimeError("provider 挂了")


def rec(provider: str, session: str, updated: float, **kwargs) -> ProgressRecord:
    return ProgressRecord(source=provider, session_id=session, updated_at=updated, **kwargs)


def test_merges_and_keeps_newest_per_session():
    now = time.time()
    tracker = ProgressTracker([
        FakeProvider("a", [
            rec("a", "s1", now - 100, state="idle", title="旧"),
            rec("a", "s1", now - 10, state="working", title="新"),
        ]),
        FakeProvider("b", [rec("b", "s2", now - 5, state="thinking")]),
    ], stale_minutes=30)
    snapshot = tracker.snapshot(now=now)
    by_session = {item.record.session_id: item for item in snapshot.sessions}
    assert set(by_session) == {"s1", "s2"}
    assert by_session["s1"].record.title == "新"
    assert by_session["s1"].record.state == "working"


def test_same_session_id_from_different_sources_stay_separate():
    now = time.time()
    tracker = ProgressTracker([
        FakeProvider("a", [rec("a", "same", now)]),
        FakeProvider("b", [rec("b", "same", now)]),
    ])
    assert len(tracker.snapshot(now=now).sessions) == 2


def test_staleness_and_ordering():
    now = time.time()
    tracker = ProgressTracker([
        FakeProvider("a", [
            rec("a", "fresh", now - 60),
            rec("a", "stale", now - 3600),
        ]),
    ], stale_minutes=30)
    snapshot = tracker.snapshot(now=now)
    assert [i.record.session_id for i in snapshot.active] == ["fresh"]
    assert [i.record.session_id for i in snapshot.stale] == ["stale"]
    # 活跃的排前面
    assert snapshot.sessions[0].record.session_id == "fresh"


def test_max_sessions_caps_output():
    now = time.time()
    records = [rec("a", f"s{i}", now - i) for i in range(50)]
    tracker = ProgressTracker([FakeProvider("a", records)], max_sessions=5)
    assert len(tracker.snapshot(now=now).sessions) == 5


def test_background_tasks_counts_active_only():
    now = time.time()
    tracker = ProgressTracker([
        FakeProvider("a", [
            rec("a", "live", now, background_tasks=2),
            rec("a", "dead", now - 7200, background_tasks=5),
        ]),
    ], stale_minutes=30)
    assert tracker.snapshot(now=now).background_tasks == 2


def test_broken_provider_does_not_break_snapshot():
    now = time.time()
    tracker = ProgressTracker([
        BrokenProvider("bad", []),
        FakeProvider("good", [rec("good", "s", now)]),
    ])
    snapshot = tracker.snapshot(now=now)
    assert len(snapshot.sessions) == 1
    assert snapshot.sessions[0].record.source == "good"


def test_empty_tracker_is_honest():
    tracker = ProgressTracker([])
    snapshot = tracker.snapshot()
    assert snapshot.has_data is False
    assert "没读到" in bubble(snapshot)
    assert "无可用数据源" in report(snapshot)


def test_process_sampler_degrades_when_psutil_missing():
    """没装 psutil 时不能抛异常，只能标记不可用。"""
    sampler = ProcessSampler()
    if not sampler.available:
        assert sampler.sample() == {}
    else:
        assert isinstance(sampler.sample(), dict)


def test_process_sampling_disabled_by_default(tmp_path):
    tracker = ProgressTracker([FakeProvider("a", [])], watch_processes=False)
    assert tracker.watch_processes is False
    assert tracker.snapshot().process_sampling is False


# ------------------------------------------------------------------ 文案


@pytest.mark.parametrize(
    "agent_state,pet_state",
    [
        ("working", "working"),
        ("thinking", "thinking"),
        ("waiting", "waiting"),
        ("needsinput", "waiting"),
        ("error", "error"),
        ("failed", "error"),
        ("done", "happy"),
        ("idle", "idle"),
        ("完全没见过的状态", "idle"),
        ("", "idle"),
    ],
)
def test_pet_state_mapping(agent_state, pet_state):
    assert pet_state_for(agent_state) == pet_state


def test_state_label_has_chinese_and_falls_back():
    assert state_label("working") == "干活中"
    assert state_label("weird") == "weird"


def test_human_age():
    assert human_age(30) == "30 秒前"
    assert human_age(120) == "2 分钟前"
    assert human_age(7200) == "2 小时前"
    assert human_age(172800) == "2 天前"
    assert human_age(float("inf")) == "未知"


def test_context_bar():
    assert context_bar(None) == "—"
    assert context_bar(0) == "░" * 10
    assert context_bar(100) == "█" * 10
    assert context_bar(50) == "█" * 5 + "░" * 5


def test_bubble_reports_active_and_hot_context():
    now = time.time()
    tracker = ProgressTracker([
        FakeProvider("a", [
            rec("a", "s1", now - 5, state="working", title="重构登录", project="proj",
                context_used=150_000, context_limit=200_000),
            rec("a", "s2", now - 10, state="working", background_tasks=1),
        ]),
    ])
    snapshot = tracker.snapshot(now=now)
    text = bubble(snapshot)
    assert "2 个会话活跃" in text
    assert "2 个在干活" in text
    assert "1 个后台任务" in text
    assert "上下文已用 75%" in text


def test_report_lists_sessions_with_source_and_state():
    now = time.time()
    tracker = ProgressTracker([
        FakeProvider("codex", [
            rec("codex", "s1", now - 5, state="working", project="McPet",
                context_used=100_000, context_limit=200_000, model="gpt-5-codex"),
        ]),
    ])
    text = report(tracker.snapshot(now=now))
    assert "codex" in text
    assert "McPet" in text
    assert "干活中" in text
    assert "50%" in text
    assert "滞后" in text        # 必须说明这是日志推导，不是实时推送
