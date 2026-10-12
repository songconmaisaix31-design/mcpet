"""C UI contract fixtures: no account/credential files or real network."""
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path
import json
import subprocess
import sys
import time
from types import ModuleType

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import QApplication, QLabel

from src import config, main
from src.pet.dialogs import CompanionPanel
from src.pet.spritesheet import SpriteLoadError, AnimationSheet
from test_app_actions import MonitorStub, pump_until


@dataclass(frozen=True)
class BucketFixture:
    name: str
    used_percent: float | None
    resets_at: float | None


@dataclass(frozen=True)
class BalanceFixture:
    currency: str
    total: Decimal
    granted: Decimal
    topped_up: Decimal


@dataclass(frozen=True)
class AccountFixture:
    provider: str
    label: str
    status: str
    updated_at: float | None
    buckets: tuple = ()
    balances: tuple = ()
    message: str = ""


@dataclass(frozen=True)
class SnapshotFixture:
    accounts: tuple
    observed_at: float


class AccountMonitorStub(QObject):
    snapshot_ready = Signal(object)
    failed = Signal(str)
    stopped = Signal()

    def __init__(self):
        super().__init__()
        self.starts = self.stops = self.refreshes = 0
        self.sources = []

    def start(self): self.starts += 1
    def stop(self):
        self.stops += 1
        self.stopped.emit()
    def refresh(self): self.refreshes += 1
    def reconfigure(self, *, orca_source=None, deepseek_source=None):
        self.sources.append(deepseek_source)


class BalanceSourceStub:
    def __init__(self, api_key=""):
        self.api_key = api_key


class SheetFixture:
    """Colored test pixels are only a render contract fixture, not a character asset."""
    def __init__(self, color): self.color = color
    def frame(self, *args):
        pixmap = QPixmap(32, 32)
        pixmap.fill(self.color)
        return pixmap


def sample_snapshot(now=None):
    now = time.time() if now is None else now
    return SnapshotFixture((
        AccountFixture("codex", "Codex · 受控夹具", "ok", now, (BucketFixture("Weekly", 16.25, now + 90061),)),
        AccountFixture("cursor", "Cursor · 受控夹具", "ok", now, (BucketFixture("Models", 20, now + 3600), BucketFixture("Other Models", 90, None))),
        AccountFixture("claude", "Claude · 受控夹具", "unavailable", None, message="尚无可读取额度"),
        AccountFixture("grok", "Grok · 受控夹具", "ok", now, (BucketFixture("Weekly", 0, now + 123456),)),
        AccountFixture("deepseek", "DeepSeek · 受控夹具", "ok", now, balances=(
            BalanceFixture("CNY", Decimal("123.456789012345678901"), Decimal("3.456789012345678901"), Decimal("120")),
            BalanceFixture("USD", Decimal("0.001"), Decimal("0"), Decimal("0.001")))),
    ), now)


