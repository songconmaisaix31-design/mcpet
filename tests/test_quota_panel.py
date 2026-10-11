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


def test_thirty_actual_quota_actions_keep_rows_and_publish_new_facts(quota_monster):
    app = quota_monster
    app.action_panel()
    first = sample_snapshot()
    app.account_monitor.snapshot_ready.emit(first)
    frames = tuple(row["frame"] for row in app.panel.account_rows)
    before = time.perf_counter()
    for _ in range(30):
        app.action_quota()
        assert tuple(row["frame"] for row in app.panel.account_rows) == frames
        assert "刷新中" in app.panel.quota_status.text()
    print({"thirty_action_quota_ms": (time.perf_counter() - before) * 1000})
    assert app.account_monitor.refreshes == 30
    app.action_panel()
    assert tuple(row["frame"] for row in app.panel.account_rows) == frames
    # Reusing frozen facts must not freeze a later source observation.
    now = time.time() + 60
    changed = SnapshotFixture((
        AccountFixture("codex", "Codex 新快照", "ok", now,
                       (BucketFixture("Weekly", None, now + 600),)),
        AccountFixture("deepseek", "DeepSeek 新快照", "ok", now, balances=(
            BalanceFixture("CNY", Decimal("0.000000000001"), Decimal("0"), Decimal("0.000000000001")),)),
    ), now)
    app.account_monitor.snapshot_ready.emit(changed)
    codex, money = app.panel.account_rows
    assert codex["frame"] is frames[0]
    assert "UNKNOWN" in codex["buckets"][0][0].text()
    assert codex["buckets"][0][1].isHidden()
    assert "0.000000000001" in money["balances"][0].text()
    assert not app.account_refreshing
    app.account_monitor.failed.emit("第一次失败")
    stale_frames = tuple(row["frame"] for row in app.panel.account_rows)
    assert all(row["status"] == "stale" for row in app.panel.account_rows)
    app.account_monitor.failed.emit("第二次失败")
    assert "第二次失败" in app.panel.quota_status.text()
    assert tuple(row["frame"] for row in app.panel.account_rows) == stale_frames
    app.account_monitor.snapshot_ready.emit(changed)
    assert all(row["status"] == "ok" for row in app.panel.account_rows)
    app.panel.update_countdowns(now + 601)
    assert "等待刷新" in app.panel.account_rows[0]["buckets"][0][2].text()
    assert app.panel.account_rows[0]["buckets"][0][1].isHidden()


def test_same_character_sync_does_not_repolish_existing_styles(quota_monster, monkeypatch):
    app = quota_monster
    app.action_panel()
    calls = []
    targets = [app.panel.character_card, *app.panel.character_buttons.values()]
    for target in targets:
        original = target.setStyleSheet
        def styled(value, callback=original):
            calls.append(value)
            callback(value)
        monkeypatch.setattr(target, "setStyleSheet", styled)
    for _ in range(30):
        app._sync_panel()
    assert not calls
    app.panel.set_character("deepseek", "DeepSeek 娘", app.sheet,
                            (("maimai", "麦麦"), ("deepseek", "DeepSeek 娘")))
    assert len(calls) == 1 and "#eaf4fb" in calls[0]
    assert app.panel.character_buttons["deepseek"].isChecked()


