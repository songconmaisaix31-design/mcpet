"""Bounded read-only Windows observation benchmark, with isolated ledger writes.

python -m src.runtime.benchmark --deadline 120
Never loads .env, queries a model/MCP, or expands configured log roots.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import multiprocessing
import os
from pathlib import Path
import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from ..agentbridge import resolve_roots
from ..agentbridge.providers.base import iter_jsonl_files
from .. import config
from .monitor import AgentMonitor


class MemoryCounters(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
               ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
               ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
               ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
               ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


def working_set(pid: int) -> float:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(MemoryCounters), ctypes.c_ulong]
    handle = kernel.OpenProcess(0x410, False, pid)
    if not handle:
        return 0.0
    try:
        counters = MemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return counters.WorkingSetSize / 1024**2
        return 0.0
    finally:
        kernel.CloseHandle(handle)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--deadline", type=float, default=120)
    args = parser.parse_args()
    if os.name != "nt":
        raise RuntimeError("working-set sampling requires Windows")
    if not os.environ.get("MCPET_DATA_DIR"):
        raise RuntimeError("set an isolated MCPET_DATA_DIR first")
    state = config.data_dir() / "usage.json"
    if state.exists():
        raise RuntimeError("cold benchmark requires an unused data directory")
    roots = resolve_roots(config_path=config.agent_config_path())
    files = [p for paths in roots.roots.values() for root in paths for p in iter_jsonl_files(root)]
    output = {"files": len(files), "bytes": sum(p.stat().st_size for p in files),
              "sources": roots.active_ids(), "errors": [], "usage_samples": []}
    app = QApplication([])
    monitor = AgentMonitor(roots=roots, state_path=state, progress_interval=10, usage_interval=60)
    started = time.perf_counter()
    tick_at = started
    intervals = []
    peaks = {}
    requested_at = started
    refresh_timer = QTimer()
    refresh_timer.setSingleShot(True)

    def tick():
        nonlocal tick_at
        now = time.perf_counter()
        intervals.append((now - tick_at) * 1000)
        tick_at = now

    def sample_memory():
        pids = [os.getpid()] + [p.pid for p in multiprocessing.active_children()]
        for pid in pids:
            peaks[pid] = max(peaks.get(pid, 0), working_set(pid))

    def request_usage():
        nonlocal requested_at
        requested_at = time.perf_counter()
        monitor.refresh_usage()

    def usage_ready(payload):
        snapshot = payload[0]
        output["usage_samples"].append({
            "elapsed_s": round(time.perf_counter() - requested_at, 3),
            "lifetime_tokens": snapshot.lifetime.tokens, "status": snapshot.status,
            "estimated_models": len(snapshot.estimated_models), "unknown_models": len(snapshot.unknown_models),
        })
        if len(output["usage_samples"]) == 1:
            print(json.dumps({"cold_ready": output["usage_samples"][0]}, ensure_ascii=False), flush=True)
            refresh_timer.start(300)
        else:
            monitor.stop()
            app.quit()

    def progress_ready(snapshot):
        if "first_progress_s" not in output:
            output["first_progress_s"] = round(time.perf_counter() - started, 3)
            output["progress_sessions"] = len(snapshot.sessions)

    def failure(message):
        output["errors"].append(message)
        monitor.stop()
        app.quit()

    def timed_out():
        failure("benchmark deadline exceeded")

    heartbeat = QTimer()
    heartbeat.setInterval(60)
    heartbeat.timeout.connect(tick)
    memory = QTimer()
    memory.setInterval(100)
    memory.timeout.connect(sample_memory)
    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.timeout.connect(timed_out)
    refresh_timer.timeout.connect(request_usage)
    monitor.usage_ready.connect(usage_ready)
    monitor.progress_ready.connect(progress_ready)
    monitor.failed.connect(failure)
    heartbeat.start()
    memory.start()
    deadline.start(round(args.deadline * 1000))
    monitor.start()
    app.exec()
    stop_started = time.perf_counter()
    monitor.stop()
    output["stop_ms"] = round((time.perf_counter() - stop_started) * 1000, 3)
    output["qt_heartbeat_max_ms"] = round(max(intervals, default=0), 3)
    output["qt_heartbeat_samples"] = len(intervals)
    output["sampled_working_set_peak_mib"] = {str(pid): round(value, 2) for pid, value in peaks.items()}
    output["parent_pid"] = os.getpid()
    output["elapsed_s"] = round(time.perf_counter() - started, 3)
    print(json.dumps(output, ensure_ascii=False), flush=True)
    return 1 if output["errors"] else 0


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
