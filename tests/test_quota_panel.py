"""C UI contract fixtures: no account/credential files or real network."""
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
import json
import subprocess
import sys
import time
from types import ModuleType

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QLabel

from src import config, main
from src.pet.dialogs import CompanionPanel
from src.pet.spritesheet import SpriteLoadError
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


def test_separate_buckets_precise_currency_unknown_and_countdown(quota_monster):
    app = quota_monster
    app.account_monitor.snapshot_ready.emit(sample_snapshot(1_800_000_000))
    app.action_panel()
    panel = app.panel
    codex, cursor, claude, grok, deepseek = panel.account_rows
    assert "剩余 83.75%" in codex["buckets"][0][0].text()
    assert codex["buckets"][0][1].value() == 162
    assert len(cursor["buckets"]) == 2
    assert "Models · 剩余 80%" in cursor["buckets"][0][0].text()
    assert "Other Models · 剩余 10%" in cursor["buckets"][1][0].text()
    assert claude["status"] == "unavailable" and not claude["buckets"]
    assert "123.456789012345678901" in deepseek["balances"][0].text()
    assert "USD · 余额 0.001" in deepseek["balances"][1].text()
    assert not deepseek["buckets"]  # no invented balance cap/bar
    QApplication.processEvents()
    assert codex["frame"].height() >= codex["frame"].minimumSizeHint().height() > 40
    assert cursor["frame"].height() >= cursor["frame"].minimumSizeHint().height() > 60
    assert grok["buckets"][0][1].value() == 0 and not grok["buckets"][0][1].isHidden()
    assert codex["buckets"][0][0].isVisible()
    for row in panel.account_rows:
        for summary, bar, reset in row["buckets"]:
            assert summary.height() >= summary.heightForWidth(summary.width()), (summary.text(), summary.size())
            assert reset.height() >= reset.heightForWidth(reset.width()), (reset.text(), reset.size())
    panel.update_countdowns(1_800_000_000)
    assert codex["buckets"][0][2].text() == "距重置 1天 1小时 2分钟"
    assert cursor["buckets"][1][2].text() == "重置时间 UNKNOWN"
    panel.update_countdowns(1_800_100_000)
    assert "重置时间已到" in codex["buckets"][0][2].text()
    assert codex["buckets"][0][1].value() == 162  # reset elapsed doesn't invent replenishment
    texts = "\n".join(label.text() for label in panel.findChildren(QLabel))
    assert "Orca 账号缓存" in texts and "DeepSeek 官方余额" in texts
    assert "本机用量" in panel.usage_status.parentWidget().findChildren(QLabel)[0].text()


@pytest.mark.parametrize("percent", [None, float("nan"), -1, 101])
def test_unknown_percentage_has_no_fake_zero_bar(quota_monster, percent):
    app = quota_monster
    app.action_panel()
    app.account_monitor.snapshot_ready.emit(SnapshotFixture((AccountFixture("codex", "Codex", "error", None,
        (BucketFixture("weekly", percent, None),), message="刷新失败"),), time.time()))
    summary, bar, _ = app.panel.account_rows[0]["buckets"][0]
    assert "UNKNOWN" in summary.text() and "0%" not in summary.text()
    assert bar.isHidden()


def test_refresh_error_stale_recover_reuses_monitor_and_no_model(quota_monster, monkeypatch):
    app = quota_monster
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-balance-secret")
    app.action_panel()
    app.account_monitor.snapshot_ready.emit(sample_snapshot())
    app.panel.buttons["quota"].click()
    assert app.account_refreshing and app.account_monitor.refreshes == 1
    assert "刷新中" in app.panel.quota_status.text()
    app.account_monitor.failed.emit("查询失败 fixture-balance-secret")
    assert "fixture-balance-secret" not in app.panel.quota_status.text()
    assert "过时" in app.panel.quota_status.text()
    assert all(row["status"] == "stale" for row in app.panel.account_rows if row["buckets"] or row["balances"])
    assert "16.25%" in app.panel.account_rows[0]["buckets"][0][0].text()
    app.account_monitor.snapshot_ready.emit(sample_snapshot())
    assert not app.account_refreshing and app.account_error == ""
    assert app.account_monitor.starts == 1 and not app.tasks.busy
    assert not (config.data_dir() / "chat.json").exists()


