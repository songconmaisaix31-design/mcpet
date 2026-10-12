"""McPet 默认 stdio 入口；显式 --desktop 才装配旧桌面与后台 worker。"""
from __future__ import annotations

import copy
import atexit
import hashlib
import inspect
import json
import os
import sys

# The public command now belongs to the existing Agent host. Keep the old GUI
# only behind an explicit compatibility flag and avoid importing Qt headlessly.
if __name__ == "__main__" and "--desktop" not in sys.argv:
    from src.agent_mcp import main as agent_main
    agent_main()
    raise SystemExit(0)

from collections import deque
from datetime import datetime

from PySide6.QtCore import QObject, QThread, Signal, Slot, QTimer, QLockFile, QEvent
from PySide6.QtGui import QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from . import config
from .mcd_mcp.brain import McdBrain, OrderOutcome
from .mcd_mcp.client import McdMcpClient, McpError
from .mcd_mcp.guards import OrderGuard, OrderAuditEntry
from .mcd_mcp.validation import validate_arguments
from .mcd_mcp import tools as T
from .nutrition.ledger import NutritionLedger
from .pet.dialogs import character_preview
from .pet.spritesheet import SpriteLoadError, SpriteSheet
from .pet.tray import PetTray
from .pet.window import PetWindow
from .schedule.clock import DailySchedule, DailyTask, QtDailyScheduler
from .luckin import LuckinService
from .pet.functions import PetFunctions


class _SerialWorker(QObject):
    completed = Signal(object, object, str)
    closed = Signal()
    cleanup_failed = Signal(str)

    def __init__(self, guard):
        super().__init__()
        self.guard = guard
        self.client = self.brain = None
        self._credentials = None
        self.coffee = LuckinService(guard=guard)

    def ensure_client(self):
        """仅在唯一 worker 中调用；失败初始化不发布半成品 client。"""
        token = config.mcp_token()
        if not token:
            raise McpError("缺少麦当劳 Token，请右键 → 设置 → 麦当劳 Token。会话观测无需凭证。")
        credentials = (token, config.mcp_url())
        if self.brain is not None and self._credentials == credentials:
            return self.brain
        if self.client is not None:
            self.client.close()
        self.client = self.brain = None
        # 账号写请求不能因网络未知效果自动重试；同一客户端只发送一次。
        provisional = McdMcpClient(token, credentials[1], max_retries_on_429=0)
        try:
            provisional.initialize()
        except Exception:
            provisional.close()
            raise
        self.client = provisional
        self.brain = McdBrain(provisional, self.guard)
        self._credentials = credentials
        return self.brain

    @Slot(object)
    def execute(self, job):
        key, fn = job
        try:
            self.completed.emit(key, fn(), "")
        except Exception as exc:
            self.completed.emit(key, None, config.redact(f"{type(exc).__name__}: {exc}"))

    @Slot()
    def close(self):
        try:
            if self.client:
                self.client.close()
        except Exception as exc:
            self.cleanup_failed.emit(config.redact(f"客户端清理失败：{exc}"))
        finally:
            self.client = self.brain = None
            self.closed.emit()


