"""Official MCP stdio server. All interaction remains in the hosting Agent."""
from __future__ import annotations

import asyncio
import json
import threading
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from . import config
from .agent_service import AgentService, public

INSTRUCTIONS = """McPet is an ability of this existing Agent conversation.
Use these tools for actual coupons, prices, nutrition, balances and local activity;
do not answer real-time meal facts from model memory. No independent UI or model is required.
Show order/claim/cancel/nutrition summaries in this conversation and get explicit user
confirmation before the matching write tool. Never infer consent from a query.
Never retry delivery_unknown writes; verify existing account/order state first.
Unknown/stale is not zero or success. idle/Stop is not task completion.
Credentials are inherited from existing local configuration, never request them in chat.
Character/actions are resources and logical state; do not open a separate window.
"""


def create_server(service=None):
    service = service or AgentService()
    server = FastMCP("McPet", instructions=INSTRUCTIONS, log_level="WARNING")
    gate = threading.RLock()
    read = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True)
    local = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)
    write = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True)

    async def invoke(method, *args, **kwargs):
        def run():
            with gate:
                try:
                    return public(getattr(service, method)(*args, **kwargs))
                except Exception as exc:
                    # Never expose SDK/internal arguments, credentials or raw
                    # upstream payloads in error results consumed by the model.
                    return {"status": "error", "reason": config.redact(str(exc))}
        return await asyncio.to_thread(run)

    @server.tool(annotations=read)
    async def mcpet_status() -> dict[str, Any]:
        """查看当前角色、动作与 Agent 内接入状态。不会打开桌面窗口。"""
        return await invoke("status")

    @server.tool(annotations=local)
    async def mcpet_pet(action: Literal["idle", "working", "thinking", "greet", "happy", "sleeping", "eating", "frying", "outfit", "stop"] = "idle",
                        character_id: Literal["", "maimai", "deepseek"] = "", loop: bool = False,
                        skin_id: Literal["", "default", "maimai"] = "") -> dict[str, Any]:
        """切角色、动作或持久皮肤。DeepSeek 娘 default/maimai 随时切换；换装一次切到另一套，炸薯条穿麦麦套装。"""
        return await invoke("pet", action, character_id, loop, skin_id)

    @server.tool(annotations=read)
    async def mcpet_settings() -> dict[str, Any]:
        """查看城市、饭点及凭证是否已配置；不返回任何 Key/Token。"""
        return await invoke("settings")

    @server.tool(annotations=local)
    async def mcpet_configure(city: str = "", lunch_time: str = "", reminders_enabled: bool | None = None,
                              agent_roots: dict[str, str] | None = None) -> dict[str, Any]:
        """原会话配置城市、HH:MM 饭点、提醒开关；日志来源只用用户明确指定的 claude/codex/generic 目录。"""
        return await invoke("configure", city, lunch_time, reminders_enabled, agent_roots)

    @server.tool(annotations=read)
    async def mcpet_coupons() -> dict[str, Any]:
        """只读查询真实可领取券和已有券；此调用绝不领取。"""
        return await invoke("coupons")

    @server.tool(annotations=write)
    async def mcpet_claim_coupons(confirmed: bool = False) -> dict[str, Any]:
        """真实领取全部可领券。先说明范围，只有用户明确确认才传 confirmed=true；未知结果不可自动重试。"""
        return await invoke("claim_coupons", confirmed)

    @server.tool(annotations=read)
    async def mcpet_deals(keyword: str = "") -> dict[str, Any]:
        """查询营业门店和真实餐品/券实付报价，返回编码用于准备订单，不下单。"""
        return await invoke("deals", keyword)

    @server.tool(annotations=read)
    async def mcpet_prepare_order(product_codes: list[str], meal_names: list[str], store: dict,
                                   coupon_id: str = "", coupon_code: str = "", coupon_name: str = "",
                                   take_way_code: str = "take-in-store") -> dict[str, Any]:
        """从真实报价选择餐品并准备完整订单摘要。仅算价，不提交；在原会话展示并等待用户确认。"""
        return await invoke("prepare_order", product_codes, meal_names, store, coupon_id, coupon_code, coupon_name, take_way_code)

    @server.tool(annotations=write)
    async def mcpet_confirm_order(confirmed: bool = False) -> dict[str, Any]:
        """用户明确确认本会话已展示的订单摘要后提交。拒绝过期/涨价；delivery_unknown 不重下。"""
        return await invoke("confirm_order", confirmed)

    @server.tool(annotations=write)
    async def mcpet_cancel_order(order_no: str, confirmed: bool = False) -> dict[str, Any]:
        """展示具体订单号后，由用户明确确认再撤单。不把普通查询视为撤单授权。"""
        return await invoke("cancel_order", order_no, confirmed)

    @server.tool(annotations=read)
    async def mcpet_nutrition(keyword: str = "") -> dict[str, Any]:
        """查询真实营养餐品及每份营养值，供用户选择。"""
        return await invoke("nutrition", keyword)

    @server.tool(annotations=local)
    async def mcpet_nutrition_log(meal_name: str, quantity: float = 1.0, confirmed: bool = False) -> dict[str, Any]:
        """用户确认具体餐品与份数后记本机营养台账；只接受本会话查询出的真实营养餐品。"""
        return await invoke("nutrition_log", meal_name, quantity, confirmed)

    @server.tool(annotations=read)
    async def mcpet_nutrition_today() -> dict[str, Any]:
        """查看今日已记餐品、份数和累计营养。"""
        return await invoke("nutrition_today")

    @server.tool(annotations=read)
    async def mcpet_balances(source: Literal["all", "orca", "deepseek"] = "all") -> dict[str, Any]:
        """只读获取已有 Orca 额度缓存/官方 DeepSeek 余额。窗口/桶/币种独立，未知不填零。"""
        return await invoke("balances", source)

    @server.tool(annotations=read)
    async def mcpet_progress() -> dict[str, Any]:
        """按既有配置查看本机会话状态和上下文；不向其他 Agent 发消息，不推断任务完成。"""
        return await invoke("progress")

    @server.tool(annotations=local)
    async def mcpet_usage(refresh: bool = False) -> dict[str, Any]:
        """查看本机 token/费用台账。refresh=true 才扫描既有配置来源；不是厂商余额或账单。"""
        return await invoke("usage", refresh)

    @server.tool(annotations=local)
    async def mcpet_reminders() -> dict[str, Any]:
        """检查饭点提醒，复用原调度逻辑，同一天跨 Agent 不重复。在原会话呈现。"""
        return await invoke("reminders")

    @server.resource("mcpet://animation/maimai/frying", mime_type="image/gif", description="用户提供的炸薯条透明循环动画；宿主按自身资源能力呈现")
    def frying_animation() -> bytes:
        return service.animation("frying")

    @server.resource("mcpet://animation/maimai/outfit", mime_type="image/gif", description="用户提供的透明换装动画，完整一段约十秒；不打开单独窗口")
    def outfit_animation() -> bytes:
        return service.animation("outfit")

    @server.resource("mcpet://animation/deepseek/frying", mime_type="image/gif")
    def deepseek_frying() -> bytes:
        return service.animation("frying", "deepseek")

    @server.resource("mcpet://animation/deepseek/outfit", mime_type="image/gif")
    def deepseek_outfit() -> bytes:
        return service.animation("outfit", "deepseek")

    @server.resource("mcpet://animation/deepseek/outfit-default", mime_type="image/gif")
    def deepseek_default_outfit() -> bytes:
        return service.animation("outfit-default", "deepseek")

    @server.resource("mcpet://skin/deepseek/maimai", mime_type="image/gif")
    def deepseek_maimai_skin() -> bytes:
        from .agent_service import ASSETS
        return (ASSETS / "deepseek-skins/maimai/idle.gif").read_bytes()

    @server.resource("mcpet://guide", mime_type="text/plain")
    def guide() -> str:
        return INSTRUCTIONS

    @server.prompt()
    def mcpet_assistant() -> str:
        """让原 Agent 使用 McPet 能力；不创建新的聊天或模型请求。"""
        return INSTRUCTIONS

    return server


def main():
    config.load_env()
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
