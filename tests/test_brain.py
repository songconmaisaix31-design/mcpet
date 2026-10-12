"""麦麦大脑测试（离线，用假的 client 返回真实结构样本）。

样本数据全部来自 2026-10-10 对真实 MCP 的实测抓取（已脱敏），
用于锁死「真实返回结构 → 业务对象」的解析逻辑，防止改代码时回归。
"""

from __future__ import annotations

import pytest

from src.mcd_mcp import tools as T
from src.mcd_mcp.brain import (
    DealQuote,
    McdBrain,
    NutritionFact,
    StoreInfo,
    parse_nutrition_table,
)
from src.mcd_mcp.client import McpError, ToolResult
from src.mcd_mcp.guards import GuardLimits, OrderGuard


def wrapped(data, *, success=True, code=200, message="请求成功"):
    """构造麦当劳统一响应壳。"""
    return ToolResult(
        name="x",
        raw={},
        text="",
        data={"success": success, "code": code, "message": message, "data": data},
    )


# ---------------------------------------------------------------- 营养表解析

REAL_NUTRITION_TEXT = (
    "[160]{productName,nutritionDescription,energyKj,energyKcal,protein,fat,"
    "carbohydrate,sodium,calcium}:\n"
    "  猪柳麦满分,null,1288,308,16,16,24,781,213\n"
    "  巨无霸,null,2146,513,27,26,42,961,171\n"
    "  纯悦,能量约清水1杯,0,0,0,0,0,0,0\n"
    "  无糖可口可乐中杯,null,0,0,0,0,1,35,0\n"
)


def test_parse_nutrition_table_extracts_rows():
    rows = parse_nutrition_table(REAL_NUTRITION_TEXT)
    assert len(rows) == 4
    assert rows[0]["productName"] == "猪柳麦满分"
    assert rows[0]["energyKcal"] == "308"
    assert rows[0]["protein"] == "16"


def test_parse_nutrition_table_treats_null_as_empty():
    rows = parse_nutrition_table(REAL_NUTRITION_TEXT)
    assert rows[1]["nutritionDescription"] == ""


def test_parse_nutrition_table_keeps_text_notes():
    rows = parse_nutrition_table(REAL_NUTRITION_TEXT)
    assert rows[2]["nutritionDescription"] == "能量约清水1杯"


def test_parse_nutrition_table_handles_zero_energy():
    rows = parse_nutrition_table(REAL_NUTRITION_TEXT)
    assert rows[3]["energyKcal"] == "0"
    assert rows[3]["sodium"] == "35"


def test_parse_nutrition_table_tolerates_preamble_and_junk():
    assert parse_nutrition_table("") == []
    assert parse_nutrition_table("随便一段没有表头的文本") == []


# ---------------------------------------------------------------- 假 client

class FakeClient:
    """按工具名返回预置结果，并记录收到的参数。"""

    def __init__(self, responses: dict[str, list[ToolResult]]):
        self.responses = {k: list(v) for k, v in responses.items()}
        self.calls: list[tuple[str, dict]] = []

    def call_tool(self, name: str, arguments: dict | None = None) -> ToolResult:
        self.calls.append((name, arguments or {}))
        queue = self.responses.get(name)
        if not queue:
            return wrapped(None)
        return queue.pop(0)

    def calls_of(self, name: str) -> list[dict]:
        return [args for tool, args in self.calls if tool == name]


@pytest.fixture()
def guard(tmp_path):
    return OrderGuard(GuardLimits(), tmp_path / "audit.json")


# ---------------------------------------------------------------- 领券汇报

AVAILABLE_SAMPLE = [
    {"couponName": "巧克力味厚松饼猪柳蛋套餐", "couponStatus": "HAVING_RECEIVE", "label": "已领取"},
    {"couponName": "免费脆薯饼", "couponStatus": "CAN_RECEIVE", "label": "领取"},
    {"couponName": "人气麦旋风买一送一", "couponStatus": "CAN_RECEIVE", "label": "领取"},
]
MY_COUPONS_SAMPLE = {
    "coupons": [
        {"id": "264B97DBE02BE6CF996AA6914151C4A9", "code": "MCD600469095R6L11M1U0",
         "title": "9.9元中杯冰美式"},
        {"id": "E85705ED6843E5CFF4B7C4DCDEDBADC4", "code": "MCD690G0055U10015RL91",
         "title": "巧克力味厚松饼猪柳蛋套餐"},
    ],
    "totalCount": 2,
}


