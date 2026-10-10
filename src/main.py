"""McPet（麦麦搭子） —— 入口。

把四层拼起来：托盘 + 桌宠窗口（表现层）、调度器（时间层）、麦麦大脑（MCP 层）、
护栏 + 台账（安全与留痕层）。
"""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QInputDialog, QSystemTrayIcon

from . import config
from .mcd_mcp.brain import DealQuote, McdBrain
from .mcd_mcp.client import McdMcpClient, McpError
from .mcd_mcp.guards import OrderGuard
from .nutrition.ledger import NutritionLedger
from .pet.dialogs import OrderConfirmDialog, prompt_for_token, show_error
from .pet.spritesheet import SpriteLoadError, SpriteSheet
from .pet.tray import PetTray
from .pet.window import PetWindow
from .schedule.clock import DailySchedule, DailyTask, QtDailyScheduler

DEFAULT_LUNCH = (11, 30)


class _FnThread(QThread):
    """把阻塞的 MCP 调用挪出 UI 线程。"""

    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:  # noqa: D102
        try:
            self.done.emit(self._fn())
        except Exception as exc:  # noqa: BLE001 - 线程里任何异常都要能回传
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class MonsterApp:
    def __init__(self, argv: list[str] | None = None):
        config.load_env()
        self.app = QApplication(argv or sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.app.setApplicationName("McPet")

        self._threads: list[_FnThread] = []
        self.guard = OrderGuard()
        self.ledger = NutritionLedger()
        self.client: McdMcpClient | None = None
        self.brain: McdBrain | None = None
        self.pending_quote: DealQuote | None = None
        self.pending_store: Any = None
        self.last_order_no: str = ""

        self.sheet = self._load_sheet()
        self.window = PetWindow(self.sheet)
        self.window.clicked.connect(self.on_click)
        self.window.menu_requested.connect(self.on_menu)
        self.window.move(1200, 700)
        self.window.show()

        self.tray = PetTray(
            self._icon(),
            [
                ("问麦麦", self.action_ask),
                ("领券汇报", self.action_coupon_report),
                ("今天最划算", self.action_best_deal),
                ("记一笔麦当劳", self.action_log_meal),
                ("今日营养", self.action_nutrition_summary),
                None,
                ("项目进度", self.action_progress),
                ("账号余额", self.action_balance),
                None,
                ("退出", self.quit),
            ],
        )
        self.tray.on_activate = self.toggle_window

        self.schedule = DailySchedule()
        self.scheduler = QtDailyScheduler(self.schedule)
        self.scheduler.fired.connect(self.on_scheduled)
        self._add_lunch_task()
        self.scheduler.start()

        self.window.say("McPet 上线了。右键我有菜单。", 6000)

    # ---------- 装配 ----------

    def _load_sheet(self) -> SpriteSheet | None:
        base = config.PROJECT_ROOT / "assets" / "longniang"
        image = base / "spritesheet.webp"
        if not image.exists():
            return None
        try:
            sheet = SpriteSheet.load(
                image,
                pet_json=base / "pet.json",
                rows_json=base / "sprite-rows.json",
            )
            issues = getattr(sheet, "validation_issues", [])
            if issues:
                print("[spritesheet] 校验提示：", *issues, sep="\n  - ")
            return sheet
        except SpriteLoadError as exc:
            print(f"[spritesheet] 加载失败：{exc}")
            return None

    def _icon(self) -> QIcon:
        icon_path = config.PROJECT_ROOT / "assets" / "icon.png"
        if icon_path.exists():
            return QIcon(str(icon_path))
        if self.sheet:
            pixmap: QPixmap = self.sheet.frame("idle", 0)
            if not pixmap.isNull():
                return QIcon(pixmap)
        return QIcon()

    def _add_lunch_task(self) -> None:
        raw = os.environ.get("MCPET_LUNCH_TIME", "11:30")
        try:
            hour, minute = (int(part) for part in raw.split(":", 1))
        except ValueError:
            hour, minute = DEFAULT_LUNCH
        self.schedule.add(
            DailyTask(name="lunch", hour=hour, minute=minute, callback=self.on_lunch)
        )

    # ---------- 异步 ----------

    def run_async(self, fn, on_done, on_error=None) -> None:
        self.window.set_state("thinking")
        thread = _FnThread(fn, self.app)
        self._threads.append(thread)

        def handle_done(result):
            self._release(thread)
            self.window.set_state("idle")
            on_done(result)

        def handle_failed(message: str):
            self._release(thread)
            self.window.set_state("error")
            self.window.say(f"出错了：{message}", 8000)
            if on_error:
                on_error(message)

        thread.done.connect(handle_done)
        thread.failed.connect(handle_failed)
        thread.start()

    def _release(self, thread: _FnThread) -> None:
        if thread in self._threads:
            self._threads.remove(thread)

    # ---------- 客户端 ----------

    def ensure_client(self) -> bool:
        if self.brain:
            return True
        token = config.mcp_token()
        if not token:
            token = prompt_for_token(self.window)
        if not token:
            self.window.say("没有 MCP Token，我只能陪你待着。", 6000)
            return False
        try:
            self.client = McdMcpClient(token, config.mcp_url())
            self.client.initialize()
        except McpError as exc:
            show_error(self.window, "连不上麦当劳 MCP", str(exc))
            return False
        self.brain = McdBrain(self.client, self.guard)
        return True

    # ---------- 动作 ----------

    def action_coupon_report(self) -> None:
        if not self.ensure_client():
            return

        def work():
            roundup = self.brain.coupon_roundup()
            return roundup

        def done(roundup):
            if not roundup.claim_ok:
                self.window.say_state("error", f"领券没成功：{roundup.claim_error}", 10000)
                return
            if not roundup.claimed and not roundup.my_coupons:
                self.window.say_state("coupon", "今天没有可领的券，也没查到手上的券。", 8000)
                return
            head = f"麦麦省券已全领（{len(roundup.claimed)} 张）" if roundup.claimed else "没有新券可领"
            detail = f"手上共 {len(roundup.my_coupons)} 张券"
            self.window.say_state("coupon", f"{head}。{detail}。", 9000)

        self.run_async(work, done)

    def action_best_deal(self) -> None:
        if not self.ensure_client():
            return

        def work():
            store = self.brain.resolve_default_store()
            if not store:
                return None, None
            quotes = self.brain.best_deal(store)
            return quotes[:1], store

        def done(result):
            quotes, store = result
            if not quotes:
                self.window.say_state("coupon", "没找到可用报价（请检查 MCPET_CITY 设置）。", 8000)
                return
            quote: DealQuote = quotes[0]
            self.pending_quote = quote
            self.pending_store = store
            self.window.say_state("coupon", f"{quote.sentence()}。要下单吗？", 12000)

        self.run_async(work, done)

    def action_place_order(self) -> None:
        quote = getattr(self, "pending_quote", None)
        if not quote:
            self.window.say("先点「今天最划算」让我找一单。", 5000)
            return
        if not self.ensure_client():
            return
        store = getattr(self, "pending_store", None)
        if not store:
            self.window.say("门店信息丢了，重新点「今天最划算」。", 5000)
            return
        summary = self.brain.render_order_summary(
            store.store_name,
            [quote.meal_name],
            quote.payable_cents or quote.baseline_cents,
            quote.coupon_name,
        )
        dialog = OrderConfirmDialog(summary, self.window)
        if not dialog.confirmed:
            self.window.say("好的，不下单。", 4000)
            return

        def work():
            return self.brain.place_order(
                store,
                [quote.meal_code],
                [quote.meal_name],
                coupon_id=quote.coupon_id,
                coupon_code=quote.coupon_code,
                coupon_name=quote.coupon_name,
                confirmed=True,
            )

        def done(outcome):
            if outcome.status == "placed":
                self.window.say_state(
                    "happy",
                    f"下单成功，实付 {outcome.amount_cents / 100:.2f} 元。支付链接已生成。",
                    12000,
                )
                self.last_order_no = outcome.order_no
            elif outcome.status == "dry_run_skipped":
                self.window.say_state(
                    "happy", f"演练模式：算价是真实调用，未提交订单。{outcome.summary}", 10000
                )
            else:
                self.window.say_state("error", f"没下成：{outcome.reason}", 10000)

        self.run_async(work, done)

    def action_cancel_last_order(self) -> None:
        order_no = getattr(self, "last_order_no", "")
        if not order_no:
            self.window.say("这一轮还没有我下的单。", 5000)
            return

        def work():
            return self.brain.cancel_order(order_no)

        def done(ok: bool):
            if ok:
                self.window.say_state("idle", f"已撤单：{order_no}", 8000)
                self.last_order_no = ""
            else:
                self.window.say_state("error", "撤单失败，请到麦当劳 App 里处理。", 8000)

        self.run_async(work, done)

    def action_log_meal(self) -> None:
        """记一笔：查营养表，把今天第一顿麦当劳记进台账。

        当前实现取营养表的第一项作为示例入口；真实交互应让用户选餐品，
        这在 UI 上还差一个选择框，属于待补项（见 README 的未做清单）。
        """
        if not self.ensure_client():
            return

        def work():
            facts = self.brain.nutrition()
            if not facts:
                return None
            return self.ledger.add_fact(facts[0])

        def done(entry):
            if not entry:
                self.window.say_state("error", "没查到营养数据。", 7000)
                return
            self.window.say_state("happy", f"记下了：{entry.meal_name}（{entry.energy_kcal:.0f} kcal）", 8000)

        self.run_async(work, done)

    def action_nutrition_summary(self) -> None:
        self.window.say_state("idle", self.ledger.summary(), 8000)

    # ---------- 复用 LLMPET 基础设施的两个动作 ----------

    def action_progress(self) -> None:
        """项目进度汇报。只读日志，不碰任何 Agent。"""
        from .progress import build_tracker, bubble, report

        def work():
            tracker = build_tracker()
            if not tracker.providers:
                return None, "没有可用的 Agent 数据源。"
            return tracker.snapshot(), ""

        def done(result):
            snapshot, error = result
            if snapshot is None:
                self.window.say_state("error", error, 8000)
                return
            if not snapshot.has_data:
                self.window.say_state("progress", "没读到任何 Agent 的会话。", 8000)
                return
            self.window.say_state("progress", bubble(snapshot), 12000)
            # 详情走 stdout，避免气泡塞不下十几行
            print(report(snapshot))

        self.run_async(work, done)

    def action_balance(self) -> None:
        """账号余额提醒。扫台账 → 报窗口用量。"""
        from .metering import build_meter, bubble, reminder_level

        def work():
            meter = build_meter()
            if not meter.providers:
                return None, None, None, "没有可用的 Agent 数据源。"
            meter.scan()
            snapshot = meter.snapshot()
            projected, _, sample_ok = meter.window_projection(snapshot)
            return snapshot, projected, sample_ok, ""

        def done(result):
            snapshot, projected, sample_ok, error = result
            if snapshot is None:
                self.window.say_state("error", error, 8000)
                return
            state = reminder_level(snapshot, projected)
            # 用量偏重时用 error 表情提一句，别让它悄无声息地烧
            pet_state = "error" if state == "heavy" else "balance"
            self.window.say_state(pet_state, bubble(snapshot, projected, sample_ok), 12000)

        self.run_async(work, done)

    def action_ask(self) -> None:
        """问麦麦：大模型读真实 tools/list 后自己决定调哪个麦当劳工具。"""
        if not self.ensure_client():
            return
        question, ok = QInputDialog.getText(
            self.window, "问麦麦", "想问点什么？会真实调用麦当劳 MCP。"
        )
        if not ok or not question.strip():
            return

        def work():
            from .llm.stepfun import StepFunClient
            from .mcd_mcp.skill import run_skill

            with StepFunClient() as llm:
                return run_skill(question.strip(), self.brain, llm)

        def done(result):
            if result.needs_confirmation:
                self.window.say_state(
                    "waiting",
                    f"{result.pending_reason}参数：{result.pending_write.arguments}",
                    12000,
                )
                return
            self.window.say_state("happy", result.answer or "它没答上来。", 12000)

        self.run_async(work, done)

    # ---------- 定时 ----------

    def on_lunch(self, late: bool) -> None:
        greeting = "刚才该吃饭了" if late else "该吃饭了"
        self.window.say_state("remind", f"{greeting}！我去看看今天有什么券…", 6000)
        self.action_coupon_report()
        self.action_best_deal()

    def on_scheduled(self, name: str, late: bool) -> None:
        if name == "lunch":
            self.on_lunch(late)

    # ---------- 交互 ----------

    def on_click(self) -> None:
        self.window.say(self.ledger.summary(), 6000)

    def on_menu(self, point) -> None:
        self.window.show_menu(
            [
                ("问麦麦", self.action_ask),
                ("领券汇报", self.action_coupon_report),
                ("今天最划算", self.action_best_deal),
                ("就下这一单", self.action_place_order),
                ("撤销上一单", self.action_cancel_last_order),
                ("记一笔麦当劳", self.action_log_meal),
                ("今日营养", self.action_nutrition_summary),
                ("项目进度", self.action_progress),
                ("账号余额", self.action_balance),
                ("退出", self.quit),
            ],
            point,
        )

    def toggle_window(self) -> None:
        if self.window.isVisible():
            self.window.hide()
        else:
            self.window.show()
            self.window.raise_()

    def quit(self) -> None:
        self.scheduler.stop()
        if self.client:
            self.client.close()
        self.app.quit()


def main() -> int:
    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("警告：当前系统没有可用托盘，程序将以普通窗口方式运行。")
    monster = MonsterApp()
    return monster.app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