def test_new_same_shape_snapshot_updates_all_fields_without_replacing_cards(quota_monster):
    app = quota_monster
    app.action_panel()
    now = time.time()
    first = sample_snapshot(now)
    app.account_monitor.snapshot_ready.emit(first)
    frames = tuple(row["frame"] for row in app.panel.account_rows)
    changed = list(first.accounts)
    changed[0] = replace(changed[0], label="Codex 最新来源", updated_at=now + 180,
                         message="新来源说明", buckets=(BucketFixture("Session", 97.5, now + 120),))
    changed[2] = replace(changed[2], label="Claude 查询失败", status="error", message="来源出错")
    changed[-1] = replace(changed[-1], balances=(
        BalanceFixture("USD", Decimal("0.000000000009"), Decimal("0"), Decimal("0.000000000009")),
        BalanceFixture("CNY", Decimal("1.234567890123456789"), Decimal("1"), Decimal("0.234567890123456789"))))
    app.account_monitor.snapshot_ready.emit(SnapshotFixture(tuple(changed), now + 180))
    assert tuple(row["frame"] for row in app.panel.account_rows) == frames
    codex, _, claude, _, money = app.panel.account_rows
    assert codex["heading"].text() == "Codex 最新来源" and codex["frame"].toolTip() == "新来源说明"
    assert "Session · 剩余 2.5% · 已用 97.5%" == codex["buckets"][0][0].text()
    assert codex["buckets"][0][1].value() == 975 and "#ae5962" in codex["buckets"][0][1].styleSheet()
    assert codex["stamps"][0][0].text() != "更新时间 UNKNOWN"
    assert claude["status"] == "error" and "失败" in claude["state_label"].text()
    assert "USD · 余额 0.000000000009" in money["balances"][0].text()
    assert "CNY · 余额 1.234567890123456789" in money["balances"][1].text()
    app.panel.update_countdowns(now + 121)
    assert "等待刷新" in codex["buckets"][0][2].text()
    app.account_monitor.failed.emit("断线")
    assert codex["status"] == "stale" and not codex["stale_label"].isHidden()
    assert "#b7aea6" in codex["buckets"][0][1].styleSheet()
    app.action_quota()
    assert codex["status"] == "stale" and not codex["stale_label"].isHidden()
    assert "断线" in app.panel.quota_status.text() and "刷新中" in app.panel.quota_status.text()
    app.account_monitor.snapshot_ready.emit(SnapshotFixture(tuple(changed), now + 181))
    assert codex["status"] == "ok" and codex["stale_label"].isHidden()
    assert "#ae5962" in codex["buckets"][0][1].styleSheet()


def test_static_preview_and_tray_do_not_evict_active_animation_atlas(quota_monster):
    app = quota_monster
    app.action_panel()
    sheet = AnimationSheet.__new__(AnimationSheet)
    sheet.image = QImage(32, 32, QImage.Format_ARGB32)
    sheet.image.fill("blue")
    resident = sheet._atlases = {"working-fixture": object()}
    def forbidden(*args):
        pytest.fail("C idle preview decoded/evicted the active animation source")
    sheet.frame = forbidden
    app.sheet = sheet
    app.panel.set_character("deepseek", "DeepSeek 娘", sheet, (("deepseek", "DeepSeek 娘"),))
    assert app.panel.preview.pixmap().toImage().pixelColor(0, 0).name() == "#0000ff"
    assert app._icon().pixmap(32, 32).toImage().pixelColor(0, 0).name() == "#0000ff"
    assert sheet._atlases is resident and list(resident) == ["working-fixture"]


def test_key_save_reconfigures_same_monitor_and_clears_old_account(quota_monster, monkeypatch):
    app = quota_monster
    app.action_settings()
    monitor = app.account_monitor
    app.account_monitor.snapshot_ready.emit(sample_snapshot())
    previous_cards = tuple(row["frame"] for row in app.panel.account_rows)
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
    assert not app.panel.account_rows and all(card.isHidden() for card in previous_cards)
    assert app.panel.money_layout.count() == 1
    assert "等待查询" in app.panel.money_layout.itemAt(0).widget().text()
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


@pytest.mark.parametrize("size", [560, 700])
def test_small_panel_scrolls_without_clipping_quota_and_settings(quota_monster, size):
    app = quota_monster
    app.action_panel()
    app.account_monitor.snapshot_ready.emit(sample_snapshot())
    panel = app.panel
    panel.resize(size, size)
    panel.settings.advanced.setChecked(True)
    for page in ("home", "sessions", "mcd", "settings"):
        panel.select_page(page)
        QApplication.processEvents()
        scroll = panel.tabs.currentWidget()
        assert scroll.horizontalScrollBar().maximum() == 0
        if size == 560 and page in ("home", "mcd", "settings"):
            assert scroll.verticalScrollBar().maximum() > 0
        assert scroll.widget().height() >= scroll.widget().minimumSizeHint().height()
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


