"""A/B/C assembly with native Qt and controlled logs; no live task or network."""
from __future__ import annotations

import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]


def probe_env(directory):
    env = dict(os.environ, MCPET_DATA_DIR=str(directory),
               QT_QPA_PLATFORM="windows" if sys.platform == "win32" else "offscreen",
               MCD_MCP_TOKEN="mock-token-only", STEPFUN_API_KEY="mock-key-only",
               MCPET_WATCH_PROCESSES="0", PYTHONIOENCODING="utf-8")
    # Explicit nonexistent roots prevent fallback to any user Agent directory.
    env["MCPET_AGENT_ROOTS"] = (
        f"claude={directory / 'absent-claude'},codex={directory / 'absent-codex'},"
        f"generic={directory / 'inbox'}")
    env["MCPET_CONFIG_PATH"] = str(directory / "absent-config.json")
    return env


def pid_running(pid):
    if sys.platform == "win32":
        import ctypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x100000, False, pid)
        if not handle:
            return False
        try:
            return kernel.WaitForSingleObject(handle, 0) == 258
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def native_window_state(widget):
    """只读检查本探针创建的 HWND；不枚举或操作其他应用窗口。"""
    state = {"minimized": widget.isMinimized(), "visible": widget.isVisible()}
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        user = ctypes.WinDLL("user32", use_last_error=True)
        user.IsIconic.argtypes = [wintypes.HWND]
        user.IsWindowVisible.argtypes = [wintypes.HWND]
        user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        rectangle = wintypes.RECT()
        handle = int(widget.winId())
        assert user.GetWindowRect(handle, ctypes.byref(rectangle))
        state.update(iconic=bool(user.IsIconic(handle)), native_visible=bool(user.IsWindowVisible(handle)),
                     rect=[rectangle.left, rectangle.top, rectangle.right, rectangle.bottom])
    return state


