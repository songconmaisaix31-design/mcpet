"""Qt/spawn integration and bounded whole-interpreter shutdown checks."""

from __future__ import annotations

import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest
from PySide6.QtCore import QCoreApplication

from src.agentbridge.paths import AgentRoots
from src.agentbridge.records import ProgressRecord
from src.progress.tracker import ProgressSnapshot, SessionProgress
from src.runtime.monitor import AgentMonitor


def pump_until(predicate, timeout=12):
    started = time.monotonic()
    while not predicate() and time.monotonic() - started < timeout:
        QCoreApplication.processEvents()
        time.sleep(0.005)
    assert predicate(), "bounded Qt observation timed out"


def roots_at(root):
    return AgentRoots(roots={"generic": [root]}, declared={"generic": [root]})


def write_progress(path, state, *, completed=False):
    entry = {"kind": "progress", "session": "s", "ts": time.time(), "state": state,
             "contextUsed": 10, "contextLimit": 100}
    if completed:
        entry["kind"] = "task_complete"
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")


def test_spawn_refresh_completion_and_serial_usage_persistence(tmp_path):
    root = tmp_path / "inbox"
    root.mkdir()
    progress = root / "s.json"
    write_progress(progress, "working")
    usage = root / "usage.jsonl"
    usage.write_text(json.dumps({"kind": "usage", "key": "u1", "ts": time.time(),
                                 "model": "gpt-5.5", "input": 40}) + "\n", encoding="utf-8")
    monitor = AgentMonitor(roots=roots_at(root), state_path=tmp_path / "usage.json",
                           progress_interval=0.08, usage_interval=0.1)
    completions, errors = [], []
    monitor.task_completed.connect(completions.append)
    monitor.failed.connect(errors.append)
    try:
        started = time.monotonic()
        monitor.start()
        assert time.monotonic() - started < 0.1
        for _ in range(100):
            monitor.refresh_progress()
            monitor.refresh_usage()
        assert monitor._queues["usage"].qsize() <= 1
        pump_until(lambda: monitor.last_progress is not None and monitor.last_usage is not None)
        assert monitor.last_usage[0].lifetime.tokens == 40
        assert not errors
        write_progress(progress, "done", completed=True)
        pump_until(lambda: len(completions) == 1)
        last = monitor.last_progress.sampled_at
        pump_until(lambda: monitor.last_progress.sampled_at > last + 0.15)
        assert len(completions) == 1
        assert monitor.last_usage[0].lifetime.tokens == 40
        assert "gpt-5.5" in monitor.last_usage[0].estimated_models
    finally:
        started = time.monotonic()
        monitor.stop()
        assert time.monotonic() - started < 0.05
        pump_until(lambda: all(not t.is_alive() for t in monitor._threads))
    from src.metering.usage import UsageMeter
    assert UsageMeter([], state_path=tmp_path / "usage.json").snapshot().lifetime.tokens == 40


def test_no_sources_returns_unknown_without_inventing_data(tmp_path):
    monitor = AgentMonitor(roots=AgentRoots(), state_path=tmp_path / "usage.json")
    try:
        monitor.start()
        pump_until(lambda: monitor.last_progress is not None and monitor.last_usage is not None)
        assert monitor.last_progress.status == "UNKNOWN"
        assert monitor.last_usage[0].status == "UNKNOWN"
        assert monitor.last_usage[2] is False
    finally:
        monitor.stop()
        pump_until(lambda: all(not t.is_alive() for t in monitor._threads))


def test_failure_retains_last_snapshot_and_first_failure(tmp_path):
    monitor = AgentMonitor(roots=AgentRoots(), state_path=tmp_path / "usage.json")
    monitor._active = True
    snapshot = ProgressSnapshot()
    monitor._deliver("progress", "ready", snapshot)
    errors = []
    monitor.failed.connect(errors.append)
    monitor._deliver("progress", "failed", "first failure")
    monitor._deliver("progress", "failed", "second failure")
    assert monitor.last_progress is snapshot
    assert monitor.first_failure == "first failure"
    assert errors == ["first failure", "second failure"]
    monitor.stop()


def test_stale_and_initial_completed_sessions_do_not_trigger_celebration(tmp_path):
    monitor = AgentMonitor(roots=AgentRoots(), state_path=tmp_path / "usage.json")
    monitor._active = True
    monitor._started_at = time.time()
    completed = []
    monitor.task_completed.connect(completed.append)
    record = ProgressRecord("codex", "s", state="done", completed_at=time.time() - 100,
                            completion_id="old")
    snapshot = ProgressSnapshot(sessions=[SessionProgress(record)])
    monitor._deliver("progress", "ready", snapshot)
    monitor._deliver("progress", "ready", snapshot)
    assert completed == []
    record.completed_at = time.time()
    record.completion_id = "new"
    monitor._deliver("progress", "ready", snapshot)
    monitor._deliver("progress", "ready", snapshot)
    assert completed == [record]
    monitor.stop()


def test_spawn_stop_then_interpreter_exit_is_bounded_and_reaps_children(tmp_path):

    root = tmp_path / "inbox"
    root.mkdir()
    # Enough parsing work to stop during a scan, without touching user logs.
    with (root / "cold.jsonl").open("wb") as handle:
        line = json.dumps({"padding": "x" * 65536}).encode() + b"\n"
        for _ in range(1024):
            handle.write(line)
    env = dict(os.environ, MCPET_DATA_DIR=str(tmp_path / "data"))
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    started = time.monotonic()
    result = subprocess.run([sys.executable, __file__, "--spawn-exit", str(root)],
                            capture_output=True, text=True, env=env, timeout=15)
    assert result.returncode == 0, result.stderr
    assert time.monotonic() - started < 8
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["children"]
    assert payload["stop_ms"] < 50
    assert all(not pid_running(pid) for pid in payload["children"])


def pid_running(pid: int) -> bool:
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


def spawn_exit(root: Path | None) -> None:
    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    options = {"roots": roots_at(root)} if root is not None else {}
    monitor = AgentMonitor(**options)
    monitor.start()
    started = time.monotonic()
    children = []
    while time.monotonic() - started < 8:
        app.processEvents()
        children = multiprocessing.active_children()
        if len(children) >= 2:
            time.sleep(0.1)
            break
        time.sleep(0.005)
    if len(children) < 2:
        monitor.stop()
        raise RuntimeError("spawn children were not observed")
    started = time.monotonic()
    monitor.stop()
    print(json.dumps({"children": [p.pid for p in children],
                      "stop_ms": (time.monotonic() - started) * 1000}), flush=True)
    # Deliberately no join/pump: exercise interpreter exit with active bridges.


if __name__ == "__main__":
    if sys.argv[1] == "--spawn-exit":
        spawn_exit(Path(sys.argv[2]))
    elif sys.argv[1] == "--real-exit":
        spawn_exit(None)
