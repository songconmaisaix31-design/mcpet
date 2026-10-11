"""真实 Qt 事件循环 + 网络 mock。没有 live 账号或模型请求。"""
import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from PySide6.QtCore import QObject, Signal, QTimer, QThread
from PySide6.QtWidgets import QApplication

from src import config, main
from src.mcd_mcp.brain import DealQuote, StoreInfo, NutritionFact, CouponRoundup
from src.mcd_mcp.client import Tool, ToolResult, McpError
from src.progress.tracker import ProgressSnapshot, SessionProgress
from src.agentbridge.records import ProgressRecord


class MonitorStub(QObject):
    progress_ready = Signal(object)
    usage_ready = Signal(object)
    failed = Signal(str)
    task_completed = Signal(object)

    def __init__(self):
        super().__init__()
        self.starts = self.stops = self.progress_requests = self.usage_requests = 0

    def start(self): self.starts += 1
    def stop(self): self.stops += 1
    def refresh_progress(self): self.progress_requests += 1
    def refresh_usage(self): self.usage_requests += 1


def pump_until(predicate, timeout=4):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.002)
    assert predicate(), "Qt condition timed out"


@pytest.fixture
def monster(tmp_path, monkeypatch):
    monkeypatch.setenv("MCPET_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MCD_MCP_TOKEN", "test-mcp-secret")
    monkeypatch.setenv("STEPFUN_API_KEY", "test-step-secret")
    monkeypatch.setattr(config, "load_env", lambda: None)  # 绝不读根 .env
    monkeypatch.setattr(main.QtDailyScheduler, "start", lambda self: None)
    monkeypatch.setattr(main.MonsterApp, "_load_sheet", lambda s: None)
    app = main.MonsterApp([], enforce_single_instance=False, monitor_factory=MonitorStub)
    app.activity = []
    app.window.set_activity = lambda state, context_percent=None, label="": app.activity.append((state, context_percent, label))
    pump_until(lambda: app.monitor is not None)
    yield app
    app.quit()
    pump_until(lambda: not app.tasks.thread.isRunning())
    if app.panel:
        app.panel.close()


class BusinessClient:
    def __init__(self):
        self.calls = []
        self.response = {"orderNo": "O-1", "payUrl": "https://pay.example/order"}
        self.error = None

    def list_tools(self):
        data = json.loads((config.PROJECT_ROOT / "docs/mcp-schemas.json").read_text(encoding="utf-8"))
        return [Tool("create-order", input_schema=data["create-order"]["inputSchema"])]

    def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if self.error:
            raise self.error
        return ToolResult(name, {}, json.dumps(self.response), self.response)


def order_brain(monster):
    brain = main.McdBrain(BusinessClient(), monster.guard)
    brain.take_way_options = lambda *a: [{"code": "take-in-store"}]
    brain.quote_order = lambda *a, **k: 990
    monster.tasks.worker.ensure_client = lambda: brain
    monster.pending_store = StoreInfo("S-1", "测试门店")
    monster.pending_quote = DealQuote("测试美式", "P-1", "测试券", "C-1", "CC-1", 1190, 990)
    return brain


def test_init_serial_single_flight_and_gui_responsive(monster, monkeypatch):
    events, completed, errors, ticks = [], [], [], []
    release, entered = threading.Event(), threading.Event()

    class Client:
        def __init__(self, *a, **k):
            assert k["max_retries_on_429"] == 0
            events.append(("construct", QThread.currentThread()))
        def initialize(self):
            events.append(("init", QThread.currentThread()))
            entered.set()
            assert release.wait(3)
        def close(self): events.append(("close", QThread.currentThread()))

    monkeypatch.setattr(main, "McdMcpClient", Client)
    timer = QTimer()
    timer.setInterval(10)
    timer.timeout.connect(lambda: ticks.append(time.monotonic()))
    timer.start()
    try:
        assert monster.run_mcp("one", lambda b: "one", completed.append, errors.append)
        assert monster.activity[-1][0] == "thinking"
        assert not monster.run_mcp("one", lambda b: "duplicate", completed.append)
        assert monster.run_mcp("two", lambda b: "two", completed.append, errors.append)
        pump_until(entered.is_set)
        pump_until(lambda: len(ticks) >= 5)
        assert completed == []
    finally:
        release.set()
        timer.stop()
    pump_until(lambda: not monster.tasks.busy)
    assert completed == ["one", "two"] and not errors
    assert len([e for e in events if e[0] == "init"]) == 1
    assert events[0][1] != QApplication.instance().thread()


