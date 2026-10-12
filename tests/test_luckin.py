"""Official documented envelopes and isolated fixtures; no account order/payment."""
import copy
import json
import pytest
import httpx

from src import config
from src.luckin import LuckinService, LuckinClient, READ_TOOLS, amount_cents
from src.mcd_mcp.client import Tool, ToolResult, McpError


def schema(properties, required):
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


PRODUCT = {"productId": 9, "skuCode": "fixture-hot", "productName": "夹具咖啡"}
PREVIEW = {"discountPrice": 16, "shopInfo": {"deptId": 7, "deptName": "夹具门店"}, "couponCodeList": [],
           "productInfoList": [{"productId": 9, "skuCode": "fixture-hot", "name": "夹具咖啡", "amount": 1, "additionDesc": "热"}]}
ORDER_ARGS = {"deptId": {"type": "integer"}, "productList": {"type": "array", "minItems": 1, "items": schema(
    {"productId": {"type": "integer"}, "skuCode": {"type": "string"}, "amount": {"type": "integer", "minimum": 1}}, ["productId", "skuCode", "amount"])}}


class Upstream:
    def __init__(self):
        self.calls = []
        self.preview = copy.deepcopy(PREVIEW)
        self.error = None
        self.result = {"orderIdStr": "fixture-very-long-id", "payOrderUrl": "https://example.invalid/pay"}
        self.closed = 0
    def __enter__(self): return self
    def __exit__(self, *args): self.closed += 1
    def ensure_initialized(self): pass
    def list_tools(self):
        return [Tool("searchProductForMcp", input_schema=schema({"deptId": {"type": "integer"}, "query": {"type": "string"}}, ["deptId", "query"])),
                Tool("previewOrder", input_schema=schema(ORDER_ARGS, list(ORDER_ARGS))),
                Tool("createOrder", input_schema=schema({**ORDER_ARGS, "longitude": {"type": "number"}, "latitude": {"type": "number"},
                                                        "couponCodeList": {"type": "array", "items": {"type": "string"}}}, list(ORDER_ARGS) + ["longitude", "latitude"])),
                Tool("cancelOrder", input_schema=schema({"orderId": {"type": "string"}}, ["orderId"]))]
    def call_tool(self, name, arguments):
        self.calls.append((name, copy.deepcopy(arguments)))
        if name in {"createOrder", "cancelOrder"} and self.error:
            raise self.error
        node = {"searchProductForMcp": [PRODUCT], "previewOrder": self.preview, "createOrder": self.result, "cancelOrder": True}[name]
        return ToolResult(name, {}, "", {"code": 0, "success": True, "data": copy.deepcopy(node)})


@pytest.fixture
def coffee(tmp_path, monkeypatch):
    monkeypatch.setenv("MCPET_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LUCKIN_MCP_TOKEN", "fixture-luckin-secret")
    monkeypatch.setattr(config, "load_env", lambda: None)
    upstream = Upstream()
    service = LuckinService(lambda: upstream)
    service.query("searchProductForMcp", {"deptId": 7, "query": "拿铁"})
    return service, upstream


def prepare(service):
    return service.prepare(7, [{"productId": 9, "skuCode": "fixture-hot", "amount": 1}], 116.4, 39.9)


def test_yuan_integer_is_not_mcd_cents():
    assert amount_cents({"discountPrice": 16}) == 1600
    assert amount_cents({"discountPrice": "9.90"}) == 990


@pytest.mark.parametrize("value", [None, True, "nan", "Infinity", -1, 0, "1.001"])
def test_missing_or_invalid_price_is_not_zero(value):
    with pytest.raises(McpError): amount_cents({"discountPrice": value})


def test_read_allowlist_and_runtime_schema_fail_before_call(coffee):
    service, upstream = coffee
    with pytest.raises(ValueError): service.query("createOrder", {})
    with pytest.raises(ValueError): service.query("searchProductForMcp", {"deptId": 7})
    assert len(upstream.calls) == 1


def test_confirmation_price_and_official_coupon_payload(coffee):
    service, upstream = coffee
    result = prepare(service)
    assert result["amount_cents"] == 1600 and "夹具门店" in result["summary"] and "热" in result["summary"]
    assert service.confirm()["status"] == "needs_confirmation"
    assert not any(c[0] == "createOrder" for c in upstream.calls)
    result = service.confirm(True)
    assert result["status"] == "placed" and result["order_id"] == "fixture-very-long-id"
    assert [n for n, _ in upstream.calls].count("createOrder") == 1
    assert service.guard.entries[-1].amount_cents == 1600
    with pytest.raises(McpError): service.confirm(True)


