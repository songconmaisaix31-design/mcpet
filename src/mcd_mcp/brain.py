"""麦麦大脑：把麦当劳 MCP 的原始工具包装成「宠物能说人话」的业务动作。

四个动作，全部走真实 MCP 调用：
  1. coupon_roundup()   —— 领券汇报（可领 → 一键领 → 我的券）
  2. best_deal()        —— 找今天最划算的一单
  3. nutrition()        —— 餐品营养查询（供营养台账记账）
  4. place_order()      —— 真实下单（必须过护栏 + 显式确认）

设计约束：这里不做 mock、不做缓存冒充实时。任何拿不到的数据就返回空并如实上报。

═══════════════════════════════════════════════════════════════════════
2026-10-10 用真实 Token 逐工具校正（下面的结构都是实测出来的，不是推测）
═══════════════════════════════════════════════════════════════════════
参数名：
  - 门店号是 storeCode（不是 storeId）；餐品编码是 productCode（不是 mealCode）
  - 所有门店查询必须带 beType + orderType；到店(beType=1)场景不返回 beCode，不要传
  - 券必须挂在**每个 item** 的 couponId 上，而且 couponId 与 couponCode **两个都要给**

响应壳：统一 {success, code, message, datetime, traceId, data}，
        已由 client.ToolResult.unwrap() 剥掉，业务代码拿到的是 data。

各工具 data 的真实形状：
  query-nearby-stores  → [{storeCode, storeName, address, distance,
                           businessStatus(bool), businessStartTime, businessEndTime, ...}]
                         ⚠ businessStatus=False 的门店调 query-meals 会报 600057，必须优先挑 True 的
  query-meals          → {categories:[{name, meals:[{code, tags}]}],
                          meals:{productCode:{name, image, currentPrice, originalPrice, canWithOrder}}}
                         ⚠ 这里的 currentPrice/originalPrice 是**元**的字符串（"33.5"），
                           与 calculate-price 的**分**单位不同，别搞混
  query-store-coupons  → [{title, couponId, couponCode, tradeDateTime,
                           products:[{productCode, productName}], promotionId}]
                         ⚠ products[].productCode 就是「这张券能用在哪些餐品」的索引
  query-my-coupons     → {coupons:[{id, code, title, discountInfo:{...}, ...}],
                          totalCount, currentPage, pageSize, totalPages}
                         ⚠ 字段名是 id/code/title，不是 couponId/couponCode/couponName
  available-coupons    → [{couponName, couponImage, couponStatus, label}]
  calculate-price      → {productOriginalPrice, productPrice, originalPrice, discount,
                          price, productList:[{productCode, productName, quantity,
                          originalSubtotal, subtotal}], takeWayList:[...]}
                         ⚠ 单位是**分**：price=3350 即 33.50 元，price=990 即 9.90 元
  list-nutrition-foods → data 是**字符串**（不是 JSON！），自定义表格格式：
                         "[160]{productName,nutritionDescription,energyKj,energyKcal,
                          protein,fat,carbohydrate,sodium,calcium}:\n
                           猪柳麦满分,null,1288,308,16,16,24,781,213\n  ..."
"""

from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from .. import config
from .client import McdMcpClient, ToolResult
from .guards import GuardViolation, OrderAuditEntry, OrderGuard, to_cents
from . import tools as T


def _pick(mapping: Any, *keys: str, default: Any = None) -> Any:
    if not isinstance(mapping, dict):
        return default
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return default


def _text_of(item: Any, *keys: str) -> str:
    value = _pick(item, *keys)
    return str(value) if value is not None else ""


def _num_of(item: Any, *keys: str, default: float = 0.0) -> float:
    value = _pick(item, *keys)
    if value is None:
        return default
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------- 营养表解析

_NUTRITION_HEADER = re.compile(r"\[(\d+)\]\{([^}]*)\}\s*:")


