"""Qt-facing bounded account monitor using one standard spawn process.

The GUI never starts/joins a process or waits for IPC/network. A non-daemon
bridge finishes bounded cleanup before interpreter exit; the worker is owned
by a Windows Job Object (POSIX session), including any CLI descendants.
Injected sources must be spawn-pickleable and expose the documented fetch.
"""

from __future__ import annotations

from dataclasses import replace
import math
import multiprocessing
import queue
import threading
import time

from PySide6.QtCore import QCoreApplication, QObject, QTimer, Signal, Slot, Qt

from .models import AccountSnapshot
from .processes import ProcessFamily
from .sources import DeepSeekBalanceSource, OrcaAccountSource
from .worker import observe, source_failure


class AccountMonitor(QObject):
    snapshot_ready = Signal(object)
    failed = Signal(str)
    stopped = Signal()
    _received = Signal(int, object)
    _finished = Signal(bool)

    def __init__(self, parent=None, *, orca_source=None, deepseek_source=None,
                 interval: float = 300.0, query_timeout: float = 15.0):
        super().__init__(parent)
        if not math.isfinite(interval) or interval <= 0 or not math.isfinite(query_timeout) or query_timeout <= 0:
            raise ValueError("monitor intervals and timeouts must be finite and positive")
        self.last_snapshot: AccountSnapshot | None = None
        self.first_failure: str | None = None
        self._sources = (orca_source if orca_source is not None else OrcaAccountSource(),
                         deepseek_source if deepseek_source is not None else DeepSeekBalanceSource())
        self._query_timeout = query_timeout
        self._generation = 0
        self._lock = threading.Lock()
        self._requests = queue.Queue(maxsize=1)
        self._stopping = threading.Event()
        self._threads: list[threading.Thread] = []
        self._active = False
        self._closed = False
        self._pending = False
        self._again = False
        self._last_good = {}
        self._received.connect(self._deliver, Qt.ConnectionType.QueuedConnection)
        self._finished.connect(self._did_stop, Qt.ConnectionType.QueuedConnection)
        self._timer = QTimer(self)
        self._timer.setInterval(max(1, min(2147483647, round(interval * 1000))))
        self._timer.timeout.connect(self.refresh)
        application = QCoreApplication.instance()
        if application is not None:
            application.aboutToQuit.connect(self.stop)

    def start(self) -> None:
        if self._active:
            return
        if self._closed:
            self._failure("账号监控已停止；需要新实例才能启动")
            return
        self._active = True
        thread = threading.Thread(target=self._bridge, daemon=False, name="mcpet-accounts-ipc")
        self._threads.append(thread)
        thread.start()
        self._timer.start()
        self.refresh()

    def refresh(self) -> None:
        if not self._active:
            return
        if self._pending:
            self._again = True
            return
        self._pending = True
        self._requests.put_nowait(True)

    def reconfigure(self, *, orca_source=None, deepseek_source=None) -> None:
        """Keep None sources; invalidate old credential results without GUI waits.

        The caller follows with refresh(). A single pending refresh is sufficient
        even when the old query is still running. Cached data for a changed source
        is cleared, so old credentials cannot become the new source's fallback.
        """
        if self._closed or (orca_source is None and deepseek_source is None):
            return
        with self._lock:
            old_orca, old_deepseek = self._sources
            self._sources = (orca_source if orca_source is not None else old_orca,
                             deepseek_source if deepseek_source is not None else old_deepseek)
            self._generation += 1
        if orca_source is not None:
            self._last_good = {p: a for p, a in self._last_good.items() if p == "deepseek"}
        if deepseek_source is not None:
            self._last_good.pop("deepseek", None)
        # last_snapshot is historical only until the next snapshot_ready. Consumers
        # show refreshing after saving a key; it is never republished as new data.

    def stop(self) -> None:
        """Immediately stop requests/signals; the bridge owns bounded reaping."""
        self._active = False
        self._closed = True
        self._timer.stop()
        self._again = False
        self._stopping.set()
        if not self._threads:
            self.stopped.emit()

    @staticmethod
    def _reap(process, connection, family) -> None:
        if connection is not None:
            connection.close()
        if process is not None and process.pid is not None:
            process.join(timeout=0.2)
            if process.is_alive():
                process.terminate()
                process.join(timeout=1.0)
            # Closing the Job kills descendants even if their parent is already gone.
            if family is not None:
                family.close()
            if process.is_alive():
                process.kill()
                process.join(timeout=1.0)
            if process.is_alive():
                raise RuntimeError("account worker did not exit")
            process.close()
        elif family is not None:
            family.close()

    def _emit(self, generation: int, snapshot: AccountSnapshot) -> None:
        try:
            self._received.emit(generation, snapshot)
        except RuntimeError:
            # QObject may already have been deleted during application teardown.
            self._stopping.set()

    def _bridge(self) -> None:
        process = connection = family = child = None
        applied_generation = None
        reaped = True
        try:
            context = multiprocessing.get_context("spawn")
            while not self._stopping.is_set():
                try:
                    self._requests.get(timeout=0.05)
                except queue.Empty:
                    continue
                with self._lock:
                    generation, sources = self._generation, self._sources
                deadline = time.monotonic() + self._query_timeout
                try:
                    if process is None:
                        connection, child = context.Pipe()
                        process = context.Process(target=observe, args=(child,), name="mcpet-accounts")
                        if self._stopping.is_set():
                            break
                        process.start()
                        child.close()
                        child = None
                        family = ProcessFamily(process.pid)
                        # The child cannot launch the CLI before ownership is established.
                        while not self._stopping.is_set() and not connection.poll(0.025):
                            if time.monotonic() >= deadline or not process.is_alive():
                                raise TimeoutError("worker startup")
                        if self._stopping.is_set():
                            break
                        if connection.recv() != "ready":
                            raise RuntimeError("invalid worker startup")
                    replacement = sources if applied_generation != generation else None
                    connection.send((generation, replacement))
                    applied_generation = generation
                    while not self._stopping.is_set() and not connection.poll(0.025):
                        if time.monotonic() >= deadline:
                            raise TimeoutError("account query")
                        if not process.is_alive():
                            raise RuntimeError("account worker exited")
                    if self._stopping.is_set():
                        break
                    received_generation, snapshot = connection.recv()
                    if received_generation != generation or not isinstance(snapshot, AccountSnapshot):
                        raise RuntimeError("invalid worker response")
                    self._emit(generation, snapshot)
                except Exception as exc:
                    if self._stopping.is_set():
                        break
                    # Classify without copying arbitrary exception text or pickle args.
                    message = "账号查询超时" if isinstance(exc, TimeoutError) else "账号后台查询失败"
                    self._reap(process, connection, family)
                    process = connection = family = None
                    applied_generation = None
                    self._emit(generation, AccountSnapshot(source_failure(message), time.time()))
        finally:
            try:
                self._reap(process, connection, family)
            except Exception:
                reaped = False
            if child is not None:
                child.close()
            try:
                self._finished.emit(reaped)
            except RuntimeError:
                pass

    def _failure(self, message: str) -> None:
        if self.first_failure is None:
            self.first_failure = message
        self.failed.emit(message)

    @Slot(int, object)
    def _deliver(self, generation: int, snapshot: AccountSnapshot) -> None:
        if not self._active:
            return
        self._pending = False
        if generation == self._generation:
            accounts = []
            errors = set()
            for account in snapshot.accounts:
                original = account
                if account.status == "ok":
                    self._last_good[account.provider] = account
                elif account.status in ("error", "unavailable"):
                    previous = self._last_good.get(account.provider)
                    # A valid official is_available=false response (including
                    # an exact zero balance) is a new fact, not a failed read.
                    if previous is not None and not (account.provider == "deepseek" and account.balances):
                        account = replace(previous, status="stale",
                                          message=f"{account.label} 刷新失败；保留上次成功观测")
                    if original.status == "error":
                        errors.add(f"{original.label}: {original.message}")
                accounts.append(account)
            self.last_snapshot = AccountSnapshot(tuple(accounts), snapshot.observed_at)
            for message in sorted(errors):
                self._failure(message)
            self.snapshot_ready.emit(self.last_snapshot)
        if self._again:
            self._again = False
            self.refresh()

    @Slot(bool)
    def _did_stop(self, reaped: bool) -> None:
        if reaped:
            self.stopped.emit()
        else:
            self._failure("账号后台进程回收失败")

