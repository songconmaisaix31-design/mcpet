"""McPet capabilities for existing Agent conversations, without Qt or an LLM."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from datetime import datetime
from decimal import Decimal
import json
import math
import os
from pathlib import Path
import time

from . import config
from .agent_local import data_lock
from .mcd_mcp.brain import McdBrain, StoreInfo
from .mcd_mcp.client import McdMcpClient, McpError
from .mcd_mcp.guards import OrderGuard, OrderAuditEntry
from .nutrition.ledger import NutritionLedger
from .pet.preferences import PetPreferences
from .pet.skins import SKINS, validate_skin
from .pet.identity import DEFAULT_CHARACTER, CHARACTER_NAMES

ASSETS = config.PROJECT_ROOT / "assets"
CHARACTERS = CHARACTER_NAMES
ACTIONS = {"idle", "working", "thinking", "greet", "happy", "sleeping", "eating", "frying", "outfit"}


def public(value):
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dict):
        return {key: public(item) for key, item in value.items() if key not in {"raw", "raw_claim"}}
    if isinstance(value, (list, tuple)):
        return [public(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, str):
        return config.redact(value, personal=False)
    return value


class AgentService:
    def __init__(self, client_factory=None):
        self.client_factory = client_factory or self._client
        self.pending_order = None
        self.pending_nutrition = {}
        self.deal_options = None
        from .luckin import LuckinService
        self.coffee = LuckinService()

    def coffee_query(self, tool, arguments):
        return {"status": "ok", "data": self.coffee.query(tool, arguments)}

    def coffee_prepare(self, dept_id, products, longitude, latitude):
        return self.coffee.prepare(dept_id, products, longitude, latitude)

    def coffee_confirm(self, confirmed=False):
        return self.coffee.confirm(confirmed)

    def coffee_cancel(self, order_id, confirmed=False):
        return self.coffee.cancel(order_id, confirmed)

    @staticmethod
    def _client():
        config.load_env()
        token = config.mcp_token()
        if not token:
            raise McpError("未配置麦当劳凭证。沿用已有 MCD_MCP_TOKEN 配置即可，无需新的模型 Key")
        client = McdMcpClient(token, config.mcp_url(), max_retries_on_429=0)
        try:
            client.initialize()
        except Exception:
            client.close()
            raise
        return client

    @contextmanager
    def brain(self):
        with self.client_factory() as client:
            yield McdBrain(client, OrderGuard())

    def status(self):
        with data_lock():
            prefs = PetPreferences().load()
            character = prefs.get("character_id", DEFAULT_CHARACTER)
            if character not in CHARACTERS:
                character = DEFAULT_CHARACTER
            skin = prefs.get("skin_id", "default") if character == "deepseek" else "default"
            if skin not in SKINS:
                skin = "default"
            animation = prefs.get("action_animation", prefs.get("action", "idle"))
            return {"hosted_by": "your Agent", "separate_window": False,
                    "character_id": character, "character_name": CHARACTERS[character],
                    "skin_id": skin, "skin_name": SKINS[skin],
                    "available_skins": SKINS if character == "deepseek" else {"default": SKINS["default"]},
                    "pending_skin_id": prefs.get("pending_skin_id"),
                    "action": prefs.get("action", "idle"),
                    "animation": self.animation_info(character, animation, skin),
                    "interaction": "在这里告诉我想查什么、想换哪套衣服就好啦",
                    "model_requests": False}

    def pet(self, action="idle", character_id="", loop=False, skin_id=""):
        if action not in ACTIONS | {"stop"}:
            raise ValueError("未知动作")
        with data_lock():
            preferences = PetPreferences()
            prefs = preferences.load()
            character = character_id or prefs.get("character_id", DEFAULT_CHARACTER)
            if character not in CHARACTERS:
                raise ValueError("未知角色")
            skin = skin_id or (prefs.get("deepseek_skin_id", prefs.get("skin_id", "default")) if character == "deepseek" else "default")
            validate_skin(character, skin)
            prefs.update(character_id=character, action="idle" if action == "stop" else action,
                         resting=action == "sleeping", skin_id=skin,
                         action_loop=bool(loop and action == "frying"), pet_command_at=time.time())
            prefs.pop("action_until", None)
            prefs.pop("pending_skin_id", None)
            prefs.pop("action_animation", None)
            animation = action
            if character == "deepseek":
                if action == "frying":
                    skin = prefs["skin_id"] = "maimai"
                elif action == "outfit":
                    prefs["pending_skin_id"] = "maimai" if skin == "default" else "default"
                    animation = "outfit" if skin == "default" else "outfit-default"
                prefs["deepseek_skin_id"] = skin
            prefs["action_animation"] = animation
            if action in {"frying", "outfit"} and not (loop and action == "frying"):
                prefs["action_until"] = time.time() + self.animation_info(character, animation, skin)["duration_seconds"]
            if not preferences.save(prefs):
                raise OSError(preferences.error)
        return self.status()

    @staticmethod
    def animation_info(character, action, skin="default"):
        if character == "maimai" and action in {"frying", "outfit"}:
            return {"uri": f"mcpet://animation/maimai/{action}", "mime_type": "image/gif",
                    "duration_seconds": 10.16, "rendering": "宿主支持图像资源时可展示；不创建播放窗口"}
        if character == "deepseek":
            if action in {"frying", "outfit", "outfit-default"}:
                return {"uri": f"mcpet://animation/deepseek/{action}", "mime_type": "image/gif",
                        "duration_seconds": 2.40 if action == "frying" else 3.84,
                        "rendering": "支持图像资源的宿主可展示；已运行的桌宠可接收此动作"}
            if skin == "maimai":
                return {"uri": "mcpet://skin/deepseek/maimai", "mime_type": "image/gif",
                        "duration_seconds": 5.04, "rendering": "持久麦麦皮肤；无对应穿装动作的状态复用穿装待机"}
        return {"rendering": "宿主中的角色状态；原素材保留，跨宿主动画显示能力未假定"}

    @staticmethod
    def animation(action, character="maimai"):
        if action not in ({"frying", "outfit", "outfit-default"} if character == "deepseek" else {"frying", "outfit"}):
            raise ValueError("未知动画资源")
        return (ASSETS / ("deepseek-actions" if character == "deepseek" else "maimai-actions") / f"{action}.gif").read_bytes()

    def settings(self):
        config.load_env()
        return {"city": os.environ.get("MCPET_CITY", "北京"),
                "lunch_time": os.environ.get("MCPET_LUNCH_TIME", "11:30"),
                "mcd_configured": bool(config.mcp_token()),
                "luckin_configured": bool(config.luckin_token()),
                "coffee_time": os.environ.get("MCPET_COFFEE_TIME", "15:00"),
                "deepseek_configured": bool(config.deepseek_api_key()),
                "independent_model_required": False,
                "credentials": "沿用你本机的小钥匙，聊天里不会显示密钥哦"}

    def configure(self, city="", lunch_time="", reminders_enabled=None, agent_roots=None, coffee_time=""):
        values = {}
        if city:
            if len(city) > 80 or any(c in city for c in "\r\n\0"):
                raise ValueError("城市格式无效")
            values["MCPET_CITY"] = city
        if lunch_time:
            parsed = datetime.strptime(lunch_time, "%H:%M")
            if parsed.strftime("%H:%M") != lunch_time:
                raise ValueError("提醒时间请写成 HH:MM，比如 11:30 哦")
            values["MCPET_LUNCH_TIME"] = lunch_time
        if coffee_time:
            parsed = datetime.strptime(coffee_time, "%H:%M")
            if parsed.strftime("%H:%M") != coffee_time:
                raise ValueError("提醒时间请写成 HH:MM，比如 11:30 哦")
            values["MCPET_COFFEE_TIME"] = coffee_time
        if agent_roots is not None:
            keys = {"claude": "MCPET_AGENT_ROOT_CLAUDE", "codex": "MCPET_AGENT_ROOT_CODEX",
                    "generic": "MCPET_AGENT_ROOT_GENERIC"}
            if set(agent_roots) - set(keys):
                raise ValueError("日志来源只支持 claude/codex/generic")
            for source, raw in agent_roots.items():
                if not isinstance(raw, str) or not raw.strip() or any(c in raw for c in "\r\n\0"):
                    raise ValueError("日志目录格式无效")
                path = Path(os.path.expandvars(raw)).expanduser().resolve()
                if not path.is_dir():
                    raise ValueError("日志目录不存在；只使用用户明确指定的已有目录")
                values[keys[source]] = str(path)
        with data_lock():
            # save_settings normally accepts the public whitelist. Lunch time is
            # a non-secret setting now exposed through the same existing writer.
            if values:
                config.save_settings(values)
            if reminders_enabled is not None:
                preferences = PetPreferences()
                prefs = preferences.load()
                prefs["reminders_enabled"] = bool(reminders_enabled)
                if not preferences.save(prefs):
                    raise OSError(preferences.error)
        return self.settings()

    def coupons(self):
        with self.brain() as brain:
            return public(brain.coupon_roundup(claim=False))

    def claim_coupons(self, confirmed=False):
        if confirmed is not True:
            return {"status": "needs_confirmation", "summary": "要领取当前账号全部可领的优惠券吗？确认这个范围后我再帮你领哦"}
        with data_lock(), self.brain() as brain:
            try:
                result = brain.coupon_roundup(claim=True)
                return {"status": "claimed" if result.claim_ok else "failed", "result": public(result)}
            except Exception as exc:
                return {"status": "delivery_unknown", "reason": config.redact(str(exc)),
                        "retry": "不要自动重发领取；先查询当前优惠券核对"}

    def deals(self, keyword="", store_keyword=""):
        with self.brain() as brain:
            store = (brain.resolve_default_store(store_keyword=store_keyword)
                     if store_keyword else brain.resolve_default_store())
            if store is None:
                raise McpError("没有可用门店，请在原 Agent 会话设置城市")
            quotes = brain.best_deal(store, keyword=keyword)
            self.deal_options = (store, quotes)
            return {"store": public(store), "quotes": public(quotes), "status": "known" if quotes else "unavailable"}

    def prepare_order(self, product_codes, meal_names, store, coupon_id="", coupon_code="",
                      coupon_name="", take_way_code="take-in-store"):
        if take_way_code not in {"eat-in", "take-in-store"}:
            raise ValueError("取餐方式须为堂食或外带")
        if not product_codes or len(product_codes) != len(meal_names):
            raise ValueError("请先选择真实报价中的餐品编码和名称")
        if self.deal_options is None:
            raise ValueError("请先查询真实报价，再选择其中的门店与餐品")
        known_store, quotes = self.deal_options
        known = {quote.meal_code: quote for quote in quotes}
        if store.get("store_code") != known_store.store_code or any(code not in known for code in product_codes):
            raise ValueError("门店或餐品不在本会话真实报价中")
        if meal_names != [known[code].meal_name for code in product_codes]:
            raise ValueError("餐品名称与真实报价不一致")
        if coupon_id or coupon_code:
            if not any(quote.coupon_id == coupon_id and quote.coupon_code == coupon_code
                       and quote.meal_code in product_codes for quote in quotes):
                raise ValueError("优惠券不在本会话真实报价中")
            coupon_name = next(quote.coupon_name for quote in quotes
                               if quote.coupon_id == coupon_id and quote.coupon_code == coupon_code
                               and quote.meal_code in product_codes)
        else:
            coupon_name = ""
        actual_store = StoreInfo(**asdict(known_store))
        if not actual_store.business_status:
            raise ValueError("门店未营业")
        with data_lock(), self.brain() as brain:
            amount = brain.quote_order(actual_store, product_codes, coupon_id=coupon_id or None,
                                       coupon_code=coupon_code or None)
            brain.guard.check(amount)
            summary = brain.render_order_summary(actual_store.store_name, meal_names, amount,
                                                  coupon_name, "堂食" if take_way_code == "eat-in" else "外带")
        self.pending_order = {"store": actual_store, "product_codes": list(product_codes),
                              "meal_names": list(meal_names), "coupon_id": coupon_id or None,
                              "coupon_code": coupon_code or None, "coupon_name": coupon_name,
                              "take_way_code": take_way_code, "amount": amount,
                              "summary": summary, "prepared_at": time.time()}
        return {"status": "needs_confirmation", "summary": summary, "amount_cents": amount,
                "next": "先核对上面的门店、餐品和实付，确认好了我再下单哦"}

    def confirm_order(self, confirmed=False):
        pending = self.pending_order
        if not pending:
            raise ValueError("没有待确认订单，请先准备订单")
        if confirmed is not True:
            return {"status": "needs_confirmation", "summary": pending["summary"]}
        if time.time() - pending["prepared_at"] > 300:
            self.pending_order = None
            return {"status": "expired", "reason": "报价已过期，请重新准备订单"}
        # Consume before external I/O. Ambiguous failures never permit an
        # automatic replay of the same confirmation in this host session.
        self.pending_order = None
        with data_lock(), self.brain() as brain:
            options = {key: pending[key] for key in ("coupon_id", "coupon_code", "coupon_name", "take_way_code")}
            current = brain.quote_order(pending["store"], pending["product_codes"],
                                        coupon_id=options["coupon_id"], coupon_code=options["coupon_code"])
            if current != pending["amount"]:
                return {"status": "needs_confirmation", "reason": "价格已变化，请重新准备并确认订单",
                        "amount_cents": current}
            # Freeze the reviewed quote inside this call; place_order otherwise
            # re-queries and could submit a newly changed, unreviewed price.
            brain.quote_order = lambda *args, **kwargs: current
            try:
                outcome = brain.place_order(pending["store"], pending["product_codes"],
                                            pending["meal_names"], confirmed=True, **options)
                if outcome.status == "placed" and not outcome.order_no:
                    try:
                        brain.guard.mark_latest_delivery_unknown("提交响应缺少订单号；先核对账号，不可自动重发")
                    except OSError:
                        pass
                    return {"status": "delivery_unknown", "summary": pending["summary"],
                            "reason": "提交响应缺少订单号；请核对账号，不要自动重下"}
                return public(outcome)
            except Exception as exc:
                try:
                    brain.guard.record(OrderAuditEntry(datetime.now().isoformat(timespec="seconds"),
                        "create-order", pending["store"].store_name, "、".join(pending["meal_names"]),
                        current, status="delivery_unknown", note="结果不确定；不可自动重发"))
                except OSError:
                    pass  # Preserve external ambiguity even if local audit persistence fails.
                return {"status": "delivery_unknown", "summary": pending["summary"],
                        "reason": config.redact(str(exc)), "retry": "先核对账号订单，不要自动重下"}

    def cancel_order(self, order_no, confirmed=False):
        if not order_no or len(order_no) > 128:
            raise ValueError("请输入需要撤销的具体订单号")
        if confirmed is not True:
            return {"status": "needs_confirmation", "summary": f"撤销订单 {order_no}，用户明确确认后再调用"}
        with data_lock(), self.brain() as brain:
            try:
                return {"status": "cancelled" if brain.cancel_order(order_no) else "rejected", "order_no": order_no}
            except Exception as exc:
                return {"status": "delivery_unknown", "order_no": order_no,
                        "reason": config.redact(str(exc)), "retry": "先核对订单状态，不要自动重发撤单"}

    def nutrition(self, keyword=""):
        with self.brain() as brain:
            facts = brain.nutrition(keyword)
        self.pending_nutrition = {fact.name: fact for fact in facts}
        return {"foods": public(facts), "source": "麦当劳真实营养查询"}

    def nutrition_log(self, meal_name, quantity=1.0, confirmed=False):
        if isinstance(quantity, bool) or not math.isfinite(quantity) or not 0.25 <= quantity <= 20:
            raise ValueError("份数须在 0.25–20 之间")
        fact = self.pending_nutrition.get(meal_name)
        if fact is None:
            raise ValueError("请先查询并选择当前会话返回的具体营养餐品，不接受模型猜测营养值")
        if confirmed is not True:
            return {"status": "needs_confirmation", "meal_name": meal_name, "quantity": quantity}
        with data_lock():
            entry = NutritionLedger().add_fact(fact, quantity=quantity)
        return {"status": "recorded", "entry": public(entry)}

    def nutrition_today(self):
        with data_lock():
            ledger = NutritionLedger()
            return {"entries": public(ledger.day()), "totals": ledger.totals(), "summary": ledger.summary()}

    def balances(self, source="all"):
        from .accounts.sources import OrcaAccountSource, DeepSeekBalanceSource
        if source not in {"all", "orca", "deepseek"}:
            raise ValueError("未知额度来源")
        config.load_env()
        accounts = []
        if source in {"all", "orca"}:
            accounts.extend(OrcaAccountSource().fetch())
        if source in {"all", "deepseek"}:
            accounts.append(DeepSeekBalanceSource(config.deepseek_api_key() or "").fetch())
        return {"accounts": public(accounts), "observed_at": time.time(),
                "note": "订阅额度保留独立窗口/桶；本机 token 台账不等于厂商余额"}

    def progress(self):
        from .progress import build_tracker
        snapshot = build_tracker(roots=self.agent_roots(), watch_processes=False).snapshot()
        return {"status": snapshot.status, "sources": snapshot.sources, "errors": public(snapshot.errors),
                "sessions": [{"source": session.record.source, "session_id": session.record.session_id,
                              "label": config.redact(session.label), "state": session.record.state,
                              "stale": session.stale, "context_percent": session.context_percent,
                              "context_estimated": session.record.context_limit_estimated,
                              "updated_at": session.record.updated_at} for session in snapshot.sessions],
                "note": "上下文占用不是完成进度哦；idle、Stop 或日志停更都不能说明任务成功"}

    def usage(self, refresh=False):
        from .metering import build_meter, report, reminder_level
        with data_lock():
            meter = build_meter(roots=self.agent_roots(), state_path=config.data_dir() / "agent-usage.json")
            if refresh:
                meter.scan()
            snapshot = meter.snapshot()
            projection = meter.window_projection(snapshot)
            return {"status": snapshot.status, "snapshot": public(snapshot),
                    "summary": config.redact(report(snapshot, *projection)),
                    "reminder_level": reminder_level(snapshot, projection[0] if projection[2] else snapshot.window.tokens),
                    "note": "这是本机用量小本本哦，不是厂商额度或账单"}

    def host_usage_reminder(self):
        """Native usage events only; never scan unrelated transcript roots."""
        from .agentbridge import AgentRoots
        from .metering import build_meter, bubble, reminder_level
        with data_lock():
            prefs_store = PetPreferences()
            prefs = prefs_store.load()
            if prefs.get("reminders_enabled", True) is False:
                return []
            inbox = config.data_dir() / "inbox"
            meter = build_meter(roots=AgentRoots(roots={"generic": [inbox]}),
                                state_path=config.data_dir() / "agent-host-usage.json")
            meter.scan()
            snapshot = meter.snapshot()
            projected, _, sample_ok = meter.window_projection(snapshot)
            level = reminder_level(snapshot, projected if sample_ok else snapshot.window.tokens)
            previous = prefs.get("agent_usage_level")
            prefs["agent_usage_level"] = level
            if not prefs_store.save(prefs):
                raise OSError(prefs_store.error)
            if level in {"busy", "heavy"} and level != previous:
                return [config.redact(bubble(snapshot, projected, sample_ok)) + " 本机台账，不等于厂商余额。"]
            return []

    @staticmethod
    def agent_roots():
        from .agentbridge import resolve_roots
        roots = resolve_roots(config_path=config.agent_config_path())
        inbox = config.data_dir() / "inbox"
        if inbox.is_dir() and inbox not in roots.for_provider("generic"):
            roots.roots.setdefault("generic", []).append(inbox)
        return roots

    def reminders(self, now=None):
        from .schedule.core import DailySchedule, DailyTask
        now = now or datetime.now()
        with data_lock():
            prefs_store = PetPreferences()
            prefs = prefs_store.load()
            if prefs.get("reminders_enabled", True) is False:
                return {"messages": []}
            raw = os.environ.get("MCPET_LUNCH_TIME", "11:30")
            try:
                hour, minute = map(int, raw.split(":"))
                if not 0 <= hour < 24 or not 0 <= minute < 60:
                    raise ValueError()
            except ValueError:
                hour, minute = 11, 30
            task = DailyTask("lunch", hour, minute, last_fired=prefs.get("agent_lunch_last_fired"))
            due = DailySchedule([task]).fire(now)
            if prefs.get("agent_lunch_last_fired") != task.last_fired:
                prefs["agent_lunch_last_fired"] = task.last_fired
                if not prefs_store.save(prefs):
                    raise OSError(prefs_store.error)
            return {"messages": ["饭点到啦～想吃什么？叫我看看今天的券和价格吧。" for _ in due],
                    "delivery": "原 Agent 会话/宿主原生通知，非独立弹窗"}