def parse_nutrition_table(text: str) -> list[dict[str, str]]:
    """解析 list-nutrition-foods 的自定义表格字符串。

    真实格式（实测）：
        [160]{productName,nutritionDescription,energyKj,energyKcal,protein,
              fat,carbohydrate,sodium,calcium}:
          猪柳麦满分,null,1288,308,16,16,24,781,213
          纯悦,能量约清水1杯,0,0,0,0,0,0,0
    第一行是 `[行数]{字段名...}:`，之后每行是逗号分隔的一条记录。
    `null` 表示该字段为空。
    """
    if not text or "{" not in text:
        return []
    match = _NUTRITION_HEADER.search(text)
    if not match:
        return []
    fields = [f.strip() for f in match.group(2).split(",") if f.strip()]
    if not fields:
        return []

    rows: list[dict[str, str]] = []
    for line in text[match.end():].splitlines():
        line = line.strip()
        if not line:
            continue
        cells = next(csv.reader([line], skipinitialspace=True))
        if not cells or not any(c.strip() for c in cells):
            continue
        row: dict[str, str] = {}
        for index, name in enumerate(fields):
            cell = cells[index].strip() if index < len(cells) else ""
            row[name] = "" if cell.lower() == "null" else cell
        rows.append(row)
    return rows


@dataclass
class StoreInfo:
    store_code: str
    store_name: str
    be_type: int = 1  # 1=到店取餐
    order_type: int = 1  # 1=到店
    be_code: str = ""
    address: str = ""
    distance: int = 0
    business_status: bool = True


@dataclass
class CouponRoundup:
    available_count: int = 0    # 券中心可见的券总数（含已领）
    claimable_before: int = 0   # 其中「还没领」的，才是真正可领的
    my_coupon_count: int = 0    # 领完之后手上的券数量
    claimed: list[str] = field(default_factory=list)      # 本次新领到的券名
    my_coupons: list[str] = field(default_factory=list)   # 手上的券名（全部）
    raw_claim: str = ""
    claim_ok: bool = True       # 是否属于「正常结束」（含「暂无可领取」这种良性结果）
    claim_error: str = ""
    claim_message: str = ""


@dataclass
class DealQuote:
    meal_name: str
    meal_code: str
    coupon_name: str = ""
    coupon_id: str = ""
    coupon_code: str = ""
    baseline_cents: int = 0
    payable_cents: int = 0
    addon_available: bool = False  # 是否可「随单购」（canWithOrder），只是加分项，不影响能否单独下单

    @property
    def discount_cents(self) -> int:
        return max(self.baseline_cents - self.payable_cents, 0)

    def sentence(self) -> str:
        if not self.discount_cents:
            return f"{self.meal_name} 暂无可用券（{self.baseline_cents / 100:.2f} 元）"
        return (
            f"{self.meal_name} 减 {self.discount_cents / 100:.2f} 元"
            f"（原价 {self.baseline_cents / 100:.2f} → 实付 {self.payable_cents / 100:.2f}）"
        )


