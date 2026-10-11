"""Native assembly against controlled sources, never live balances or tasks.

Account sources are top-level/pickleable. Both production monitors and all three
read workers run normally. Contract/exit and performance are separate assertions
over one run, so a heartbeat RED cannot conceal process-cleanup evidence.
"""
from __future__ import annotations

from decimal import Decimal
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.accounts import AccountStatus, MoneyBalance, QuotaBucket
from test_companion_integration import native_window_state, pid_running, probe_env


def deny_network(*args, **kwargs):
    raise AssertionError("controlled integration forbids network")


def install_network_guard(directory):
    import httpx
    import socket

    def blocked(*args, **kwargs):
        with (Path(directory) / "network-denied").open("a", encoding="utf-8") as handle:
            handle.write("denied\n")
        deny_network()

    httpx.Client.request = blocked
    socket.create_connection = blocked
    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked


class ControlledQuota:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.calls = 0

    def fetch(self):
        install_network_guard(self.directory)
        self.calls += 1
        with (self.directory / "quota-calls").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"call": self.calls, "pid": os.getpid()}) + "\n")
        gate = self.directory / "hold-query"
        if gate.exists():
            gate.unlink()
            (self.directory / "query-entered").write_text("entered", encoding="utf-8")
            deadline = time.monotonic() + 12
            while not (self.directory / "release-query").exists():
                if time.monotonic() > deadline:
                    raise AssertionError("controlled release timed out")
                time.sleep(0.01)
            (self.directory / "release-query").unlink()
        now = time.time()
        return (
            AccountStatus("codex", "Codex · 受控夹具", "ok", now,
                          (QuotaBucket("session", 16.25, now + 3600), QuotaBucket("weekly", 30, now + 86400))),
            AccountStatus("cursor", "Cursor · 受控夹具", "ok", now,
                          tuple(QuotaBucket(name, value, now + 90000) for name, value in
                                (("monthly", 20), ("Cursor Models", 35.5), ("Other Models", 90)))),
            AccountStatus("claude", "Claude · 受控夹具", "unavailable", None),
            AccountStatus("grok", "Grok · 受控夹具", "ok", now,
                          (QuotaBucket("weekly", 0, now + 86400),)),
        )


class ControlledMoney:
    def __init__(self, directory, version):
        self.directory, self.version = Path(directory), version

    def fetch(self):
        install_network_guard(self.directory)
        with (self.directory / "money-calls").open("a", encoding="utf-8") as handle:
            handle.write(str(self.version) + "\n")
        return AccountStatus("deepseek", "DeepSeek · 受控夹具", "ok", time.time(), balances=(
            MoneyBalance("CNY", Decimal("123.456789012345678901") if self.version == 1 else Decimal("0.001"),
                         Decimal("0"), Decimal("123.456789012345678901") if self.version == 1 else Decimal("0.001")),))


def observed_agent_worker(connection, stopping, kind, options):
    """Record this controlled worker's real body PID, then run the original worker."""
    from src.runtime.worker import observe
    directory = Path(options["state_path"]).parent
    install_network_guard(directory)
    (directory / (kind + "-body-pid")).write_text(str(os.getpid()), encoding="ascii")
    observe(connection, stopping, kind, options)