def test_key_clear_erases_hidden_text_accessibility_and_reuses_only_observed_rows(quota_monster, monkeypatch):
    from PySide6.QtGui import QAccessible
    from PySide6.QtWidgets import QWidget, QProgressBar
    app = quota_monster
    app.action_panel()
    assert not app.panel._provider_rows  # No provider is prebuilt without facts.
    snapshot = sample_snapshot()
    app._accounts_ready(snapshot)
    rows = tuple(app.panel.account_rows)
    old_summary = rows[0]["buckets"][0][0].text()
    rows[0]["frame"].setAccessibleDescription("旧账号说明")
    monkeypatch.setattr(config, "save_settings", lambda values: [monkeypatch.setenv(k, v) for k, v in values.items()])
    for key in ("fixture-replacement-one", "fixture-replacement-two", ""):
        app._save_settings({"DEEPSEEK_API_KEY": key})
        assert not app.panel.account_rows and len(app.panel._provider_rows) == 5
        assert app.panel._quota_snapshot is None and not app.panel.reset_labels
        for row in rows:
            assert row["frame"].isHidden()
            for widget in (row["frame"], *row["frame"].findChildren(QWidget)):
                assert not widget.toolTip() and not widget.accessibleName() and not widget.accessibleDescription()
                if isinstance(widget, QLabel):
                    assert not widget.text()
                    interface = QAccessible.queryAccessibleInterface(widget)
                    assert interface is not None
                    assert interface.text(QAccessible.Name) == ""
                    assert interface.text(QAccessible.Description) == ""
                    text_interface = interface.textInterface()
                    if text_interface is not None:
                        assert text_interface.characterCount() == 0
                        assert text_interface.text(0, text_interface.characterCount()) == ""
                elif isinstance(widget, QProgressBar):
                    assert widget.isHidden() and widget.value() == -1
                    interface = QAccessible.queryAccessibleInterface(widget)
                    assert interface.text(QAccessible.Name) == ""
                    assert interface.valueInterface().currentValue() == -1
        app.panel.update_countdowns(snapshot.observed_at + 10_000)
        assert rows[0]["buckets"][0][2].text() == ""
    app._accounts_failed("新来源失败")
    assert old_summary not in " ".join(label.text() for label in app.panel.findChildren(QLabel))
    assert not app.panel.account_rows
    app._accounts_ready(snapshot)
    assert tuple(row["frame"] for row in app.panel.account_rows) == tuple(row["frame"] for row in rows)
    assert rows[0]["buckets"][0][0].text() == old_summary
    assert rows[0]["buckets"][0][1].value() == 162
    assert app.account_monitor.refreshes == 3 and app.account_monitor.starts == 1


def test_structure_changes_reuse_unaffected_providers_and_children_and_move_sections(quota_monster):
    app = quota_monster
    app.action_panel()
    first = sample_snapshot()
    app._accounts_ready(first)
    old = {row["provider"]: row for row in app.panel.account_rows}
    cursor_first = old["cursor"]["buckets"][0]
    discarded_bucket = old["cursor"]["buckets"][1]
    accounts = (
        replace(first.accounts[1], buckets=(BucketFixture("New Models", None, None),)),
        replace(first.accounts[0], buckets=(), balances=(BalanceFixture("JPY", Decimal("987.00001"), Decimal("0"), Decimal("987.00001")),)),
        replace(first.accounts[-1], balances=first.accounts[-1].balances[:1]),
        AccountFixture("new-provider", "新实际来源", "unavailable", None),
    )
    app._accounts_ready(SnapshotFixture(accounts, first.observed_at + 60))
    cursor, codex, money, new = app.panel.account_rows
    assert cursor is old["cursor"] and codex is old["codex"] and money is old["deepseek"]
    assert cursor["buckets"][0] == cursor_first and len(cursor["buckets"]) == 1
    assert all(not widget.accessibleName() for widget in discarded_bucket)
    assert not discarded_bucket[0].text() and discarded_bucket[1].value() == -1
    assert codex["buckets"] == [] and "JPY · 余额 987.00001" in codex["balances"][0].text()
    assert app.panel.accounts_layout.itemAt(0).widget() is cursor["frame"]
    assert app.panel.accounts_layout.itemAt(1).widget() is new["frame"]
    assert app.panel.money_layout.itemAt(0).widget() is codex["frame"]
    assert app.panel.money_layout.itemAt(1).widget() is money["frame"]
    assert len(app.panel._provider_rows) == 4
    # Grow the same provider's actual buckets and reorder the real providers.
    changed = (replace(accounts[0], buckets=(BucketFixture("Session", 25, None), BucketFixture("Weekly", 90, None))), accounts[2])
    app._accounts_ready(SnapshotFixture(tuple(reversed(changed)), first.observed_at + 120))
    assert app.panel.account_rows[1] is cursor and cursor["buckets"][0] == cursor_first
    assert len(cursor["buckets"]) == 2 and "Weekly" in cursor["buckets"][1][0].text()
    assert len(app.panel._provider_rows) == 2
    assert old["codex"]["frame"].isHidden() and old["codex"]["balances"][0].text() == ""


