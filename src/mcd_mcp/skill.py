"""把麦当劳 MCP 工具交给大模型调度——这就是本项目的「Skill」。

流程：真实 tools/list → 转成 OpenAI function 定义 → 大模型决定调哪个 →
真实调用 → 把结果喂回去 → 直到它给出人话回答。

安全闸门：写操作（领券 / 下单 / 撤单 / 抽奖）默认不允许大模型自主执行。
它想调的时候我们停下来，把「要做什么」翻译成人话交给用户确认。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
from .. import config
from ..chat.store import bounded_history

from ..llm.stepfun import ChatReply, StepFunClient, ToolCall
from ..mcd_mcp import tools as T
from ..mcd_mcp.brain import McdBrain
from ..mcd_mcp.client import Tool

# 会产生真实副作用的工具，大模型不能自作主张
WRITE_TOOLS: frozenset[str] = frozenset(
    {
        T.TOOL_AUTO_BIND_COUPONS,
        T.TOOL_CREATE_ORDER,
        T.TOOL_CANCEL_ORDER,
        T.TOOL_MALL_CREATE_ORDER,
        T.TOOL_DRAW_LOTTERY,
    }
)

SYSTEM_PROMPT = (
    "你是「麦麦搭子」（McPet），一个换上麦当劳制服、住在用户系统托盘里的 AI 搭子。"
    "你会用麦当劳 MCP 工具查真实数据来回答问题。\n"
    "规则：\n"
    "1. 涉及券、价格、营养、门店的问题，必须调工具，不许凭印象回答；\n"
    "2. 拿不到数据就直说拿不到，不要编；\n"
    "3. 回答用中文，短句、口语化，像搭子在跟你说话，一两句话说完；\n"
    "4. 需要下单或领券时，先说明你要做什么，等用户确认；\n"
    "5. 不做医疗或营养建议，只陈述查到的数据。"
)

MAX_TOOL_RESULT_CHARS = 4000
READ_TOOLS = frozenset(T.USED_TOOLS) - WRITE_TOOLS | {T.TOOL_ORDER_LIST}


def validate_arguments(arguments: Any, schema: dict[str, Any]) -> None:
    """校验工具 payload，不把坏 JSON、缺字段或未知字段默默变成写请求。"""
    kind = schema.get("type")
    checks = {"object": lambda v: isinstance(v, dict),
              "array": lambda v: isinstance(v, list),
              "string": lambda v: isinstance(v, str),
              "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
              "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
              "boolean": lambda v: isinstance(v, bool)}
    if kind in checks and not checks[kind](arguments):
        raise ValueError("工具参数类型不正确")
    if "enum" in schema and arguments not in schema["enum"]:
        raise ValueError("工具参数不在允许值中")
    if isinstance(arguments, dict):
        props = schema.get("properties", {})
        if set(schema.get("required", [])) - set(arguments):
            raise ValueError("工具参数缺少必填字段")
        if set(arguments) - set(props):
            raise ValueError("工具参数含未知字段")
        for key, value in arguments.items():
            validate_arguments(value, props[key])
    if isinstance(arguments, list) and "items" in schema:
        for value in arguments:
            validate_arguments(value, schema["items"])


@dataclass
class SkillStep:
    tool: str
    arguments: dict[str, Any]
    result_preview: str


@dataclass
class SkillResult:
    answer: str = ""
    steps: list[SkillStep] = field(default_factory=list)
    pending_write: ToolCall | None = None
    pending_reason: str = ""
    usage: dict[str, Any] = field(default_factory=dict)

    @property
    def needs_confirmation(self) -> bool:
        return self.pending_write is not None


def build_function_defs(
    tools: list[Tool], *, only: set[str] | None = None, exclude_write: bool = True
) -> list[dict[str, Any]]:
    """把 MCP 的 inputSchema 转成 OpenAI function 定义。"""
    defs: list[dict[str, Any]] = []
    for tool in tools:
        if only and tool.name not in only:
            continue
        if exclude_write and tool.name in WRITE_TOOLS:
            continue
        if exclude_write and tool.name not in READ_TOOLS:
            continue
        schema = dict(tool.input_schema or {})
        schema.setdefault("type", "object")
        schema.setdefault("properties", {})
        defs.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": (tool.description or tool.name)[:500],
                    "parameters": schema,
                },
            }
        )
    return defs


def _preview(text: str, limit: int = MAX_TOOL_RESULT_CHARS) -> str:
    text = config.redact((text or "").strip())
    if len(text) > limit:
        return text[:limit] + f"…（已截断，原长 {len(text)} 字符）"
    return text or "（工具没有返回文本）"


def run_skill(
    question: str,
    brain: McdBrain,
    llm: StepFunClient,
    *,
    max_steps: int = 6,
    allow_write: bool = False,
    extra_system: str = "",
    on_step: Callable[[SkillStep], None] | None = None,
    history: list[dict[str, Any]] | None = None,
) -> SkillResult:
    """跑一次 Skill：提问 → 模型选工具 → 真调 → 收敛成一句人话。"""
    mcp_tools = brain.client.list_tools()
    defs = build_function_defs(
        mcp_tools, exclude_write=not allow_write
    ) or build_function_defs(mcp_tools, exclude_write=True)

    system = SYSTEM_PROMPT + (("\n" + extra_system) if extra_system else "")
    messages: list[dict[str, Any]] = [{"role": "system", "content": config.redact(system)}]
    messages.extend(bounded_history(history or []))
    messages.append({"role": "user", "content": config.redact(question)[:4000]})

    result = SkillResult()
    for _ in range(max_steps):
        reply: ChatReply = llm.chat(messages, tools=defs)
        result.usage = reply.usage or result.usage

        if not reply.wants_tools:
            result.answer = config.redact(reply.text.strip())
            return result

        for call in reply.tool_calls:
            if not getattr(call, "arguments_valid", True) or not isinstance(call.arguments, dict):
                raise ValueError("模型返回了无效工具参数，未执行")
            if call.name in WRITE_TOOLS and not allow_write:
                result.pending_write = call
                result.pending_reason = (
                    f"麦麦想执行「{call.name}」，这是会产生真实结果的操作，需要你确认。"
                )
                return result

            allowed = {d["function"]["name"] for d in defs}
            if call.name not in allowed:
                raise ValueError("模型请求了未授权工具，未执行")
            tool = next(t for t in mcp_tools if t.name == call.name)
            validate_arguments(call.arguments, tool.input_schema)

            tool_result = brain.client.call_tool(call.name, call.arguments)
            if tool_result.is_error or not tool_result.ok:
                raise ValueError(config.redact(tool_result.error_message or tool_result.text))
            step = SkillStep(
                tool=call.name,
                arguments=call.arguments,
                result_preview=_preview(tool_result.text),
            )
            result.steps.append(step)
            if on_step:
                on_step(step)
            messages.append(
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.name,
                                "arguments": _dump_args(call.arguments),
                            },
                        }
                    ],
                }
            )
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": _preview(tool_result.text)}
            )

    result.answer = "转了好几圈还是没结论，你直接问我「今天最划算」吧。"
    return result


def _dump_args(arguments: dict[str, Any]) -> str:
    import json

    try:
        return json.dumps(arguments, ensure_ascii=False)
    except (TypeError, ValueError):
        return "{}"