def test_shutdown_drops_queued_work_and_returns_without_wait(monster):
    entered, release, seen = threading.Event(), threading.Event(), []
    def work():
        entered.set()
        release.wait(3)
        seen.append("active-finished")
    monster.run_async(work, lambda r: seen.append("callback"), key="active")
    monster.run_async(lambda: seen.append("queued"), lambda r: None, key="queued")
    pump_until(entered.is_set)
    started = time.monotonic()
    monster.quit()
    assert time.monotonic() - started < 0.1
    assert monster.tasks.thread.isRunning()
    assert monster.monitor.stops == 1
    release.set()
    pump_until(lambda: not monster.tasks.thread.isRunning())
    assert seen == ["active-finished"]


def test_init_failure_closes_provisional_and_next_task_can_retry(monster, monkeypatch):
    created, results, errors = [], [], []
    class Client:
        def __init__(self, *a, **k): created.append(self); self.closed = False
        def initialize(self):
            if len(created) == 1:
                raise McpError("bad test-mcp-secret test-step-secret")
        def close(self): self.closed = True
    monkeypatch.setattr(main, "McdMcpClient", Client)
    monster.run_mcp("first", lambda b: 1, results.append, errors.append)
    pump_until(lambda: not monster.tasks.busy)
    assert created[0].closed and monster.tasks.worker.brain is None
    assert "test-mcp-secret" not in errors[0] and "test-step-secret" not in errors[0]
    monster.run_mcp("second", lambda b: 2, results.append, errors.append)
    pump_until(lambda: not monster.tasks.busy)
    assert results == [2]


def test_order_cancel_does_not_write_and_confirmation_is_complete(monster, monkeypatch):
    brain = order_brain(monster)
    confirmations = []
    monkeypatch.setattr(monster, "_confirm", lambda title, summary, action: confirmations.append(summary) or False)
    monster.action_place_order()
    pump_until(lambda: not monster.tasks.busy)
    assert brain.client.calls == []
    assert all(t in confirmations[0] for t in ("测试门店", "测试美式", "测试券", "9.90", "外带", "storeCode", "items"))
    assert monster.guard.entries == []


@pytest.mark.parametrize("failure", ["network", "missing-order-id", "unknown-format"])
def test_unknown_order_consumes_quote_and_never_retries(monster, monkeypatch, failure):
    monkeypatch.setenv("MCD_DRY_RUN", "0")
    brain = order_brain(monster)
    if failure == "network": brain.client.error = McpError("connection lost")
    if failure == "missing-order-id": brain.client.response = {"success": True}
    if failure == "unknown-format": brain.client.response = ["unexpected"]
    monkeypatch.setattr(monster, "_confirm", lambda *a: True)
    monster.action_place_order()
    pump_until(lambda: not monster.tasks.busy)
    assert monster.pending_quote is None and monster.pending_store is None
    assert len(brain.client.calls) == 1
    assert monster.guard.entries[-1].status == "unknown"
    monster.action_place_order()
    assert len(brain.client.calls) == 1 and monster.last_order_no == ""


def test_price_change_needs_new_confirmation_and_no_write(monster, monkeypatch):
    brain = order_brain(monster)
    prices = iter([990, 1090])
    brain.quote_order = lambda *a, **k: next(prices)
    monkeypatch.setattr(monster, "_confirm", lambda *a: True)
    monster.action_place_order()
    pump_until(lambda: not monster.tasks.busy)
    assert brain.client.calls == []
    assert monster.pending_quote is None


def test_confirmed_mock_order_has_payment_ui_and_cancel_confirmation(monster, monkeypatch):
    monkeypatch.setenv("MCD_DRY_RUN", "0")
    brain = order_brain(monster)
    monkeypatch.setattr(monster, "_confirm", lambda *a: True)
    monster.action_place_order()
    pump_until(lambda: not monster.tasks.busy)
    assert monster.last_order_no == "O-1"
    assert monster.panel.open_button.isEnabled()
    assert monster.panel.copy_button.isEnabled()
    monkeypatch.setattr(monster, "_confirm", lambda *a: False)
    monster.action_cancel_last_order()
    assert [c[0] for c in brain.client.calls] == ["create-order"]


