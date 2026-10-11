"""Real Qt/spawn against controlled sources; no real CLI or account requests."""

from decimal import Decimal
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest
from PySide6.QtCore import QCoreApplication, QTimer

from src.accounts import AccountMonitor, AccountStatus, DeepSeekBalanceSource, MoneyBalance, OrcaAccountSource, QuotaBucket


class FixtureOrca:
    def fetch(self):
        return (AccountStatus("codex", "Codex", "ok", time.time(),
                              (QuotaBucket("weekly", 16, time.time() + 600),)),)


class FixtureDeepSeek:
    def fetch(self):
        return AccountStatus("deepseek", "DeepSeek", "unconfigured", None)


class CountingOrca(FixtureOrca):
    def __init__(self, path, delay=0.05):
        self.path = Path(path)
        self.delay = delay

    def fetch(self):
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write("query\n")
        time.sleep(self.delay)
        return super().fetch()


class FlakyOrca(FixtureOrca):
    def __init__(self):
        self.calls = 0

    def fetch(self):
        self.calls += 1
        if self.calls == 2:
            raise RuntimeError("Bearer DO_NOT_EXPOSE")
        return super().fetch()


class FixtureMoney:
    def __init__(self, total, path=None, delay=0):
        self.total = total
        self.path = path
        self.delay = delay

    def fetch(self):
        if self.path:
            Path(self.path).write_text("balance started", encoding="utf-8")
        time.sleep(self.delay)
        return AccountStatus("deepseek", "DeepSeek", "ok", time.time(), balances=(
            MoneyBalance("CNY", Decimal(self.total), Decimal("0"), Decimal(self.total)),))


class FailedMoney:
    def fetch(self):
        raise RuntimeError("fixture-secret-in-exception")


class ZeroMoney:
    def fetch(self):
        return AccountStatus("deepseek", "DeepSeek", "unavailable", time.time(), balances=(
            MoneyBalance("CNY", Decimal("0"), Decimal("0"), Decimal("0")),))


class SlowCliOrca:
    """Controlled child simulates a stuck CLI, never starts Orca account list."""

    def __init__(self, path):
        self.path = str(path)

    def fetch(self):
        actual_pid = Path(self.path).with_suffix(".cli-pid")
        child_code = ("import os, time; from pathlib import Path; "
                      f"Path({str(actual_pid)!r}).write_text(str(os.getpid())); time.sleep(60)")
        process = subprocess.Popen([sys.executable, "-c", child_code],
                                   shell=False, creationflags=(subprocess.CREATE_NO_WINDOW
                                                               if sys.platform == "win32" else 0))
        Path(self.path).write_text(json.dumps({"worker": os.getpid(), "cli": process.pid,
                                              }), encoding="utf-8")
        time.sleep(60)
        return ()


def close_monitor(monitor):
    monitor.stop()
    pump_until(lambda: all(not t.is_alive() for t in monitor._threads))


def pump_until(predicate, timeout=12):
    started = time.monotonic()
    while not predicate() and time.monotonic() - started < timeout:
        QCoreApplication.processEvents()
        time.sleep(0.005)
    assert predicate(), "bounded account observation timed out"


def test_public_monitor_nonblocking_spawn_and_stop():
    monitor = AccountMonitor(orca_source=FixtureOrca(), deepseek_source=FixtureDeepSeek())
    snapshots, failures = [], []
    monitor.snapshot_ready.connect(snapshots.append)
    monitor.failed.connect(failures.append)
    try:
        start = time.monotonic()
        monitor.start()
        assert time.monotonic() - start < 0.05
        for _ in range(100):
            monitor.refresh()
        pump_until(lambda: snapshots)
        assert snapshots[0].accounts[0].buckets[0].used_percent == 16
        assert snapshots[0].accounts[1].status == "unconfigured"
        assert failures == []
    finally:
        start = time.monotonic()
        monitor.stop()
        assert time.monotonic() - start < 0.05
        pump_until(lambda: all(not t.is_alive() for t in monitor._threads))


def test_refresh_burst_merges_and_same_worker_queries_serially(tmp_path):
    calls = tmp_path / "calls.txt"
    monitor = AccountMonitor(orca_source=CountingOrca(calls, 0.15), deepseek_source=FixtureDeepSeek())
    snapshots = []
    monitor.snapshot_ready.connect(snapshots.append)
    try:
        monitor.start()
        pump_until(calls.exists)
        for _ in range(200):
            monitor.refresh()
        assert monitor._requests.qsize() <= 1
        pump_until(lambda: len(snapshots) >= 2)
        for _ in range(20):
            QCoreApplication.processEvents()
            time.sleep(0.01)
        assert calls.read_text().splitlines() == ["query", "query"]
        assert len(monitor._threads) == 1
        assert monitor._threads[0].daemon is False
    finally:
        close_monitor(monitor)


