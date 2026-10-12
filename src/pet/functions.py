"""Pet-only presentation of existing capabilities. No dialog or model runtime."""
from __future__ import annotations

import copy
from datetime import datetime
import math
import os
import time
from decimal import Decimal

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication

from .. import config
from .characters import CHARACTER_IDS, character_name
from .preferences import PetPreferences
from ..agent_local import data_lock
from ..schedule.core import DailyTask


class PetFunctions:
    def action_panel(self, page="home"):
        # Compatibility entry name retained for existing integrations; no panel.
        if not self.closing:
            if self.window.isMinimized():
                self.window.showNormal()
            else:
                self.show_window()
            self.window.say("右键选择功能；查询、设置和确认都在宠物气泡里。", 6000)

    def _confirm(self, title, summary, action):
        return self.window.ask(config.redact(title + "\n" + summary), [("确认" + action, True)]) is True

    def _choose(self, title, choices):
        page = 0
        while choices and not self.closing:
            entries = choices[page * 5:(page + 1) * 5]
            controls = [(str(label)[:46], index + page * 5) for index, (label, _) in enumerate(entries)]
            if page:
                controls.append(("上一页", "prev"))
            if (page + 1) * 5 < len(choices):
                controls.append(("下一页", "next"))
            result = self.window.ask(config.redact(title), controls)
            if result == "next":
                page += 1
            elif result == "prev":
                page -= 1
            else:
                return choices[result][1] if isinstance(result, int) else None
        return None

    def _input(self, title, placeholder="", secret=False):
        return self.window.ask(title, [("保存" if secret else "确定", "__input__")], placeholder=placeholder, secret=secret)

    def _business_message(self, message, *, personal=True):
        self._business_status = config.redact(message, personal=personal)
        if not self.closing:
            self.window.say(self._business_status, 15000)

    def _render_progress(self):
        if getattr(self, "_progress_requested", False):
            from ..progress import report
            text = report(self.progress_snapshot) if self.progress_snapshot else self.monitor_error
            if self.progress_snapshot and any(item.stale for item in self.progress_snapshot.sessions):
                text += "\n过时日志：当前任务状态未知，不能据此判定完成。"
            if self._progress_error:
                text = self._progress_error + "\n最后快照（可能过时）：\n" + text
            self._business_message(text)
            self._progress_requested = False

    def _render_usage(self):
        if getattr(self, "_usage_requested", False):
            from ..metering import report
            text = self.monitor_error
            if self.usage_snapshot:
                snapshot, projected, sample_ok = self.usage_snapshot
                text = report(snapshot, projected, 0, sample_ok)
                if not sample_ok:
                    text += "\n样本不足，窗口外推未知。"
            if self._usage_error:
                text = self._usage_error + "\n最后快照（可能过时）：\n" + text
            self._business_message(text + "\n本机台账不等于厂商余额。")
            self._usage_requested = False

    def _render_accounts(self):
        if getattr(self, "_accounts_requested", False) and not self.account_refreshing:
            lines = [self.account_error] if self.account_error else []
            if self.account_snapshot:
                for account in self.account_snapshot.accounts:
                    stamp = "更新时间 UNKNOWN" if account.updated_at is None else datetime.fromtimestamp(account.updated_at).strftime("%m-%d %H:%M 更新")
                    state = "stale（最后快照，刷新失败）" if self.account_error else account.status
                    lines.append(f"{config.redact(account.label)} · {state} · {stamp} · {config.redact(account.message)}")
                    for bucket in account.buckets:
                        value = bucket.used_percent
                        used = "UNKNOWN" if value is None or not math.isfinite(value) or not 0 <= value <= 100 else f"已用 {value:g}%"
                        reset = "重置时间 UNKNOWN" if bucket.resets_at is None else datetime.fromtimestamp(bucket.resets_at).strftime("%m-%d %H:%M 重置")
                        lines.append(f"{config.redact(bucket.name)}: {used}；{reset}")
                    def amount(value):
                        return format(value, "f") if isinstance(value, Decimal) and value.is_finite() and value >= 0 else "UNKNOWN"
                    lines += [f"{config.redact(b.currency)} 余额 {amount(b.total)}；赠送 {amount(b.granted)}；充值 {amount(b.topped_up)}" for b in account.balances]
                    if not account.buckets and not account.balances:
                        lines.append("余额 / 额度 UNKNOWN")
            self._business_message("\n".join(lines) or "账号额度 UNKNOWN，尚未取得快照。", personal=False)
            self._accounts_requested = False

    def _accounts_ready(self, snapshot):
        if self.closing:
            return
        self.account_snapshot = snapshot
        self.account_refreshing = False
        self.account_error = ""
        requested = getattr(self, "_accounts_requested", False)
        self._render_accounts()
        low = {(a.provider, b.name) for a in snapshot.accounts if a.status == "ok" for b in a.buckets
               if b.used_percent is not None and math.isfinite(b.used_percent) and 80 <= b.used_percent <= 100}
        previous = getattr(self, "_low_quota", set())
        self._low_quota = low
        if low - previous and not requested and self._reminders_enabled():
            self.window.say("账号额度提醒：" + "、".join(f"{provider} · {name} 已用 ≥80%" for provider, name in sorted(low - previous)), 10000)

    def _accounts_failed(self, message):
        if not self.closing:
            self.account_error = config.redact(message)
            self.account_refreshing = False
            self._render_accounts()

    def _progress_ready(self, snapshot):
        if self.closing:
            return
        self.progress_snapshot = snapshot
        self._progress_error = ""
        requested = getattr(self, "_progress_requested", False)
        self._render_progress()
        waiting = {item.record.session_id for item in snapshot.active if item.record.state in {"needsinput", "waiting", "error", "failed"}}
        previous = getattr(self, "_waiting_sessions", set())
        self._waiting_sessions = waiting
        if waiting - previous and not requested and self._reminders_enabled():
            self.window.say("有活跃会话需要你输入或处理错误。右键 → 会话进度查看。", 9000)
        if not self.tasks.busy:
            self._apply_progress()

    def action_progress(self):
        self._progress_requested = True
        self._render_progress()
        self._progress_requested = True
        if self.monitor:
            self.monitor.refresh_progress()

    def action_balance(self):
        self._usage_requested = True
        self._render_usage()
        self._usage_requested = True
        if self.monitor:
            self.monitor.refresh_usage()

    def action_quota(self):
        self._accounts_requested = True
        self.window.say("正在刷新账号额度…", 6000)
        self.account_refreshing = True
        if self.account_monitor:
            self.account_monitor.refresh()
        else:
            self._start_account_monitor()

    def _change_character(self, identifier):
        if not self.closing:
            try:
                self.window.set_character(identifier)
                self._pet_appearance_changed()
                self.window.say("已切换：" + character_name(identifier))
            except (ValueError, RuntimeError) as exc:
                self._error(str(exc))

    def _order_done(self, outcome):
        self.pay_url = outcome.pay_url
        if outcome.status == "placed":
            self.last_order_no = outcome.order_no
            self.pending_quote = self.pending_store = None
            self.payments = {**getattr(self, "payments", {}), "mcd": outcome.pay_url}
        self._business_message(f"{outcome.summary}\n状态：{outcome.status}\n订单号：{outcome.order_no or '未提交'}\n{outcome.reason}\n付款入口在右键菜单。")

    def action_payment(self, provider=""):
        pay = getattr(self, "payments", {}).get(provider, "") if provider else getattr(self, "pay_url", "")
        if not pay:
            self.window.say("本次运行暂无已知订单的付款链接。")
            return
        if config.redact(pay, personal=False) != pay:
            self._error("付款链接包含本机凭证，已阻止展示、复制和打开；请到官方 App 核对。")
            return
        result = self.window.ask("订单付款：请选择打开官方付款链接或复制。", [("打开付款链接", "open"), ("复制付款链接", "copy")])
        url = QUrl(pay)
        if url.scheme() not in {"https", "weixin"} or not url.host():
            self._error("付款链接格式无效，请到官方 App 核对。")
            return
        if result == "copy":
            QApplication.clipboard().setText(pay)
            self.window.say("付款链接已复制。")
        elif result == "open":
            if not QDesktopServices.openUrl(url):
                self._error("未能打开付款链接，可复制到官方客户端。")

    def _forget_payment(self, provider):
        pay = getattr(self, "payments", {}).pop(provider, "")
        if pay and getattr(self, "pay_url", "") == pay:
            self.pay_url = ""

    def _select_nutrition(self, facts):
        fact = self._choose("选择真实营养餐品", [(f.name, f) for f in facts])
        if fact is None:
            return None
        raw = self._input(f"{fact.name}\n输入份数（0.1–20），确认后才记账。", "例如 1 或 1.5")
        if raw is None:
            return None
        try:
            quantity = float(raw)
            if not math.isfinite(quantity) or not 0.1 <= quantity <= 20:
                raise ValueError()
        except ValueError:
            self._error("份数须为 0.1–20 的数字，未记账。")
            return None
        return (fact, quantity) if self._confirm("营养记账", f"{fact.name} × {quantity:g} 份；约 {fact.energy_kcal * quantity:g} kcal", "记账") else None

    def _reminders_enabled(self):
        return (os.environ.get("MCPET_REMINDERS", "true").lower() not in {"0", "false", "off"}
                and PetPreferences().load().get("reminders_enabled", True))

    def action_reminders(self):
        enabled = not self._reminders_enabled()
        with data_lock():
            store = PetPreferences()
            prefs = store.load()
            prefs["reminders_enabled"] = enabled
            if not store.save(prefs):
                self._error(store.error)
                return
        os.environ["MCPET_REMINDERS"] = str(enabled).lower()
        self.window.say("自动提醒已" + ("开启" if enabled else "关闭"))
        self.tray.set_entries(self.menu_entries())

    def _add_lunch_task(self):
        # QtDailyScheduler also emits fired; do not attach duplicate callbacks.
        for name, key, default in (("lunch", "MCPET_LUNCH_TIME", "11:30"), ("coffee", "MCPET_COFFEE_TIME", "15:00")):
            try:
                hour, minute = map(int, os.environ.get(key, default).split(":"))
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError()
            except ValueError:
                hour, minute = map(int, default.split(":"))
            previous = next((t.last_fired for t in self.schedule.tasks if t.name == name), None)
            self.schedule.tasks = [t for t in self.schedule.tasks if t.name != name]
            self.schedule.add(DailyTask(name, hour, minute, last_fired=previous))

    def on_lunch(self, late=False):
        if not self.closing and self._reminders_enabled():
            self.window.say("该吃饭啦，正在只读查询券和报价。")
            if config.mcp_token():
                self.action_coupon_report()
                self.action_best_deal()

    def on_scheduled(self, name, late):
        if name == "lunch":
            self.on_lunch(late)
        elif name == "coffee" and not self.closing and self._reminders_enabled():
            if config.luckin_token() and os.environ.get("MCPET_COFFEE_DEPT_ID"):
                self.action_coffee_products(automatic=True)
            else:
                self.window.say("咖啡时间到了。右键 → 瑞幸咖啡，选门店后可自动查询；不会自动下单。")

    def action_settings(self):
        self.window.say(f"饭点 {os.environ.get('MCPET_LUNCH_TIME', '11:30')}；咖啡 {os.environ.get('MCPET_COFFEE_TIME', '15:00')}\n麦当劳：{'已配置' if config.mcp_token() else '未配置'}；瑞幸：{'已配置' if config.luckin_token() else '未配置'}\n右键 → 设置，可逐项修改。", 12000)

    def _edit_setting(self, key, title):
        if self.tasks.busy:
            self.window.say("请等待当前请求结束后再修改设置。")
            return
        secret = key.endswith(("TOKEN", "KEY"))
        value = self._input(title + ("\n留空保留原值；清除请用菜单的清除凭证。" if secret else ""), "输入新值" if secret else os.environ.get(key, ""), secret)
        if value is not None and (value or not secret):
            self._save_settings({key: value})

    def _save_settings(self, values):
        if self.tasks.busy:
            self.window.say("请等待当前请求结束后再保存。")
            return
        try:
            for key, value in values.items():
                if key.endswith("_TIME"):
                    if datetime.strptime(value, "%H:%M").strftime("%H:%M") != value:
                        raise ValueError("时间须为 HH:MM")
                if key in {"MCPET_LONGITUDE", "MCPET_LATITUDE"}:
                    bound = 180 if key.endswith("LONGITUDE") else 90
                    if not math.isfinite(float(value)) or not -bound <= float(value) <= bound:
                        raise ValueError("经纬度无效")
            config.save_settings(values)
        except (ValueError, OSError) as exc:
            message = str(exc)
            for value in values.values():
                message = config.redact(message, token=value)
            self._error("保存失败：" + message)
            return
        self.pending_quote = self.pending_store = None
        self.tasks.worker.coffee.pending = None
        self._add_lunch_task()
        if "DEEPSEEK_API_KEY" in values:
            self.account_snapshot = None
            self.account_error = ""
            try:
                from ..accounts import DeepSeekBalanceSource
                if self.account_monitor:
                    self.account_monitor.reconfigure(deepseek_source=DeepSeekBalanceSource(config.deepseek_api_key()))
                self.action_quota()
            except Exception as exc:
                self._accounts_failed("凭证已保存，余额刷新失败：" + config.redact(str(exc)))
        self.window.say("设置已保存。凭证下次请求生效；日志目录修改后请重启。" + "\n".join(config.root_warnings(values)))

    def _clear_setting(self, key, title):
        if self._confirm("清除凭证", title + "；仅清除本机 McPet 配置。", "清除"):
            self._save_settings({key: ""})

    def run_coffee(self, key, fn, done, failed=None):
        return self.run_async(lambda: fn(self.tasks.worker.coffee), done, failed, key="coffee-" + key,
                              label="" if key == "order-watch" else "正在查询瑞幸")

    def _coffee_location(self):
        try:
            longitude = float(os.environ["MCPET_LONGITUDE"])
            latitude = float(os.environ["MCPET_LATITUDE"])
            if not math.isfinite(longitude + latitude) or not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
                raise ValueError()
            return longitude, latitude
        except (KeyError, ValueError):
            self.window.say("请先在右键 → 设置中填写经度、纬度；不会自动读取定位。")
            return None

    def action_coffee_shops(self):
        location = self._coffee_location()
        if location is None:
            return
        name = self._input("查找瑞幸门店（名称可留空）", "门店关键词")
        if name is None:
            return
        def done(shops):
            if not isinstance(shops, list) or not shops:
                self.window.say("瑞幸未返回可用门店。")
                return
            shop = self._choose("选择瑞幸门店", [(f"{s.get('deptName', '?')} · {s.get('distance', '?')} km", s) for s in shops])
            if shop is not None:
                config.save_settings({"MCPET_COFFEE_DEPT_ID": str(shop["deptId"])})
                self.window.say(config.redact(f"已选 {shop.get('deptName', shop['deptId'])}；右键 → 瑞幸咖啡 → 查商品。"))
        self.run_coffee("shops", lambda s: s.query("queryShopList", {"longitude": location[0], "latitude": location[1], "deptName": name}), done)

    def action_coffee_products(self, automatic=False):
        try:
            dept = int(os.environ.get("MCPET_COFFEE_DEPT_ID", ""))
        except ValueError:
            self.window.say("先查找并选择瑞幸门店。")
            return
        query = os.environ.get("MCPET_COFFEE_QUERY", "拿铁") if automatic else self._input("想喝什么？", os.environ.get("MCPET_COFFEE_QUERY", "拿铁"))
        if not query:
            return
        def done(products):
            if not isinstance(products, list) or not products:
                self.window.say("瑞幸未返回匹配商品。")
                return
            if automatic:
                self._business_message("咖啡时间 · 只读查询\n" + "\n".join(f"{p.get('productName', '?')} · 预估 ¥{p.get('estimatePrice', '?')}" for p in products[:8]) + "\n右键查商品可选规格并预览订单。")
                return
            product = self._choose("瑞幸商品（预估价，实付以预览为准）", [(f"{p.get('productName', '?')} · ¥{p.get('estimatePrice', '?')}", p) for p in products])
            if product:
                self.coffee_product = copy.deepcopy(product)
                self.coffee_dept = dept
                self.window.say(config.redact(f"已选 {product.get('productName', '?')}；右键可调整规格或预览订单。"))
        self.run_coffee("products", lambda s: s.query("searchProductForMcp", {"deptId": dept, "query": query}), done)

    def action_coffee_specs(self):
        product = getattr(self, "coffee_product", None)
        if not product:
            self.window.say("先查商品并选择一款咖啡。")
            return
        def details(node):
            choices = [(f"{group.get('attributeName', '')} · {sub.get('attributeName', '')}", (group['attributeId'], sub['attributeId']))
                       for group in node.get("productAttrs", []) for sub in group.get("productSubAttrs", []) if sub.get("canSelected") != 0]
            chosen = self._choose("选择要切换的规格", choices)
            if chosen is None:
                return
            args = {"deptId": self.coffee_dept, "productId": node["productId"], "skuCode": node["skuCode"], "amount": 1,
                    "attrOperationParam": {"attributeId": chosen[0], "subAttr": {"attributeId": chosen[1], "operation": 3}}}
            def switched(updated):
                self.coffee_product = updated
                self.tasks.worker.coffee.pending = None
                self.window.say("规格已更新；请重新预览订单核对。")
            self.run_coffee("spec-switch", lambda s: s.query("switchProduct", args), switched)
        self.run_coffee("details", lambda s: s.query("queryProductDetailInfo", {"deptId": self.coffee_dept, "productId": product["productId"]}), details)

    def action_coffee_preview(self):
        product = getattr(self, "coffee_product", None)
        location = self._coffee_location()
        if not product or location is None:
            self.window.say("先设置位置、选门店和商品。")
            return
        raw = self._input("咖啡数量（1–10）", "1")
        if raw is None:
            return
        try:
            amount = int(raw)
            if not 1 <= amount <= 10:
                raise ValueError()
        except ValueError:
            self._error("数量须为 1–10 的整数。")
            return
        items = [{"productId": product["productId"], "skuCode": product["skuCode"], "amount": amount}]
        self.run_coffee("preview", lambda s: s.prepare(self.coffee_dept, items, *location), lambda r: self._business_message(r["summary"] + "\n右键 → 确认瑞幸订单，核对后再提交。"))

    def action_coffee_confirm(self):
        pending = self.tasks.worker.coffee.pending
        if not pending:
            self.window.say("请先预览瑞幸订单。")
            return
        if self._confirm("确认瑞幸订单", pending["summary"], "下单"):
            if self.tasks.worker.coffee.pending is not pending:
                self.window.say("瑞幸候选订单已变化，请重新预览确认。")
                return
            self.run_coffee("submit", lambda s: s.confirm(True), self._coffee_order_done)

    def _coffee_order_done(self, result):
        if result.get("status") == "placed":
            self.coffee_order = result["order_id"]
            self.pay_url = result.get("pay_url", "")
            self.payments = {**getattr(self, "payments", {}), "luckin": self.pay_url}
            self._coffee_watch_order = self.coffee_order
            self._coffee_watch_deadline = time.monotonic() + 3600
            self._coffee_watch_status = None
        self._business_message("\n".join(str(result.get(k, "")) for k in ("status", "summary", "order_id", "reason", "warning")) + "\n付款入口在右键菜单。")

    def action_coffee_order(self, use_known=True):
        order = getattr(self, "coffee_order", "") if use_known else ""
        if not order:
            order = self._input("查询瑞幸订单号", "官方订单号")
        if not order:
            return
        def done(node):
            self.coffee_order = order
            self._business_message(f"瑞幸订单 {order}\n{node.get('orderStatusName', '状态 UNKNOWN')}\n取餐码：{node.get('takeMealCodeInfo', {}).get('code', 'UNKNOWN')}")
        self.run_coffee("order", lambda s: s.query("queryOrderDetailInfo", {"orderId": order}), done)

    def _poll_coffee_order(self):
        if (self.closing or not self._reminders_enabled() or not config.luckin_token()
                or time.monotonic() >= getattr(self, "_coffee_watch_deadline", 0)):
            return
        order = self._coffee_watch_order
        def done(node):
            status = node.get("orderStatus")
            if status != self._coffee_watch_status:
                self._coffee_watch_status = status
                self.window.say(config.redact(f"瑞幸订单：{node.get('orderStatusName', '状态 UNKNOWN')}\n取餐码：{(node.get('takeMealCodeInfo') or {}).get('code', 'UNKNOWN')}"), 12000)
            if status in {80, 100}:
                self._coffee_watch_deadline = 0
        def failed(message):
            self._coffee_watch_deadline = 0
            self._error("瑞幸查单失败，自动查单已暂停：" + message)
        self.run_coffee("order-watch", lambda s: s.query("queryOrderDetailInfo", {"orderId": order}), done, failed)

    def action_coffee_cancel(self):
        order = getattr(self, "coffee_order", "")
        if not order:
            self.window.say("请先查单，核对要取消的瑞幸订单号。")
            return
        if self._confirm("确认瑞幸撤单", "订单号：" + order, "撤单"):
            def done(result):
                if result.get("status") == "cancelled":
                    self._forget_payment("luckin")
                    self._coffee_watch_deadline = 0
                self._business_message(str(result))
            self.run_coffee("cancel", lambda s: s.cancel(order, True), done)

    def menu_entries(self):
        actions = [("闲逛：" + ("开" if self.window.roaming_enabled else "关"), self.action_roaming),
                   ("休息 / 继续", self.action_resting), ("停止动作", self.action_stop_animation)]
        if self.window.sheet and "frying" in self.window.sheet.meta.get("animations", {}):
            actions += [("炸薯条 · 循环", self.action_frying), ("换装", self.action_outfit)]
        if self.window.character_id == "deepseek":
            actions += [("默认套装", self.action_skin_default), ("麦麦套装", self.action_skin_maimai)]
        settings = [("查看设置", self.action_settings), ("自动提醒：" + ("开" if self._reminders_enabled() else "关"), self.action_reminders)]
        setting_groups = {"时间与位置": [], "账号凭证": [], "日志来源": []}
        for key, label in (("MCPET_CITY", "城市"), ("MCPET_LUNCH_TIME", "饭点"), ("MCPET_COFFEE_TIME", "咖啡时间"),
                           ("MCPET_COFFEE_QUERY", "自动查询咖啡"), ("MCPET_LONGITUDE", "经度"), ("MCPET_LATITUDE", "纬度"),
                           ("MCD_MCP_TOKEN", "麦当劳 Token"), ("LUCKIN_MCP_TOKEN", "瑞幸 Token"), ("DEEPSEEK_API_KEY", "DeepSeek Key"),
                           ("MCPET_AGENT_ROOT_CLAUDE", "Claude 日志目录"), ("MCPET_AGENT_ROOT_CODEX", "Codex 日志目录"), ("MCPET_AGENT_ROOT_GENERIC", "通用日志目录")):
            group = "日志来源" if "AGENT_ROOT" in key else "账号凭证" if key.endswith(("TOKEN", "KEY")) else "时间与位置"
            setting_groups[group].append((label, lambda k=key, t=label: self._edit_setting(k, t)))
        setting_groups["账号凭证"].append(("清除凭证", [(title, lambda k=key, t=title: self._clear_setting(k, t)) for key, title in
                                     (("MCD_MCP_TOKEN", "麦当劳 Token"), ("LUCKIN_MCP_TOKEN", "瑞幸 Token"), ("DEEPSEEK_API_KEY", "DeepSeek Key"))]))
        settings.extend(setting_groups.items())
        return [("会话与额度", [("会话进度", self.action_progress), ("本机用量", self.action_balance), ("账号额度 / 余额", self.action_quota)]),
                ("麦当劳", [("查优惠券", self.action_coupon_report), ("主动领券", self.action_claim_coupons), ("今天最划算", self.action_best_deal),
                            ("确认订单", self.action_place_order), ("撤销本次订单", self.action_cancel_last_order)]),
                ("瑞幸咖啡", [("查找 / 选择门店", self.action_coffee_shops), ("查商品 / 选择咖啡", self.action_coffee_products),
                             ("调整规格", self.action_coffee_specs), ("预览订单", self.action_coffee_preview), ("确认瑞幸订单", self.action_coffee_confirm),
                             ("查订单 / 取餐码", self.action_coffee_order), ("查询其他订单", lambda: self.action_coffee_order(False)), ("取消已核对订单", self.action_coffee_cancel),
                             ("登录瑞幸开放平台", lambda: QDesktopServices.openUrl(QUrl("https://open.lkcoffee.com/mcp")))]),
                ("营养台账", [("选择餐品 / 记账", self.action_log_meal), ("今日营养", self.action_nutrition_summary)]),
                ("订单付款", [("麦当劳付款", lambda: self.action_payment("mcd")), ("瑞幸付款", lambda: self.action_payment("luckin"))]),
                ("角色与动作", [(character_name(i), lambda c=i: self._change_character(c)) for i in CHARACTER_IDS] + [None] + actions),
                ("设置", settings), None, ("隐藏宠物", self.toggle_window), ("退出", self.quit)]
