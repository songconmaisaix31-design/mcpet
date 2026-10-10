import pytest

from src.mcd_mcp.guards import GuardLimits, GuardViolation, OrderAuditEntry, OrderGuard, to_cents


@pytest.fixture()
def guard(tmp_path):
    return OrderGuard(GuardLimits(max_amount_cents=5_000, max_orders_per_day=2), tmp_path / "audit.json")


def test_amount_over_limit_rejected(guard):
    with pytest.raises(GuardViolation) as excinfo:
        guard.check(6_000)
    assert "上限" in str(excinfo.value)


def test_zero_amount_rejected(guard):
    with pytest.raises(GuardViolation):
        guard.check(0)


def test_daily_limit_rejected(guard):
    for _ in range(2):
        guard.check(1_000)
        guard.record(OrderAuditEntry(created_at="2026-10-10T11:30:00", tool="create-order",
                                     store="某店", items="巨无霸", amount_cents=1_000, status="placed"))
    with pytest.raises(GuardViolation) as excinfo:
        guard.check(1_000)
    assert "今日已下单" in str(excinfo.value)


def test_dry_run_entries_do_not_count_against_daily_limit(guard):
    guard.record(OrderAuditEntry(created_at="2026-10-10T11:30:00", tool="create-order",
                                 store="某店", items="巨无霸", amount_cents=1_000,
                                 dry_run=True, status="dry_run_skipped"))
    guard.check(1_000)  # 演练不占额度，不应抛


def test_audit_is_persisted_and_reloadable(guard):
    guard.record(OrderAuditEntry(created_at="2026-10-10T12:00:00", tool="create-order",
                                 store="某店", items="薯条", amount_cents=900,
                                 order_no="NO-1", status="placed"))
    reloaded = OrderGuard(GuardLimits(), guard.audit_path)
    assert len(reloaded.entries) == 1
    assert reloaded.entries[0].order_no == "NO-1"


def test_mark_cancelled(guard):
    guard.record(OrderAuditEntry(created_at="2026-10-10T12:00:00", tool="create-order",
                                 store="某店", items="薯条", amount_cents=900,
                                 order_no="NO-2", status="placed"))
    assert guard.mark_cancelled("NO-2") is True
    assert guard.entries[0].status == "cancelled"
    assert guard.mark_cancelled("NO-404") is False


def test_to_cents_assumes_yuan():
    assert to_cents(25.9) == 2590
    assert to_cents("25.9") == 2590
    assert to_cents("¥25.9") == 2590
    assert to_cents(None) == 0
    assert to_cents("不是数字") == 0
