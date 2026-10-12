"""Account contracts only: fixture CLI output and mocked official balance GET."""

from dataclasses import FrozenInstanceError
from decimal import Decimal
import json
import subprocess
import sys
import time

import httpx
import pytest

from src.accounts import (
    AccountSnapshot, AccountStatus, DeepSeekBalanceSource, MoneyBalance,
    OrcaAccountSource, QuotaBucket,
)


def orca_payload(now=None):
    now = now or time.time()
    return {"ok": True, "result": {"accounts": [{"secret": "DO_NOT_COPY"}],
            "rateLimits": [
                {"provider": "codex", "status": "ok", "updatedAt": now * 1000,
                 "weekly": {"usedPercent": 16, "windowMinutes": 10080,
                            "resetsAt": (now + 3600) * 1000}},
                {"provider": "grok", "status": "ok", "updatedAt": now * 1000,
                 "weekly": {"usedPercent": 0, "resetsAt": (now + 600) * 1000}},
                {"provider": "cursor", "status": "ok", "updatedAt": now * 1000,
                 "monthly": {"usedPercent": 41, "resetsAt": (now + 5000) * 1000},
                 "buckets": [{"name": "Cursor Models", "usedPercent": 10,
                              "resetsAt": (now + 1000) * 1000},
                             {"name": "Other Models", "usedPercent": 70,
                              "resetsAt": (now + 2000) * 1000}]},
                {"provider": "claude", "status": "unavailable", "updatedAt": now * 1000,
                 "error": "DO_NOT_COPY"},
                {"provider": "unknown", "status": "ok", "apiKey": "DO_NOT_COPY"},
            ]}}


def cli_result(monkeypatch, payload):
    calls = []

    def run(argv, **options):
        calls.append((argv, options))
        return subprocess.CompletedProcess(argv, 0, json.dumps(payload, ensure_ascii=False).encode(), b"")

    monkeypatch.setattr(subprocess, "run", run)
    source = OrcaAccountSource(command=[sys.executable, "fixture_cli.py"], timeout=0.25)
    return source.fetch(), calls


def test_frozen_public_contract_and_decimal():
    bucket = QuotaBucket("weekly", None, None)
    money = MoneyBalance("CNY", Decimal("1.00000000000000001"), Decimal("0"), Decimal("1"))
    status = AccountStatus("deepseek", "DeepSeek", "ok", 10, balances=(money,))
    snapshot = AccountSnapshot((status,), 10)
    with pytest.raises(FrozenInstanceError):
        bucket.used_percent = 0
    assert snapshot.accounts[0].buckets == ()
    assert snapshot.accounts[0].balances[0].total == Decimal("1.00000000000000001")


def test_orca_whitelist_seconds_and_independent_cursor_buckets(monkeypatch):
    # Whole seconds give an exact millisecond wire fixture. Arbitrary wall-clock
    # fractions can round on *1000 /1000 and fail the unchanged equality below.
    now = float(int(time.time()))
    accounts, calls = cli_result(monkeypatch, orca_payload(now))
    assert [a.provider for a in accounts] == ["codex", "grok", "cursor", "claude"]
    codex, grok, cursor, claude = accounts
    assert codex.status == "ok"
    assert codex.updated_at == pytest.approx(now)
    assert codex.buckets == (QuotaBucket("weekly", 16, now + 3600),)
    assert grok.buckets[0].used_percent == 0
    assert [b.name for b in cursor.buckets] == ["monthly", "Cursor Models", "Other Models"]
    assert [b.used_percent for b in cursor.buckets] == [41, 10, 70]
    assert [b.resets_at for b in cursor.buckets] == pytest.approx([now + 5000, now + 1000, now + 2000])
    assert claude.status == "unavailable"
    assert "DO_NOT_COPY" not in repr(accounts)
    argv, options = calls[0]
    assert argv == [sys.executable, "fixture_cli.py", "account", "list", "--json"]
    assert options["shell"] is False
    assert options["timeout"] == 0.25