def run_observation(directory, screenshots=None):
    directory.mkdir(parents=True, exist_ok=True)
    env = probe_env(directory)
    env["DEEPSEEK_API_KEY"] = "mock-initial-key-only"
    command = [sys.executable, str(Path(__file__).resolve()), "--probe"]
    arguments = command + ["observe"] + ([str(screenshots)] if screenshots else [])
    primary = subprocess.Popen(arguments, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, encoding="utf-8")
    try:
        deadline = time.monotonic() + 20
        while not (directory / "ready").exists() and primary.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert (directory / "ready").exists(), primary.communicate(timeout=5)
        duplicate = subprocess.run(command + ["secondary"], cwd=ROOT, env=env,
                                   capture_output=True, text=True, encoding="utf-8", timeout=10)
        assert duplicate.returncode == 0, duplicate.stderr
        assert json.loads(duplicate.stdout.strip().splitlines()[-1]) == {"secondary": True, "has_readers": False}
        (directory / "duplicate-checked").write_text("checked", encoding="utf-8")
        started = time.monotonic()
        stdout, stderr = primary.communicate(timeout=12)
        elapsed = time.monotonic() - started
        assert primary.returncode == 0, stdout + stderr
        result = json.loads(stdout.strip().splitlines()[-1])
        print(json.dumps(result, ensure_ascii=False))
        result["exit_elapsed_s"] = elapsed
        result["quit_to_reaped_s"] = time.monotonic() - result.pop("quit_requested_at")
        result["stderr"] = stderr
        result["unreaped"] = [pid for pid in result["children"] + result["body_pids"] if pid_running(pid)]
        result["lock_removed"] = not (directory / "app.lock").exists()
        restored = subprocess.run(command + ["restore"], cwd=ROOT, env=env,
                                  capture_output=True, text=True, encoding="utf-8", timeout=12)
        assert restored.returncode == 0, restored.stdout + restored.stderr
        result["restart"] = json.loads(restored.stdout.strip().splitlines()[-1])
        assert not (directory / "network-denied").exists()
        print(json.dumps({"post_duplicate_elapsed_s": elapsed, "quit_to_reaped_s": result["quit_to_reaped_s"], "unreaped": result["unreaped"],
                          "lock_removed": result["lock_removed"], "restart": result["restart"]}))
        return result
    finally:
        if primary.poll() is None:
            primary.terminate()
            primary.wait(timeout=5)


@pytest.fixture(scope="module")
def native_combination(tmp_path_factory):
    return run_observation(tmp_path_factory.mktemp("native-dual-quota"))


def assert_contract(result):
    assert result["platform"] == ("windows" if sys.platform == "win32" else "offscreen")
    assert result["real_monitors"] and result["auto_start"] and result["working"]
    assert result["roles"] == ["maimai", "deepseek", "maimai", "deepseek"]
    assert result["role_frames_advanced"] and result["drag_with_live_notification"]
    assert result["cursor_values"] == [20, 35.5, 90] and result["decimal_exact"]
    assert result["generation_discarded"] and result["singleflight_queries"] == 3
    assert result["money_versions"] == [1, 1, 2]
    assert set(result["restored_entries"]) == {"duplicate", "tray", "right-menu", "double-click"}
    for state in result["restored_entries"].values():
        assert state["visible"] and not state["minimized"]
        if sys.platform == "win32":
            assert state["native_visible"] and not state["iconic"]
    assert len(result["children"]) == len(result["body_pids"]) == 3 and result["writer_count"] == 1
    assert not result["unreaped"] and result["lock_removed"]
    assert result["active_exit"] and not result["thread_running"] and result["all_windows_closed"]
    assert result["stop_ms"] < 50 and result["exit_elapsed_s"] < 8 and result["quit_to_reaped_s"] < 8
    assert "QThread: Destroyed" not in result["stderr"]
    assert result["restart"] == {"restored": True, "character": "deepseek", "thread_running": False}
    assert result["errors"] == [] and result["network_calls"] == 0


def test_native_dual_pet_accounts_contract_and_bounded_exit(native_combination):
    assert_contract(native_combination)


def test_native_dual_pet_accounts_heartbeat(native_combination):
    assert native_combination["heartbeat_ticks"] > 20
    assert native_combination["max_tick_gap_ms"] < 150


