"""MCP 客户端协议测试（离线，用 httpx.MockTransport 伪造传输层）。

覆盖：initialize / session 回带 / tools/list / tools/call、
SSE 流解析、401 直接失败、429 退避重试。
"""

import json

import httpx
import pytest

from src.mcd_mcp.client import MCP_PROTOCOL_VERSION, McdMcpClient, McpError

SESSION = "sess-test-001"


def _jsonrpc_response(request_id, result):
    return httpx.Response(
        200,
        json={"jsonrpc": "2.0", "id": request_id, "result": result},
        headers={"content-type": "application/json", "mcp-session-id": SESSION},
    )


def _sse_response(request_id, result):
    payload = json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}, ensure_ascii=False)
    return httpx.Response(
        200,
        text=f"event: message\ndata: {payload}\n\n",
        headers={"content-type": "text/event-stream", "mcp-session-id": SESSION},
    )


def _make_client(handler):
    """包一层：JSON-RPC 通知（无 id）直接回 202，不打扰各个 handler。"""

    def wrapped(request: httpx.Request):
        body = json.loads(request.content)
        if "id" not in body:
            return httpx.Response(202, text="")
        return handler(request)

    client = McdMcpClient("test-token", "https://example.invalid/mcp")
    # 保留真实客户端的默认头（Authorization / Accept），只替换传输层
    client._http = httpx.Client(
        transport=httpx.MockTransport(wrapped), headers=dict(client._http.headers)
    )
    return client


def test_initialize_captures_session_id():
    seen = {}

    def handler(request: httpx.Request):
        body = json.loads(request.content)
        seen["method"] = body["method"]
        seen["protocol"] = request.headers.get("MCP-Protocol-Version")
        seen["accept"] = request.headers.get("Accept")
        return _jsonrpc_response(body["id"], {"serverInfo": {"name": "mcd"}, "protocolVersion": MCP_PROTOCOL_VERSION})

    with _make_client(handler) as client:
        client.initialize()

    assert seen["method"] == "initialize"
    assert seen["protocol"] == MCP_PROTOCOL_VERSION
    assert "text/event-stream" in seen["accept"]
    assert client.session_id == SESSION


def test_session_id_is_sent_back():
    seen_headers = []

    def handler(request: httpx.Request):
        body = json.loads(request.content)
        if body["method"] == "notifications/initialized":
            return httpx.Response(202, text="")
        seen_headers.append(request.headers.get("mcp-session-id"))
        return _jsonrpc_response(body["id"], {"tools": []})

    with _make_client(handler) as client:
        client.initialize()
        client.list_tools()

    assert seen_headers and seen_headers[-1] == SESSION


def test_list_tools_parses_schema():
    def handler(request: httpx.Request):
        body = json.loads(request.content)
        if body["method"] == "notifications/initialized":
            return httpx.Response(202, text="")
        return _jsonrpc_response(
            body["id"],
            {
                "tools": [
                    {
                        "name": "available-coupons",
                        "description": "麦麦省券列表查询",
                        "inputSchema": {"type": "object", "properties": {"page": {}}, "required": []},
                    }
                ]
            },
        )

    with _make_client(handler) as client:
        tools = client.list_tools()

    assert len(tools) == 1
    assert tools[0].name == "available-coupons"
    assert tools[0].arg_names == ["page"]


def test_call_tool_parses_json_text():
    def handler(request: httpx.Request):
        body = json.loads(request.content)
        if body["method"] == "notifications/initialized":
            return httpx.Response(202, text="")
        if body["method"] == "tools/call":
            assert body["params"]["name"] == "now-time-info"
            return _jsonrpc_response(
                body["id"],
                {"content": [{"type": "text", "text": '{"date":"2026-10-10"}'}], "isError": False},
            )
        return _jsonrpc_response(body["id"], {})

    with _make_client(handler) as client:
        result = client.call_tool("now-time-info")

    assert result.data == {"date": "2026-10-10"}
    assert result.is_error is False


def test_call_tool_handles_sse_stream():
    def handler(request: httpx.Request):
        body = json.loads(request.content)
        if body["method"] == "notifications/initialized":
            return httpx.Response(202, text="")
        return _sse_response(body["id"], {"content": [{"type": "text", "text": "ok"}], "isError": False})

    with _make_client(handler) as client:
        result = client.call_tool("available-coupons")

    assert result.text == "ok"


def test_tool_result_as_list_is_tolerant():
    def handler(request: httpx.Request):
        body = json.loads(request.content)
        if body["method"] == "notifications/initialized":
            return httpx.Response(202, text="")
        return _jsonrpc_response(
            body["id"], {"content": [{"type": "text", "text": '{"items":[{"a":1},{"a":2}]}'}]}
        )

    with _make_client(handler) as client:
        result = client.call_tool("query-my-coupons")

    assert result.as_list() == [{"a": 1}, {"a": 2}]


def test_401_raises_without_retry():
    calls = []

    def handler(request: httpx.Request):
        calls.append(1)
        return httpx.Response(401, text="unauthorized")

    with _make_client(handler) as client:
        with pytest.raises(McpError) as excinfo:
            client.initialize()

    assert excinfo.value.http_status == 401
    assert len(calls) == 1, "401 不该重试"


def test_429_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    state = {"n": 0}

    def handler(request: httpx.Request):
        body = json.loads(request.content)
        state["n"] += 1
        if state["n"] == 1:
            return httpx.Response(429, text="too many", headers={"Retry-After": "1"})
        return _jsonrpc_response(body["id"], {"serverInfo": {}})

    with _make_client(handler) as client:
        client.initialize()

    assert state["n"] == 2


def test_429_gives_up_after_max_retries(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)

    def handler(request: httpx.Request):
        return httpx.Response(429, text="too many")

    client = _make_client(handler)
    client._max_retries = 2
    with client:
        with pytest.raises(McpError) as excinfo:
            client.initialize()
    assert excinfo.value.http_status == 429


def test_missing_token_refuses_to_construct():
    with pytest.raises(McpError):
        McdMcpClient("")