@dataclass
class NutritionFact:
    name: str
    energy_kj: float = 0.0
    energy_kcal: float = 0.0
    protein_g: float = 0.0
    fat_g: float = 0.0
    carb_g: float = 0.0
    sodium_mg: float = 0.0
    calcium_mg: float = 0.0
    note: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderOutcome:
    status: str  # needs_confirmation | dry_run_skipped | placed | rejected
    summary: str = ""
    amount_cents: int = 0
    order_no: str = ""
    pay_url: str = ""
    reason: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class McdBrain:
    def __init__(
        self,
        client: McdMcpClient,
        guard: OrderGuard | None = None,
    ):
        self.client = client
        self.guard = guard or OrderGuard()
        self._default_store: StoreInfo | None = None

    # ---------- 门店解析 ----------

    def resolve_default_store(self) -> StoreInfo | None:
        """无地址时默认用「到店自取」场景。先找外送地址，没有就按城市搜附近门店。

        2026-10-10 实测：该账号无配送地址，fallback 到 query-nearby-stores。
        ⚠ 必须优先挑 businessStatus=True 的门店——营业中的门店才查得到菜单，
          否则 query-meals 会报 600057「门店可能已关闭或不在营业时间」。
        """
        if self._default_store is not None:
            return self._default_store

        # 1) 尝试外送地址
        addresses = self.client.call_tool(T.TOOL_DELIVERY_ADDRESSES).as_list()
        for address in addresses:
            address_id = str(_pick(address, "addressId", "id", default="") or "")
            if not address_id:
                continue
            stores = self.client.call_tool(
                T.TOOL_DELIVERY_STORES,
                {T.ARG_KEYS["address_id"]: address_id, T.ARG_KEYS["be_type"]: 2},
            ).as_list()
            for store in stores:
                code = str(_pick(store, "storeCode", "id", default="") or "")
                if code:
                    be_code = str(_pick(store, "beCode", default="") or "")
                    self._default_store = StoreInfo(
                        store_code=code,
                        store_name=_text_of(store, "storeName", "name"),
                        be_type=2,
                        order_type=2,
                        be_code=be_code,
                        address=_text_of(store, "address"),
                        distance=int(_num_of(store, "distance", default=0)),
                    )
                    return self._default_store

        # 2) fallback：到店自取（beType=1, orderType=1）
        city = os.environ.get("MCPET_CITY", "北京").strip()
        stores = self.client.call_tool(
            T.TOOL_NEARBY_STORES,
            {
                T.ARG_KEYS["be_type"]: 1,
                T.ARG_KEYS["order_type"]: 1,
                T.ARG_KEYS["search_type"]: 2,
                T.ARG_KEYS["city"]: city,
                T.ARG_KEYS["keyword"]: "麦当劳",
            },
        ).as_list()
        if not stores:
            return None

        def is_open(store: Any) -> bool:
            return bool(_pick(store, "businessStatus", "business_status", default=False))

        # 营业中的优先，其次按距离排序
        ordered = sorted(
            [s for s in stores if isinstance(s, dict)],
            key=lambda s: (not is_open(s), int(_num_of(s, "distance", default=10**9))),
        )
        for store in ordered:
            code = str(_pick(store, "storeCode", "id", default="") or "")
            if not code:
                continue
            self._default_store = StoreInfo(
                store_code=code,
                store_name=_text_of(store, "storeName", "name"),
                be_type=1,
                order_type=1,
                be_code="",
                address=_text_of(store, "address"),
                distance=int(_num_of(store, "distance", default=0)),
                business_status=is_open(store),
            )
            return self._default_store
        return None

    # ---------- 1. 领券汇报 ----------

    # 已领取状态：available-coupons 里 couponStatus 为这些值时说明已到手，不算「可领」
    _RECEIVED_STATUS = frozenset({"HAVING_RECEIVE", "RECEIVED", "HAVE_RECEIVED"})
    # auto-bind-coupons 的良性业务码：没有新券可领，不是错误
    _NOTHING_TO_CLAIM_CODES = frozenset({499})

    def coupon_roundup(self, *, claim: bool = True) -> CouponRoundup:
        """真实执行：查可领 → 一键领全部 → 查我的券。

        claim=False 时只读不领（用于纯汇报场景）。
        ⚠ auto-bind-coupons 在「没有新券可领」时返回 {success:false, code:499,
          message:"暂无可领取的优惠券"} —— 这是良性结果，不能当失败报给用户。
        """
        before = [item for item in self.client.call_tool(T.TOOL_AVAILABLE_COUPONS).as_list()
                  if isinstance(item, dict)]
        roundup = CouponRoundup(available_count=len(before))
        roundup.claimable_before = sum(
            1
            for item in before
            if str(_pick(item, "couponStatus", "status", default="")).upper()
            not in self._RECEIVED_STATUS
        )

        if claim:
            result = self.client.call_tool(T.TOOL_AUTO_BIND_COUPONS)
            roundup.raw_claim = result.text[:500]
            code = None
            node = result.data
            if isinstance(node, list) and len(node) == 1:
                node = node[0]
            if isinstance(node, dict):
                code = node.get("code")
            if result.ok:
                roundup.claim_ok = True
                roundup.claim_message = "领取成功"
            elif code in self._NOTHING_TO_CLAIM_CODES:
                roundup.claim_ok = True
                roundup.claim_message = result.error_message or "暂无可领取的优惠券"
            else:
                roundup.claim_ok = False
                roundup.claim_error = result.error_message or result.text[:200]

        after = self.client.call_tool(T.TOOL_MY_COUPONS).as_list()
        my_names = [
            _text_of(item, "title", "couponName", "name")
            for item in after
            if isinstance(item, dict)
        ]
        roundup.my_coupons = [n for n in my_names if n]
        roundup.my_coupon_count = len(roundup.my_coupons)
        # 手上的券里，不在「券中心可见名单」中的，就是本次新领到的
        before_names = {
            _text_of(item, "couponName", "name", "title") for item in before
        }
        roundup.claimed = [n for n in roundup.my_coupons if n not in before_names]
        return roundup

    # ---------- 2. 找最划算的一单 ----------

    def _meal_index(self, store: StoreInfo) -> dict[str, dict[str, Any]]:
        """query-meals → {productCode: {name, currentPrice, originalPrice, canWithOrder, ...}}"""
        result = self.client.call_tool(T.TOOL_MEALS, self._store_args(store))
        node = result.unwrap()
        if not isinstance(node, dict):
            return {}
        meals = node.get("meals")
        if isinstance(meals, dict):
            return {str(code): (info if isinstance(info, dict) else {}) for code, info in meals.items()}
        return {}

    def _store_coupons(self, store: StoreInfo) -> list[dict[str, Any]]:
        """query-store-coupons → 门店可用券列表。"""
        items = self.client.call_tool(T.TOOL_STORE_COUPONS, self._store_args(store)).as_list()
        return [c for c in items if isinstance(c, dict)]

    def meal_detail(self, store: StoreInfo, product_code: str) -> dict[str, Any]:
        """query-meal-detail：单个餐品详情（含特制选项 modification）。

        ⚠ 这个工具的餐品编码字段名是 `code`（不是 productCode），别和其它工具混。
        返回形状（实测）：
          {code, name, rounds, image, supportModify,
           modification:{items:[{maxValues, minValues,
                                 values:[{code, price, name, selectedKey, unselectedKey, ...}]}]}}
        """
        args = {**self._store_args(store), T.ARG_KEYS["detail_code"]: product_code}
        node = self.client.call_tool(T.TOOL_MEAL_DETAIL, args).unwrap()
        return node if isinstance(node, dict) else {}

    def best_deal(
        self,
        store: StoreInfo,
        *,
        keyword: str | None = None,
        max_candidates: int = 8,
        progress: Callable[[str], None] | None = None,
    ) -> list[DealQuote]:
        """在给定门店下，对候选餐品逐个试券，返回按优惠额降序的报价。

        优化：先用门店券的 products[].productCode 反查出「哪些餐品有券可用」，
        只对这批餐品做 calculate-price（有券 / 无券各一次），
        调用量 ≈ 菜单 1 + 门店券 1 + 候选数×2，远低于 600 次/分钟。
        """
        def say(message: str) -> None:
            if progress:
                progress(message)

        say("正在拉取菜单…")
        meals = self._meal_index(store)
        if not meals:
            return []

        say("正在拉取门店可用券…")
        coupons = self._store_coupons(store)

        # 券 → 适用餐品 的索引
        coupon_by_product: dict[str, list[dict[str, Any]]] = {}
        for coupon in coupons:
            for product in coupon.get("products") or []:
                if not isinstance(product, dict):
                    continue
                code = str(_pick(product, "productCode", default="") or "")
                if code:
                    coupon_by_product.setdefault(code, []).append(coupon)

        # 候选排序：有券可用的排前面，其次按名字匹配
        def rank(code: str) -> tuple[int, int]:
            has_coupon = 0 if code in coupon_by_product else 1
            return (has_coupon, len(code))

        candidates: list[tuple[str, str]] = []
        for code in sorted(meals, key=rank):
            info = meals[code]
            name = _text_of(info, "name", "productName")
            if keyword and keyword not in name and keyword not in code:
                continue
            candidates.append((name or code, code))
            if len(candidates) >= max_candidates:
                break
        if not candidates:
            return []

        say(f"正在给 {len(candidates)} 个餐品算价…")
        quotes: list[DealQuote] = []
        for name, code in candidates:
            baseline = self._price(store, code)
            if baseline is None:
                # 兜底：用菜单里的 currentPrice（单位是元）
                fallback = _pick(meals.get(code, {}), "currentPrice", default=None)
                baseline = to_cents(fallback) if fallback is not None else None
            if baseline is None:
                continue

            best = DealQuote(
                meal_name=name,
                meal_code=code,
                baseline_cents=baseline,
                payable_cents=baseline,
                addon_available=bool(_pick(meals.get(code, {}), "canWithOrder", default=False)),
            )
            for coupon in coupon_by_product.get(code, []):
                coupon_id = _text_of(coupon, "couponId", "id")
                coupon_code = _text_of(coupon, "couponCode", "code")
                if not coupon_id:
                    continue
                payable = self._price(store, code, coupon_id=coupon_id, coupon_code=coupon_code)
                if payable is None:
                    continue
                quote = DealQuote(
                    meal_name=name,
                    meal_code=code,
                    coupon_name=_text_of(coupon, "title", "couponName", "name"),
                    coupon_id=coupon_id,
                    coupon_code=coupon_code,
                    baseline_cents=baseline,
                    payable_cents=payable,
                    addon_available=best.addon_available,
                )
                if quote.discount_cents > best.discount_cents:
                    best = quote
            quotes.append(best)

        quotes.sort(key=lambda q: q.discount_cents, reverse=True)
        return quotes

    def _store_args(self, store: StoreInfo) -> dict[str, Any]:
        args: dict[str, Any] = {
            T.ARG_KEYS["store_code"]: store.store_code,
            T.ARG_KEYS["be_type"]: store.be_type,
            T.ARG_KEYS["order_type"]: store.order_type,
        }
        if store.be_code:
            args[T.ARG_KEYS["be_code"]] = store.be_code
        return args

    def _item(
        self,
        product_code: str,
        quantity: int = 1,
        *,
        coupon_id: str | None = None,
        coupon_code: str | None = None,
    ) -> dict[str, Any]:
        """构造 calculate-price / create-order 的 item。

        ⚠ 实测：使用优惠券必须同时给 couponId 和 couponCode，
          只给一个会报 600010「使用优惠券需要couponId和couponCode」。
        """
        item: dict[str, Any] = {
            T.ARG_KEYS["product_code"]: product_code,
            T.ARG_KEYS["quantity"]: quantity,
        }
        if coupon_id:
            item[T.ARG_KEYS["coupon_id"]] = coupon_id
            if coupon_code:
                item[T.ARG_KEYS["coupon_code"]] = coupon_code
        return item

    # calculate-price 里真正代表「实付」的字段（单位：分）
    _PRICE_FIELDS = (
        "price", "productPrice", "payAmount", "payableAmount",
        "totalAmount", "actualAmount", "amount",
    )

    def _price(
        self,
        store: StoreInfo,
        product_code: str,
        coupon_id: str | None = None,
        coupon_code: str | None = None,
    ) -> int | None:
        items = [self._item(product_code, 1, coupon_id=coupon_id, coupon_code=coupon_code)]
        args = {**self._store_args(store), T.ARG_KEYS["items"]: items}
        result = self.client.call_tool(T.TOOL_CALCULATE_PRICE, args)
        if result.is_error:
            return None
        node = result.unwrap()
        if not isinstance(node, dict):
            return None

        # 优先按 productList 的 subtotal 求和（多商品时更准）
        product_list = node.get("productList")
        if isinstance(product_list, list) and product_list:
            subtotals = [
                to_cents(_pick(p, "subtotal", "payAmount", default=None))
                for p in product_list
                if isinstance(p, dict)
            ]
            if any(s > 0 for s in subtotals):
                return sum(subtotals)

        for key in self._PRICE_FIELDS:
            if key in node and node[key] not in (None, ""):
                return to_cents(node[key])
        return None

    # ---------- 3. 营养查询 ----------

    def nutrition(self, keyword: str = "") -> list[NutritionFact]:
        """list-nutrition-foods 无入参，返回全量营养表。

        ⚠ 实测 data 是**字符串**（自定义表格格式），不是 JSON。用 parse_nutrition_table 解析。
        keyword 在本地过滤。
        """
        result = self.client.call_tool(T.TOOL_NUTRITION)
        node = result.unwrap()
        rows = parse_nutrition_table(node if isinstance(node, str) else result.text)

        facts: list[NutritionFact] = []
        for row in rows:
            name = row.get("productName", "").strip()
            if not name:
                continue
            if keyword and keyword not in name:
                continue
            facts.append(
                NutritionFact(
                    name=name,
                    energy_kj=_num_of(row, "energyKj"),
                    energy_kcal=_num_of(row, "energyKcal"),
                    protein_g=_num_of(row, "protein"),
                    fat_g=_num_of(row, "fat"),
                    carb_g=_num_of(row, "carbohydrate"),
                    sodium_mg=_num_of(row, "sodium"),
                    calcium_mg=_num_of(row, "calcium"),
                    note=row.get("nutritionDescription", "").strip(),
                    raw=row,
                )
            )
        return facts

    def find_nutrition(self, product_name: str) -> NutritionFact | None:
        """按名字找一条营养数据（营养台账记账用）。"""
        if not product_name:
            return None
        facts = self.nutrition()
        # 精确 > 包含
        for fact in facts:
            if fact.name == product_name:
                return fact
        for fact in facts:
            if product_name in fact.name or fact.name in product_name:
                return fact
        return None

    # ---------- 4. 真实下单 ----------

    # 到店场景(orderType=1) create-order 必传 takeWayCode。
    # 取值来自 calculate-price 的 data.takeWayList[].code：
    #   eat-in        堂食（店内用餐）
    #   take-in-store 外带（店内自提）
    # 宠物是「打包带走」的叙事，默认外带。
    DEFAULT_TAKE_WAY_CODE = "take-in-store"

    def take_way_options(self, store: StoreInfo, product_code: str) -> list[dict[str, Any]]:
        """取 calculate-price 返回的 takeWayList，供下单时选堂食/外带。"""
        args = {**self._store_args(store), T.ARG_KEYS["items"]: [self._item(product_code, 1)]}
        result = self.client.call_tool(T.TOOL_CALCULATE_PRICE, args)
        node = result.unwrap()
        if isinstance(node, dict) and isinstance(node.get("takeWayList"), list):
            return [o for o in node["takeWayList"] if isinstance(o, dict)]
        return []

    def quote_order(
        self,
        store: StoreInfo,
        product_codes: list[str],
        *,
        coupon_id: str | None = None,
        coupon_code: str | None = None,
    ) -> int:
        items = [
            self._item(code, 1, coupon_id=coupon_id, coupon_code=coupon_code)
            for code in product_codes
        ]
        args = {**self._store_args(store), T.ARG_KEYS["items"]: items}
        result = self.client.call_tool(T.TOOL_CALCULATE_PRICE, args)
        if result.is_error:
            return 0
        node = result.unwrap()
        if not isinstance(node, dict):
            return 0
        for key in self._PRICE_FIELDS:
            if key in node and node[key] not in (None, ""):
                return to_cents(node[key])
        return 0

    def render_order_summary(
        self,
        store_name: str,
        meal_names: list[str],
        amount_cents: int,
        coupon_name: str = "",
        take_way_label: str = "",
    ) -> str:
        lines = [f"门店：{store_name or '（未指定）'}"]
        if take_way_label:
            lines.append(f"取餐方式：{take_way_label}")
        lines.append("商品：" + "、".join(meal_names))
        if coupon_name:
            lines.append(f"用券：{coupon_name}")
        lines.append(f"实付：{amount_cents / 100:.2f} 元")
        return "\n".join(lines)

    def place_order(
        self,
        store: StoreInfo,
        product_codes: list[str],
        meal_names: list[str],
        *,
        coupon_id: str | None = None,
        coupon_code: str | None = None,
        coupon_name: str = "",
        take_way_code: str | None = None,
        confirmed: bool = False,
    ) -> OrderOutcome:
        amount = self.quote_order(
            store, product_codes, coupon_id=coupon_id, coupon_code=coupon_code
        )
        # 到店场景(orderType=1) create-order 必传 takeWayCode
        if store.order_type == 1:
            take_way_code = take_way_code or self.DEFAULT_TAKE_WAY_CODE
        else:
            take_way_code = None
        take_way_label = {
            "eat-in": "堂食",
            "take-in-store": "外带",
        }.get(take_way_code or "", "")
        summary = self.render_order_summary(
            store.store_name, meal_names, amount, coupon_name, take_way_label
        )

        try:
            self.guard.check(amount)
        except GuardViolation as exc:
            return OrderOutcome(status="rejected", summary=summary, amount_cents=amount, reason=str(exc))

        if not confirmed:
            return OrderOutcome(status="needs_confirmation", summary=summary, amount_cents=amount)

        if config.dry_run():
            self.guard.record(
                OrderAuditEntry(
                    created_at=datetime.now().isoformat(timespec="seconds"),
                    tool=T.TOOL_CREATE_ORDER,
                    store=store.store_name,
                    items="、".join(meal_names),
                    amount_cents=amount,
                    dry_run=True,
                    status="dry_run_skipped",
                    note="演练模式：算价为真实调用，未提交 create-order",
                )
            )
            return OrderOutcome(status="dry_run_skipped", summary=summary, amount_cents=amount)

        items = [
            self._item(code, 1, coupon_id=coupon_id, coupon_code=coupon_code)
            for code in product_codes
        ]
        args = {**self._store_args(store), T.ARG_KEYS["items"]: items}
        if take_way_code:
            args[T.ARG_KEYS["take_way_code"]] = take_way_code
        result: ToolResult = self.client.call_tool(T.TOOL_CREATE_ORDER, args)
        if result.is_error:
            return OrderOutcome(
                status="rejected",
                summary=summary,
                amount_cents=amount,
                reason=f"下单失败：{result.text[:300]}",
            )

        node = result.unwrap()
        order_no = str(_pick(node, "orderNo", "orderId", "orderCode", default="") or "")
        pay_url = str(_pick(node, "payUrl", "paymentUrl", "payLink", default="") or "")
        self.guard.record(
            OrderAuditEntry(
                created_at=datetime.now().isoformat(timespec="seconds"),
                tool=T.TOOL_CREATE_ORDER,
                store=store.store_name,
                items="、".join(meal_names),
                amount_cents=amount,
                order_no=order_no,
                pay_url=pay_url,
                status="placed",
            )
        )
        return OrderOutcome(
            status="placed",
            summary=summary,
            amount_cents=amount,
            order_no=order_no,
            pay_url=pay_url,
            raw=result.raw,
        )

    def cancel_order(self, order_no: str) -> bool:
        """撤单。真实调用 cancel-order，成功后同步更新审计台账。"""
        result = self.client.call_tool(
            T.TOOL_CANCEL_ORDER,
            {T.ARG_KEYS["order_id"]: order_no, T.ARG_KEYS["cancel_reason_code"]: "1"},
        )
        if result.is_error:
            return False
        self.guard.mark_cancelled(order_no)
        return True