@pytest.mark.parametrize("provider", ["codex", "grok", "claude"])
def test_session_and_weekly_real_fields_are_independent_for_known_providers(monkeypatch, provider):
    now = int(time.time()) + 0.125  # Fresh, exact binary fraction; ms->s fixture roundtrip is exact.
    row = {"provider": provider, "status": "ok", "updatedAt": now * 1000,
           "session": {"usedPercent": 7.5, "windowMinutes": 300,
                       "resetsAt": (now + 300) * 1000, "resetDescription": "fixture 5h"},
           "weekly": {"usedPercent": 48, "windowMinutes": 10080,
                      "resetsAt": (now + 8000) * 1000, "resetDescription": "fixture weekly"},
           "daily": {"usedPercent": 99, "resetsAt": (now + 600) * 1000}}
    accounts, _ = cli_result(monkeypatch, {"result": {"rateLimits": [row]}})
    account = next(a for a in accounts if a.provider == provider)
    assert account.status == "ok"
    assert account.buckets == (QuotaBucket("session", 7.5, now + 300),
                               QuotaBucket("weekly", 48, now + 8000))
    assert len(accounts) == 4  # no new providers or undocumented daily window


@pytest.mark.parametrize("provider", ["codex", "grok", "claude"])
def test_session_only_keeps_only_the_observed_window(monkeypatch, provider):
    now = time.time()
    row = {"provider": provider, "status": "ok", "updatedAt": now * 1000,
           "session": {"usedPercent": 0, "windowMinutes": 300, "resetsAt": (now + 300) * 1000}}
    accounts, _ = cli_result(monkeypatch, {"result": {"rateLimits": [row]}})
    account = next(a for a in accounts if a.provider == provider)
    assert account.status == "ok"
    assert account.buckets == (QuotaBucket("session", 0, now + 300),)


def test_claude_weekly_without_session_does_not_invent_session(monkeypatch):
    now = time.time()
    row = {"provider": "claude", "status": "ok", "updatedAt": now * 1000,
           "weekly": {"usedPercent": 33, "resetsAt": (now + 600) * 1000}}
    accounts, _ = cli_result(monkeypatch, {"result": {"rateLimits": [row]}})
    account = accounts[-1]
    assert account.status == "ok"
    assert account.buckets == (QuotaBucket("weekly", 33, now + 600),)


@pytest.mark.parametrize("provider", ["codex", "grok", "claude"])
def test_null_session_with_valid_weekly_keeps_only_weekly(monkeypatch, provider):
    now = int(time.time())
    row = {"provider": provider, "status": "ok", "updatedAt": now * 1000,
           "session": None,
           "weekly": {"usedPercent": 33, "windowMinutes": 10080,
                      "resetsAt": (now + 600) * 1000}}
    accounts, _ = cli_result(monkeypatch, {"result": {"rateLimits": [row]}})
    account = next(a for a in accounts if a.provider == provider)
    assert account.status == "ok"
    assert account.buckets == (QuotaBucket("weekly", 33, now + 600),)


def test_invalid_session_is_unknown_without_erasing_valid_weekly(monkeypatch):
    payload = orca_payload()
    row = payload["result"]["rateLimits"][0]
    row["session"] = {"usedPercent": True, "resetsAt": -1, "windowMinutes": 300}
    accounts, _ = cli_result(monkeypatch, payload)
    account = accounts[0]
    assert account.status == "unavailable"
    assert account.buckets[0] == QuotaBucket("session", None, None)
    assert account.buckets[1].name == "weekly"
    assert account.buckets[1].used_percent == 16


@pytest.mark.parametrize("invalid", [None, True, False, -1, 101, "16", float("nan"), float("inf")])
def test_invalid_percent_is_unknown_never_zero(monkeypatch, invalid):
    payload = orca_payload()
    payload["result"]["rateLimits"][0]["weekly"]["usedPercent"] = invalid
    accounts, _ = cli_result(monkeypatch, payload)
    assert accounts[0].buckets[0].used_percent is None
    assert accounts[0].status != "ok"


def test_missing_provider_and_window_are_explicit_unknown(monkeypatch):
    payload = orca_payload()
    payload["result"]["rateLimits"] = [payload["result"]["rateLimits"][0]]
    payload["result"]["rateLimits"][0].pop("weekly")
    accounts, _ = cli_result(monkeypatch, payload)
    assert len(accounts) == 4
    assert all(a.status != "ok" for a in accounts)
    assert accounts[0].buckets == (QuotaBucket("weekly", None, None),)
    assert all(b.used_percent is None for a in accounts for b in a.buckets)


