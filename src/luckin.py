"""Official Luckin tools; shared HTTP transport and guards, no Qt or host dependency."""
from __future__ import annotations

import copy
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal, InvalidOperation
import time
import math
from functools import wraps

from . import config
from .mcd_mcp.client import McdMcpClient, McpError
from .mcd_mcp.guards import OrderGuard, OrderAuditEntry
from .mcd_mcp.validation import validate_arguments
from .agent_local import data_lock

READ_TOOLS = frozenset({"queryShopList", "searchProductForMcp", "switchProduct",
                        "queryProductDetailInfo", "previewOrder", "queryOrderDetailInfo"})


def locked_order(method):
    @wraps(method)
    def run(self, *args, **kwargs):
        with data_lock():
            # A different host can have added audit entries since construction.
            self.guard = OrderGuard(self.guard.limits, self.guard.audit_path)
            return method(self, *args, **kwargs)
    return run


class LuckinClient(McdMcpClient):
    def __init__(self, token):
        super().__init__(token, config.LUCKIN_MCP_URL, max_retries_on_429=0,
                         rate_limit_per_minute=60)

    def _post(self, payload):
        try:
            return super()._post(payload)
        except McpError as exc:
            if exc.http_status == 401:
                raise McpError("瑞幸 Token 无效或过期，请在瑞幸 AI 开放平台登录后更新本机设置。", http_status=401) from None
            if exc.http_status == 429:
                raise McpError("瑞幸服务限流；本次请求未自动重试。", http_status=429) from None
            raise


def amount_cents(preview):
    # Luckin prices are yuan, including integer prices (16 means 16 yuan).
    try:
        value = preview["discountPrice"]
        if isinstance(value, bool):
            raise ValueError()
        price = Decimal(str(value))
        if not price.is_finite() or price <= 0 or price != price.quantize(Decimal("0.01")):
            raise ValueError()
        return int(price * 100)
    except (KeyError, TypeError, ValueError, InvalidOperation):
        raise McpError("瑞幸未返回有效实付金额，未提交订单。") from None