def test_coupon_roundup_counts_only_unclaimed_as_claimable(guard):
    client = FakeClient({
        T.TOOL_AVAILABLE_COUPONS: [wrapped(AVAILABLE_SAMPLE)],
        T.TOOL_AUTO_BIND_COUPONS: [wrapped(None)],
        T.TOOL_MY_COUPONS: [wrapped(MY_COUPONS_SAMPLE)],
    })
    roundup = McdBrain(client, guard).coupon_roundup()
    assert roundup.available_count == 3
    assert roundup.claimable_before == 2  # HAVING_RECEIVE 那张不算可领
    assert roundup.my_coupon_count == 2
    assert "9.9元中杯冰美式" in roundup.my_coupons


def test_coupon_roundup_treats_code_499_as_benign(guard):
    """auto-bind-coupons 返回 code=499「暂无可领取的优惠券」不是错误。"""
    client = FakeClient({
        T.TOOL_AVAILABLE_COUPONS: [wrapped(AVAILABLE_SAMPLE)],
        T.TOOL_AUTO_BIND_COUPONS: [
            wrapped(None, success=False, code=499, message="暂无可领取的优惠券")
        ],
        T.TOOL_MY_COUPONS: [wrapped(MY_COUPONS_SAMPLE)],
    })
    roundup = McdBrain(client, guard).coupon_roundup()
    assert roundup.claim_ok is True
    assert roundup.claim_message == "暂无可领取的优惠券"
    assert roundup.claim_error == ""


def test_coupon_roundup_reports_real_failure(guard):
    client = FakeClient({
        T.TOOL_AVAILABLE_COUPONS: [wrapped(AVAILABLE_SAMPLE)],
        T.TOOL_AUTO_BIND_COUPONS: [wrapped(None, success=False, code=500, message="服务异常")],
        T.TOOL_MY_COUPONS: [wrapped(MY_COUPONS_SAMPLE)],
    })
    roundup = McdBrain(client, guard).coupon_roundup()
    assert roundup.claim_ok is False
    assert "服务异常" in roundup.claim_error


def test_coupon_roundup_no_claim_skips_write(guard):
    client = FakeClient({
        T.TOOL_AVAILABLE_COUPONS: [wrapped(AVAILABLE_SAMPLE)],
        T.TOOL_MY_COUPONS: [wrapped(MY_COUPONS_SAMPLE)],
    })
    roundup = McdBrain(client, guard).coupon_roundup(claim=False)
    assert client.calls_of(T.TOOL_AUTO_BIND_COUPONS) == []
    assert roundup.claimable_before == 2


# ---------------------------------------------------------------- 门店解析

NEARBY_SAMPLE = [
    {"storeCode": "1950970", "storeName": "中粮广场餐厅", "distance": 29, "businessStatus": False},
    {"storeCode": "1951035", "storeName": "东单北大街餐厅", "distance": 1031, "businessStatus": True},
    {"storeCode": "1950973", "storeName": "雅宝路餐厅", "distance": 1155, "businessStatus": True},
]


def test_resolve_default_store_prefers_open_store(guard):
    client = FakeClient({
        T.TOOL_DELIVERY_ADDRESSES: [wrapped([])],
        T.TOOL_NEARBY_STORES: [wrapped(NEARBY_SAMPLE)],
    })
    store = McdBrain(client, guard).resolve_default_store()
    assert store is not None
    assert store.store_code == "1951035"  # 营业中优先，而非距离最近但关门的 1950970
    assert store.business_status is True
    assert store.be_type == 1 and store.order_type == 1


def test_resolve_default_store_reports_no_store_when_nothing(guard):
    client = FakeClient({
        T.TOOL_DELIVERY_ADDRESSES: [wrapped([])],
        T.TOOL_NEARBY_STORES: [wrapped([])],
    })
    with pytest.raises(McpError, match="未查询到可用门店"):
        McdBrain(client, guard).resolve_default_store()


# ---------------------------------------------------------------- 最划算一单