class SerialTasks(QObject):
    """单飞队列。退出只排队 cleanup，GUI 继续处理事件，绝不 wait QThread。"""
    requested = Signal(object)
    close_requested = Signal()
    busy_changed = Signal(bool, str)
    stopped = Signal()
    cleanup_failed = Signal(str)

    def __init__(self, guard, parent=None):
        super().__init__(parent)
        self.worker = _SerialWorker(guard)
        self.thread = QThread(self)
        self.worker.moveToThread(self.thread)
        self.requested.connect(self.worker.execute)
        self.close_requested.connect(self.worker.close)
        self.worker.completed.connect(self._completed)
        self.worker.closed.connect(self.thread.quit)
        self.worker.cleanup_failed.connect(self.cleanup_failed)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.stopped)
        self.pending = deque()
        self.active = None
        self.closing = False
        self.thread.start()

    @property
    def busy(self):
        return self.active is not None or bool(self.pending)

    def contains(self, key):
        return (self.active is not None and self.active[0] == key) or any(j[0] == key for j in self.pending)

    def submit(self, key, fn, done, failed, label="我来办，稍等一下～"):
        if self.closing or self.contains(key):
            return False
        self.pending.append((key, fn, done, failed, label))
        self.busy_changed.emit(True, label if self.active is None else ("排队中" if label else ""))
        self._next()
        return True

    def _next(self):
        if self.active is None and self.pending and not self.closing:
            self.active = self.pending.popleft()
            self.busy_changed.emit(True, self.active[4])
            self.requested.emit((self.active[0], self.active[1]))
        elif self.active is None and not self.closing:
            self.busy_changed.emit(False, "")

    @Slot(object, object, str)
    def _completed(self, key, result, error):
        job = self.active
        if self.closing:
            self.active = None
            self.close_requested.emit()
            return
        try:
            if error:
                job[3](error)
            else:
                job[2](result)
        except Exception as exc:
            job[3](config.redact(f"界面处理失败：{exc}"))
        finally:
            self.active = None
            if self.closing:
                self.close_requested.emit()
            else:
                self._next()

    def shutdown(self):
        if self.closing:
            return
        self.closing = True
        self.pending.clear()
        if self.active is None:
            self.close_requested.emit()