def test_failure_stales_previous_success_and_recovery_is_separate():
    monitor = AccountMonitor(orca_source=FlakyOrca(), deepseek_source=FixtureMoney("2.01"))
    snapshots, failures = [], []
    monitor.snapshot_ready.connect(snapshots.append)
    monitor.failed.connect(failures.append)
    try:
        monitor.start()
        pump_until(lambda: len(snapshots) == 1)
        first = snapshots[0].accounts[0]
        monitor.refresh()
        pump_until(lambda: len(snapshots) == 2)
        stale = snapshots[-1].accounts[0]
        assert stale.status == "stale"
        assert stale.buckets == first.buckets and stale.updated_at == first.updated_at
        assert snapshots[-1].accounts[-1].status == "ok"
        assert monitor.first_failure == failures[0]
        assert "DO_NOT_EXPOSE" not in repr(failures) + repr(snapshots)
        monitor.refresh()
        pump_until(lambda: len(snapshots) == 3)
        assert snapshots[-1].accounts[0].status == "ok"
        assert monitor.first_failure == failures[0]
    finally:
        close_monitor(monitor)


def test_reconfigure_discards_inflight_old_credentials_and_keeps_single_monitor(tmp_path):
    marker = tmp_path / "old-started.txt"
    calls = tmp_path / "orca-calls.txt"
    monitor = AccountMonitor(orca_source=CountingOrca(calls, 0),
                             deepseek_source=FixtureMoney("1.25", marker, 0.25))
    snapshots, failures = [], []
    monitor.snapshot_ready.connect(snapshots.append)
    monitor.failed.connect(failures.append)
    try:
        monitor.start()
        pump_until(marker.exists)
        started = time.monotonic()
        monitor.reconfigure(deepseek_source=FixtureMoney("7.1234567890123456789"))
        monitor.refresh()
        assert time.monotonic() - started < 0.05
        for _ in range(100):
            monitor.refresh()
        pump_until(lambda: snapshots)
        assert snapshots[0].accounts[-1].balances[0].total == Decimal("7.1234567890123456789")
        assert all(s.accounts[-1].balances[0].total != Decimal("1.25") for s in snapshots)
        assert calls.read_text().splitlines() == ["query", "query"]
        assert len(monitor._threads) == 1
        assert failures == []
    finally:
        close_monitor(monitor)


def test_reconfigure_clears_changed_source_fallback_and_none_keeps_source():
    monitor = AccountMonitor(orca_source=FixtureOrca(), deepseek_source=FixtureMoney("6"))
    snapshots = []
    monitor.snapshot_ready.connect(snapshots.append)
    try:
        monitor.start()
        pump_until(lambda: len(snapshots) == 1)
        generation = monitor._generation
        monitor.reconfigure()
        assert monitor._generation == generation
        monitor.reconfigure(deepseek_source=FailedMoney())
        monitor.refresh()
        pump_until(lambda: len(snapshots) == 2)
        assert snapshots[-1].accounts[0].status == "ok"
        assert snapshots[-1].accounts[-1].status == "error"
        assert snapshots[-1].accounts[-1].balances == ()  # old key's balance cannot be fallback
        assert "fixture-secret" not in repr(snapshots) + str(monitor.first_failure)
    finally:
        close_monitor(monitor)


def test_actual_sources_are_spawn_safe_with_fixture_cli_and_no_key(tmp_path):
    script = tmp_path / "fixture.py"
    payload = {"result": {"rateLimits": [{
        "provider": "codex", "status": "ok", "updatedAt": time.time() * 1000,
        "weekly": {"usedPercent": 27, "resetsAt": (time.time() + 600) * 1000},
    }]}}
    body = json.dumps(payload).encode()
    script.write_text(f"import sys\nsys.stdout.buffer.write({body!r})\n", encoding="utf-8")
    monitor = AccountMonitor(orca_source=OrcaAccountSource(command=[sys.executable, str(script)]),
                             deepseek_source=DeepSeekBalanceSource())
    snapshots = []
    monitor.snapshot_ready.connect(snapshots.append)
    try:
        monitor.start()
        pump_until(lambda: snapshots)
        assert snapshots[0].accounts[0].buckets[0].used_percent == 27
        assert snapshots[0].accounts[-1].status == "unconfigured"
        assert not (tmp_path / "data" / "usage.json").exists()
    finally:
        close_monitor(monitor)