def test_stale_updated_and_expired_reset_are_not_fresh(monkeypatch):
    now = time.time()
    payload = orca_payload(now)
    payload["result"]["rateLimits"][0]["updatedAt"] = (now - 10000) * 1000
    payload["result"]["rateLimits"][1]["weekly"]["resetsAt"] = (now - 1) * 1000
    accounts, _ = cli_result(monkeypatch, payload)
    assert accounts[0].status == accounts[1].status == "stale"
    assert accounts[0].buckets[0].used_percent == 16  # retained with an honest stale label


def test_keyed_whitelisted_rate_limits_and_utf8_bom(monkeypatch):
    payload = orca_payload()
    rows = payload["result"]["rateLimits"]
    payload["result"]["rateLimits"] = {r["provider"]: r for r in rows}
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(
        a[0], 0, b"\xef\xbb\xbf" + json.dumps(payload, ensure_ascii=False).encode("utf-8"), b""))
    accounts = OrcaAccountSource(command=["fixture"]).fetch()
    assert accounts[2].buckets[1].name == "Cursor Models"


def test_nested_cursor_buckets_use_explicit_monthly_window_and_stay_separate(monkeypatch):
    payload = orca_payload()
    cursor = payload["result"]["rateLimits"][2]
    cursor["monthly"]["buckets"] = cursor.pop("buckets")
    for bucket in cursor["monthly"]["buckets"]:
        bucket.pop("resetsAt")
    accounts, _ = cli_result(monkeypatch, payload)
    buckets = accounts[2].buckets
    assert [b.used_percent for b in buckets] == [41, 10, 70]
    assert all(b.resets_at == buckets[0].resets_at for b in buckets)


@pytest.mark.parametrize("value", [None, True, -100, "123", float("nan"), float("inf")])
def test_invalid_timestamp_stays_unknown(monkeypatch, value):
    payload = orca_payload()
    payload["result"]["rateLimits"][0]["updatedAt"] = value
    payload["result"]["rateLimits"][0]["weekly"]["resetsAt"] = value
    accounts, _ = cli_result(monkeypatch, payload)
    assert accounts[0].updated_at is None
    assert accounts[0].buckets[0].resets_at is None
    assert accounts[0].status == "unavailable"


def test_real_windows_utf8_fixture_cli_and_finite_timeout(tmp_path):
    # Run the correct Python as a fake CLI, not the real account executable.
    script = tmp_path / "fixture cli 中文.py"
    payload = orca_payload()
    payload["result"]["rateLimits"][0]["ignored"] = "中文，令牌不复制"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    script.write_text("import sys\nassert sys.argv[1:] == ['account', 'list', '--json']\n"
                      f"sys.stdout.buffer.write({body!r})\n", encoding="utf-8")
    accounts = OrcaAccountSource(command=[sys.executable, str(script)]).fetch()
    assert accounts[0].status == "ok"
    assert accounts[0].buckets[0].used_percent == 16
    assert "令牌" not in repr(accounts)
    script.write_text("import time\ntime.sleep(10)\n", encoding="utf-8")
    started = time.monotonic()
    accounts = OrcaAccountSource(command=[sys.executable, str(script)], timeout=0.1).fetch()
    # Windows CreateProcess cannot itself be interrupted by subprocess timeout;
    # the separate monitor tests enforce the GUI and post-stop cleanup budgets.
    assert time.monotonic() - started < 5
    assert all(a.status == "error" and "超时" in a.message for a in accounts)


@pytest.mark.parametrize("case", ["timeout", "nonzero", "json", "shape", "encoding", "missing"])
def test_cli_failures_are_sanitized_unknown(monkeypatch, case):
    def run(*args, **kwargs):
        if case == "timeout":
            raise subprocess.TimeoutExpired(args[0], 0.1, output=b"SECRET")
        if case == "missing":
            raise FileNotFoundError("SECRET")
        body = {"json": b"SECRET", "shape": b'{"result": {"accounts": []}}',
                "encoding": b"\xff", "nonzero": b"SECRET"}[case]
        return subprocess.CompletedProcess(args[0], 1 if case == "nonzero" else 0, body, b"SECRET")
    monkeypatch.setattr(subprocess, "run", run)
    accounts = OrcaAccountSource(command=["fixture"]).fetch()
    assert len(accounts) == 4
    assert all(a.status == "error" for a in accounts)
    assert all(b.used_percent is None for a in accounts for b in a.buckets)
    assert "SECRET" not in repr(accounts)


