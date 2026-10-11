"""统一小窝的 Qt 接线与隐私边界；所有数据均为临时夹具。"""
import json
import multiprocessing
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import QApplication, QLineEdit, QPlainTextEdit, QMenu

from src import config, main
from src.agentbridge.records import ProgressRecord, UsageTotals
from src.progress.tracker import ProgressSnapshot, SessionProgress
from src.metering.usage import UsageSnapshot
from src.mcd_mcp.brain import OrderOutcome
from test_app_actions import monster, pump_until
from test_quota_panel import AccountMonitorStub, sample_snapshot


@pytest.fixture(autouse=True)
def offline_account_monitor(monkeypatch):
    """Keep this C-owned suite offline after B's account module is integrated."""
    start = main.MonsterApp._start_account_monitor
    def start_fixture(app):
        if app._account_monitor_factory is None:
            app._account_monitor_factory = AccountMonitorStub
        start(app)
    monkeypatch.setattr(main.MonsterApp, "_start_account_monitor", start_fixture)


def test_real_qaction_and_double_click_reuse_single_panel(monster, monkeypatch):
    from src.chat.store import ChatStore
    from src.llm.stepfun import StepFunClient
    from src.mcd_mcp import skill
    def forbidden(*args, **kwargs):
        pytest.fail("面板不得创建聊天 / 模型 / MCP 会话")
    monkeypatch.setattr(ChatStore, "__init__", forbidden)
    monkeypatch.setattr(StepFunClient, "__init__", forbidden)
    monkeypatch.setattr(skill, "run_skill", forbidden)
    monster.tasks.worker.ensure_client = forbidden
    monster.tray.contextMenu().actions()[0].trigger()  # triggered(bool)
    panel = monster.panel
    assert panel.isVisible() and not panel.isModal()
    assert panel.tabs.currentIndex() == panel.pages["home"]
    panel.close()
    monster.window.chat_requested.emit()
    assert monster.panel is panel and panel.isVisible()
    # Drive the actual popup event loop; always close it after triggering QAction.
    def activate_menu():
        menu = QApplication.activePopupWidget()
        if menu is None:
            QTimer.singleShot(10, activate_menu)
            return
        menu.actions()[0].trigger()
        menu.close()
    QTimer.singleShot(10, activate_menu)
    monster.on_menu(monster.window.pos())
    assert monster.panel is panel and panel.tabs.currentIndex() == panel.pages["home"]
    monster.action_progress()
    assert panel.tabs.currentIndex() == panel.pages["sessions"]
    monster.action_balance()
    assert monster.panel is panel
    monster.action_settings()
    assert panel.tabs.currentIndex() == panel.pages["settings"]
    assert not hasattr(monster, "chat_store") and not hasattr(monster, "chat")
    assert all(edit.isReadOnly() for edit in panel.findChildren(QPlainTextEdit))
    assert all("聊天" not in action.text() and "偏好" not in action.text() for action in monster.tray.contextMenu().actions())
    assert not (config.data_dir() / "chat.json").exists()
    assert monster.monitor.starts == 1 and not monster.tasks.busy


def test_panel_signals_true_context_unknown_stale_and_failure(monster):
    monster.action_panel("sessions")
    panel = monster.panel
    assert "UNKNOWN" in panel.progress_status.text()
    record = ProgressRecord(source="codex", session_id="controlled", title="真实夹具任务",
                            state="needsinput", context_used=25, context_limit=100)
    record.context_limit_estimated = True
    monster.monitor.progress_ready.emit(ProgressSnapshot([SessionProgress(record, stale=True, age_seconds=3600)]))
    assert panel.session_table.item(0, 0).text() == "codex"
    assert "待输入" in panel.session_table.item(0, 2).text()
    assert "过时" in panel.session_table.item(0, 2).text()
    assert "UNKNOWN" in panel.session_table.item(0, 2).text()
    assert panel.session_table.item(0, 3).text() == "25% · 上限估算"
    usage = UsageSnapshot(window=UsageTotals(tokens=30), today=UsageTotals(tokens=50),
                          lifetime=UsageTotals(tokens=80), sources=["codex"])
    monster.monitor.usage_ready.emit((usage, 100, False))
    assert "30 token" in panel.usage_status.text() and "样本不足" in panel.usage_status.text()
    monster.monitor.failed.emit("读取失败 test-mcp-secret")
    assert "UNKNOWN" in panel.progress_status.text()
    assert "最后成功快照" in panel.progress_detail.toPlainText()
    assert "test-mcp-secret" not in panel.progress_detail.toPlainText()
    assert "UNKNOWN" in panel.usage_status.text()
    record.context_limit = 0
    monster.monitor.progress_ready.emit(ProgressSnapshot([SessionProgress(record)]))
    assert "UNKNOWN" in panel.session_table.item(0, 3).text()
    assert monster.monitor.starts == 1


