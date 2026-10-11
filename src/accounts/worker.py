"""One serial account query process; no ledger, scheduler or model requests."""

import os
import sys
import time

from .models import AccountSnapshot, AccountStatus
from .sources import PROVIDERS, unknown_account


def source_failure(message: str) -> tuple[AccountStatus, ...]:
    return tuple(unknown_account(p, "error", message) for p in (*PROVIDERS, "deepseek"))


def observe(connection) -> None:
    if sys.platform != "win32":
        os.setsid()
    sources = None
    try:
        connection.send(("ready", os.getpid()))
        while True:
            request = connection.recv()
            if request is None:
                return
            generation, replacement = request
            if replacement is not None:
                sources = replacement
            orca, deepseek = sources
            try:
                accounts = tuple(orca.fetch())
                if not all(isinstance(a, AccountStatus) and a.provider in PROVIDERS for a in accounts):
                    raise ValueError("invalid quota source")
                if not accounts or len({a.provider for a in accounts}) != len(accounts):
                    raise ValueError("empty or duplicate quota source")
            except Exception:
                accounts = tuple(unknown_account(p, "error", "Orca 额度数据源查询失败") for p in PROVIDERS)
            try:
                balance = deepseek.fetch()
                if not isinstance(balance, AccountStatus) or balance.provider != "deepseek":
                    raise ValueError("invalid balance source")
            except Exception:
                balance = unknown_account("deepseek", "error", "DeepSeek 余额数据源查询失败")
            connection.send((generation, AccountSnapshot((*accounts, balance), time.time())))
    except (EOFError, BrokenPipeError, OSError):
        pass
    finally:
        connection.close()