MEALS_SAMPLE = {
    "categories": [{"name": "人气热卖", "meals": [{"code": "507411"}]}],
    "meals": {
        "507411": {"name": "麦咖啡™美式", "currentPrice": "11.9", "originalPrice": "19",
                   "canWithOrder": False},
        "1440": {"name": "巨无霸", "currentPrice": "25.5", "originalPrice": "25.5",
                 "canWithOrder": True},
    },
}
STORE_COUPONS_SAMPLE = [
    {
        "title": "9.9元中杯冰美式",
        "couponId": "264B97DBE02BE6CF996AA6914151C4A9",
        "couponCode": "MCD600469095R6L11M1U0",
        "products": [{"productCode": "507411", "productName": "麦咖啡™冰美式中杯"}],
    }
]


def _price_result(price_cents: int, product_code: str = "507411", original: int | None = None):
    return wrapped({
        "productOriginalPrice": original or price_cents,
        "productPrice": price_cents,
        "originalPrice": original or price_cents,
        "discount": (original or price_cents) - price_cents,
        "price": price_cents,
        "productList": [
            {"productCode": product_code, "quantity": 1,
             "originalSubtotal": original or price_cents, "subtotal": price_cents}
        ],
        "takeWayList": [
            {"code": "eat-in", "title": "堂食"},
            {"code": "take-in-store", "title": "外带"},
        ],
    })


STORE = StoreInfo(store_code="1951035", store_name="东单北大街餐厅")


def test_best_deal_pairs_coupon_by_product_code(guard):
    client = FakeClient({
        T.TOOL_MEALS: [wrapped(MEALS_SAMPLE)],
        T.TOOL_STORE_COUPONS: [wrapped(STORE_COUPONS_SAMPLE)],
        T.TOOL_CALCULATE_PRICE: [
            _price_result(1190, "507411", 1190),   # 无券基线
            _price_result(990, "507411", 1190),    # 带券
            _price_result(2550, "1440"),
        ],
    })
    quotes = McdBrain(client, guard).best_deal(STORE)
    top = quotes[0]
    assert top.meal_code == "507411"
    assert top.baseline_cents == 1190
    assert top.payable_cents == 990
    assert top.discount_cents == 200
    assert top.coupon_id == "264B97DBE02BE6CF996AA6914151C4A9"
    assert top.coupon_code == "MCD600469095R6L11M1U0"


def test_best_deal_passes_both_coupon_id_and_code(guard):
    """实测：只给 couponId 会报 600010，必须 couponId + couponCode 都给。"""
    client = FakeClient({
        T.TOOL_MEALS: [wrapped(MEALS_SAMPLE)],
        T.TOOL_STORE_COUPONS: [wrapped(STORE_COUPONS_SAMPLE)],
        T.TOOL_CALCULATE_PRICE: [
            _price_result(1190, "507411", 1190),
            _price_result(990, "507411", 1190),
            _price_result(2550, "1440"),
        ],
    })
    McdBrain(client, guard).best_deal(STORE)
    priced_items = [args["items"][0] for args in client.calls_of(T.TOOL_CALCULATE_PRICE)]
    coupon_items = [it for it in priced_items if "couponId" in it]
    assert coupon_items, "应当至少有一次带券算价"
    for item in coupon_items:
        assert item["couponId"] == "264B97DBE02BE6CF996AA6914151C4A9"
        assert item["couponCode"] == "MCD600469095R6L11M1U0"


def test_best_deal_does_not_apply_coupon_to_other_products(guard):
    """巨无霸不在券的 products 里，不该拿冰美式的券去套。"""
    client = FakeClient({
        T.TOOL_MEALS: [wrapped(MEALS_SAMPLE)],
        T.TOOL_STORE_COUPONS: [wrapped(STORE_COUPONS_SAMPLE)],
        T.TOOL_CALCULATE_PRICE: [
            _price_result(1190, "507411", 1190),
            _price_result(990, "507411", 1190),
            _price_result(2550, "1440", 2550),
        ],
    })
    quotes = McdBrain(client, guard).best_deal(STORE)
    bigmac = next(q for q in quotes if q.meal_code == "1440")
    assert bigmac.coupon_id == ""
    assert bigmac.discount_cents == 0