def test_real_empty_snapshot_releases_cleared_rows_and_does_not_keep_old_payload(quota_monster):
    app = quota_monster
    app.action_panel()
    app._accounts_ready(sample_snapshot())
    frames = tuple(row["frame"] for row in app.panel.account_rows)
    app.panel.set_accounts(None, refreshing=True)
    assert len(app.panel._provider_rows) == 5
    app.panel.set_accounts(SnapshotFixture((), time.time()))
    assert app.panel._provider_rows == {} and app.panel.account_rows == []
    assert app.panel.accounts_layout.count() == 1
    assert "暂无账号" in app.panel.accounts_layout.itemAt(0).widget().text()
    assert all(frame.isHidden() for frame in frames)
    app.panel.set_accounts(sample_snapshot())
    assert all(row["frame"] not in frames for row in app.panel.account_rows)
    assert app.panel.account_placeholder.text() == "" and app.panel.account_placeholder.isHidden()


def test_render_exception_restores_repaint_and_allows_next_observation(quota_monster, monkeypatch):
    app = quota_monster
    app.action_panel()
    page = app.panel.home_layout.parentWidget()
    create = app.panel._create_account_row
    def fail(provider):
        raise ValueError("controlled render error")
    monkeypatch.setattr(app.panel, "_create_account_row", fail)
    with pytest.raises(ValueError, match="controlled render"):
        app.panel.set_accounts(sample_snapshot())
    assert page.updatesEnabled()
    monkeypatch.setattr(app.panel, "_create_account_row", create)
    app.panel.set_accounts(sample_snapshot())
    assert len(app.panel.account_rows) == 5
    page.setUpdatesEnabled(False)
    app.panel.set_accounts(SnapshotFixture((), time.time()))
    assert not page.updatesEnabled()
    page.setUpdatesEnabled(True)


def test_key_source_construction_failure_clears_old_facts_and_error_before_reporting(quota_monster, monkeypatch):
    app = quota_monster
    app.action_panel()
    app._accounts_ready(sample_snapshot())
    old = tuple(app.panel.account_rows)
    app._accounts_failed("旧账号来源错误")
    monkeypatch.setattr(config, "save_settings", lambda values: None)
    def failure(key):
        raise ValueError("controlled new source error")
    monkeypatch.setattr(sys.modules["src.accounts"], "DeepSeekBalanceSource", failure)
    app._save_settings({"DEEPSEEK_API_KEY": "fixture-failed-source"})
    assert app.account_snapshot is None and not app.account_refreshing
    assert "旧账号" not in app.panel.quota_status.text()
    assert "controlled new source error" in app.panel.quota_status.text()
    assert not app.panel.account_rows and not app.panel.reset_labels
    assert all(row["heading"].text() == "" for row in old)
    assert not app.account_monitor.sources