@pytest.mark.parametrize("field", ["price", "coupon", "spec", "account", "expiry"])
def test_mutation_demands_fresh_preview(coffee, monkeypatch, field):
    service, upstream = coffee
    prepare(service)
    if field == "price": upstream.preview["discountPrice"] = 17
    if field == "coupon": upstream.preview["couponCodeList"] = ["different"]
    if field == "spec": upstream.preview["productInfoList"][0]["additionDesc"] = "冰"
    if field == "account": monkeypatch.setenv("LUCKIN_MCP_TOKEN", "other-fixture-secret")
    if field == "expiry": service.pending["at"] -= 301
    with pytest.raises(McpError): service.confirm(True)
    assert service.pending is None and not any(c[0] == "createOrder" for c in upstream.calls)


@pytest.mark.parametrize("failure", ["network", "missing-id", "unknown-format"])
def test_delivery_unknown_consumed_and_persisted_no_replay(coffee, failure):
    service, upstream = coffee
    prepare(service)
    if failure == "network": upstream.error = OSError("submit disconnected")
    if failure == "missing-id": upstream.result = {}
    if failure == "unknown-format": upstream.result = []
    assert service.confirm(True)["status"] == "delivery_unknown"
    assert service.guard.entries[-1].status == "delivery_unknown"
    with pytest.raises(McpError): prepare(service)
    restarted = LuckinService(lambda: upstream)
    restarted.selections = service.selections.copy()
    with pytest.raises(McpError): prepare(restarted)
    assert [n for n, _ in upstream.calls].count("createOrder") == 1


def test_invented_selection_and_daily_guard_rejected(coffee):
    service, upstream = coffee
    with pytest.raises(McpError): service.prepare(7, [{"productId": 99, "skuCode": "invented", "amount": 1}], 0, 0)
    service.guard.limits.max_amount_cents = 1000
    with pytest.raises(RuntimeError): prepare(service)
    assert not any(c[0] == "createOrder" for c in upstream.calls)


def test_cancel_confirmation_unknown_never_resent(coffee):
    service, upstream = coffee
    assert service.cancel("fixture-order")["status"] == "needs_confirmation"
    upstream.error = OSError("cancel disconnected")
    assert service.cancel("fixture-order", True)["status"] == "delivery_unknown"
    with pytest.raises(McpError): service.cancel("fixture-order", True)
    with pytest.raises(McpError): LuckinService(lambda: upstream).cancel("fixture-order", True)
    assert [n for n, _ in upstream.calls].count("cancelOrder") == 1


def test_http_official_endpoint_bearer_session_no_retry(coffee):
    service, _ = coffee
    client = LuckinClient("fixture-luckin-secret")
    seen = []
    def handle(request):
        assert str(request.url) == config.LUCKIN_MCP_URL
        assert request.headers["Authorization"] == "Bearer fixture-luckin-secret"
        payload = json.loads(request.content)
        seen.append(payload["method"])
        if len(seen) > 1: assert request.headers["mcp-session-id"] == "fixture-session"
        result = {"tools": []} if payload["method"] == "tools/list" else {"protocolVersion": "2025-06-18", "capabilities": {}, "serverInfo": {"name": "fixture", "version": "1"}}
        return httpx.Response(200, headers={"mcp-session-id": "fixture-session"}, json={"jsonrpc": "2.0", "id": payload.get("id"), "result": result})
    client._http.close()
    client._http = httpx.Client(transport=httpx.MockTransport(handle), headers={"Authorization": "Bearer fixture-luckin-secret"})
    assert client.list_tools() == []
    assert seen == ["initialize", "notifications/initialized", "tools/list"]
    seen.clear()
    client._http.close()
    client._http = httpx.Client(transport=httpx.MockTransport(lambda r: seen.append(r) or httpx.Response(429)))
    with pytest.raises(McpError, match="未自动重试"): client.list_tools()
    assert len(seen) == 1
    client.close()


def test_config_and_errors_do_not_expose_luckin_secret(coffee):
    assert config.redact("fixture-luckin-secret") == "***"


def test_cross_host_fresh_audit_enforces_shared_daily_limit(coffee):
    service, upstream = coffee
    service.guard.limits.max_orders_per_day = 1
    other = LuckinService(lambda: upstream)
    other.guard.limits.max_orders_per_day = 1
    other.query("searchProductForMcp", {"deptId": 7, "query": "拿铁"})
    prepare(service)
    prepare(other)
    assert service.confirm(True)["status"] == "placed"
    with pytest.raises(RuntimeError, match="今日已下单"):
        other.confirm(True)
    assert [n for n, _ in upstream.calls].count("createOrder") == 1


def test_preview_must_match_selected_sku_quantity(coffee):
    service, upstream = coffee
    upstream.preview["productInfoList"][0]["amount"] = 2
    with pytest.raises(McpError, match="不一致"):
        prepare(service)
    assert service.pending is None