@pytest.fixture
def quota_monster(tmp_path, monkeypatch):
    monkeypatch.setenv("MCPET_DATA_DIR", str(tmp_path))
    for key in ("MCD_MCP_TOKEN", "STEPFUN_API_KEY", "DEEPSEEK_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(config, "load_env", lambda: None)
    monkeypatch.setattr(main.QtDailyScheduler, "start", lambda self: None)
    monkeypatch.setattr(main.MonsterApp, "_load_sheet", lambda self: None)
    accounts = ModuleType("src.accounts")
    accounts.DeepSeekBalanceSource = BalanceSourceStub
    monkeypatch.setitem(sys.modules, "src.accounts", accounts)
    def forbidden(*args, **kwargs):
        pytest.fail("C contract test attempted model/MCP/account network")
    import httpx
    monkeypatch.setattr(httpx.Client, "request", forbidden)
    monkeypatch.setattr(main.McdMcpClient, "__init__", forbidden)
    from src.llm.stepfun import StepFunClient
    monkeypatch.setattr(StepFunClient, "__init__", forbidden)
    app = main.MonsterApp([], enforce_single_instance=False, monitor_factory=MonitorStub,
                         account_monitor_factory=AccountMonitorStub)
    pump_until(lambda: app.monitor is not None and app.account_monitor is not None)
    yield app
    app.quit()
    pump_until(lambda: not app.tasks.thread.isRunning())
    assert app.account_monitor.stops == 1


def test_bubble_preserves_buckets_precise_money_unknown_and_sources(quota_monster):
    app = quota_monster
    app.action_quota()
    app.account_monitor.snapshot_ready.emit(sample_snapshot())
    text = app.window.bubble.label.text()
    assert "Weekly" in text and "16.25%" in text and "Other Models" in text
    assert "123.456789012345678901" in text and "USD 余额 0.001" in text
    assert "UNKNOWN" in text and "重置时间 UNKNOWN" in text
    assert app.panel is None and app.window.bubble.width() == 260
    assert app.account_monitor.refreshes == 1


@pytest.mark.parametrize("percent", [None, float("nan"), -1, 101])
def test_invalid_percentage_is_unknown_not_fake_zero(quota_monster, percent):
    app = quota_monster
    app.action_quota()
    app.account_monitor.snapshot_ready.emit(SnapshotFixture((AccountFixture("codex", "Codex", "error", None,
        (BucketFixture("weekly", percent, None),), message="刷新失败"),), time.time()))
    text = app.window.bubble.label.text()
    assert "UNKNOWN" in text and "已用 0%" not in text and "已用 nan" not in text
    assert "刷新失败" in text


def test_failed_refresh_retains_explicit_stale_snapshot_then_recovers(quota_monster):
    app = quota_monster
    app.account_monitor.snapshot_ready.emit(sample_snapshot())
    app.action_quota()
    app.account_monitor.failed.emit("断线")
    text = app.window.bubble.label.text()
    assert "断线" in text and "上次的记录" in text and "可能过时" in text and "123.456789012345678901" in text
    app.action_quota()
    app.account_monitor.snapshot_ready.emit(sample_snapshot())
    assert "可能过时" not in app.window.bubble.label.text()
    assert app.account_monitor.starts == 1 and app.account_monitor.refreshes == 2


def test_new_snapshot_replaces_values_and_empty_clears_old_money(quota_monster):
    app = quota_monster
    app.action_quota()
    app.account_monitor.snapshot_ready.emit(sample_snapshot())
    app.action_quota()
    app.account_monitor.snapshot_ready.emit(SnapshotFixture((AccountFixture("deepseek", "新账号", "ok", time.time(), balances=(
        BalanceFixture("USD", Decimal("0.000000000009"), Decimal("0"), Decimal("0.000000000009")),)),), time.time()))
    text = app.window.bubble.label.text()
    assert "新账号" in text and "0.000000000009" in text and "123.456789" not in text
    app.action_quota()
    app.account_monitor.snapshot_ready.emit(SnapshotFixture((), time.time()))
    assert app.account_snapshot.accounts == ()
    assert "UNKNOWN" in app.window.bubble.label.text() and "0.000000000009" not in app.window.bubble.label.text()


def test_key_reconfigure_clears_old_facts_same_monitor(quota_monster, monkeypatch):
    app = quota_monster
    app.account_monitor.snapshot_ready.emit(sample_snapshot())
    monitor = app.account_monitor
    monkeypatch.setattr(config, "save_settings", lambda values: [monkeypatch.setenv(k, v) for k, v in values.items()])
    app._save_settings({"DEEPSEEK_API_KEY": "fixture-new-balance-key"})
    assert app.account_snapshot is None and app.account_monitor is monitor
    assert monitor.sources[-1].api_key == "fixture-new-balance-key" and monitor.refreshes == 1
    assert "123.456789" not in app.window.bubble.label.text()
    app._save_settings({"DEEPSEEK_API_KEY": ""})
    assert monitor.sources[-1].api_key == "" and monitor.starts == 1 and monitor.refreshes == 2


def test_save_failure_masks_unsaved_key_and_does_not_reconfigure(quota_monster, monkeypatch):
    app = quota_monster
    monkeypatch.setattr(config, "save_settings", lambda values: (_ for _ in ()).throw(OSError(values["DEEPSEEK_API_KEY"])))
    app._save_settings({"DEEPSEEK_API_KEY": "fixture-unsaved-key"})
    assert "fixture-unsaved-key" not in app.window.bubble.label.text()
    assert not app.account_monitor.sources and app.account_monitor.refreshes == 0


def test_key_source_failure_does_not_restore_previous_account(quota_monster, monkeypatch):
    app = quota_monster
    app.account_monitor.snapshot_ready.emit(sample_snapshot())
    monkeypatch.setattr(config, "save_settings", lambda values: None)
    monkeypatch.setattr(sys.modules["src.accounts"], "DeepSeekBalanceSource", lambda key: (_ for _ in ()).throw(RuntimeError("fixture-source-failure")))
    app._save_settings({"DEEPSEEK_API_KEY": "fixture-new-key"})
    assert app.account_snapshot is None and "fixture-source-failure" in app.account_error
    assert "123.456789" not in app.window.bubble.label.text()


def test_quota_condition_alert_only_on_fresh_threshold_transition(quota_monster, monkeypatch):
    app = quota_monster
    monkeypatch.setenv("MCPET_REMINDERS", "true")
    snapshot = sample_snapshot()
    app.account_monitor.snapshot_ready.emit(snapshot)
    assert "≥80%" in app.window.bubble.label.text()
    app.window.say("用户本次结果")
    app.account_monitor.snapshot_ready.emit(snapshot)
    assert app.window.bubble.label.text() == "用户本次结果"
    app.account_monitor.failed.emit("失败不重发阈值提醒")
    assert app.window.bubble.label.text() == "用户本次结果"


def test_late_account_signal_ignored_after_nonblocking_quit(quota_monster):
    app = quota_monster
    app.quit()
    app.account_monitor.snapshot_ready.emit(sample_snapshot())
    assert app.account_snapshot is None
    pump_until(lambda: not app.tasks.thread.isRunning())
    pump_until(lambda: not app.window.isVisible())


def test_native_active_exit_reaps_children_releases_lock_and_saves_position(tmp_path):
    """独立检查原心跳断言之后的收尾；不替代或放宽原联合性能测试。"""
    from test_companion_integration import ROOT, probe_env, pid_running
    env = probe_env(tmp_path)
    env["DEEPSEEK_API_KEY"] = ""
    # Reuse the controlled native protocol; account UI remains an explicit stub even
    # after integration. Real AgentMonitor still owns its two spawn processes.
    script = tmp_path / "finite_exit_probe.py"
    script.write_text(
        "import sys, runpy\n"
        f"sys.path[:0] = [{str(ROOT)!r}, {str(ROOT / 'tests')!r}]\n"
        "from src import main\n"
        "from test_quota_panel import AccountMonitorStub\n"
        "import httpx\n"
        "def forbidden(*args, **kwargs): raise AssertionError('offline exit probe network')\n"
        "httpx.Client.request = forbidden\n"
        "original = main.MonsterApp.__init__\n"
        "def init(self, *args, **kwargs):\n"
        "    kwargs['account_monitor_factory'] = AccountMonitorStub\n"
        "    original(self, *args, **kwargs)\n"
        "main.MonsterApp.__init__ = init\n"
        f"runpy.run_path({str(ROOT / 'tests/test_companion_integration.py')!r}, run_name='__main__')\n",
        encoding="utf-8",
    )
    command = [sys.executable, str(script), "--probe"]
    primary = subprocess.Popen(command + ["observe"], cwd=ROOT, env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8")
    try:
        deadline = time.monotonic() + 15
        while not (tmp_path / "ready").exists() and primary.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert (tmp_path / "ready").exists(), primary.communicate(timeout=5)
        secondary = subprocess.run(command + ["secondary"], cwd=ROOT, env=env,
                                   capture_output=True, text=True, encoding="utf-8", timeout=10)
        assert secondary.returncode == 0, secondary.stderr
        (tmp_path / "duplicate-checked").write_text("checked", encoding="utf-8")
        stopped_at = time.monotonic()
        stdout, stderr = primary.communicate(timeout=12)
        assert primary.returncode == 0, stdout + stderr
        result = json.loads(stdout.strip().splitlines()[-1])
        print(json.dumps(result))
        assert not result["errors"] and result["gestures"]
        assert result["stop_ms"] < 50 and result["thread_running"] is False
        assert time.monotonic() - stopped_at < 8
        assert result["writer_count"] == 1 and len(result["children"]) == 2
        assert all(not pid_running(pid) for pid in result["children"])
        assert "QThread: Destroyed" not in stderr
        assert not (tmp_path / "app.lock").exists()
        saved = json.loads((tmp_path / "pet-preferences.json").read_text(encoding="utf-8"))
        assert saved["position"] == [170, 140] and saved["roaming"] and saved["resting"]
        restored = subprocess.run(command + ["restore"], cwd=ROOT, env=env,
                                  capture_output=True, text=True, encoding="utf-8", timeout=12)
        assert restored.returncode == 0, restored.stdout + restored.stderr
        assert json.loads(restored.stdout.strip().splitlines()[-1])["restored"]
    finally:
        if primary.poll() is None:
            primary.terminate()
            primary.wait(timeout=5)