class SingleInstance(QObject):
    activated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        directory = config.data_dir().resolve()
        self.name = "mcpet-" + hashlib.sha256(str(directory).casefold().encode()).hexdigest()[:20]
        self.lock = QLockFile(str(directory / "app.lock"))
        self.primary = self.lock.tryLock(0)
        if not self.primary and self.lock.error() != QLockFile.LockFailedError:
            raise RuntimeError("无法锁定 McPet 用户数据目录，请检查目录权限")
        self.server = None
        if self.primary:
            QLocalServer.removeServer(self.name)
            self.server = QLocalServer(self)
            if not self.server.listen(self.name):
                self.lock.unlock()
                raise RuntimeError("无法建立 McPet 本机单实例服务")
            # Python 会先回收 non-daemon 桥线程，再运行 atexit；锁不能在
            # app.exec 结束时提早释放，让另一实例抢写尚在回收的 usage.json。
            atexit.register(self.lock.unlock)
            self.server.newConnection.connect(self._connected)

    def _connected(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            socket.close()
            socket.deleteLater()
            self.activated.emit()

    def notify_existing(self, app):
        self.socket = QLocalSocket(self)
        self.socket.connected.connect(app.quit)
        self.socket.errorOccurred.connect(app.quit)
        self.socket.connectToServer(self.name)
        QTimer.singleShot(1000, app.quit)

    def close(self):
        if self.server:
            self.server.close()


class MonsterApp(PetFunctions, QObject):
    def __init__(self, argv=None, *, enforce_single_instance=True, monitor_factory=None, account_monitor_factory=None):
        self.app = QApplication.instance() or QApplication(argv or sys.argv)
        super().__init__()
        self.app.setQuitOnLastWindowClosed(False)
        self.app.setApplicationName("McPet")
        self.instance = SingleInstance(self) if enforce_single_instance else None
        self.secondary = self.instance is not None and not self.instance.primary
        if self.secondary:
            self.instance.notify_existing(self.app)
            return
        config.load_env()
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("当前系统无托盘，可通过桌宠右键菜单操作。")
        self.closing = self._allow_quit = False
        self.app.installEventFilter(self)
        self.guard, self.ledger = OrderGuard(), NutritionLedger()
        self.tasks = SerialTasks(self.guard, self)
        self.tasks.busy_changed.connect(self._busy_changed)
        self.tasks.stopped.connect(self._finish_quit)
        self.shutdown_error = ""
        self.tasks.cleanup_failed.connect(self._cleanup_failed)
        self.sheet = self._load_sheet()
        self.window = PetWindow(self.sheet)
        self.sheet = self.window.sheet  # A 恢复上次选定角色后的实际图集。
        self.window.menu_requested.connect(self.on_menu)
        if hasattr(self.window, "chat_requested"):
            self.window.chat_requested.connect(self.action_panel)
        self.window.show()
        self.tray = PetTray(self._icon(), self.menu_entries())
        self.window.appearance_changed.connect(self._pet_appearance_changed)
        self.tray.on_activate = self.action_panel
        if self.instance:
            self.instance.activated.connect(self.action_panel)
        self.panel = None
        self._business_status = "尚未查询实时数据。"
        self.progress_snapshot = self.usage_snapshot = None
        self.pending_quote = self.pending_store = None
        self.last_order_no = ""
        self._usage_level = "unknown"
        self._progress_error = self._usage_error = ""
        self._monitor_factory = monitor_factory
        self.monitor = None
        self.monitor_error = "后台观测正在启动…"
        self._account_monitor_factory = account_monitor_factory
        self.account_monitor = None
        self.account_snapshot = None
        self.account_error = ""
        self.account_refreshing = True
        self.schedule = DailySchedule()
        self.scheduler = QtDailyScheduler(self.schedule)
        self.scheduler.fired.connect(self.on_scheduled)
        self.scheduler._timer.timeout.connect(self._poll_coffee_order)
        self._add_lunch_task()
        self.scheduler.start()
        QTimer.singleShot(0, self._start_monitor)
        QTimer.singleShot(0, self._start_account_monitor)
        greeting = "鲸鲸到岗！" if self.window.character_id == "deepseek" else "ChatGPT 娘来陪你啦！"
        self.window.say(greeting + "右键找我，饭饭、咖啡和工作小账本都准备好啦。", 6000)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Quit and not self._allow_quit:
            self.quit()
            return True
        return super().eventFilter(watched, event)

    def _load_sheet(self):
        try:
            from .pet.characters import load_character
            from .pet.identity import DEFAULT_CHARACTER, CHARACTER_NAMES
            from .pet.preferences import PetPreferences
            selected = PetPreferences().load().get("character_id", DEFAULT_CHARACTER)
            return load_character(selected if selected in CHARACTER_NAMES else DEFAULT_CHARACTER)
        except SpriteLoadError as exc:
            print(config.redact(f"图集加载失败：{exc}"))
            return None

    def _icon(self):
        if hasattr(self, "window") and hasattr(self.window, "character_id") and self.sheet:
            return QIcon(character_preview(self.sheet))
        icon = config.PROJECT_ROOT / "assets" / "icon.png"
        if icon.exists():
            return QIcon(str(icon))
        return QIcon(self.sheet.frame("idle", 0)) if self.sheet else QIcon()


    def _activity(self, state, percent=None, label=""):
        if hasattr(self.window, "set_activity"):
            self.window.set_activity(state, context_percent=percent, label=config.redact(label))
        elif getattr(self, "_fallback_state", None) != state:
            self.window.set_state(state)
            self._fallback_state = state

    @Slot(bool, str)
    def _busy_changed(self, busy, label):
        if self.closing:
            return
        if busy:
            if label:
                self._activity("thinking", label=label)
                self.window.say(config.redact(label) + "…", 3000)
        else:
            self._apply_progress()

    def _error(self, message):
        if not self.closing:
            self.window.say_state("error", config.redact(message), 10000)
            self._business_message("这一步没办成，看看原因吧：" + message)

    def _cleanup_failed(self, message):
        self.shutdown_error = config.redact(message)
        print(self.shutdown_error)

    def run_async(self, fn, on_done, on_error=None, *, key="action", label="我来办，稍等一下～"):
        return self.tasks.submit(key, fn, on_done, on_error or self._error, label)

    def run_mcp(self, key, fn, done, failed=None, label="我去麦当劳看看，稍等一下～"):
        return self.run_async(lambda: fn(self.tasks.worker.ensure_client()), done, failed,
                              key=key, label=label)

    def _start_monitor(self):
        if self.closing or self.monitor is not None:
            return
        try:
            factory = self._monitor_factory
            if factory is None:
                from .runtime.monitor import AgentMonitor
                factory = AgentMonitor
            self.monitor = factory()
            self.monitor.progress_ready.connect(self._progress_ready)
            self.monitor.usage_ready.connect(self._usage_ready)
            self.monitor.failed.connect(self._monitor_failed)
            self.monitor.task_completed.connect(self._task_completed)
            self.monitor.start()
            self.monitor_error = "我去看看你指定的工作记录，稍等一下～"
        except Exception as exc:
            self.monitor_error = config.redact(f"后台观测不可用：{type(exc).__name__}: {exc}")
            self._monitor_failed(self.monitor_error)

    def _monitor_failed(self, error):
        if self.closing:
            return
        self.monitor_error = config.redact(error)
        self._progress_error = self._usage_error = self.monitor_error
        self._render_progress()
        self._render_usage()
        self._error(self.monitor_error)



    def _apply_progress(self):
        from .progress import pet_state_for
        snapshot = self.progress_snapshot
        active = snapshot.active if snapshot is not None else []
        if not active:
            self._activity("idle", label="暂时没看到活跃日志，任务是否完成还是未知哦")
            return
        priority = {"error": 5, "failed": 5, "waiting": 4, "needsinput": 4,
                    "thinking": 3, "working": 2}
        item = max(active, key=lambda s: priority.get(s.record.state, 0))
        state = pet_state_for(item.record.state)
        if state == "happy":
            state = "idle"
        label = item.label
        if self._progress_error:
            label += " · 最后快照，刷新失败"
        if getattr(item.record, "context_limit_estimated", False):
            label += " · 上下文上限估算"
        self._activity(state, item.context_percent, label)

    def _usage_ready(self, payload):
        if self.closing:
            return
        from .metering import bubble, reminder_level
        snapshot, projected, sample_ok = payload
        self.usage_snapshot = payload
        self._usage_error = ""
        self._render_usage()
        level = reminder_level(snapshot, projected if sample_ok else snapshot.window.tokens)
        if level in {"busy", "heavy"} and level != self._usage_level:
            self.window.say_state("balance", config.redact(bubble(snapshot, projected, sample_ok)) +
                                  " 本机日志台账，不等于厂商余额。", 10000)
        self._usage_level = level


    def _task_completed(self, event):
        if not self.closing:
            self.window.say_state("happy", "日志明确记录了任务完成。", 6000)


    def _sync_pet(self):
        self.sheet = self.window.sheet


    def _start_account_monitor(self):
        if self.closing or self.account_monitor is not None:
            return
        try:
            if self._account_monitor_factory is None:
                from .accounts import AccountMonitor, DeepSeekBalanceSource
                monitor = AccountMonitor(self, deepseek_source=DeepSeekBalanceSource(config.deepseek_api_key()))
            else:
                monitor = self._account_monitor_factory()
            self.account_monitor = monitor
            monitor.snapshot_ready.connect(self._accounts_ready)
            monitor.failed.connect(self._accounts_failed)
            monitor.start()
        except Exception as exc:
            self._accounts_failed(f"账号额度不可用：{type(exc).__name__}: {exc}")









    def action_coupon_report(self):
        def done(roundup):
            message = f"只查询：券中心 {roundup.available_count} 张；手上 {len(roundup.my_coupons)} 张。未主动领取。"
            self.window.say_state("coupon", message, 9000)
            self._business_message(message)
        self.run_mcp("coupons", lambda b: b.coupon_roundup(claim=False), done, label="优惠券雷达启动，只查不领哦～")

    def action_claim_coupons(self):
        if self.tasks.contains("claim"):
            return
        if not self._confirm("确认主动领券", '操作：auto-bind-coupons\npayload：{}\n将主动领取账号当前可领的券，具体结果以服务端返回为准。', "领取"):
            return
        def done(roundup):
            if not roundup.claim_ok:
                self._error(roundup.claim_error)
            else:
                message = f"主动领取返回：{roundup.claim_message or roundup.raw_claim or '已返回'}；新领 {len(roundup.claimed)} 张，手上 {len(roundup.my_coupons)} 张。"
                self.window.say_state("coupon", config.redact(message), 9000)
                self._business_message(message)
        self.run_mcp("claim", lambda b: b.coupon_roundup(claim=True), done, label="按你确认的范围去领券啦～")

    def action_best_deal(self):
        def work(brain):
            store = brain.resolve_default_store()
            if store is None:
                raise McpError("没有可用门店，请在设置中核对城市。")
            return brain.best_deal(store), store
        def done(result):
            quotes, store = result
            self.pending_quote = quotes[0] if quotes else None
            self.pending_store = store if quotes else None
            if not quotes:
                self._error("未找到可用实时报价。")
                return
            message = f"{store.store_name}：{quotes[0].sentence()}。右键 → 麦当劳 → 确认订单。"
            self.window.say_state("coupon", config.redact(message), 12000)
            self._business_message(message)
        if not self.tasks.contains("deal"):
            self.pending_quote = self.pending_store = None
        self.run_mcp("deal", work, done, label="先找找营业中的门店～ / 寻找实时报价")

    def action_place_order(self):
        if self.tasks.contains("order") or self.tasks.contains("prepare-order"):
            return
        if not self.pending_quote or not self.pending_store:
            self.window.say("先用「今天最划算」查询一份实时报价。", 6000)
            return
        quote, store = copy.deepcopy(self.pending_quote), copy.deepcopy(self.pending_store)
        def prepare(brain):
            options = brain.take_way_options(store, quote.meal_code)
            option = next((o for o in options if o.get("code") == "take-in-store"), None)
            if not option:
                raise McpError("该餐品未返回可用的外带取餐方式，未提交订单。")
            amount = brain.quote_order(store, [quote.meal_code], coupon_id=quote.coupon_id, coupon_code=quote.coupon_code)
            self.guard.check(amount)
            payload = {**brain._store_args(store), "items": [brain._item(quote.meal_code, 1, coupon_id=quote.coupon_id, coupon_code=quote.coupon_code)],
                       "takeWayCode": "take-in-store"}
            schema = next(t.input_schema for t in brain.client.list_tools() if t.name == T.TOOL_CREATE_ORDER)
            validate_arguments(payload, schema)
            summary = brain.render_order_summary(store.store_name, [quote.meal_name], amount,
                                                  quote.coupon_name or "无券", "外带")
            return amount, payload, summary
        def prepared(request):
            amount, payload, summary = request
            if not self._confirm("这份订单对了吗？", summary + "\n确认后会创建真实订单，付款还要你亲自操作哦。", "下单"):
                self.window.say("已取消，没有提交订单。", 5000)
                return
            # GUI 线程先消费候选，任何提交异常都不能复用原订单重试。
            self.pending_quote = self.pending_store = None
            self.run_mcp("order", lambda b: self._submit_order(b, quote, store, amount, payload, summary),
                         self._order_done, label="再核对一遍报价，提交你确认的订单～")
        self.run_mcp("prepare-order", prepare, prepared, label="我来核对取餐方式和实付金额～")

    def _submit_order(self, brain, quote, store, amount, payload, summary):
        fresh = brain.quote_order(store, [quote.meal_code], coupon_id=quote.coupon_id, coupon_code=quote.coupon_code)
        if fresh != amount:
            raise McpError("价格已变化，未提交订单，请重新核对确认。")
        self.guard.check(fresh)
        dry = config.dry_run()
        if dry:
            outcome = OrderOutcome("dry_run_skipped", summary, amount)
        else:
            try:
                result = brain.client.call_tool(T.TOOL_CREATE_ORDER, copy.deepcopy(payload))
            except Exception as exc:
                self._audit_unknown(store, quote, amount, config.redact(str(exc)))
                raise McpError("订单提交结果未知，未重试。请到麦当劳 App 核对后再重新查报价。" + config.redact(str(exc))) from None
            result.raise_for_error()
            if not result.ok:
                raise McpError(result.error_message or "服务端拒绝订单")
            node = result.unwrap()
            if not isinstance(node, dict):
                self._audit_unknown(store, quote, amount, "返回格式未知")
                raise McpError("订单返回格式未知，效果未知；请到麦当劳 App 核对，不要重复提交。")
            order_no = str(node.get("orderNo") or node.get("orderId") or node.get("orderCode") or "")
            if not order_no:
                self._audit_unknown(store, quote, amount, "服务端未返回订单号")
                raise McpError("服务端未返回订单号，效果未知；请到麦当劳 App 核对，不要重复提交。")
            outcome = OrderOutcome("placed", summary, amount, order_no,
                                   str(node.get("payUrl") or node.get("paymentUrl") or node.get("payLink") or ""))
        try:
            self.guard.record(OrderAuditEntry(datetime.now().isoformat(timespec="seconds"),
                              T.TOOL_CREATE_ORDER, config.redact(store.store_name), config.redact(quote.meal_name), amount,
                              config.redact(outcome.order_no), config.redact(outcome.pay_url), dry, outcome.status))
        except OSError as exc:
            outcome.reason = config.redact(f"本机订单审计保存失败：{exc}。服务端结果仍以本窗口显示为准，请到官方核对。")
        return outcome

    def _audit_unknown(self, store, quote, amount, note):
        try:
            self.guard.record(OrderAuditEntry(datetime.now().isoformat(timespec="seconds"),
                              T.TOOL_CREATE_ORDER, config.redact(store.store_name), config.redact(quote.meal_name), amount,
                              status="unknown", note=config.redact(note)))
        except OSError as exc:
            raise McpError(config.redact(f"订单提交效果未知，且本机审计保存失败：{exc}。请到麦当劳 App 核对，不要重复提交。")) from None


    def action_cancel_last_order(self):
        if not self.last_order_no:
            self.window.say("本次运行没有可撤销的已知订单。", 6000)
            return
        if self.tasks.contains("cancel"):
            return
        order_no = self.last_order_no
        payload = {"orderId": order_no, "cancelReasonCode": "1"}
        if not self._confirm("确定撤销这一单吗？", "订单号：" + order_no + "\n确认后会向官方申请撤单，请核对是不是这单哦。", "撤单"):
            return
        def work(brain):
            result = brain.client.call_tool(T.TOOL_CANCEL_ORDER, payload)
            result.raise_for_error()
            if not result.ok:
                raise McpError(result.error_message or "撤单失败")
            try:
                self.guard.mark_cancelled(order_no)
            except OSError as exc:
                return config.redact(f"本机审计更新失败：{exc}，请到官方核对。")
            return ""
        def done(warning):
            self.last_order_no = ""
            self.window.say("服务端已确认撤单。" + warning, 7000)
            self._forget_payment("mcd")
            self._business_message("服务端已确认撤单。" + warning)
        self.run_mcp("cancel", work, done, label="正在撤销已确认订单")

    def action_log_meal(self):
        def done(facts):
            if not facts:
                self._error("没有查到营养餐品，未记账。")
                return
            selection = self._select_nutrition(facts)
            if selection is None:
                self.window.say("已取消，营养台账没有写入。", 5000)
                return
            fact, quantity = selection
            def save():
                if "quantity" in inspect.signature(self.ledger.add_fact).parameters:
                    return self.ledger.add_fact(fact, quantity=quantity)
                scaled = copy.deepcopy(fact)
                for field in ("energy_kj", "energy_kcal", "protein_g", "fat_g", "carb_g", "sodium_mg", "calcium_mg"):
                    setattr(scaled, field, getattr(scaled, field) * quantity)
                scaled.name = f"{fact.name} × {quantity:g} 份"
                return self.ledger.add_fact(scaled)
            def saved(entry):
                message = f"记下 {fact.name} × {quantity:g} 份，约 {entry.energy_kcal:g} kcal。"
                self.window.say_state("happy", config.redact(message), 8000)
                self._business_message(message + "\n" + self.ledger.summary())
            self.run_async(save, saved,
                           key="save-meal", label="正在保存所选餐品")
        self.run_mcp("nutrition", lambda b: b.nutrition(), done, label="正在获取真实营养餐品")

    def action_nutrition_summary(self):
        self.action_panel("mcd")
        self._business_message(self.ledger.summary())



    def action_frying(self):
        self._play_pet_action("frying", loop=True)

    def action_outfit(self):
        self._play_pet_action("outfit")

    def _play_pet_action(self, state, *, loop=False):
        try:
            self.window.play_action(state, loop=loop)
            self.show_window()
        except SpriteLoadError as exc:
            self._error(str(exc))

    def action_stop_animation(self):
        self.window.stop_action()

    def _pet_appearance_changed(self):
        self.sheet = self.window.sheet
        self.tray.setIcon(self._icon())
        self.tray.set_entries(self.menu_entries())
        self._sync_pet()

    def _set_pet_skin(self, skin_id):
        try:
            self.window.set_skin(skin_id)
            self.sheet = self.window.sheet
            self.tray.setIcon(self._icon())
            self.tray.set_entries(self.menu_entries())
            self._sync_pet()
        except (ValueError, SpriteLoadError) as exc:
            self._error(str(exc))

    def action_skin_default(self):
        self._set_pet_skin("default")

    def action_skin_maimai(self):
        self._set_pet_skin("maimai")

    def action_roaming(self):
        if hasattr(self.window, "set_roaming"):
            self.window.set_roaming(not self.window.roaming_enabled)
            self.tray.set_entries(self.menu_entries())
            self._sync_pet()
        else:
            self._error("闲逛接口等待 A 轨集成。")

    def action_resting(self):
        if hasattr(self.window, "set_resting"):
            self.window.set_resting(not self.window.resting)
            self.tray.set_entries(self.menu_entries())
            self._sync_pet()
        else:
            self._error("休息接口等待 A 轨集成。")




    def on_menu(self, point):
        if self.window.isMinimized():
            self.window.showNormal()
        self.window.show_menu([entry for entry in self.menu_entries() if entry is not None], point)

    def show_window(self):
        self.window.show()
        self.window.raise_()

    def toggle_window(self):
        self.window.hide() if self.window.isVisible() else self.show_window()
        self._sync_pet()

    def quit(self):
        if self.closing:
            return
        self.closing = True
        if self.window.bubble.interacting:
            self.window.bubble._finish()
        self.scheduler.stop()
        if self.monitor:
            self.monitor.stop()
        if self.account_monitor:
            self.account_monitor.stop()
        self.tray.hide()
        if self.tasks.busy:
            QTimer.singleShot(0, self._show_quitting)
        self.tasks.shutdown()

    def _show_quitting(self):
        if self.closing and not self._allow_quit and self.tasks.busy:
            self.window.say("准备回窝啦，等手头这件事安全结束就走～", 6000)

    @Slot()
    def _finish_quit(self):
        self.window.close()  # A.closeEvent 保存最终位置、停止 timer 并关闭气泡。
        self.window.bubble.close()  # 兼容 A 合并前旧窗口的独立 bubble。
        self.app.removeEventFilter(self)
        if self.instance:
            self.instance.close()
        self._allow_quit = True
        self.app.quit()


def main():
    monster = MonsterApp()
    return monster.app.exec()


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    raise SystemExit(main())