def test_known_mock_order_survives_audit_disk_failure(monster, monkeypatch):
    monkeypatch.setenv("MCD_DRY_RUN", "0")
    brain = order_brain(monster)
    monkeypatch.setattr(monster.guard, "record", lambda e: (_ for _ in ()).throw(OSError("disk unavailable")))
    monkeypatch.setattr(monster, "_confirm", lambda *a: True)
    monster.action_place_order()
    pump_until(lambda: not monster.tasks.busy)
    assert monster.last_order_no == "O-1"
    assert "审计保存失败" in monster.panel.payment_text.text()
    assert len(brain.client.calls) == 1


def test_nutrition_select_second_item_quantity_and_cancel_no_write(monster, monkeypatch):
    facts = [NutritionFact("第一项", energy_kcal=1), NutritionFact("用户选择", energy_kcal=100)]
    monster.tasks.worker.ensure_client = lambda: SimpleNamespace(nutrition=lambda: facts)
    monkeypatch.setattr(main.NutritionSelectDialog, "selection", lambda self: None)
    monster.action_log_meal()
    pump_until(lambda: not monster.tasks.busy)
    assert not monster.ledger.entries and not monster.ledger.path.exists()
    monkeypatch.setattr(main.NutritionSelectDialog, "selection", lambda self: (facts[1], 2.5))
    monster.action_log_meal()
    pump_until(lambda: not monster.tasks.busy)
    assert len(monster.ledger.entries) == 1
    assert monster.ledger.entries[0].energy_kcal == 250
    assert "用户选择" in monster.ledger.entries[0].meal_name


def test_lunch_only_reads_and_all_work_is_serial(monster):
    calls = []
    brain = SimpleNamespace(coupon_roundup=lambda **k: calls.append(("coupons", k)) or CouponRoundup(),
                            resolve_default_store=lambda: StoreInfo("S", "测试门店"),
                            best_deal=lambda s: calls.append(("deal", {})) or [])
    monster.tasks.worker.ensure_client = lambda: brain
    monster.on_lunch()
    pump_until(lambda: not monster.tasks.busy)
    assert calls == [("coupons", {"claim": False}), ("deal", {})]


def test_monitor_uses_real_context_estimate_no_stale_success(monster):
    record = ProgressRecord(source="codex", session_id="s", state="working", context_used=20, context_limit=100)
    record.context_limit_estimated = True
    monster.monitor.progress_ready.emit(ProgressSnapshot([SessionProgress(record)]))
    assert monster.activity[-1][0:2] == ("working", 20)
    assert "上下文上限估算" in monster.activity[-1][2]
    monster.monitor.progress_ready.emit(ProgressSnapshot([SessionProgress(record, stale=True)]))
    assert monster.activity[-1][0] == "idle" and monster.activity[-1][1] is None
    assert "未知" in monster.activity[-1][2]
    monster.action_progress()
    assert monster.monitor.progress_requests == 1
    monster.monitor.failed.emit("刷新失败 test-step-secret")
    text = monster.panel.progress_detail.toPlainText()
    monster.action_progress()
    assert monster.panel.progress_detail.toPlainText() == text
    assert "test-step-secret" not in text and "最后成功快照" in text
    assert monster.monitor.starts == 1


def test_touch_signal_does_not_override_a_feedback_and_close_runs(monster):
    monster.window.say("A 的触摸反馈", 2000)
    monster.window.clicked.emit()
    assert monster.window.bubble.label.text() == "A 的触摸反馈"
    closed, unlock_checks = [], []
    preferences = config.data_dir() / "pet-preferences.json"
    original = monster.window.closeEvent
    def close_event(event):
        # A.closeEvent 的持久化契约 stub：C 必须触发 close 而不能只 hide。
        preferences.write_text(json.dumps({"position": [monster.window.x(), monster.window.y()]}), encoding="utf-8")
        closed.append(monster.window.pos())
        original(event)
    monster.window.closeEvent = close_event
    monster.instance = SimpleNamespace(close=lambda: unlock_checks.append(preferences.exists()))
    monster.window.move(321, 234)
    monster.quit()
    pump_until(lambda: not monster.tasks.thread.isRunning())
    pump_until(lambda: bool(closed))
    assert (closed[0].x(), closed[0].y()) == (321, 234)
    assert json.loads(preferences.read_text(encoding="utf-8"))["position"] == [321, 234]
    assert unlock_checks == [True]