@pytest.mark.skipif(sys.platform != "win32", reason="Windows native foreground/focus contract")
def test_native_four_entries_restore_foreground_and_focused_keyboard_input(tmp_path):
    from test_companion_integration import ROOT, probe_env
    env = probe_env(tmp_path)
    env["DEEPSEEK_API_KEY"] = ""
    script = tmp_path / "focus_probe.py"
    script.write_text(f"import sys\nsys.path[:0] = {[str(ROOT), str(ROOT / 'tests')]!r}\n" + r'''
import ctypes as c, json, subprocess, time
from ctypes import wintypes as w
from PySide6.QtCore import QEvent, QPointF, Qt, QTimer
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QSystemTrayIcon
from src import config, main
from test_app_actions import MonitorStub
from test_quota_panel import AccountMonitorStub
config.load_env=lambda:None
main.QtDailyScheduler.start=lambda self:None
main.MonsterApp._load_sheet=lambda self:None
def forbidden(*args,**kwargs):raise AssertionError('focus fixture forbids network')
import httpx
httpx.Client.request=forbidden
monster=main.MonsterApp([],monitor_factory=MonitorStub,account_monitor_factory=AccountMonitorStub)
if monster.secondary:
    raise SystemExit(monster.app.exec())
u=c.WinDLL('user32',use_last_error=True)
u.GetForegroundWindow.restype=w.HWND
u.IsIconic.argtypes=[w.HWND];u.IsWindowVisible.argtypes=[w.HWND]
u.GetWindowRect.argtypes=[w.HWND,c.POINTER(w.RECT)]
u.GetAncestor.argtypes=[w.HWND,w.UINT];u.GetAncestor.restype=w.HWND
class GUI(c.Structure):
    _fields_=[('cbSize',w.DWORD),('flags',w.DWORD),('active',w.HWND),('focus',w.HWND),
      ('capture',w.HWND),('menu',w.HWND),('move',w.HWND),('caret',w.HWND),('rect',w.RECT)]
u.GetGUIThreadInfo.argtypes=[w.DWORD,c.POINTER(GUI)]
kernel=c.WinDLL('kernel32');kernel.GetCurrentThreadId.restype=w.DWORD
gui_thread=kernel.GetCurrentThreadId()
results={};errors=[];secondary=None;awaiting=None;action_begin=None;returned=None;in_action=False;checking=False
events=[];ticks=[];stop_ms=None
heartbeat=QTimer();heartbeat.setInterval(10)
heartbeat.timeout.connect(lambda:ticks.append(time.monotonic()));heartbeat.start()
# Observe the actual entry signal handler, not a later test callback's start.
original_class_panel=main.MonsterApp.action_panel
# Already-connected bound slots resolve the class method body above only through
# their original callable, so observe calls using a scoped profiler instead of
# replacing the slots or C entry routing.
def profile(frame,event,arg):
    global action_begin,returned,in_action
    if frame.f_code is original_class_panel.__code__ and awaiting is not None:
        if event=='call':action_begin=time.monotonic();in_action=True
        elif event=='return':
            in_action=False
            returned={'elapsed_ms':(time.monotonic()-action_begin)*1000,
                      'foreground':u.GetForegroundWindow()==int(monster.panel.winId()),
                      'qt_active':monster.panel.windowHandle().isActive()}
sys.setprofile(profile)
def check(entry):
    panel=monster.panel;hwnd=int(panel.winId());rect=w.RECT()
    assert u.GetWindowRect(hwnd,c.byref(rect))
    # Read only our HWND and current GUI thread. No foreign window enumeration,
    # focus stealing, global input or system/accessibility settings.
    observed={'visible':bool(u.IsWindowVisible(hwnd)),'iconic':bool(u.IsIconic(hwnd)),
       'foreground':u.GetForegroundWindow()==hwnd,'rect':[rect.left,rect.top,rect.right,rect.bottom],
       'qt_active':panel.windowHandle().isActive(),'action_return':returned,
       'observed_ms':(time.monotonic()-action_begin)*1000}
    assert observed['visible'] and not observed['iconic'],(entry,observed)
    assert any(s.availableGeometry().intersects(panel.frameGeometry()) for s in QApplication.screens())
    panel.select_page('settings')
    field=panel.settings.fields['MCPET_CITY']
    QTest.mouseClick(field,Qt.LeftButton)  # Ordinary user focus within our panel.
    info=GUI();info.cbSize=c.sizeof(info)
    assert u.GetGUIThreadInfo(gui_thread,c.byref(info))
    observed['native_keyboard_root']=u.GetAncestor(info.focus,2)==hwnd
    observed['qt_keyboard_focus']=QApplication.focusWidget() is field and field.hasFocus()
    field.selectAll();QTest.keyClicks(field,'controlled-focus')
    observed['keyboard_input']=field.text()=='controlled-focus'
    results[entry]=observed
    panel.settings.reset()  # Never save the controlled keyboard input.
def minimize():
    monster.panel.showMinimized();QApplication.processEvents()
    assert monster.panel.isMinimized() and u.IsIconic(int(monster.panel.winId()))
def safe(call):
    try:call()
    except Exception as exc:
        errors.append(str(exc));monster.quit()
def right_menu():
    def click_menu():
        menu=QApplication.activePopupWidget()
        if menu is None:
            QTimer.singleShot(10,click_menu);return
        menu.actions()[0].trigger();menu.close()
    QTimer.singleShot(10,click_menu)
    monster.on_menu(monster.window.pos())
def double_click():
    point=QPointF(monster.window.rect().center());global_point=QPointF(monster.window.mapToGlobal(point.toPoint()))
    QApplication.sendEvent(monster.window,QMouseEvent(QEvent.MouseButtonDblClick,point,global_point,Qt.LeftButton,Qt.LeftButton,Qt.NoModifier))
    QApplication.sendEvent(monster.window,QMouseEvent(QEvent.MouseButtonRelease,point,global_point,Qt.LeftButton,Qt.NoButton,Qt.NoModifier))
def finish():
    global stop_ms
    started=time.monotonic();monster.quit();stop_ms=(time.monotonic()-started)*1000
def next_entry():
    global awaiting,action_begin,returned
    next_name={'duplicate':'tray','tray':'right-menu','right-menu':'double-click','double-click':None}[awaiting]
    if next_name is None:finish();return
    minimize();awaiting=next_name;action_begin=None;returned=None
    if next_name=='tray':monster.tray.activated.emit(QSystemTrayIcon.Trigger)
    elif next_name=='right-menu':right_menu()
    else:double_click()
def inspect():
    global checking
    if awaiting is None or action_begin is None or in_action or checking or awaiting in results:return
    panel=monster.panel
    settled=(u.GetForegroundWindow()==int(panel.winId()) and panel.windowHandle().isActive())
    if not settled and time.monotonic()-action_begin<1.5:return
    # Conditional observation of platform activation, not a fixed sleep or a
    # deferred product request. Original joint heartbeat/budgets are untouched.
    checking=True
    try:check(awaiting)
    finally:checking=False
    QTimer.singleShot(0,lambda:safe(next_entry))
observe=QTimer();observe.setInterval(10);observe.timeout.connect(lambda:safe(inspect));observe.start()
def begin():
    global secondary,awaiting
    monster.action_panel();minimize()
    def active_changed():
        events.append({'entry':awaiting,'active':monster.panel.windowHandle().isActive(),
                       'elapsed_ms':(time.monotonic()-action_begin)*1000 if action_begin is not None else None})
        QTimer.singleShot(0,lambda:safe(inspect))
    monster.panel.windowHandle().activeChanged.connect(active_changed)
    monster.app.focusChanged.connect(lambda old,new:events.append({'entry':awaiting,'focus_in_panel':bool(new and new.window() is monster.panel),
        'elapsed_ms':(time.monotonic()-action_begin)*1000 if action_begin is not None else None}))
    awaiting='duplicate'
    secondary=subprocess.Popen([sys.executable,__file__,'secondary'])
QTimer.singleShot(0,lambda:safe(begin))
QTimer.singleShot(18_000,lambda:safe(lambda:(_ for _ in ()).throw(AssertionError('focus probe timeout'))))
monster.app.exec()
sys.setprofile(None);observe.stop();heartbeat.stop()
if secondary:
    try:secondary.wait(timeout=3)
    except subprocess.TimeoutExpired:
        secondary.terminate();secondary.wait(timeout=3);errors.append('secondary timeout')
print(json.dumps({'entries':results,'events':events,'errors':errors,'stop_ms':stop_ms,
 'max_tick_gap_ms':max((1000*(b-a) for a,b in zip(ticks,ticks[1:])),default=0),
 'thread_running':monster.tasks.thread.isRunning()}),flush=True)
''', encoding="utf-8")
    completed = subprocess.run([sys.executable, str(script)], cwd=ROOT, env=env,
                               capture_output=True, text=True, encoding="utf-8", timeout=25)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads(completed.stdout.strip().splitlines()[-1])
    print(json.dumps(result))
    assert not result["errors"] and not result["thread_running"]
    assert result["stop_ms"] < 50
    assert set(result["entries"]) == {"duplicate", "tray", "right-menu", "double-click"}
    assert all(entry["foreground"] and entry["native_keyboard_root"] and entry["qt_keyboard_focus"]
               and entry["keyboard_input"] for entry in result["entries"].values()), result["entries"]
    assert "QThread: Destroyed" not in completed.stderr
