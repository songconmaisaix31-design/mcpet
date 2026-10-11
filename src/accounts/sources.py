"""Read-only account sources. No config, credentials discovery or usage ledger.

Orca exposes a cached observation, not vendor settlement. Only the documented
provider/window/bucket fields are extracted; raw account metadata and diagnostics
never enter a snapshot. DeepSeek amounts remain Decimal, never quota percentages.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

import httpx

from .models import AccountStatus, MoneyBalance, QuotaBucket


PROVIDERS = {"codex": "Codex", "grok": "Grok", "cursor": "Cursor", "claude": "Claude"}
_CURSOR_BUCKETS = ("Cursor Models", "Other Models")
BALANCE_URL = "https://api.deepseek.com/user/balance"


def positive_seconds(value: object) -> float | None:
    """Orca's whitelist timestamps are milliseconds, even if they look small."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        result = float(value) / 1000.0
    except (OverflowError, ValueError):
        return None
    return result if math.isfinite(result) and result > 0 else None


def _percent(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        result = float(value)
    except (OverflowError, ValueError):
        return None
    return result if math.isfinite(result) and 0 <= result <= 100 else None


def unknown_account(provider: str, status: str, message: str) -> AccountStatus:
    names = ("weekly",) if provider in ("codex", "grok") else (
        ("monthly", *_CURSOR_BUCKETS) if provider == "cursor" else ())
    return AccountStatus(provider, PROVIDERS.get(provider, "DeepSeek"), status, None,
                         tuple(QuotaBucket(name, None, None) for name in names), message=message)


def _quota(name: str, row: object, *, parent_reset: object = None) -> QuotaBucket:
    row = row if isinstance(row, dict) else {}
    return QuotaBucket(name, _percent(row.get("usedPercent")),
                       positive_seconds(row.get("resetsAt", parent_reset)))


def _parse_provider(provider: str, row: object, now: float, max_age: float) -> AccountStatus:
    if not isinstance(row, dict):
        return unknown_account(provider, "unavailable", "Orca 缓存未提供此账号额度")
    if row.get("status") == "unavailable":
        # Server diagnostics may contain account identifiers/credentials. Only
        # retain the documented status, not its arbitrary error text.
        return AccountStatus(provider, PROVIDERS[provider], "unavailable",
                             positive_seconds(row.get("updatedAt")),
                             unknown_account(provider, "unavailable", "").buckets,
                             message="Orca 缓存报告额度不可用")
    if row.get("status") != "ok":
        return unknown_account(provider, "error", "Orca 缓存状态无法识别")
    updated = positive_seconds(row.get("updatedAt"))
    if provider in ("codex", "grok"):
        buckets = (_quota("weekly", row.get("weekly")),)
    elif provider == "cursor":
        monthly = row.get("monthly")
        nested = isinstance(monthly, dict) and "buckets" in monthly
        raw_buckets = monthly.get("buckets") if nested else row.get("buckets")
        rows = {}
        if isinstance(raw_buckets, list):
            for item in raw_buckets:
                if isinstance(item, dict) and item.get("name") in _CURSOR_BUCKETS:
                    name = item["name"]
                    # Duplicate known bucket names are ambiguous, not a sum.
                    rows[name] = None if name in rows else item
        reset = monthly.get("resetsAt") if nested else None
        buckets = (_quota("monthly", monthly), *(
            _quota(name, rows.get(name), parent_reset=reset) for name in _CURSOR_BUCKETS))
    else:
        return unknown_account(provider, "unavailable", "Orca 未提供可识别额度窗口")
    if updated is None or any(b.used_percent is None or b.resets_at is None for b in buckets):
        state, message = "unavailable", "Orca 额度字段不完整；未知值未填充"
    elif now - updated > max_age or any(b.resets_at <= now for b in buckets):
        state, message = "stale", "Orca 缓存已过期；保留上次观测，等待刷新"
    else:
        state, message = "ok", "Orca 账号缓存观测；非厂商即时结算"
    return AccountStatus(provider, PROVIDERS[provider], state, updated, buckets, message=message)


class OrcaAccountSource:
    """command is an executable or argv prefix; account list --json is appended.

    No shell is used. Resolution/execution happens in fetch, never on GUI setup.
    timeout bounds the CLI; max_age is the accepted cache age in seconds.
    """

    def __init__(self, command=None, *, timeout: float = 5.0, max_age: float = 900.0):
        if not math.isfinite(timeout) or timeout <= 0 or not math.isfinite(max_age) or max_age <= 0:
            raise ValueError("source timeouts and cache age must be finite and positive")
        self.command = command
        self.timeout = timeout
        self.max_age = max_age

    def _argv(self) -> list[str]:
        command = self.command
        if command is None:
            command = os.environ.get("ORCA_CLI_COMMAND") or (
                "orca-dev" if os.environ.get("ORCA_DEV_REPO_ROOT") else
                "orca-ide" if sys.platform.startswith("linux") and not os.environ.get("ORCA_TERMINAL_ID")
                else "orca")
        if isinstance(command, (str, Path)):
            command = [str(command)]
        if not command or not all(isinstance(part, str) and part for part in command):
            raise ValueError("invalid CLI command")
        return [*command, "account", "list", "--json"]

    def fetch(self) -> tuple[AccountStatus, ...]:
        try:
            completed = subprocess.run(self._argv(), shell=False, capture_output=True,
                                       timeout=self.timeout,
                                       creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            if completed.returncode != 0:
                return self._error("Orca 额度 CLI 执行失败")
            # Binary capture avoids the Windows ACP and replacement characters.
            payload = json.loads(completed.stdout.decode("utf-8-sig"))
            if not isinstance(payload, dict) or payload.get("ok") is False:
                return self._error("Orca 额度 CLI 报告失败")
            result = payload.get("result")
            rate_limits = result.get("rateLimits") if isinstance(result, dict) else None
            rows = {}
            if isinstance(rate_limits, list):
                for row in rate_limits:
                    if isinstance(row, dict) and row.get("provider") in PROVIDERS:
                        provider = row["provider"]
                        if provider in rows:
                            return self._error("Orca 额度包含重复 provider")
                        rows[provider] = row
            elif isinstance(rate_limits, dict):
                rows = {provider: rate_limits.get(provider) for provider in PROVIDERS}
            else:
                return self._error("Orca 额度响应缺少 rateLimits")
            now = time.time()
            return tuple(_parse_provider(p, rows.get(p), now, self.max_age) for p in PROVIDERS)
        except subprocess.TimeoutExpired:
            return self._error("Orca 额度 CLI 查询超时")
        except (UnicodeError, json.JSONDecodeError):
            return self._error("Orca 额度响应不是合法 UTF-8 JSON")
        except Exception:
            # Do not forward command argv, stdout/stderr, account errors or exception text.
            return self._error("Orca 额度 CLI 不可用")

    @staticmethod
    def _error(message: str) -> tuple[AccountStatus, ...]:
        return tuple(unknown_account(p, "error", message) for p in PROVIDERS)


def _money(row: object) -> MoneyBalance:
    if not isinstance(row, dict):
        raise ValueError("invalid balance row")
    currency = row.get("currency")
    if not isinstance(currency, str) or not currency.isascii() or len(currency) != 3 or not currency.isalpha():
        raise ValueError("invalid currency")
    amounts = []
    for name in ("total_balance", "granted_balance", "topped_up_balance"):
        value = row.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError("missing string amount")
        amount = Decimal(value)
        if not amount.is_finite() or amount < 0:
            raise ValueError("invalid amount")
        amounts.append(amount)
    return MoneyBalance(currency.upper(), *amounts)


class DeepSeekBalanceSource:
    """Explicit key only, official read-only GET, no environment discovery."""

    def __init__(self, api_key: str = "", *, timeout: float = 5.0):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("balance timeout must be finite and positive")
        self._api_key = api_key.strip()
        self.timeout = timeout

    def fetch(self) -> AccountStatus:
        if not self._api_key:
            return unknown_account("deepseek", "unconfigured", "未配置 DeepSeek API key")
        try:
            # Disable inherited proxy credentials and redirects; never send the
            # bearer token to another endpoint or create a model request.
            with httpx.Client(timeout=self.timeout, trust_env=False, follow_redirects=False) as client:
                response = client.get(BALANCE_URL, headers={"Authorization": f"Bearer {self._api_key}"})
            if response.status_code != 200:
                return unknown_account("deepseek", "error", f"DeepSeek 余额查询 HTTP {response.status_code}")
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("is_available"), bool):
                raise ValueError("missing availability")
            rows = payload.get("balance_infos")
            if not isinstance(rows, list) or not rows:
                raise ValueError("missing balances")
            balances = tuple(_money(row) for row in rows)
            if len({b.currency for b in balances}) != len(balances):
                raise ValueError("duplicate currency")
            available = payload["is_available"]
            return AccountStatus("deepseek", "DeepSeek", "ok" if available else "unavailable",
                                 time.time(), balances=balances,
                                 message="官方余额观测" if available else "官方报告余额不可用 (is_available=false)")
        except httpx.TimeoutException:
            return unknown_account("deepseek", "error", "DeepSeek 余额查询超时")
        except (ValueError, InvalidOperation):
            return unknown_account("deepseek", "error", "DeepSeek 余额响应字段缺失或金额不合法")
        except Exception:
            return unknown_account("deepseek", "error", "DeepSeek 余额查询失败")

