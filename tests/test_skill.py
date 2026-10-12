"""Skill 层测试（离线）：假 MCP + 假大模型，验证调度与写操作闸门。"""

import pytest

from src.mcd_mcp.brain import McdBrain
from src.mcd_mcp.client import Tool, ToolResult
from src.mcd_mcp.guards import OrderGuard
from src.mcd_mcp.skill import WRITE_TOOLS, build_function_defs, run_skill
from src.llm.stepfun import ChatReply, ToolCall


class FakeMcpClient:
    def __init__(self, tools, results):
        self._tools = tools
        self._results = results
        self.calls: list[tuple[str, dict]] = []

    def list_tools(self):
        return self._tools

    def call_tool(self, name, arguments=None):
        self.calls.append((name, arguments or {}))
        raw = self._results.get(name)
        text = "" if raw is None else str(raw)
        return ToolResult(name=name, raw=raw or {}, text=text, data=raw, is_error=False)


class FakeLLM:
    """按脚本依次返回回复；记录每次收到的 tools 定义。"""

    def __init__(self, replies):
        self._replies = list(replies)
        self.seen_tool_defs: list[list[dict]] = []

    def chat(self, messages, tools=None, **kwargs):
        self.seen_tool_defs.append(tools or [])
        return self._replies.pop(0)


def _tools():
    return [
        Tool(name="available-coupons", description="可领券列表", input_schema={"type": "object", "properties": {}}),
        Tool(name="auto-bind-coupons", description="一键领券", input_schema={"type": "object", "properties": {}}),
        Tool(name="query-meals", description="菜单", input_schema={"type": "object", "properties": {"storeId": {}}}),
    ]


def test_build_function_defs_excludes_write_tools():
    defs = build_function_defs(_tools())
    names = {d["function"]["name"] for d in defs}
    assert "available-coupons" in names
    assert "query-meals" in names
    assert "auto-bind-coupons" not in names, "写操作默认不外露给大模型"


def test_build_function_defs_can_include_write_tools():
    defs = build_function_defs(_tools(), exclude_write=False)
    names = {d["function"]["name"] for d in defs}
    assert "auto-bind-coupons" in names


def test_skill_calls_tool_then_answers():
    client = FakeMcpClient(_tools(), {"available-coupons": {"items": [{"couponName": "巨无霸立减8元"}]}})
    brain = McdBrain(client, OrderGuard())
    llm = FakeLLM(
        [
            ChatReply(tool_calls=[ToolCall(id="c1", name="available-coupons", arguments={})]),
            ChatReply(text="今天有 1 张券：巨无霸立减 8 元。"),
        ]
    )

    result = run_skill("今天有什么券", brain, llm)  # type: ignore[arg-type]

    assert client.calls == [("available-coupons", {})]
    assert result.answer == "今天有 1 张券：巨无霸立减 8 元。"
    assert len(result.steps) == 1
    assert "巨无霸立减8元" in result.steps[0].result_preview


def test_write_tool_is_gated_and_not_executed():
    client = FakeMcpClient(_tools(), {"auto-bind-coupons": {"ok": True}})
    brain = McdBrain(client, OrderGuard())
    llm = FakeLLM([ChatReply(tool_calls=[ToolCall(id="c2", name="auto-bind-coupons", arguments={})])])

    result = run_skill("帮我领券", brain, llm)  # type: ignore[arg-type]

    assert result.needs_confirmation
    assert result.pending_write is not None
    assert result.pending_write.name == "auto-bind-coupons"
    assert client.calls == [], "未确认前绝不能真的领券"


def test_write_tool_runs_when_explicitly_allowed():
    client = FakeMcpClient(_tools(), {"auto-bind-coupons": {"ok": True}})
    brain = McdBrain(client, OrderGuard())
    llm = FakeLLM(
        [
            ChatReply(tool_calls=[ToolCall(id="c3", name="auto-bind-coupons", arguments={})]),
            ChatReply(text="券领好了。"),
        ]
    )

    result = run_skill("帮我领券", brain, llm, allow_write=True)  # type: ignore[arg-type]

    assert not result.needs_confirmation
    assert ("auto-bind-coupons", {}) in client.calls
    assert result.answer == "券领好了。"


def test_unknown_tool_result_is_still_reported():
    client = FakeMcpClient(_tools(), {})
    brain = McdBrain(client, OrderGuard())
    llm = FakeLLM(
        [
            ChatReply(tool_calls=[ToolCall(id="c4", name="query-meals", arguments={"storeId": "S1"})]),
            ChatReply(text="没查到菜单。"),
        ]
    )
    result = run_skill("有啥吃的", brain, llm)  # type: ignore[arg-type]
    assert result.steps[0].result_preview == "（工具没有返回文本）"
    assert result.answer == "没查到菜单。"


def test_write_tool_names_are_known_to_mcp_registry():
    from src.mcd_mcp import tools as T

    for name in WRITE_TOOLS:
        assert name in T.USED_TOOLS or name in {T.TOOL_MALL_CREATE_ORDER, T.TOOL_DRAW_LOTTERY}


def test_long_result_is_truncated():
    client = FakeMcpClient(_tools(), {"query-meals": {"t": "x" * 9000}})
    brain = McdBrain(client, OrderGuard())
    llm = FakeLLM(
        [
            ChatReply(tool_calls=[ToolCall(id="c5", name="query-meals", arguments={})]),
            ChatReply(text="菜单很长。"),
        ]
    )
    result = run_skill("菜单", brain, llm)  # type: ignore[arg-type]
    assert "已截断" in result.steps[0].result_preview
    assert len(result.steps[0].result_preview) < 5000


@pytest.mark.parametrize("name,args", [("delivery-create-address", {}), ("query-meals", {"unexpected": 1})])
def test_default_denies_unknown_write_or_bad_payload(name, args):
    client = FakeMcpClient(_tools(), {})
    llm = FakeLLM([ChatReply(tool_calls=[ToolCall("c", name, args)])])
    with pytest.raises(ValueError):
        run_skill("查询", McdBrain(client), llm)
    assert client.calls == []


def test_malformed_tool_arguments_never_become_empty_write_payload():
    client = FakeMcpClient(_tools(), {})
    llm = FakeLLM([ChatReply(tool_calls=[ToolCall("c", "auto-bind-coupons", {}, arguments_valid=False)])])
    with pytest.raises(ValueError):
        run_skill("帮我领券", McdBrain(client), llm)
    assert client.calls == []