def test_best_deal_sorted_by_discount(guard):
    client = FakeClient({
        T.TOOL_MEALS: [wrapped(MEALS_SAMPLE)],
        T.TOOL_STORE_COUPONS: [wrapped(STORE_COUPONS_SAMPLE)],
        T.TOOL_CALCULATE_PRICE: [
            _price_result(1190, "507411", 1190),
            _price_result(990, "507411", 1190),
            _price_result(2550, "1440", 2550),
        ],
    })
    quotes = McdBrain(client, guard).best_deal(STORE)
    assert [q.discount_cents for q in quotes] == sorted(
        [q.discount_cents for q in quotes], reverse=True
    )
    assert quotes[0].discount_cents == 200


def test_best_deal_propagates_server_failure_without_menu_price_fallback(guard):
    client = FakeClient({
        T.TOOL_MEALS: [wrapped(MEALS_SAMPLE)],
        T.TOOL_STORE_COUPONS: [wrapped([])],
        T.TOOL_CALCULATE_PRICE: [wrapped(None, success=False, code=600057, message="门店已关闭")],
    })
    with pytest.raises(McpError, match="门店已关闭") as error:
        McdBrain(client, guard).best_deal(STORE)
    assert error.value.code == 600057


def test_best_deal_keyword_filter(guard):
    client = FakeClient({
        T.TOOL_MEALS: [wrapped(MEALS_SAMPLE)],
        T.TOOL_STORE_COUPONS: [wrapped([])],
        T.TOOL_CALCULATE_PRICE: [_price_result(2550, "1440", 2550)],
    })
    quotes = McdBrain(client, guard).best_deal(STORE, keyword="巨无霸")
    assert [q.meal_code for q in quotes] == ["1440"]


# ---------------------------------------------------------------- 营养查询

def test_nutrition_parses_real_table(guard):
    client = FakeClient({T.TOOL_NUTRITION: [wrapped(REAL_NUTRITION_TEXT)]})
    facts = McdBrain(client, guard).nutrition()
    assert len(facts) == 4
    bigmac = next(f for f in facts if f.name == "巨无霸")
    assert bigmac.energy_kcal == 513
    assert bigmac.energy_kj == 2146
    assert bigmac.protein_g == 27
    assert bigmac.sodium_mg == 961


def test_nutrition_keyword_filter(guard):
    client = FakeClient({T.TOOL_NUTRITION: [wrapped(REAL_NUTRITION_TEXT)]})
    facts = McdBrain(client, guard).nutrition(keyword="巨无霸")
    assert [f.name for f in facts] == ["巨无霸"]


def test_find_nutrition_matches_by_substring(guard):
    client = FakeClient({T.TOOL_NUTRITION: [wrapped(REAL_NUTRITION_TEXT)]})
    fact = McdBrain(client, guard).find_nutrition("巨无霸")
    assert fact is not None and fact.name == "巨无霸"
    assert McdBrain(client, guard).find_nutrition("不存在的餐品") is None


# ---------------------------------------------------------------- 下单

def test_place_order_needs_confirmation_without_flag(guard):
    client = FakeClient({T.TOOL_CALCULATE_PRICE: [_price_result(990, "507411", 1190)]})
    outcome = McdBrain(client, guard).place_order(STORE, ["507411"], ["麦咖啡™美式"])
    assert outcome.status == "needs_confirmation"
    assert client.calls_of(T.TOOL_CREATE_ORDER) == []


def test_place_order_passes_take_way_code_for_pickup(guard):
    """实测：orderType=1 时 create-order 必传 takeWayCode，否则下单失败。"""
    client = FakeClient({
        T.TOOL_CALCULATE_PRICE: [_price_result(990, "507411", 1190)],
        T.TOOL_CREATE_ORDER: [wrapped({"orderNo": "NO-1", "payUrl": "https://pay.example/x"})],
    })
    outcome = McdBrain(client, guard).place_order(
        STORE, ["507411"], ["麦咖啡™美式"], confirmed=True
    )
    assert outcome.status == "placed"
    args = client.calls_of(T.TOOL_CREATE_ORDER)[0]
    assert args["takeWayCode"] == "take-in-store"
    assert args["orderType"] == 1
    assert args["beType"] == 1


def test_place_order_respects_explicit_take_way(guard):
    client = FakeClient({
        T.TOOL_CALCULATE_PRICE: [_price_result(990, "507411", 1190)],
        T.TOOL_CREATE_ORDER: [wrapped({"orderNo": "NO-2"})],
    })
    McdBrain(client, guard).place_order(
        STORE, ["507411"], ["麦咖啡™美式"], take_way_code="eat-in", confirmed=True
    )
    assert client.calls_of(T.TOOL_CREATE_ORDER)[0]["takeWayCode"] == "eat-in"