def test_key_save_reconfigures_same_monitor_and_clears_old_account(quota_monster, monkeypatch):
    app = quota_monster
    app.action_settings()
    monitor = app.account_monitor
    app.account_monitor.snapshot_ready.emit(sample_snapshot())
    def save(values):
        for key, value in values.items(): monkeypatch.setenv(key, value)
    monkeypatch.setattr(config, "save_settings", save)
    form = app.panel.settings
    form.fields["DEEPSEEK_API_KEY"].setText("fixture-new-balance-key")
    form.save_button.click()
    assert app.account_monitor is monitor and monitor.starts == 1 and monitor.stops == 0
    assert monitor.sources[-1].api_key == "fixture-new-balance-key" and monitor.refreshes == 1
    assert app.account_snapshot is None and app.account_refreshing
    assert "刷新中" in app.panel.quota_status.text()
    assert form.fields["DEEPSEEK_API_KEY"].text() == ""
    form.clear_deepseek.setChecked(True)
    form.save_button.click()
    assert monitor.sources[-1].api_key == "" and monitor.refreshes == 2
    monitor.snapshot_ready.emit(SnapshotFixture((AccountFixture("deepseek", "DeepSeek", "unconfigured", None),), time.time()))
    assert app.panel.account_rows[0]["status"] == "unconfigured"


def test_save_failure_masks_unsaved_key_and_does_not_reconfigure(quota_monster, monkeypatch):
    app = quota_monster
    app.action_settings()
    form = app.panel.settings
    form.fields["DEEPSEEK_API_KEY"].setText("unsaved-arbitrary-fixture-key")
    def fail(values): raise OSError("failed " + values["DEEPSEEK_API_KEY"])
    monkeypatch.setattr(config, "save_settings", fail)
    form.save_button.click()
    assert "保存失败" in form.message.text()
    assert "unsaved-arbitrary-fixture-key" not in form.message.text()
    assert not app.account_monitor.sources and app.account_monitor.refreshes == 0
    form.cancel_button.click()
    assert form.fields["DEEPSEEK_API_KEY"].text() == ""


def test_panel_close_and_escape_discard_deepseek_unsaved_input(quota_monster):
    app = quota_monster
    app.action_settings()
    form = app.panel.settings
    form.fields["DEEPSEEK_API_KEY"].setText("unsaved-fixture")
    form.clear_deepseek.setChecked(True)
    app.panel.close()
    app.action_settings()
    assert form.fields["DEEPSEEK_API_KEY"].text() == "" and not form.clear_deepseek.isChecked()
    form.fields["DEEPSEEK_API_KEY"].setText("unsaved-fixture")
    app.panel.reject()
    assert form.fields["DEEPSEEK_API_KEY"].text() == ""
    assert not app.account_monitor.sources


def test_character_contract_selection_failure_keeps_preview_and_tray(quota_monster, monkeypatch):
    app = quota_monster
    characters = ModuleType("src.pet.characters")
    characters.CHARACTER_IDS = ("maimai", "deepseek")
    characters.character_name = lambda identifier: {"maimai": "麦麦", "deepseek": "DeepSeek 娘"}[identifier]
    monkeypatch.setitem(sys.modules, "src.pet.characters", characters)
    app.window.current_character = "maimai"
    monkeypatch.setattr(type(app.window), "character_id", property(lambda window: window.current_character), raising=False)
    sheets = {"maimai": SheetFixture("orange"), "deepseek": SheetFixture("blue")}
    app.sheet = app.window.sheet = sheets["maimai"]
    def switch(identifier):
        app.window.current_character = identifier
        app.window.sheet = sheets[identifier]
    monkeypatch.setattr(app.window, "set_character", switch, raising=False)
    app.action_panel()
    panel = app.panel
    panel.character_buttons["deepseek"].click()
    assert app.window.character_id == "deepseek" and app.sheet is sheets["deepseek"]
    assert panel.character_name.text() == "DeepSeek 娘"
    assert panel.character_buttons["deepseek"].isChecked() and not panel.character_buttons["maimai"].isChecked()
    assert panel.preview.pixmap().toImage().pixelColor(0, 0).name() == "#0000ff"
    icon = app.tray.icon().cacheKey()
    def fail(identifier): raise SpriteLoadError("受控素材加载失败")
    monkeypatch.setattr(app.window, "set_character", fail)
    panel.character_buttons["maimai"].click()
    assert app.sheet is sheets["deepseek"] and app.tray.icon().cacheKey() == icon
    assert panel.character_buttons["deepseek"].isChecked() and not panel.character_buttons["maimai"].isChecked()
    assert "失败" in panel.character_message.text()
    assert app.monitor.starts == app.account_monitor.starts == 1


