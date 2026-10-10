"""阶跃星辰客户端测试（离线，httpx.MockTransport）。"""

import json

import httpx
import pytest

from src.llm.stepfun import StepFunClient, StepFunError


def _make(handler, **kwargs):
    client = StepFunClient("test-key", **kwargs)
    # 保留真实客户端的默认头（Authorization），只替换传输层
    client._http = httpx.Client(
        transport=httpx.MockTransport(handler), headers=dict(client._http.headers)
    )
    return client


def test_chat_returns_text_and_usage():
    def handler(request: httpx.Request):
        assert request.headers["Authorization"] == "Bearer test-key"
        body = json.loads(request.content)
        assert body["model"] == "step-3.5-flash"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": "该吃饭了"}}],
                "usage": {"total_tokens": 42},
            },
        )

    with _make(handler) as client:
        reply = client.chat([{"role": "user", "content": "hi"}])

    assert reply.text == "该吃饭了"
    assert reply.usage == {"total_tokens": 42}
    assert not reply.wants_tools


def test_chat_parses_tool_calls():
    def handler(request: httpx.Request):
        body = json.loads(request.content)
        assert body["tools"][0]["function"]["name"] == "query-meals"
        assert body["tool_choice"] == "auto"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "query-meals",
                                        "arguments": '{"storeId": "S1"}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        )

    with _make(handler) as client:
        reply = client.chat(
            [{"role": "user", "content": "菜单"}],
            tools=[{"type": "function", "function": {"name": "query-meals", "parameters": {}}}],
        )

    assert reply.wants_tools
    assert reply.tool_calls[0].name == "query-meals"
    assert reply.tool_calls[0].arguments == {"storeId": "S1"}
    assert reply.tool_calls[0].id == "call_1"


def test_bad_arguments_json_degrades_gracefully():
    def handler(request: httpx.Request):
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {"id": "c", "function": {"name": "x", "arguments": "{坏掉的json"}}
                            ]
                        }
                    }
                ]
            },
        )

    with _make(handler) as client:
        reply = client.chat([{"role": "user", "content": "x"}])

    assert reply.tool_calls[0].arguments == {}


def test_models_filter_chat_only():
    def handler(request: httpx.Request):
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "step-3.5-flash", "model_type": "大语言模型", "supported_protocols": ["chat"]},
                    {"id": "step-tts-mini", "model_type": "语音合成"},
                    {"id": "step-asr", "model_type": "语音识别"},
                ]
            },
        )

    with _make(handler) as client:
        models = client.models()

    assert [m["id"] for m in models] == ["step-3.5-flash"]


def test_401_raises():
    with _make(lambda r: httpx.Response(401, text="bad key")) as client:
        with pytest.raises(StepFunError) as excinfo:
            client.chat([{"role": "user", "content": "x"}])
    assert excinfo.value.http_status == 401


def test_429_retries(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    state = {"n": 0}

    def handler(request: httpx.Request):
        state["n"] += 1
        if state["n"] == 1:
            return httpx.Response(429, text="slow down")
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    with _make(handler) as client:
        assert client.chat([{"role": "user", "content": "x"}]).text == "ok"
    assert state["n"] == 2


def test_missing_key_refuses_to_construct(monkeypatch):
    monkeypatch.delenv("STEPFUN_API_KEY", raising=False)
    with pytest.raises(StepFunError):
        StepFunClient("")
