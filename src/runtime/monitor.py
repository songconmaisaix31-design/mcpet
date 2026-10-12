"""Qt-facing observation with bounded queues and standard spawn processes.

The GUI never receives from a pipe, starts a process, joins a process, waits on
a Future, or shuts down an executor. Small bridge threads handle IPC and cleanup;
CPU parsing and the persistent usage ledger live exclusively in child processes.
"""

from __future__ import annotations

import multiprocessing
import queue
import threading
import time
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject, QTimer, Signal, Slot, Qt

from ..agentbridge import AgentRoots, resolve_roots
from .. import config
from .worker import observe


class AgentMonitor(QObject):
    progress_ready = Signal(object)
    usage_ready = Signal(object)
    failed = Signal(str)
    task_completed = Signal(object)
    _received = Signal(str, str, object)

    def __init__(
        self, parent: QObject | None = None, *, roots: AgentRoots | None = None,
        state_path: Path | None = None, pricing_override: Path | None = None,
        progress_interval: float = 10.0, usage_interval: float = 60.0,
        window_hours: float | None = None, stale_minutes: int | None = None,
        max_sessions: int = 12, watch_processes: bool | None = None,
    ) -> None:
        super().__init__(parent)
        if progress_interval <= 0 or usage_interval <= 0:
            raise ValueError("refresh intervals must be positive")
        self.last_progress = None
        self.last_usage = None
        self.first_failure: str | None = None
        self._active = False
        self._closed = False
        self._options = dict(
            roots=roots, state_path=state_path, pricing_override=pricing_override,
            window_hours=window_hours, stale_minutes=stale_minutes,
            max_sessions=max_sessions, watch_processes=watch_processes,
        )
        self._stopping = threading.Event()
        self._queues = {kind: queue.Queue(maxsize=1) for kind in ("progress", "usage")}
        self._pending = {kind: False for kind in self._queues}
        self._threads: list[threading.Thread] = []
        self._completions: dict[tuple[str, str], tuple[str, float]] = {}
        self._baseline = False
        self._started_at = 0.0
        self._received.connect(self._deliver, Qt.ConnectionType.QueuedConnection)
        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(max(1, round(progress_interval * 1000)))
        self._progress_timer.timeout.connect(self.refresh_progress)
        self._usage_timer = QTimer(self)
        self._usage_timer.setInterval(max(1, round(usage_interval * 1000)))
        self._usage_timer.timeout.connect(self.refresh_usage)
        application = QCoreApplication.instance()
        if application is not None:
            application.aboutToQuit.connect(self.stop)

    def start(self) -> None:
        if self._active:
            return
        if self._closed:
            self._failure("monitor 已停止；重新启动请创建新实例")
            return
        self._active = True
        self._started_at = time.time()
        for kind in self._queues:
            # Non-daemon bridges finish bounded cleanup before the interpreter's
            # multiprocessing atexit hook joins children. GUI stop never joins.
            thread = threading.Thread(target=self._bridge, args=(kind,), daemon=False,
                                      name=f"mcpet-{kind}-ipc")
            self._threads.append(thread)
            thread.start()
        self._progress_timer.start()
        self._usage_timer.start()
        self.refresh_progress()
        self.refresh_usage()

    def stop(self) -> None:
        """Return immediately. Bridge threads cooperatively stop then reap children."""
        self._active = False
        self._closed = True
        self._progress_timer.stop()
        self._usage_timer.stop()
        self._stopping.set()

    def refresh_progress(self) -> None:
        self._request("progress")

    def refresh_usage(self) -> None:
        self._request("usage")

    def _request(self, kind: str) -> None:
        if not self._active or self._pending[kind]:
            return
        self._pending[kind] = True
        self._queues[kind].put_nowait(True)

    def _bridge(self, kind: str) -> None:
        process = connection = child = stopping = None
        try:
            # Resolve only the configured/default candidates, never enumerate
            # additional Orca accounts. All filesystem setup runs off the GUI.
            options = dict(self._options)
            options["roots"] = options["roots"] or resolve_roots(config_path=config.agent_config_path())
            options["state_path"] = options["state_path"] or config.data_dir() / "usage.json"
            options["pricing_override"] = options["pricing_override"] or config.data_dir() / "pricing.json"
            options["window_hours"] = options["window_hours"] or config.usage_window_hours()
            options["stale_minutes"] = options["stale_minutes"] or config.progress_stale_minutes()
            if options["watch_processes"] is None:
                options["watch_processes"] = config.watch_processes()
            context = multiprocessing.get_context("spawn")
            connection, child = context.Pipe()
            stopping = context.Event()
            process = context.Process(target=observe, args=(child, stopping, kind, options),
                                      name=f"mcpet-{kind}")
            if self._stopping.is_set():
                return
            process.start()
            child.close()
            while not self._stopping.is_set():
                try:
                    self._queues[kind].get(timeout=0.05)
                except queue.Empty:
                    if not process.is_alive():
                        raise RuntimeError(f"后台进程退出 ({process.exitcode})")
                    continue
                connection.send(True)
                while not self._stopping.is_set():
                    if connection.poll(0.05):
                        state, payload = connection.recv()
                        self._received.emit(kind, state, payload)
                        break
                    if not process.is_alive():
                        raise RuntimeError(f"后台进程退出 ({process.exitcode})")
        except Exception as exc:
            if not self._stopping.is_set():
                self._received.emit(kind, "failed", f"{kind}: {type(exc).__name__}: {exc}")
        finally:
            if stopping is not None:
                stopping.set()
            if process is not None and process.pid is not None:
                process.join(timeout=1.0)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=2.0)
                if not process.is_alive():
                    process.close()
            if connection is not None:
                connection.close()
            if child is not None:
                child.close()

    def _failure(self, message: str) -> None:
        if self.first_failure is None:
            self.first_failure = message
        self.failed.emit(message)

    @Slot(str, str, object)
    def _deliver(self, kind: str, state: str, payload: object) -> None:
        if not self._active:
            return
        self._pending[kind] = False
        if state == "failed":
            self._failure(str(payload))
            return
        snapshot = payload[0] if kind == "usage" else payload
        if snapshot.errors:
            for error in snapshot.errors:
                self._failure(f"{kind}: {error}")
            # Keep the last successful observation, do not label partial reads
            # successful. Snapshot/report itself also retains UNKNOWN diagnostics.
            return
        if kind == "usage":
            self.last_usage = payload
            self.usage_ready.emit(payload)
        else:
            for session in snapshot.sessions:
                record = session.record
                if not record.completed_at or not record.completion_id:
                    continue
                key = (record.source, record.session_id)
                event = (record.completion_id, record.completed_at)
                previous = self._completions.get(key)
                if self._baseline and event != previous and record.completed_at >= self._started_at and record.completed_at > (previous[1] if previous else 0):
                    self.task_completed.emit(record)
                self._completions[key] = event
            self._baseline = True
            self.last_progress = snapshot
            self.progress_ready.emit(snapshot)