@pytest.mark.parametrize("action_index,page", [(0, "home"), (1, "sessions"), (2, "mcd"), (3, "settings")])
def test_minimized_panel_reopens_from_each_tray_menu_tab(monster, action_index, page):
    monster.action_panel()
    panel = monster.panel
    panel.showMinimized()
    QApplication.processEvents()
    assert panel.isMinimized()
    monster.tray.contextMenu().actions()[action_index].trigger()
    assert monster.panel is panel and panel.isVisible() and not panel.isMinimized()
    assert panel.tabs.currentIndex() == panel.pages[page]
    assert monster.monitor.starts == 1 and not monster.tasks.busy


def test_settings_cancel_blank_retain_clear_save_and_no_second_monitor(monster, monkeypatch):
    saved = []
    def save(values):
        saved.append(dict(values))
        for key, value in values.items():
            monkeypatch.setenv(key, value)
    monkeypatch.setattr(config, "save_settings", save)
    monster.action_settings()
    form = monster.panel.settings
    assert "STEPFUN_API_KEY" not in form.fields
    assert form.fields["MCD_MCP_TOKEN"].echoMode() == QLineEdit.Password
    assert form.fields["MCD_MCP_TOKEN"].text() == ""
    form.fields["MCD_MCP_TOKEN"].setText("unsaved-test-secret")
    form.fields["MCPET_CITY"].setText("未保存城市")
    form.cancel_button.click()
    assert not saved and form.fields["MCD_MCP_TOKEN"].text() == ""
    form.fields["MCPET_CITY"].setText("杭州")
    form.save_button.click()
    assert "MCD_MCP_TOKEN" not in saved[-1] and config.city() == "杭州"
    assert "重启" in form.message.text()
    form.fields["MCD_MCP_TOKEN"].setText("new-fixture-secret")
    form.save_button.click()
    assert saved[-1]["MCD_MCP_TOKEN"] == "new-fixture-secret"
    assert form.fields["MCD_MCP_TOKEN"].text() == ""
    assert "new-fixture-secret" not in form.message.text()
    form.clear_token.setChecked(True)
    form.save_button.click()
    assert saved[-1]["MCD_MCP_TOKEN"] == ""
    form.fields["MCD_MCP_TOKEN"].setText("discard-on-close")
    monster.panel.close()
    monster.action_settings()
    assert form.fields["MCD_MCP_TOKEN"].text() == "" and monster.monitor.starts == 1
    form.fields["MCD_MCP_TOKEN"].setText("discard-on-escape")
    monster.panel.reject()
    monster.action_settings()
    assert form.fields["MCD_MCP_TOKEN"].text() == ""


def test_settings_failure_busy_guard_and_missing_credentials(monster, monkeypatch):
    monkeypatch.setenv("MCD_MCP_TOKEN", "")
    monster.monitor.failed.emit("controlled boot failure")  # 面板尚未创建。
    monster.action_settings()
    form = monster.panel.settings
    assert "UNKNOWN" in monster.panel.progress_status.text()
    assert form.fields["MCD_MCP_TOKEN"].text() == ""
    monkeypatch.setattr(config, "save_settings", lambda values: (_ for _ in ()).throw(OSError("test-step-secret")))
    form.save_button.click()
    assert "保存失败" in form.message.text() and "test-step-secret" not in form.message.text()
    monster.run_async(lambda: time.sleep(.08), lambda value: None, key="controlled-pending")
    assert not form.save_button.isEnabled()
    monster._save_settings({"MCPET_CITY": "未提交"})
    assert "等待" in form.message.text()
    pump_until(lambda: not monster.tasks.busy)
    assert form.save_button.isEnabled() and monster.monitor.starts == 1


def test_inline_payment_and_companion_controls(monster, monkeypatch):
    monster.action_panel("mcd")
    panel = monster.panel
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))
    panel.show_payment(OrderOutcome("placed", "测试门店 / 汉堡 / 无券 / 外带", 990, "fixture", "https://pay.example/order"))
    panel.open_button.click()
    panel.copy_button.click()
    assert opened == ["https://pay.example/order"] and QApplication.clipboard().text() == opened[0]
    panel.show_payment(OrderOutcome("placed", pay_url="https://pay.example/?key=test-mcp-secret"))
    assert not panel.copy_button.isEnabled() and "test-mcp-secret" not in panel.payment_text.text()
    panel.show_payment(OrderOutcome("placed", pay_url="file:///C:/bad.exe"))
    assert not panel.open_button.isEnabled()
    panel.roaming_button.click()
    assert monster.window.roaming_enabled
    panel.resting_button.click()
    assert monster.window.resting
    panel.resting_button.click()
    assert not monster.window.resting


