"""Immutable presentation contracts. All timestamps are Unix seconds."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class QuotaBucket:
    name: str
    used_percent: float | None
    resets_at: float | None


@dataclass(frozen=True)
class MoneyBalance:
    currency: str
    total: Decimal
    granted: Decimal
    topped_up: Decimal


@dataclass(frozen=True)
class AccountStatus:
    provider: str
    label: str
    status: str
    updated_at: float | None
    buckets: tuple[QuotaBucket, ...] = ()
    balances: tuple[MoneyBalance, ...] = ()
    message: str = ""


@dataclass(frozen=True)
class AccountSnapshot:
    accounts: tuple[AccountStatus, ...]
    observed_at: float