def balance_payload(**updates):
    row = dict(currency="CNY", total_balance="1.00000000000000001",
               granted_balance="0.00000000000000001", topped_up_balance="1")
    row.update(updates)
    return {"is_available": True, "balance_infos": [row]}


def mock_balance(monkeypatch, payload=None, code=200, error=None):
    requests = []

    def handle(request):
        requests.append(request)
        if error:
            raise error
        return httpx.Response(code, json=payload)

    client_type = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **options: client_type(
        **options, transport=httpx.MockTransport(handle)))
    return requests


def test_deepseek_missing_key_never_calls_network(monkeypatch):
    monkeypatch.setattr(httpx, "Client", lambda **k: pytest.fail("unconfigured must not connect"))
    assert DeepSeekBalanceSource().fetch().status == "unconfigured"
    assert DeepSeekBalanceSource("  ").fetch().balances == ()


def test_deepseek_official_get_precision_and_multiple_currencies(monkeypatch):
    payload = balance_payload()
    payload["balance_infos"].append(dict(currency="USD", total_balance="0.25",
                                        granted_balance="0.10", topped_up_balance="0.15"))
    requests = mock_balance(monkeypatch, payload)
    source = DeepSeekBalanceSource("fixture-secret")
    account = source.fetch()
    assert account.status == "ok"
    assert account.buckets == ()
    assert len(account.balances) == 2
    assert account.balances[0].total == Decimal("1.00000000000000001")
    assert account.balances[1].currency == "USD"
    assert requests[0].method == "GET"
    assert str(requests[0].url) == "https://api.deepseek.com/user/balance"
    assert requests[0].headers["Authorization"] == "Bearer fixture-secret"
    assert "fixture-secret" not in repr(source) + repr(account)


@pytest.mark.parametrize("invalid", [None, True, 0, -1, "-0.01", "NaN", "Infinity", "", "broken"])
def test_invalid_money_is_error_not_zero(monkeypatch, invalid):
    mock_balance(monkeypatch, balance_payload(total_balance=invalid))
    account = DeepSeekBalanceSource("fixture").fetch()
    assert account.status == "error"
    assert account.balances == ()


@pytest.mark.parametrize("payload", [
    {}, {"is_available": True}, {"is_available": True, "balance_infos": []},
    {"is_available": "yes", "balance_infos": []},
    balance_payload(currency=""), balance_payload(currency=True),
    {"is_available": True, "balance_infos": [{"currency": "CNY", "total_balance": "3"}]},
])
def test_incomplete_money_never_defaults_to_zero(monkeypatch, payload):
    mock_balance(monkeypatch, payload)
    account = DeepSeekBalanceSource("fixture").fetch()
    assert account.status == "error"
    assert not account.balances


def test_zero_balance_and_availability_are_distinct(monkeypatch):
    payload = balance_payload(total_balance="0", granted_balance="0", topped_up_balance="0")
    payload["is_available"] = False
    mock_balance(monkeypatch, payload)
    account = DeepSeekBalanceSource("fixture").fetch()
    assert account.status == "unavailable"
    assert account.balances[0].total == Decimal("0")
    assert not account.buckets


@pytest.mark.parametrize("code", [401, 403, 429, 500])
def test_http_errors_do_not_echo_body_or_credentials(monkeypatch, code):
    mock_balance(monkeypatch, {"secret": "fixture-secret"}, code)
    account = DeepSeekBalanceSource("fixture-secret").fetch()
    assert account.status == "error"
    assert str(code) in account.message
    assert "fixture-secret" not in account.message


def test_network_exception_is_sanitized(monkeypatch):
    mock_balance(monkeypatch, error=httpx.ReadTimeout("Bearer fixture-secret"))
    account = DeepSeekBalanceSource("fixture-secret").fetch()
    assert account.status == "error"
    assert "fixture-secret" not in account.message
