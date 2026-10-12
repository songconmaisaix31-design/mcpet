"""Serialize shared local ledgers across Agent-hosted MCP processes."""
from contextlib import contextmanager
import os
import threading
import time

from . import config

_thread_lock = threading.RLock()


@contextmanager
def data_lock(timeout=10):
    with _thread_lock:
        path = config.data_dir() / "agent-data.lock"
        with path.open("a+b") as stream:
            if stream.tell() == 0:
                stream.write(b"0")
                stream.flush()
            deadline = time.monotonic() + timeout
            while True:
                try:
                    stream.seek(0)
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError("另一个 Agent 正在更新本机数据，请稍后再试")
                    time.sleep(0.05)
            try:
                yield
            finally:
                stream.seek(0)
                if os.name == "nt":
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream, fcntl.LOCK_UN)