def native_screenshots(directory, characters_root=None):
    """Windows真实Qt + 默认B监控 + 自造小日志，截图存TEMP。"""
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    os.environ.update(MCPET_DATA_DIR=str(directory / "data"), QT_QPA_PLATFORM="windows",
                      QT_SCALE_FACTOR="1", MCPET_WATCH_PROCESSES="0", MCD_MCP_TOKEN="",
                      MCPET_CONFIG_PATH=str(directory / "absent-config.json"))
    inbox = directory / "inbox"
    inbox.mkdir(exist_ok=True)
    os.environ["MCPET_AGENT_ROOTS"] = f"claude={directory / 'absent-claude'},codex={directory / 'absent-codex'},generic={inbox}"
    os.environ["MCPET_AGENT_ROOT_GENERIC"] = str(inbox)
    os.environ["MCPET_CITY"] = "北京"
    records = [dict(kind="progress", ts=time.time(), session="panel-1", state="working", title="面板受控日志验证", contextUsed=48000, contextLimit=200000),
               dict(kind="progress", ts=time.time(), session="panel-2", state="needsinput", title="等待人工核对"),
               dict(kind="progress", ts=time.time()-3600, session="panel-3", state="working", title="过时日志 · 结果未知"),
               dict(kind="usage", ts=time.time(), session="panel-1", key="panel-usage", model="gpt-5.5", input=1234, output=321)]
    (inbox / "controlled.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in records)+"\n", encoding="utf-8")
    config.load_env = lambda: None
    if characters_root:
        # Explicit read-only A module overlay for this probe, without merge/copy.
        import importlib.util
        import src.pet
        for name in ("spritesheet", "preferences", "characters", "window"):
            path = Path(characters_root) / "src" / "pet" / (name + ".py")
            spec = importlib.util.spec_from_file_location("src.pet." + name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            setattr(src.pet, name, module)
            spec.loader.exec_module(module)
        main.PetWindow = src.pet.window.PetWindow
        main.SpriteSheet = src.pet.spritesheet.SpriteSheet
        main.SpriteLoadError = src.pet.spritesheet.SpriteLoadError
        main.MonsterApp._load_sheet = lambda self: src.pet.characters.load_character("maimai")
    calls = []
    def forbidden(*args, **kwargs):
        calls.append("forbidden-network")
        raise AssertionError("No network or independent chat in native panel probe")
    main.McdMcpClient = forbidden
    from src.llm import stepfun
    from src.chat.store import ChatStore
    import httpx
    stepfun.StepFunClient = forbidden
    ChatStore.__init__ = forbidden
    httpx.Client.request = forbidden
    main.QtDailyScheduler.start = lambda self: None  # 禁止构造时同步补饭点。
    monster = main.MonsterApp([], account_monitor_factory=AccountMonitorStub)
    monster.scheduler.stop()
    errors, screenshots = [], []
    started = time.monotonic()
    poll = QTimer()
    poll.setInterval(40)
    def capture():
        if not monster.progress_snapshot or not monster.usage_snapshot:
            if time.monotonic() - started > 20:
                errors.append(config.redact(f"monitor timeout: {monster.monitor_error}; progress={monster.progress_snapshot is not None}; usage={monster.usage_snapshot is not None}"))
                poll.stop()
                monster.quit()
            return
        poll.stop()
        try:
            monster.action_panel()
            panel = monster.panel
            monster.account_monitor.snapshot_ready.emit(sample_snapshot())
            assert panel.session_table.rowCount() == 3
            assert monster.usage_snapshot[0].lifetime.tokens == 1555
            assert not calls
            assert not monster.tasks.busy
            for page in ("home", "sessions", "mcd", "settings"):
                panel.select_page(page)
                if page == "settings":
                    panel.settings.advanced.setChecked(True)
                QApplication.processEvents()
                path = directory / (page + ".png")
                assert panel.grab().save(str(path))
                screenshots.append(str(path))
            panel.select_page("home")
            home_scroll = panel.tabs.currentWidget()
            home_scroll.verticalScrollBar().setValue(home_scroll.verticalScrollBar().maximum())
            QApplication.processEvents()
            path = directory / "home-bottom.png"
            assert panel.grab().save(str(path))
            screenshots.append(str(path))
            if characters_root:
                old_icon = monster.tray.icon().cacheKey()
                panel.character_buttons["deepseek"].click()
                assert monster.window.character_id == "deepseek"
                assert panel.character_buttons["deepseek"].isChecked()
                assert panel.character_name.text() == "DeepSeek 娘"
                assert monster.tray.icon().cacheKey() != old_icon
                home_scroll.verticalScrollBar().setValue(0)
                QApplication.processEvents()
                path = directory / "home-deepseek.png"
                assert panel.grab().save(str(path))
                screenshots.append(str(path))
            assert panel.devicePixelRatioF() == 1.5
            # Closing/reopening must reuse exactly one native panel.
            panel.close()
            monster.window.chat_requested.emit()
            assert monster.panel is panel
        except Exception:
            import traceback
            errors.append(traceback.format_exc())
        finally:
            monster.quit()
    poll.timeout.connect(capture)
    poll.start()
    code = monster.app.exec()
    print(json.dumps(dict(platform=QApplication.platformName(), dpr=monster.panel.devicePixelRatioF() if monster.panel else None,
                          screenshots=screenshots, network_calls=len(calls), errors=errors,
                          characters_root=characters_root,
                          worker_stopped=not monster.tasks.thread.isRunning()), ensure_ascii=False), flush=True)
    return 1 if errors else code


if __name__ == "__main__" and sys.argv[1:2] == ["--screenshots"]:
    multiprocessing.freeze_support()
    raise SystemExit(native_screenshots(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None))