def native_probe(mode, screenshots=None):
    from PySide6.QtCore import QEvent, QPoint, QPointF, Qt, QTimer
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon
    from src import accounts, config, main
    from src.accounts import monitor as account_module
    from src.runtime.monitor import AgentMonitor
    from src.runtime import monitor as agent_module
    from src.chat.store import ChatStore
    from src.llm import stepfun

    config.load_env = lambda: None
    # Exercise C's save/reconfigure route without creating or reading any .env.
    config.save_settings = lambda values: os.environ.update(values)
    directory = config.data_dir()
    install_network_guard(directory)
    main.McdMcpClient = stepfun.StepFunClient = ChatStore.__init__ = deny_network
    main.QtDailyScheduler.start = lambda self: None
    agent_module.observe = observed_agent_worker
    account_module.OrcaAccountSource = lambda: ControlledQuota(directory)
    accounts.DeepSeekBalanceSource = lambda key="": ControlledMoney(directory, 2 if key == "mock-new-key-only" else 1)
    inbox = directory / "inbox"
    inbox.mkdir(exist_ok=True)
    def append(**entry):
        with (inbox / "controlled.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(dict(ts=time.time(), session="controlled", **entry)) + "\n")
    if mode == "observe":
        append(kind="progress", state="idle", title="组合契约 · 非用户任务")
        append(kind="usage", key="combo-1", model="gpt-5.5", input=40)

    monster = main.MonsterApp([])  # Both default production monitors; source dependencies only are controlled.
    if monster.secondary:
        code = monster.app.exec()
        print(json.dumps({"secondary": True, "has_readers": hasattr(monster, "monitor") or hasattr(monster, "account_monitor")}))
        return code
    if mode == "restore":
        assert monster.window.character_id == "deepseek" and monster.sheet is monster.window.sheet
        assert monster.window.pos() == QPoint(170, 140) and monster.window.resting and monster.window.roaming_enabled
        QTimer.singleShot(180, monster.quit)
        code = monster.app.exec()
        print(json.dumps({"restored": True, "character": monster.window.character_id,
                          "thread_running": monster.tasks.thread.isRunning()}))
        return code

    result = {"roles": [monster.window.character_id], "restored_entries": {}, "screenshots": [], "phase_max_ms": {}}
    errors, snapshots, ticks, children = [], [], [], []
    phase, connected = "boot", False
    started = time.monotonic()
    heartbeat, poll = QTimer(), QTimer()
    heartbeat.setInterval(10)
    heartbeat.timeout.connect(lambda: ticks.append(time.monotonic()))
    heartbeat.start()
    poll.setInterval(10)

    def mouse(kind, x, buttons=Qt.LeftButton):
        point = QPoint(x, 300)
        QApplication.sendEvent(monster.window, QMouseEvent(kind, QPointF(monster.window.mapFromGlobal(point)),
                              QPointF(point), Qt.NoButton if kind == QEvent.MouseMove else Qt.LeftButton, buttons, Qt.NoModifier))

    def minimize():
        monster.panel.showMinimized()
        QApplication.processEvents()
        state = native_window_state(monster.panel)
        assert state["minimized"] and (sys.platform != "win32" or state["iconic"]), state

    def restored(entry):
        state = native_window_state(monster.panel)
        assert state["visible"] and not state["minimized"], state
        assert any(s.availableGeometry().intersects(monster.panel.frameGeometry()) for s in QApplication.screens())
        result["restored_entries"][entry] = state

    def capture(name, page="home", bottom=False):
        if not screenshots:
            return
        monster.panel.select_page(page)
        if page == "settings":
            monster.panel.settings.advanced.setChecked(True)
        if page == "home":
            scroll = monster.panel.tabs.currentWidget().verticalScrollBar()
            scroll.setValue(scroll.maximum() if bottom else 0)
        QApplication.processEvents()
        path = Path(screenshots) / (name + ".png")
        assert monster.panel.grab().save(str(path))
        result["screenshots"].append(str(path))

    def step():
        nonlocal phase, connected, children
        if time.monotonic() - started > 20:
            quota = monster.account_monitor
            result["timeout_diagnostic"] = dict(phase=phase, generation=quota._generation,
                pending=quota._pending, again=quota._again, active=quota._active,
                bridge_alive=[thread.is_alive() for thread in quota._threads],
                snapshots=len(snapshots), account_refreshing=monster.account_refreshing,
                account_present=monster.account_snapshot is not None)
            raise AssertionError(f"controlled combination timeout: {phase}")
        if monster.monitor is None or monster.account_monitor is None:
            return
        monitor, quota = monster.monitor, monster.account_monitor
        assert type(monitor) is AgentMonitor and type(quota) is accounts.AccountMonitor
        if not connected:
            monitor.failed.connect(errors.append)
            quota.failed.connect(errors.append)
            quota.snapshot_ready.connect(snapshots.append)
            connected = True
        assert not errors, errors
        if phase == "boot" and monster.progress_snapshot and monster.usage_snapshot and monster.account_snapshot:
            result.update(real_monitors=True, auto_start=True)
            assert monster.usage_snapshot[0].lifetime.tokens == 40
            children = sorted(p.pid for p in multiprocessing.active_children())
            assert len(children) == 3
            monitor.start()
            quota.start()
            assert len(monitor._threads) == 2 and len(quota._threads) == 1
            append(kind="progress", state="working", title="组合契约 · 非用户任务", contextUsed=25, contextLimit=100)
            monitor.refresh_progress()
            phase = "work"
        elif phase == "work" and monster.window.machine.base_state == "working":
            result["working"] = monster.window.context_bar.value() == 25
            begin = time.monotonic()
            monster.action_panel()
            result["first_panel_ms"] = round((time.monotonic() - begin) * 1000, 2)
            panel = monster.panel
            cursor = next(a for a in monster.account_snapshot.accounts if a.provider == "cursor")
            result["cursor_values"] = [b.used_percent for b in cursor.buckets]
            cursor_row = next(row for row in panel.account_rows if row["provider"] == "cursor")
            assert [b.name for b in cursor.buckets] == ["monthly", "Cursor Models", "Other Models"]
            assert all(f"已用 {value:g}%" in row[0].text() and f"剩余 {100-value:g}%" in row[0].text()
                       for value, row in zip(result["cursor_values"], cursor_row["buckets"]))
            balance = monster.account_snapshot.accounts[-1].balances[0]
            money_text = next(row for row in panel.account_rows if row["provider"] == "deepseek")["balances"][0].text()
            result["decimal_exact"] = balance.total == Decimal("123.456789012345678901") and "123.456789012345678901" in money_text
            capture("home")
            capture("home-bottom", bottom=True)
            for character in ("deepseek", "maimai", "deepseek"):
                old_icon = monster.tray.icon().cacheKey()
                old_state = monster.window.machine.state
                panel.character_buttons[character].click()
                assert monster.window.character_id == character and monster.sheet is monster.window.sheet
                assert monster.window.machine.state == old_state
                assert monster.tray.icon().cacheKey() != old_icon
                assert panel._preview_sheet is monster.sheet and not panel.preview.pixmap().isNull()
                result["roles"].append(character)
            frame = monster.window._index
            poll.stop()
            QTest.qWait(110)  # Actual atlas timer advance, far below notification TTL.
            result["role_frames_advanced"] = monster.window._index != frame
            monster.window.say_state("greet", "受控未过期通知", 6000)
            mouse(QEvent.MouseButtonPress, 300)
            mouse(QEvent.MouseMove, 340)
            result["drag_with_live_notification"] = monster.window.machine.state == "run-right"
            mouse(QEvent.MouseButtonRelease, 340, Qt.NoButton)
            assert monster.window.machine.state == "greet"
            capture("home-deepseek")
            for page in ("sessions", "mcd", "settings"):
                capture(page, page)
            panel.select_page("home")
            minimize()
            (directory / "ready").write_text("ready", encoding="utf-8")
            phase = "duplicate"
            poll.start()
        elif phase == "duplicate" and (directory / "duplicate-checked").exists():
            restored("duplicate")
            minimize()
            monster.tray.activated.emit(QSystemTrayIcon.Trigger)
            restored("tray")
            minimize()
            def menu_action():
                menu = QApplication.activePopupWidget()
                if menu is None:
                    QTimer.singleShot(10, menu_action)
                    return
                menu.actions()[0].trigger()
                menu.close()
            poll.stop()
            QTimer.singleShot(10, menu_action)
            monster.on_menu(monster.window.pos())
            restored("right-menu")
            minimize()
            mouse(QEvent.MouseButtonDblClick, 300)
            mouse(QEvent.MouseButtonRelease, 300, Qt.NoButton)
            restored("double-click")
            (directory / "hold-query").write_text("hold", encoding="utf-8")
            monster.action_quota()
            phase = "held-refresh"
            poll.start()
        elif phase == "held-refresh" and (directory / "query-entered").exists():
            (directory / "query-entered").unlink()
            for _ in range(30):
                # Exercise the actual monitor singleflight, not 30 complete UI
                # rebuilds in one synthetic Qt callback. C's route is exercised
                # by the initial action_quota and the save/reconfigure below.
                quota.refresh()
            monster._save_settings({"DEEPSEEK_API_KEY": "mock-new-key-only"})
            assert monster.account_monitor is quota and monster.account_snapshot is None and monster.account_refreshing
            (directory / "release-query").write_text("release", encoding="utf-8")
            phase = "new-generation"
        elif phase == "new-generation" and monster.account_snapshot and not quota._pending:
            result["generation_discarded"] = len(snapshots) == 2 and snapshots[-1].accounts[-1].balances[0].total == Decimal("0.001")
            calls = [json.loads(row) for row in (directory / "quota-calls").read_text(encoding="utf-8").splitlines()]
            result["singleflight_queries"] = len(calls)
            result["money_versions"] = [int(row) for row in (directory / "money-calls").read_text(encoding="utf-8").splitlines()]
            result["account_body_pids"] = sorted({row["pid"] for row in calls})
            result["body_pids"] = result["account_body_pids"] + [
                int((directory / (kind + "-body-pid")).read_text(encoding="ascii")) for kind in ("progress", "usage")]
            assert sorted(p.pid for p in multiprocessing.active_children()) == children
            (directory / "hold-query").write_text("hold", encoding="utf-8")
            monster.action_quota()
            phase = "exit-query"
        elif phase == "exit-query" and (directory / "query-entered").exists():
            entered = threading.Event()
            def active_task():
                entered.set()
                time.sleep(0.25)
            monster.run_async(active_task, lambda value: None, key="controlled-active")
            result["active_event"] = entered
            phase = "exit-task"
        elif phase == "exit-task" and result["active_event"].is_set():
            result.pop("active_event")
            monster.window.set_roaming(True)
            monster.window.set_resting(True)
            monster.window.move(170, 140)
            result.update(children=children, writer_count=sum(p.name == "mcpet-usage" for p in multiprocessing.active_children()))
            begin = time.monotonic()
            result["quit_requested_at"] = begin
            monster.quit()
            result["stop_ms"] = (time.monotonic() - begin) * 1000
            result["active_exit"] = monster.closing and monster.tasks.thread.isRunning() and not monster._allow_quit
            assert not monster.tasks.submit("late", lambda: None, lambda value: None, lambda error: None)
            assert not quota._timer.isActive() and not monster.panel.quota_timer.isActive()
            poll.stop()

    def safe_step():
        current_phase, begin = phase, time.monotonic()
        try:
            step()
        except Exception:
            import traceback
            errors.append(traceback.format_exc())
            result.pop("active_event", None)
            poll.stop()
            monster.quit()
        finally:
            elapsed = round((time.monotonic() - begin) * 1000, 2)
            result["phase_max_ms"][current_phase] = max(result["phase_max_ms"].get(current_phase, 0), elapsed)
    poll.timeout.connect(safe_step)
    poll.start()
    code = monster.app.exec()
    heartbeat.stop()
    result.update(platform=QApplication.platformName(), dpr=monster.window.devicePixelRatioF(),
                  thread_running=monster.tasks.thread.isRunning(), all_windows_closed=not monster.window.isVisible() and not (monster.panel and monster.panel.isVisible()),
                  heartbeat_ticks=len(ticks), max_tick_gap_ms=round(max((1000 * (b-a) for a, b in zip(ticks, ticks[1:])), default=0), 2),
                  network_calls=len((directory / "network-denied").read_text().splitlines()) if (directory / "network-denied").exists() else 0, errors=errors)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    # Production non-daemon bridges reap; no test join/event pumping after Qt exit.
    return 1 if errors else code


if __name__ == "__main__":
    multiprocessing.freeze_support()
    if sys.argv[1:2] == ["--probe"]:
        raise SystemExit(native_probe(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None))
    if sys.argv[1:2] == ["--screenshots"]:
        screenshot_dir = Path(sys.argv[2]).resolve()
        screenshot_dir.mkdir(parents=True, exist_ok=False)
        observed = run_observation(screenshot_dir / "data", screenshot_dir)
        assert_contract(observed)
        assert observed["dpr"] == 1.5 and len(observed["screenshots"]) == 6
        raise SystemExit(0)