def test_native_app_auto_monitor_gestures_single_writer_and_exit(tmp_path):
    env = probe_env(tmp_path)
    command = [sys.executable, str(Path(__file__).resolve()), "--probe"]
    primary = subprocess.Popen(command + ["observe"], cwd=ROOT, env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8")
    try:
        deadline = time.monotonic() + 15
        while not (tmp_path / "ready").exists() and primary.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert (tmp_path / "ready").exists(), primary.communicate(timeout=5)
        duplicate = subprocess.run(command + ["secondary"], cwd=ROOT, env=env,
                                   capture_output=True, text=True, encoding="utf-8", timeout=10)
        assert duplicate.returncode == 0, duplicate.stderr
        assert json.loads(duplicate.stdout.strip().splitlines()[-1]) == {
            "secondary": True, "has_monitor": False, "has_tasks": False, "has_window": False}
        (tmp_path / "duplicate-checked").write_text("checked", encoding="utf-8")
        started = time.monotonic()
        stdout, stderr = primary.communicate(timeout=12)
        assert primary.returncode == 0, stdout + stderr
        result = json.loads(stdout.strip().splitlines()[-1])
        print(json.dumps(result))  # Preserve diagnostics even when an assertion fails.
        assert result["platform"] == env["QT_QPA_PLATFORM"]
        assert result["auto_start"] and result["working"] and result["gestures"]
        assert set(result["restored_entries"]) == {"duplicate", "tray", "right-menu", "double-click"}
        assert result["before_restore"]["minimized"]
        for state in result["restored_entries"].values():
            assert state["visible"] and not state["minimized"]
            if sys.platform == "win32":
                assert state["native_visible"] and not state["iconic"]
        assert result["completed"] == 1 and result["usage_tokens"] == 110
        assert result["progress_signals"] >= 3 and result["usage_signals"] >= 2
        assert result["writer_count"] == 1 and len(result["children"]) == 2
        assert result["thread_running"] is False and result["stop_ms"] < 50
        assert result["heartbeat_ticks"] > 20 and result["max_tick_gap_ms"] < 150
        assert time.monotonic() - started < 8
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


def native_probe(mode):
    sys.path.insert(0, str(ROOT))
    from PySide6.QtCore import QEvent, QPoint, QPointF, Qt, QTimer
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon
    from src import config, main
    from src.runtime.monitor import AgentMonitor
    from test_app_actions import AccountMonitorOfflineStub

    # Never load a credential file. Network access is an assertion failure.
    config.load_env = lambda: None
    def forbidden(*args, **kwargs):
        raise AssertionError("integration probe must not access model/MCP network")
    main.McdMcpClient = forbidden
    from src.llm import stepfun
    stepfun.StepFunClient = forbidden
    directory = config.data_dir()
    root = directory / "inbox"
    root.mkdir(exist_ok=True)
    log = root / "controlled.jsonl"
    def append(**entry):
        with log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(dict(ts=time.time(), session="controlled", **entry)) + "\n")
    if mode == "observe":
        append(kind="progress", state="idle", project="contract-only")
        append(kind="usage", key="u1", model="gpt-5.5", input=40)
    main.QtDailyScheduler.start = lambda self: None  # No synchronous meal catch-up.
    panel_timings = []
    original_panel = main.MonsterApp.action_panel
    def timed_panel(self, *args, **kwargs):
        begin = time.monotonic()
        try:
            return original_panel(self, *args, **kwargs)
        finally:
            panel_timings.append(round((time.monotonic() - begin) * 1000, 2))
    main.MonsterApp.action_panel = timed_panel
    monster = main.MonsterApp([], account_monitor_factory=AccountMonitorOfflineStub)
    # Default, real AgentMonitor; only the account reader is isolated here.
    if monster.secondary:
        code = monster.app.exec()
        print(json.dumps({"secondary": True, "has_monitor": hasattr(monster, "monitor"),
                          "has_tasks": hasattr(monster, "tasks"), "has_window": hasattr(monster, "window")}))
        return code
    monster.scheduler.stop()  # No automatic meal network in any test.
    if mode == "restore":
        assert monster.window.pos() == QPoint(170, 140)
        assert monster.window.roaming_enabled and monster.window.resting
        QTimer.singleShot(180, monster.quit)
        code = monster.app.exec()
        print(json.dumps({"restored": True, "thread_running": monster.tasks.thread.isRunning()}))
        return code

    result = {"auto_start": False, "working": False, "gestures": False, "restored_entries": {}}
    errors, progress_signals, usage_signals, completed, ticks = [], [], [], [], []
    children = []
    phase, connected, sampled = "boot", False, 0
    started = time.monotonic()
    heartbeat = QTimer()
    heartbeat.setInterval(10)
    heartbeat.timeout.connect(lambda: ticks.append(time.monotonic()))
    heartbeat.start()
    poll = QTimer()
    poll.setInterval(10)

    def mouse(kind, x, button=Qt.LeftButton, buttons=Qt.LeftButton):
        global_point = QPoint(x, 300)
        event = QMouseEvent(kind, QPointF(monster.window.mapFromGlobal(global_point)),
                            QPointF(global_point), button, buttons, Qt.NoModifier)
        QApplication.sendEvent(monster.window, event)

    def refresh():
        monster.monitor.refresh_progress()
        monster.monitor.refresh_usage()

    def minimize_panel():
        monster.panel.showMinimized()
        QApplication.processEvents()
        state = native_window_state(monster.panel)
        assert state["minimized"], state
        if sys.platform == "win32":
            assert state["iconic"], state
        return state

    def assert_restored(entry):
        state = native_window_state(monster.panel)
        assert state["visible"] and not state["minimized"], (entry, state)
        if sys.platform == "win32":
            assert state["native_visible"] and not state["iconic"], (entry, state)
        assert any(screen.availableGeometry().intersects(monster.panel.frameGeometry())
                   for screen in QApplication.screens()), (entry, state)
        result["restored_entries"][entry] = state

    def step():
        nonlocal phase, connected, children, sampled
        monitor = monster.monitor
        if time.monotonic() - started > 20:
            raise AssertionError(f"real monitor probe timeout in {phase}; {errors}")
        if monitor is None:
            return
        assert type(monitor) is AgentMonitor
        if not connected:
            monitor.progress_ready.connect(progress_signals.append)
            monitor.usage_ready.connect(usage_signals.append)
            monitor.task_completed.connect(completed.append)
            monitor.failed.connect(errors.append)
            connected = True
        assert not errors, errors
        if phase == "boot" and monster.progress_snapshot and monster.usage_snapshot:
            result["auto_start"] = True
            assert monster.usage_snapshot[0].lifetime.tokens == 40
            assert not completed
            children = sorted(p.pid for p in multiprocessing.active_children())
            assert len(children) == 2
            assert len(monitor._threads) == 2
            monitor.start()  # Idempotent start must not create another writer.
            append(kind="progress", state="working", project="contract-only", title="controlled work",
                   contextUsed=25, contextLimit=100)
            append(kind="usage", key="u2", model="gpt-5.5", input=60, output=10)
            for _ in range(40):
                refresh()
            phase = "work"
        elif phase == "work" and monster.window.machine.base_state == "working" and monster.usage_snapshot[0].lifetime.tokens == 110:
            assert monster.window.context_bar.value() == 25
            assert "controlled work" in monster.window.activity_label.text()
            assert not completed
            result["working"] = True
            append(kind="task_complete", taskId="explicit-controlled-completion", project="contract-only")
            refresh()
            phase = "complete"
        elif phase == "complete" and completed:
            assert monster.window.machine.state == "happy"
            assert "明确记录" in monster.window.bubble.label.text()
            sampled = monitor.last_progress.sampled_at
            refresh()
            phase = "dedup"
        elif phase == "dedup" and monitor.last_progress.sampled_at > sampled:
            assert len(completed) == 1
            monster.action_panel()
            # The real secondary process must wake an actually minimized window.
            result["before_restore"] = minimize_panel()
            (directory / "ready").write_text("ready", encoding="utf-8")
            phase = "duplicate"
        elif phase == "duplicate" and (directory / "duplicate-checked").exists():
            assert_restored("duplicate")
            assert sorted(p.pid for p in multiprocessing.active_children()) == children
            assert len(monitor._threads) == 2
            poll.stop()  # QTest.qWait pumps events; do not reenter this phase.
            monster.window.machine.clear("happy")
            clicked = []
            monster.window.clicked.connect(lambda: clicked.append(True))
            mouse(QEvent.MouseButtonPress, 300)
            mouse(QEvent.MouseButtonRelease, 300, buttons=Qt.NoButton)
            QTest.qWait(QApplication.doubleClickInterval() + 40)
            assert clicked == [True]
            assert "我在呢" in monster.window.bubble.label.text()
            mouse(QEvent.MouseButtonDblClick, 300)
            mouse(QEvent.MouseButtonRelease, 300, buttons=Qt.NoButton)
            assert monster.panel and monster.panel.isVisible()
            panel = monster.panel
            panel.close()
            mouse(QEvent.MouseButtonDblClick, 300)
            mouse(QEvent.MouseButtonRelease, 300, buttons=Qt.NoButton)
            assert monster.panel is panel and panel.isVisible()
            minimize_panel()
            monster.tray.activated.emit(QSystemTrayIcon.Trigger)
            assert_restored("tray")
            minimize_panel()
            def activate_menu():
                menu = QApplication.activePopupWidget()
                if menu is None:
                    QTimer.singleShot(10, activate_menu)
                    return
                menu.actions()[0].trigger()  # Actual QAction.triggered(bool).
                menu.close()
            QTimer.singleShot(10, activate_menu)
            monster.on_menu(monster.window.pos())
            assert_restored("right-menu")
            minimize_panel()
            mouse(QEvent.MouseButtonDblClick, 300)
            mouse(QEvent.MouseButtonRelease, 300, buttons=Qt.NoButton)
            assert_restored("double-click")
            assert monster.panel is panel
            before = monster.window.pos()
            mouse(QEvent.MouseButtonPress, 300)
            mouse(QEvent.MouseMove, 340, Qt.NoButton)
            assert monster.window.machine.state == "run-right"
            mouse(QEvent.MouseMove, 339, Qt.NoButton)
            assert monster.window.machine.state == "run-right"
            mouse(QEvent.MouseMove, 332, Qt.NoButton)
            assert monster.window.machine.state == "run-left"
            mouse(QEvent.MouseButtonRelease, 332, buttons=Qt.NoButton)
            QTest.qWait(QApplication.doubleClickInterval() + 40)
            assert monster.window.pos() != before and clicked == [True]
            monster.action_roaming()
            monster.action_resting()
            assert monster.window.roaming_enabled and monster.window.resting
            assert monster.window.machine.state == "sleeping"
            monster.action_resting()
            assert not monster.window.resting
            monster.action_resting()
            result["gestures"] = True
            result.update(children=children, writer_count=sum(p.name == "mcpet-usage" for p in multiprocessing.active_children()),
                          completed=len(completed), usage_tokens=monster.usage_snapshot[0].lifetime.tokens,
                          progress_signals=len(progress_signals), usage_signals=len(usage_signals))
            # Exit with queued observation and a running non-network serial task.
            refresh()
            monster.run_async(lambda: time.sleep(0.25), lambda value: None, key="controlled-slow")
            monster.window.move(170, 140)
            stopped_at = time.monotonic()
            monster.quit()
            result["stop_ms"] = (time.monotonic() - stopped_at) * 1000

    def safe_step():
        try:
            step()
        except Exception as exc:
            import traceback
            errors.append(traceback.format_exc())
            poll.stop()
            monster.quit()
    poll.timeout.connect(safe_step)
    poll.start()
    code = monster.app.exec()
    heartbeat.stop()
    result.update(platform=QApplication.platformName(), thread_running=monster.tasks.thread.isRunning(),
                  heartbeat_ticks=len(ticks), max_tick_gap_ms=round(max((1000 * (b-a) for a, b in zip(ticks, ticks[1:])), default=0), 2),
                  panel_open_ms=panel_timings, errors=errors)
    print(json.dumps(result), flush=True)
    # No join or Qt pumping here: interpreter exit must reap real spawn children.
    return 1 if errors else code


if __name__ == "__main__" and sys.argv[1:2] == ["--probe"]:
    multiprocessing.freeze_support()
    raise SystemExit(native_probe(sys.argv[2]))
