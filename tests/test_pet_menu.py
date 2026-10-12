"""Pet menus and real interactive bubbles, isolated from accounts/network."""
import time
from types import SimpleNamespace
import pytest
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QDialog, QMenu, QLineEdit

from src import config, main
from test_app_actions import monster, pump_until


def all_actions(menu):
    for action in menu.actions():
        yield action
        if action.menu():
            yield from all_actions(action.menu())


def action(app, label):
    return next(a for a in all_actions(app.tray.contextMenu()) if a.text() == label)


def interact(app, callback):
    def step():
        if not app.window.bubble.interacting:
            QTimer.singleShot(5, step)
            return
        callback(app.window.bubble)
    QTimer.singleShot(5, step)


def test_all_features_in_compact_nested_menu_no_panel_or_model(monster, monkeypatch):
    from src.pet.dialogs import CompanionPanel
    monkeypatch.setattr(CompanionPanel, "__init__", lambda *a, **k: pytest.fail("大面板不得创建"))
    monster.tasks.worker.ensure_client = lambda: pytest.fail("本机功能不得请求 MCP")
    top = monster.tray.contextMenu().actions()
    assert len(top) <= 11
    labels = {a.text() for a in all_actions(monster.tray.contextMenu())}
    assert {"会话进度", "本机用量", "账号额度 / 余额", "主动领券", "确认订单", "今日营养", "瑞幸 Token", "饭点", "咖啡时间", "调整规格", "查订单 / 取餐码"} <= labels
    monster.window.chat_requested.emit()
    monster.tray.on_activate()
    action(monster, "查看设置").trigger()
    action(monster, "今日营养").trigger()
    assert monster.panel is None and not any(isinstance(w, QDialog) and w.isVisible() for w in QApplication.topLevelWidgets())
    assert monster.window.bubble.isVisible() and monster.window.bubble.width() == 260
    assert not hasattr(monster, "chat_store")


def test_actual_right_click_nested_popup(monster):
    seen = []
    def choose():
        menu = QApplication.activePopupWidget()
        if not isinstance(menu, QMenu):
            QTimer.singleShot(5, choose)
            return
        seen.extend(a.text() for a in menu.actions())
        target = next(a for a in all_actions(menu) if a.text() == "今日营养")
        target.trigger()
        menu.close()
    QTimer.singleShot(5, choose)
    monster.on_menu(monster.window.pos())
    assert "瑞幸咖啡" in seen and monster.panel is None and monster.window.bubble.isVisible()


@pytest.mark.parametrize("confirm", [True, False])
def test_real_bubble_confirmation_buttons_never_expire_or_get_overwritten(monster, confirm):
    def click(bubble):
        monster.window.say("后台自动刷新不可覆盖待确认订单", 1)
        assert "具体订单" in bubble.label.text()
        assert not monster.window._bubble_timer.isActive()
        bubble.buttons[0 if confirm else -1].click()
    interact(monster, click)
    assert monster._confirm("核对", "具体订单", "提交") is confirm
    assert not monster.window.bubble.interacting and monster.panel is None


def test_secret_input_is_masked_and_cleared_and_blank_preserves(monster, monkeypatch):
    original = config.mcp_token()
    seen = []
    def input_blank(bubble):
        assert bubble.input.echoMode() == QLineEdit.Password
        assert bubble.input.text() == ""
        bubble.buttons[0].click()
    interact(monster, input_blank)
    monster._edit_setting("MCD_MCP_TOKEN", "麦当劳 Token")
    assert config.mcp_token() == original
    assert not monster.window.bubble.input.text()
    def input_value(bubble):
        bubble.input.setText("fixture-new-luckin-secret")
        bubble.buttons[0].click()
    interact(monster, input_value)
    monster._edit_setting("LUCKIN_MCP_TOKEN", "瑞幸 Token")
    monkeypatch.setenv("LUCKIN_MCP_TOKEN", "fixture-new-luckin-secret")
    assert not monster.window.bubble.input.text()
    assert "fixture-new-luckin-secret" not in monster.window.bubble.label.text()
    assert config.redact("fixture-new-luckin-secret") == "***"


def test_settings_cancel_failure_invalid_time_and_busy_do_not_write(monster, monkeypatch):
    saves = []
    monkeypatch.setattr(config, "save_settings", lambda values: saves.append(values))
    interact(monster, lambda b: b.buttons[-1].click())
    monster._edit_setting("MCPET_CITY", "城市")
    assert not saves
    monster._save_settings({"MCPET_LUNCH_TIME": "29:00"})
    assert not saves
    monster.run_async(lambda: time.sleep(.06), lambda r: None, key="fixture-busy")
    monster._save_settings({"MCPET_CITY": "不应保存"})
    assert not saves
    pump_until(lambda: not monster.tasks.busy)
    monkeypatch.setattr(config, "save_settings", lambda values: (_ for _ in ()).throw(OSError(values["LUCKIN_MCP_TOKEN"])))
    monster._save_settings({"LUCKIN_MCP_TOKEN": "unsaved-fixture-secret"})
    assert "unsaved-fixture-secret" not in monster.window.bubble.label.text()


