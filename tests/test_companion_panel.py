"""Integration of background facts into the pet-only presentation.

The former CompanionPanel interaction contract is replaced by the user's pet-menu
requirement. Historical native performance tests remain unchanged.
"""
from src import config
from src.agentbridge.records import ProgressRecord, UsageTotals
from src.progress.tracker import ProgressSnapshot, SessionProgress
from src.metering.usage import UsageSnapshot
from test_app_actions import monster


def test_progress_requested_bubble_stale_context_and_masked_failure(monster):
    record = ProgressRecord(source="codex", session_id="fixture", title="夹具任务", state="needsinput", context_used=25, context_limit=100)
    record.context_limit_estimated = True
    monster.monitor.progress_ready.emit(ProgressSnapshot([SessionProgress(record, stale=True, age_seconds=3600)]))
    monster.action_progress()
    text = monster.window.bubble.label.text()
    assert "codex" in text and "25" in text and "估算" in text and "未知" in text
    monster.monitor.failed.emit("刷新失败 test-mcp-secret")
    monster.action_progress()
    text = monster.window.bubble.label.text()
    assert "上一次" in text and "过时" in text and "刷新失败" in text and "test-mcp-secret" not in text
    assert monster.panel is None and monster.monitor.starts == 1


def test_usage_requested_bubble_sample_unknown_and_not_vendor_quota(monster):
    usage = UsageSnapshot(window=UsageTotals(tokens=30), today=UsageTotals(tokens=50), lifetime=UsageTotals(tokens=80), sources=["codex"])
    monster.monitor.usage_ready.emit((usage, 100, False))
    monster.action_balance()
    text = monster.window.bubble.label.text()
    assert "30" in text and "记录还太少" in text and "UNKNOWN" in text and "不等于厂商余额" in text
    assert monster.monitor.usage_requests == 1 and monster.panel is None


def test_waiting_condition_bubbles_once_and_idle_does_not_claim_completion(monster):
    record = ProgressRecord(source="generic", session_id="fixture", state="needsinput")
    snapshot = ProgressSnapshot([SessionProgress(record)])
    monster.monitor.progress_ready.emit(snapshot)
    assert "等你输入" in monster.window.bubble.label.text()
    monster.window.say("保留本次结果")
    monster.monitor.progress_ready.emit(snapshot)
    assert monster.window.bubble.label.text() == "保留本次结果"
    monster.monitor.progress_ready.emit(ProgressSnapshot([]))
    assert monster.activity[-1][0] == "idle" and "未知" in monster.activity[-1][2]
    monster.monitor.task_completed.emit({"fixture": True})
    assert "日志明确记录" in monster.window.bubble.label.text()


def test_late_callbacks_after_quit_cannot_show_bubble(monster):
    monster.quit()
    monster.monitor.progress_ready.emit(ProgressSnapshot([]))
    monster.monitor.failed.emit("迟到的失败")
    assert "迟到的失败" not in monster.window.bubble.label.text()