def test_place_order_omits_take_way_for_delivery(guard):
    """orderType=2（外送）不传 takeWayCode。"""
    delivery_store = StoreInfo(store_code="1951035", store_name="某店", be_type=2, order_type=2,
                               be_code="BE1")
    client = FakeClient({
        T.TOOL_CALCULATE_PRICE: [_price_result(990, "507411", 1190)],
        T.TOOL_CREATE_ORDER: [wrapped({"orderNo": "NO-3"})],
    })
    McdBrain(client, guard).place_order(
        delivery_store, ["507411"], ["麦咖啡™美式"], confirmed=True
    )
    args = client.calls_of(T.TOOL_CREATE_ORDER)[0]
    assert "takeWayCode" not in args
    assert args["beCode"] == "BE1"


def test_place_order_blocked_by_amount_guard(guard):
    client = FakeClient({T.TOOL_CALCULATE_PRICE: [_price_result(99999, "507411")]})
    guard.limits = GuardLimits(max_amount_cents=5_000)
    outcome = McdBrain(client, guard).place_order(
        STORE, ["507411"], ["麦咖啡™美式"], confirmed=True
    )
    assert outcome.status == "rejected"
    assert "上限" in outcome.reason
    assert client.calls_of(T.TOOL_CREATE_ORDER) == []


def test_place_order_records_audit_entry(guard):
    client = FakeClient({
        T.TOOL_CALCULATE_PRICE: [_price_result(990, "507411", 1190)],
        T.TOOL_CREATE_ORDER: [wrapped({"orderNo": "NO-9", "payUrl": "https://pay.example/9"})],
    })
    McdBrain(client, guard).place_order(STORE, ["507411"], ["麦咖啡™美式"], confirmed=True)
    assert len(guard.entries) == 1
    assert guard.entries[0].order_no == "NO-9"
    assert guard.entries[0].status == "placed"


def test_deal_quote_sentence_format():
    quote = DealQuote(meal_name="巨无霸", meal_code="1440",
                      baseline_cents=2550, payable_cents=1750)
    assert "巨无霸" in quote.sentence()
    assert "8.00" in quote.sentence()


def test_deal_quote_sentence_when_no_discount():
    quote = DealQuote(meal_name="巨无霸", meal_code="1440",
                      baseline_cents=2550, payable_cents=2550)
    assert "暂无可用券" in quote.sentence()


# ---------------------------------------------------------------- 餐品详情

MEAL_DETAIL_SAMPLE = {
    "code": "1440",
    "name": "麦辣鸡腿汉堡",
    "rounds": [],
    "supportModify": True,
    "modification": {
        "items": [
            {
                "maxValues": 2,
                "minValues": 0,
                "values": [
                    {"code": "100136", "price": 0, "name": "麦香鸡酱",
                     "selectedQuantity": 1, "selectedKey": "0-1", "unselectedKey": "0-0"},
                    {"code": "120512", "price": 0, "name": "切块生菜",
                     "selectedQuantity": 1, "selectedKey": "0-1", "unselectedKey": "0-0"},
                ],
            }
        ]
    },
}


def test_meal_detail_uses_code_field_not_product_code(guard):
    """query-meal-detail 的编码字段名是 code，不是 productCode。"""
    client = FakeClient({T.TOOL_MEAL_DETAIL: [wrapped(MEAL_DETAIL_SAMPLE)]})
    detail = McdBrain(client, guard).meal_detail(STORE, "1440")
    assert detail["name"] == "麦辣鸡腿汉堡"
    args = client.calls_of(T.TOOL_MEAL_DETAIL)[0]
    assert args["code"] == "1440"
    assert "productCode" not in args


def test_meal_detail_returns_empty_on_bad_payload(guard):
    client = FakeClient({T.TOOL_MEAL_DETAIL: [wrapped("不是字典")]})
    assert McdBrain(client, guard).meal_detail(STORE, "1440") == {}


# ---------------------------------------------------------------- 取餐方式