def test_actual_worker_pid_is_owned_before_first_query(monkeypatch):
    import src.accounts.monitor as monitor_module
    from src.accounts.processes import ProcessFamily
    attached = []

    class RecordingFamily(ProcessFamily):
        def attach(self, pid):
            super().attach(pid)
            attached.append(pid)

    monkeypatch.setattr(monitor_module, "ProcessFamily", RecordingFamily)
    monitor = AccountMonitor(orca_source=FixtureOrca(), deepseek_source=FixtureDeepSeek())
    snapshots = []
    monitor.snapshot_ready.connect(snapshots.append)
    try:
        monitor.start()
        pump_until(lambda: snapshots)
        assert len(attached) >= (2 if sys.platform == "win32" else 1)
        assert all(isinstance(pid, int) and pid > 0 for pid in attached)
    finally:
        close_monitor(monitor)


def test_successful_zero_unavailable_is_published_as_fact():
    monitor = AccountMonitor(orca_source=FixtureOrca(), deepseek_source=FixtureMoney("6"))
    monitor._active = True
    from src.accounts import AccountSnapshot
    first = AccountSnapshot((FixtureMoney("6").fetch(),), time.time())
    monitor._deliver(0, first)
    monitor._deliver(0, AccountSnapshot((ZeroMoney().fetch(),), time.time()))
    assert monitor.last_snapshot.accounts[0].status == "unavailable"
    assert monitor.last_snapshot.accounts[0].balances[0].total == 0
    monitor.stop()


def test_failed_callback_can_replace_key_without_old_snapshot_publication():
    from src.accounts import AccountSnapshot
    monitor = AccountMonitor(orca_source=FixtureOrca(), deepseek_source=FixtureMoney("6"))
    monitor._active = True
    snapshots = []
    monitor.snapshot_ready.connect(snapshots.append)
    monitor.failed.connect(lambda _: monitor.reconfigure(deepseek_source=FixtureMoney("3")))
    error = AccountStatus("codex", "Codex", "error", None, message="Orca 额度 CLI 查询超时")
    try:
        monitor._deliver(0, AccountSnapshot((error, FixtureMoney("6").fetch()), time.time()))
        assert snapshots == []
    finally:
        monitor.stop()


def test_last_successful_zero_balance_is_retained_after_read_failure():
    from src.accounts import AccountSnapshot
    monitor = AccountMonitor(orca_source=FixtureOrca(), deepseek_source=FixtureMoney("6"))
    monitor._active = True
    try:
        monitor._deliver(0, AccountSnapshot((FixtureMoney("6").fetch(),), time.time()))
        monitor._deliver(0, AccountSnapshot((ZeroMoney().fetch(),), time.time()))
        error = AccountStatus("deepseek", "DeepSeek", "error", None, message="DeepSeek 余额查询超时")
        monitor._deliver(0, AccountSnapshot((error,), time.time()))
        assert monitor.last_snapshot.accounts[0].status == "stale"
        assert monitor.last_snapshot.accounts[0].balances[0].total == 0
    finally:
        monitor.stop()


def test_stop_before_start_is_idempotent():
    monitor = AccountMonitor(orca_source=FixtureOrca(), deepseek_source=FixtureDeepSeek())
    stopped = []
    monitor.stopped.connect(lambda: stopped.append(True))
    monitor.stop()
    monitor.stop()
    assert stopped == [True]