class LuckinService:
    def __init__(self, client_factory=None, guard=None):
        self.client_factory = client_factory or self._client
        self.guard = guard or OrderGuard()
        self.pending = None
        self.last_order = ""
        self.unknown = False
        self.selections = set()
        self.selection_token = config.luckin_token()
        self.cancel_unknown = set()

    @staticmethod
    def _client():
        config.load_env()
        token = config.luckin_token()
        if not token:
            raise McpError("尚未配置瑞幸 Token。右键 → 设置 → 账号凭证 → 瑞幸 Token；从瑞幸 AI 开放平台登录复制。")
        return LuckinClient(token)

    @contextmanager
    def client(self):
        with self.client_factory() as client:
            client.ensure_initialized()
            yield client

    @staticmethod
    def call(client, name, arguments):
        from jsonschema import Draft202012Validator, ValidationError, SchemaError
        tool = next((t for t in client.list_tools() if t.name == name), None)
        if tool is None:
            raise McpError("瑞幸服务未提供工具：" + name)
        try:
            Draft202012Validator.check_schema(tool.input_schema)
            Draft202012Validator(tool.input_schema).validate(arguments)
        except (ValidationError, SchemaError):
            # ValidationError messages contain raw arguments; never surface them.
            raise ValueError("瑞幸工具参数不符合官方 schema，未发送请求") from None
        result = client.call_tool(name, copy.deepcopy(arguments))
        result.raise_for_error()
        node = result.data
        if isinstance(node, list) and len(node) == 1:
            node = node[0]
        if not isinstance(node, dict) or node.get("success") is not True or node.get("code") not in (0, 200):
            raise McpError(config.redact(str(node.get("msg", "瑞幸返回未确认成功"))) if isinstance(node, dict) else "瑞幸返回格式未知")
        return node.get("data")

    def query(self, tool, arguments):
        if tool not in READ_TOOLS:
            raise ValueError("仅允许瑞幸只读工具；下单和撤单须单独确认")
        with self.client() as client:
            data = self.call(client, tool, arguments)
        if self.selection_token != config.luckin_token():
            self.selections.clear()
            self.selection_token = config.luckin_token()
        if tool in {"searchProductForMcp", "switchProduct", "queryProductDetailInfo"}:
            for item in data if isinstance(data, list) else [data]:
                if isinstance(item, dict) and item.get("productId") and item.get("skuCode"):
                    self.selections.add((arguments.get("deptId"), item["productId"], item["skuCode"]))
        return data

    @locked_order
    def prepare(self, dept_id, products, longitude, latitude):
        self.pending = None
        if self.unknown or any(e.tool == "luckin:createOrder" and e.status == "delivery_unknown" for e in OrderGuard(audit_path=self.guard.audit_path).entries):
            raise McpError("上次瑞幸提交效果未知，请先到官方 App 核对，不可重复提交。")
        if (not products or self.selection_token != config.luckin_token()
                or any((dept_id, p.get("productId"), p.get("skuCode")) not in self.selections
                       or type(p.get("amount")) is not int or not 1 <= p["amount"] <= 10 for p in products)):
            raise McpError("请先从本会话真实查询结果选择瑞幸商品和规格，数量为 1–10。")
        if (not math.isfinite(longitude) or not math.isfinite(latitude)
                or not -180 <= longitude <= 180 or not -90 <= latitude <= 90):
            raise ValueError("经纬度无效")
        args = copy.deepcopy({"deptId": dept_id, "productList": products})
        with self.client() as client:
            preview = self.call(client, "previewOrder", args)
            cents = amount_cents(preview)
            if preview.get("shopInfo", {}).get("deptId") != dept_id or not preview.get("productInfoList"):
                raise McpError("瑞幸预览未返回已选门店和商品，不能确认订单。")
            expected = sorted((p["productId"], p["skuCode"], p["amount"]) for p in products)
            actual = sorted((p.get("productId"), p.get("skuCode"), p.get("amount")) for p in preview["productInfoList"])
            if expected != actual:
                raise McpError("瑞幸预览商品、规格或数量与选择不一致，未提交订单。")
            self.guard.check(cents)
            payload = {**args, "longitude": longitude, "latitude": latitude,
                       "couponCodeList": preview.get("couponCodeList") or []}
            schema = next((t.input_schema for t in client.list_tools() if t.name == "createOrder"), None)
            if schema is None:
                raise McpError("瑞幸服务未提供 createOrder")
            validate_arguments(payload, schema)
        summary = self.summary(preview, cents)
        self.pending = {"payload": payload, "preview": preview, "amount": cents,
                        "summary": summary, "at": time.monotonic(), "token": config.luckin_token()}
        return {"status": "needs_confirmation", "summary": summary, "amount_cents": cents}

    @staticmethod
    def summary(preview, cents):
        shop = preview.get("shopInfo") or {}
        items = preview.get("productInfoList") or []
        names = "、".join(f"{p.get('name', p.get('productId', '?'))} × {p.get('amount', '?')} {p.get('additionDesc', '')}" for p in items)
        return config.redact(f"瑞幸 · {shop.get('deptName', shop.get('deptId', '?'))}\n{names}\n实付 ¥{cents / 100:.2f}；创建后按官方链接付款。")

    def _record(self, request, status, order="", pay="", note=""):
        self.guard.record(OrderAuditEntry(datetime.now().isoformat(timespec="seconds"), "luckin:createOrder",
                          config.redact(str(request["preview"].get("shopInfo", {}).get("deptName", "瑞幸"))),
                          request["summary"], request["amount"], config.redact(str(order), personal=False), config.redact(pay, personal=False), False, status, config.redact(note)))

    @locked_order
    def confirm(self, confirmed=False):
        if not confirmed:
            return {"status": "needs_confirmation"}
        request, self.pending = self.pending, None
        if request is None:
            raise McpError("没有待确认的瑞幸订单，请重新预览。")
        if time.monotonic() - request["at"] > 300 or request["token"] != config.luckin_token():
            raise McpError("瑞幸报价过期或账号已变化，请重新预览。")
        with self.client() as client:
            payload = request["payload"]
            fresh = self.call(client, "previewOrder", {k: payload[k] for k in ("deptId", "productList")})
            if (amount_cents(fresh) != request["amount"] or fresh.get("couponCodeList", []) != payload["couponCodeList"]
                    or fresh.get("productInfoList") != request["preview"].get("productInfoList")
                    or fresh.get("shopInfo", {}).get("deptId") != request["preview"].get("shopInfo", {}).get("deptId")):
                raise McpError("瑞幸价格、规格、门店或优惠已变化，请重新预览确认。")
            self.guard.check(request["amount"])
            # Validate before submission; an exception after this point is ambiguous.
            schema = next(t.input_schema for t in client.list_tools() if t.name == "createOrder")
            validate_arguments(payload, schema)
            try:
                result = self.call(client, "createOrder", payload)
                order = str(result.get("orderIdStr") or result.get("orderId") or "") if isinstance(result, dict) else ""
                if not order:
                    raise McpError("服务未返回订单号")
            except Exception:
                self.unknown = True
                try:
                    self._record(request, "delivery_unknown", note="提交后未取得确定结果；不可重试")
                except OSError:
                    pass
                return {"status": "delivery_unknown", "reason": "瑞幸提交效果未知，未重试；请到官方 App 核对。"}
        self.last_order = order
        pay = str(result.get("payOrderUrl") or result.get("payOrderQrCodeUrl") or "")
        warning = ""
        try:
            self._record(request, "placed", order, pay)
        except OSError:
            warning = "本机审计保存失败；订单号仍有效，请到官方核对。"
        return {"status": "placed", "order_id": order, "pay_url": pay,
                "summary": request["summary"], "warning": warning}

    @locked_order
    def cancel(self, order_id, confirmed=False):
        if not confirmed:
            return {"status": "needs_confirmation", "order_id": order_id}
        if order_id in self.cancel_unknown or any(e.tool == "luckin:cancelOrder" and e.order_no == order_id and e.status == "delivery_unknown" for e in OrderGuard(audit_path=self.guard.audit_path).entries):
            raise McpError("该瑞幸撤单效果未知，不能重复提交；请到官方核对。")
        with self.client() as client:
            try:
                result = self.call(client, "cancelOrder", {"orderId": order_id})
            except Exception:
                self.cancel_unknown.add(order_id)
                try:
                    self.guard.record(OrderAuditEntry(datetime.now().isoformat(timespec="seconds"), "luckin:cancelOrder", "瑞幸", "撤单", 0,
                                      order_no=order_id, status="delivery_unknown"))
                except OSError:
                    pass
                return {"status": "delivery_unknown", "reason": "瑞幸撤单效果未知，未重试；请到官方核对。"}
        if result is not True:
            raise McpError("瑞幸未确认撤单成功")
        warning = ""
        try:
            self.guard.mark_cancelled(order_id)
        except OSError:
            warning = "本机审计更新失败；请到官方核对。"
        return {"status": "cancelled", "order_id": order_id, "warning": warning}