def test_take_way_options_reads_list(guard):
    client = FakeClient({T.TOOL_CALCULATE_PRICE: [_price_result(990, "507411", 1190)]})
    options = McdBrain(client, guard).take_way_options(STORE, "507411")
    assert [o["code"] for o in options] == ["eat-in", "take-in-store"]


# ---------------------------------------------------------------- 撤单

def test_cancel_order_passes_order_id_and_reason(guard):
    client = FakeClient({T.TOOL_CANCEL_ORDER: [wrapped({"ok": True})]})
    assert McdBrain(client, guard).cancel_order("NO-1") is True
    args = client.calls_of(T.TOOL_CANCEL_ORDER)[0]
    assert args["orderId"] == "NO-1"
    assert args["cancelReasonCode"] == "1"


def test_nutrition_fact_defaults():
    fact = NutritionFact(name="测试")
    assert fact.energy_kcal == 0
    assert fact.note == ""


def test_all_five_closed_stores_are_explicit_error_without_changing_city(guard, monkeypatch):
    monkeypatch.setenv("MCPET_CITY", "北京")
    stores = [{"storeCode": str(i), "businessStatus": False} for i in range(5)]
    client = FakeClient({T.TOOL_DELIVERY_ADDRESSES: [wrapped([])], T.TOOL_NEARBY_STORES: [wrapped(stores)]})
    from src.mcd_mcp.brain import StoreUnavailable
    with pytest.raises(StoreUnavailable, match="未营业"):
        McdBrain(client, guard).resolve_default_store()
    assert client.calls_of(T.TOOL_NEARBY_STORES)[0][T.ARG_KEYS["city"]] == "北京"
    assert client.calls_of(T.TOOL_MEALS) == []


@pytest.mark.parametrize("is_error", [False, True])
def test_menu_preserves_real_business_message_and_code(guard, is_error):
    result = wrapped(None, success=False, code=600057, message="门店可能已关闭或不在营业时间")
    result.data = [result.data]
    result.is_error = is_error
    client = FakeClient({T.TOOL_MEALS: [result]})
    with pytest.raises(McpError) as error:
        McdBrain(client, guard).best_deal(STORE)
    assert str(error.value) == "门店可能已关闭或不在营业时间"
    assert error.value.code == 600057


@pytest.mark.parametrize("value", [None, True, -1, "garbage", "NaN", "Infinity", "990.5"])
def test_invalid_quote_price_never_becomes_zero_or_menu_fallback(guard, value):
    client = FakeClient({T.TOOL_CALCULATE_PRICE: [wrapped({"price": value})]})
    with pytest.raises(McpError, match="UNKNOWN"):
        McdBrain(client, guard).quote_order(STORE, ["1440"])


def test_calculate_price_decimal_cents_not_yuan(guard):
    client = FakeClient({T.TOOL_CALCULATE_PRICE: [wrapped({"price": "990.00"})]})
    assert McdBrain(client, guard).quote_order(STORE, ["1440"]) == 990


def test_no_coupon_quote_has_no_coupon_identity(guard):
    client = FakeClient({T.TOOL_MEALS: [wrapped(MEALS_SAMPLE)], T.TOOL_STORE_COUPONS: [wrapped([])],
                         T.TOOL_CALCULATE_PRICE: [_price_result(2550, "1440")]})
    quote = McdBrain(client, guard).best_deal(STORE, keyword="巨无霸")[0]
    assert quote.coupon_id == quote.coupon_code == quote.coupon_name == ""
    assert quote.discount_cents == 0
    assert quote.payable_cents == 2550


def test_coupon_calculation_failure_not_reported_as_no_coupon(guard):
    client = FakeClient({T.TOOL_MEALS: [wrapped(MEALS_SAMPLE)], T.TOOL_STORE_COUPONS: [wrapped(STORE_COUPONS_SAMPLE)],
                         T.TOOL_CALCULATE_PRICE: [_price_result(1190), wrapped(None, success=False, code=600010, message="使用优惠券失败")]})
    with pytest.raises(McpError, match="使用优惠券失败"):
        McdBrain(client, guard).best_deal(STORE)


def test_cancel_business_failure_does_not_mark_audit_cancelled(guard):
    client = FakeClient({T.TOOL_CANCEL_ORDER: [wrapped(None, success=False, code=500, message="撤单失败")]})
    assert McdBrain(client, guard).cancel_order("NO-1") is False