def test_account_late_signals_ignored_and_shutdown_nonblocking(quota_monster, monkeypatch):
    app = quota_monster
    app.action_panel()
    profile = {}
    for name, target, method in (("schedule", app.scheduler, "stop"), ("agent", app.monitor, "stop"),
                                 ("account", app.account_monitor, "stop"), ("tray", app.tray, "hide"),
                                 ("panel", app.panel, "hide"), ("bubble", app.window, "say"),
                                 ("hideEvent", app.panel, "hideEvent"),
                                 ("tasks", app.tasks, "shutdown")):
        original = getattr(target, method)
        def timed(*args, callback=original, step=name, **kwargs):
            start = time.perf_counter()
            try: return callback(*args, **kwargs)
            finally: profile[step] = (time.perf_counter() - start) * 1000
        monkeypatch.setattr(target, method, timed)
    before = time.perf_counter()
    app.quit()
    elapsed = (time.perf_counter() - before) * 1000
    print({"stop_ms": elapsed, "profile_ms": profile})
    assert elapsed < 50, profile
    app.account_monitor.snapshot_ready.emit(sample_snapshot())
    app.account_monitor.failed.emit("late error")
    assert app.account_snapshot is None and app.account_error == ""
    assert not app.panel.quota_timer.isActive()
    pump_until(lambda: app._allow_quit)
    assert not app.panel.isVisible()


def test_source_missing_does_not_fabricate_account_success(quota_monster):
    app = quota_monster
    app.action_panel()
    app.account_monitor.failed.emit("账号接口尚未集成")
    assert "UNKNOWN" in app.panel.quota_status.text()
    assert not app.panel.account_rows


def test_quit_active_task_refuses_actions_and_finally_closes_everything(quota_monster, monkeypatch):
    import threading
    app = quota_monster
    app.action_panel()
    entered, release = threading.Event(), threading.Event()
    def active():
        entered.set()
        assert release.wait(2)
    app.run_async(active, lambda result: pytest.fail("closing app must not publish result"), key="controlled-active")
    pump_until(entered.is_set)
    saved = []
    monkeypatch.setattr(config, "save_settings", saved.append)
    before = time.perf_counter()
    app.quit()
    elapsed = (time.perf_counter() - before) * 1000
    assert elapsed < 50
    assert app.monitor.stops == app.account_monitor.stops == 1
    assert app.tasks.thread.isRunning() and app.closing and not app._allow_quit
    app.panel.buttons["quota"].click()
    app._save_settings({"DEEPSEEK_API_KEY": "discarded-fixture"})
    assert not saved and app.account_monitor.refreshes == 0
    assert not app.tasks.submit("after-quit", lambda: None, lambda result: None, lambda error: None)
    release.set()
    pump_until(lambda: app._allow_quit and not app.tasks.thread.isRunning())
    assert not app.panel.isVisible() and not app.window.isVisible()
    assert not app.panel.quota_timer.isActive()


def test_small_panel_scrolls_without_clipping_quota_and_settings(quota_monster):
    app = quota_monster
    app.action_panel()
    app.account_monitor.snapshot_ready.emit(sample_snapshot())
    panel = app.panel
    panel.resize(560, 560)
    panel.settings.advanced.setChecked(True)
    for page in ("home", "sessions", "mcd", "settings"):
        panel.select_page(page)
        QApplication.processEvents()
        scroll = panel.tabs.currentWidget()
        assert scroll.horizontalScrollBar().maximum() == 0
        if page in ("home", "mcd", "settings"):
            assert scroll.verticalScrollBar().maximum() > 0
        if page == "home":
            for row in panel.account_rows:
                for summary, bar, reset in row["buckets"]:
                    assert summary.height() >= summary.heightForWidth(summary.width())
                    assert reset.height() >= reset.heightForWidth(reset.width())
    assert panel.settings.save_button.isEnabled()


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

