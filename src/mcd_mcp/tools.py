"""麦当劳 MCP 工具清单与参数名映射。

背景：官方 README 只给了工具名和中文说明，没有公开 inputSchema 字段表。
本模块把「语义参数 → 实际参数名」集中在一处，并提供 verify_against() 用真实
tools/list 的返回来核对。拿到 Token 后跑一次

    python -m src.cli tools

就能拿到每个工具真实的字段名，回来改 ARG_KEYS 即可，不用翻遍代码。

ARG_KEYS 的当前值是基于命名惯例的**推测**，在 MCP_INTEGRATION.md 里如实标注为
「待真实 tools/list 校正」。
"""

from __future__ import annotations

from dataclasses import dataclass

from .client import McdMcpClient, Tool

# 本项目实际用到的工具
TOOL_NOW_TIME = "now-time-info"
TOOL_AVAILABLE_COUPONS = "available-coupons"
TOOL_AUTO_BIND_COUPONS = "auto-bind-coupons"
TOOL_MY_COUPONS = "query-my-coupons"
TOOL_STORE_COUPONS = "query-store-coupons"
TOOL_MEALS = "query-meals"
TOOL_MEAL_DETAIL = "query-meal-detail"
TOOL_CALCULATE_PRICE = "calculate-price"
TOOL_CREATE_ORDER = "create-order"
TOOL_CANCEL_ORDER = "cancel-order"
TOOL_QUERY_ORDER = "query-order"
TOOL_ORDER_LIST = "order-list"
TOOL_NUTRITION = "list-nutrition-foods"
TOOL_NEARBY_STORES = "query-nearby-stores"
TOOL_DELIVERY_ADDRESSES = "delivery-query-addresses"
TOOL_DELIVERY_STORES = "delivery-query-stores"
TOOL_CAMPAIGN_CALENDAR = "campaign-calendar"
TOOL_MALL_CREATE_ORDER = "mall-create-order"
TOOL_DRAW_LOTTERY = "draw-lottery"

USED_TOOLS: tuple[str, ...] = (
    TOOL_NOW_TIME,
    TOOL_AVAILABLE_COUPONS,
    TOOL_AUTO_BIND_COUPONS,
    TOOL_MY_COUPONS,
    TOOL_STORE_COUPONS,
    TOOL_MEALS,
    TOOL_MEAL_DETAIL,
    TOOL_CALCULATE_PRICE,
    TOOL_CREATE_ORDER,
    TOOL_CANCEL_ORDER,
    TOOL_QUERY_ORDER,
    TOOL_NUTRITION,
    TOOL_NEARBY_STORES,
    TOOL_DELIVERY_ADDRESSES,
    TOOL_DELIVERY_STORES,
    TOOL_CAMPAIGN_CALENDAR,
)

# 语义参数 → 真实字段名（2026-10-10 用真实 tools/list 校正后）
ARG_KEYS: dict[str, str] = {
    "store_code": "storeCode",
    "be_code": "beCode",
    "be_type": "beType",
    "order_type": "orderType",
    "address_id": "addressId",
    "address": "address",
    "items": "items",
    "product_code": "productCode",
    "coupon_id": "couponId",
    "coupon_code": "couponCode",
    "quantity": "quantity",
    "keyword": "keyword",
    "name": "name",
    "page": "page",
    "page_size": "pageSize",
    "order_id": "orderId",
    "cancel_reason_code": "cancelReasonCode",
    "search_type": "searchType",
    "city": "city",
    # 2026-10-10 从真实 inputSchema 补上：
    # create-order 在 orderType=1 时**必传** takeWayCode，
    # 取值来自 calculate-price 返回的 data.takeWayList[].code（eat-in / take-in-store）。
    "take_way_code": "takeWayCode",
    "need_tableware": "needTableware",
    "with_order": "withOrder",
    "remark": "remark",
    "reservation_date": "reservationDate",
    # query-meal-detail 的餐品编码字段名与其它工具不同：它叫 code（不是 productCode）
    "detail_code": "code",
}

PLANNED_ARGS: dict[str, tuple[str, ...]] = {
    TOOL_AVAILABLE_COUPONS: (),
    TOOL_AUTO_BIND_COUPONS: (),
    TOOL_MY_COUPONS: ("page", "page_size"),
    TOOL_STORE_COUPONS: ("store_code", "be_type", "order_type", "be_code"),
    TOOL_MEALS: ("store_code", "be_type", "order_type", "be_code"),
    TOOL_MEAL_DETAIL: ("store_code", "be_type", "order_type", "be_code", "detail_code"),
    TOOL_CALCULATE_PRICE: ("store_code", "be_type", "order_type", "items", "be_code"),
    TOOL_CREATE_ORDER: ("store_code", "be_type", "order_type", "items", "be_code", "take_way_code"),
    TOOL_CANCEL_ORDER: ("order_id", "cancel_reason_code"),
    TOOL_QUERY_ORDER: ("order_id",),
    TOOL_NUTRITION: (),
    TOOL_NEARBY_STORES: ("be_type", "search_type", "city", "keyword"),
    TOOL_DELIVERY_ADDRESSES: (),
    TOOL_DELIVERY_STORES: ("address_id", "be_type"),
    TOOL_CAMPAIGN_CALENDAR: (),
    TOOL_NOW_TIME: (),
}


@dataclass
class ArgCheck:
    tool: str
    semantic: str
    assumed: str
    present: bool
    actual: tuple[str, ...]


def verify_against(client: McdMcpClient) -> tuple[dict[str, Tool], list[ArgCheck]]:
    """拉取真实工具清单，逐项核对 ARG_KEYS 的推测是否成立。"""
    real = {tool.name: tool for tool in client.list_tools()}
    checks: list[ArgCheck] = []
    for tool_name, semantics in PLANNED_ARGS.items():
        tool = real.get(tool_name)
        actual = tuple(tool.arg_names) if tool else ()
        for semantic in semantics:
            assumed = ARG_KEYS.get(semantic, semantic)
            checks.append(
                ArgCheck(
                    tool=tool_name,
                    semantic=semantic,
                    assumed=assumed,
                    present=assumed in actual,
                    actual=actual,
                )
            )
    return real, checks