def test_automatic_coffee_is_read_only_no_interactive_selection(monster, monkeypatch):
    monkeypatch.setenv("LUCKIN_MCP_TOKEN", "fixture-secret")
    monkeypatch.setenv("MCPET_COFFEE_DEPT_ID", "7")
    calls = []
    monster.tasks.worker.coffee.query = lambda t, args: calls.append((t, args)) or [{"productName": "夹具拿铁", "estimatePrice": 16}]
    monster.window.ask = lambda *a, **k: pytest.fail("自动查询不能要求选择或确认")
    monster.on_scheduled("coffee", False)
    pump_until(lambda: not monster.tasks.busy)
    assert calls == [("searchProductForMcp", {"deptId": 7, "query": "拿铁"})]
    assert "只查询，不下单" in monster.window.bubble.label.text() and "夹具拿铁" in monster.window.bubble.label.text()
    monster.action_reminders()
    monster.on_scheduled("coffee", False)
    assert len(calls) == 1


def test_daily_schedule_has_no_duplicate_callbacks(monster):
    assert {t.name for t in monster.schedule.tasks} == {"lunch", "coffee"}
    assert all(t.callback is None for t in monster.schedule.tasks)
    monster._add_lunch_task()
    assert len(monster.schedule.tasks) == 2


def test_quit_cancels_pending_bubble_and_does_not_submit(monster):
    interact(monster, lambda b: monster.quit())
    assert not monster._confirm("退出测试", "待确认订单", "提交")
    pump_until(lambda: not monster.tasks.thread.isRunning())


def test_payment_copy_open_and_reject_credentials_and_local_file(monster, monkeypatch):
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toString()) or True)
    monster.pay_url = "https://example.invalid/pay"
    monster.window.ask = lambda *a, **k: "copy"
    monster.action_payment()
    assert QApplication.clipboard().text() == monster.pay_url
    monster.window.ask = lambda *a, **k: "open"
    monster.action_payment()
    assert opened == ["https://example.invalid/pay"]
    monster.pay_url = "file:///fixture.exe"
    monster.action_payment()
    monster.pay_url = "https://example.invalid/?key=test-mcp-secret"
    monster.action_payment()
    assert opened == ["https://example.invalid/pay"] and "test-mcp-secret" not in monster.window.bubble.label.text()


def test_real_character_actions_and_switchable_skins_from_menu(monster, monkeypatch):
    monkeypatch.setattr(monster.window, "set_activity", type(monster.window).set_activity.__get__(monster.window))
    monster._change_character("deepseek")
    action(monster, "麦麦套装").trigger()
    assert monster.window.skin_id == "maimai"
    action(monster, "默认套装").trigger()
    assert monster.window.skin_id == "default"
    action(monster, "炸薯条 · 循环").trigger()
    assert monster.window.machine.state == "frying" and len(monster.window._frames) == 30
    action(monster, "停止动作").trigger()
    action(monster, "默认套装").trigger()
    assert monster.window.skin_id == "default" and monster.panel is None


def test_order_status_condition_is_read_only_deduped_and_stops(monster, monkeypatch):
    monkeypatch.setenv("LUCKIN_MCP_TOKEN", "fixture-coffee-secret")
    calls = []
    status = {"orderStatus": 60, "orderStatusName": "等待取餐", "takeMealCodeInfo": {"code": "A123"}}
    monster.tasks.worker.coffee.query = lambda tool, args: calls.append((tool, args)) or status.copy()
    monster._coffee_order_done({"status": "placed", "order_id": "fixture-order", "pay_url": "https://example.invalid/coffee"})
    monster._poll_coffee_order()
    pump_until(lambda: not monster.tasks.busy)
    assert "A123" in monster.window.bubble.label.text()
    monster.window.say("用户查看别的结果")
    monster._poll_coffee_order()
    pump_until(lambda: not monster.tasks.busy)
    assert monster.window.bubble.label.text() == "用户查看别的结果"
    status.update(orderStatus=80, orderStatusName="已完成")
    monster._poll_coffee_order()
    pump_until(lambda: not monster.tasks.busy)
    assert monster._coffee_watch_deadline == 0
    monster._poll_coffee_order()
    assert len(calls) == 3 and all(t == "queryOrderDetailInfo" for t, _ in calls)


def test_known_order_lookup_has_no_extra_input_and_payment_sources_are_independent(monster):
    monster.coffee_order = "fixture-known-order"
    monster.window.ask = lambda *a, **k: pytest.fail("已有已知订单不应额外要求输入")
    monster.tasks.worker.coffee.query = lambda t, a: {"orderStatusName": "待付款"}
    monster.action_coffee_order()
    pump_until(lambda: not monster.tasks.busy)
    assert "fixture-known-order" in monster.window.bubble.label.text()
    monster.payments = {"mcd": "https://example.invalid/meal", "luckin": "https://example.invalid/coffee"}
    monster.pay_url = monster.payments["luckin"]
    monster._forget_payment("mcd")
    assert monster.pay_url == "https://example.invalid/coffee"
    assert "mcd" not in monster.payments and "luckin" in monster.payments