def test_timeout_reaps_worker_and_cli_and_keeps_gui_heartbeat(tmp_path):
    marker = tmp_path / "pids.json"
    monitor = AccountMonitor(orca_source=SlowCliOrca(marker), deepseek_source=FixtureDeepSeek(),
                             query_timeout=3.0)
    snapshots, failures, ticks = [], [], []
    monitor.snapshot_ready.connect(snapshots.append)
    monitor.failed.connect(failures.append)
    timer = QTimer()
    timer.setInterval(20)
    timer.timeout.connect(lambda: ticks.append(time.monotonic()))
    timer.start()
    try:
        monitor.start()
        pump_until(lambda: snapshots)
        assert marker.exists()
        pids = json.loads(marker.read_text())
        actual_pid = marker.with_suffix(".cli-pid")
        if actual_pid.exists():
            pids["cli_actual"] = int(actual_pid.read_text())
        assert all(not pid_running(pid) for pid in pids.values())
        assert all(a.status == "error" for a in snapshots[-1].accounts)
        assert "超时" in monitor.first_failure
        assert len(ticks) >= 15
        assert max(b - a for a, b in zip(ticks, ticks[1:])) < 0.15
        monitor.reconfigure(orca_source=FixtureOrca())
        monitor.refresh()
        pump_until(lambda: len(snapshots) == 2)
        assert snapshots[-1].accounts[0].status == "ok"
    finally:
        timer.stop()
        close_monitor(monitor)


def test_automatic_refresh_interval_override_and_stop_signal():
    monitor = AccountMonitor(orca_source=FixtureOrca(), deepseek_source=FixtureDeepSeek(), interval=0.1)
    assert monitor._timer.interval() == 100
    snapshots, stopped = [], []
    monitor.snapshot_ready.connect(snapshots.append)
    monitor.stopped.connect(lambda: stopped.append(True))
    monitor.start()
    try:
        pump_until(lambda: len(snapshots) >= 3)
    finally:
        close_monitor(monitor)
    pump_until(lambda: stopped)
    assert len(stopped) == 1
    assert not monitor._timer.isActive()
    before = len(snapshots)
    monitor.refresh()
    monitor.reconfigure(deepseek_source=FixtureMoney("3"))
    QCoreApplication.processEvents()
    assert len(snapshots) == before


@pytest.mark.parametrize("interval", [0, -1, float("nan"), float("inf")])
def test_invalid_interval_is_rejected(interval):
    with pytest.raises(ValueError):
        AccountMonitor(interval=interval, orca_source=FixtureOrca(), deepseek_source=FixtureDeepSeek())


def pid_running(pid):
    if sys.platform == "win32":
        import ctypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
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


@pytest.mark.parametrize("mode", ["--immediate-exit", "--blocked-exit", "--qt-exit"])
def test_whole_interpreter_exit_is_bounded_and_reaps_owned_processes(tmp_path, mode):
    env = dict(os.environ, MCPET_DATA_DIR=str(tmp_path / "data"),
               TEMP=str(tmp_path), TMP=str(tmp_path), QT_QPA_PLATFORM="offscreen")
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    started = time.monotonic()
    result = subprocess.run([sys.executable, __file__, mode, str(tmp_path / "pids.json")],
                            capture_output=True, encoding="utf-8", env=env, timeout=10)
    elapsed = time.monotonic() - started
    assert result.returncode == 0, result.stderr
    assert elapsed < 8  # same whole-interpreter allowance as the existing runtime
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["pids"]
    assert payload["stop_ms"] < 50
    assert time.time() - payload["stop_finished_at"] < 3
    assert all(not pid_running(pid) for pid in payload["pids"])


def exit_probe(mode, marker):
    from PySide6.QtWidgets import QApplication
    app = QApplication([])
    monitor = AccountMonitor(orca_source=SlowCliOrca(marker), deepseek_source=FixtureDeepSeek())
    monitor.start()
    started = time.monotonic()
    if mode == "--immediate-exit":
        while not multiprocessing.active_children() and time.monotonic() - started < 4:
            time.sleep(0.002)
        pids = [p.pid for p in multiprocessing.active_children()]
    else:
        actual_pid = marker.with_suffix(".cli-pid")
        while (not marker.exists() or not actual_pid.exists()) and time.monotonic() - started < 5:
            time.sleep(0.002)
        pids = list(json.loads(marker.read_text()).values())
        pids.append(int(actual_pid.read_text()))
    if mode == "--qt-exit":
        QTimer.singleShot(0, app.quit)
        started = time.monotonic()
        app.exec()  # aboutToQuit -> stop(), no explicit stop/join/event pump afterwards
        stop_ms = (time.monotonic() - started) * 1000
    else:
        started = time.monotonic()
        monitor.stop()
        stop_ms = (time.monotonic() - started) * 1000
    print(json.dumps({"pids": pids, "stop_ms": stop_ms, "stop_finished_at": time.time()}), flush=True)
    # Deliberately return immediately: non-daemon bridge must finish before Python exits.


if __name__ == "__main__":
    exit_probe(sys.argv[1], Path(sys.argv[2]))
