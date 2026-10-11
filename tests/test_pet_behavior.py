"""Assert real Qt gestures and local behavior without model/MCP requests."""
import json
import time

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from src.pet.behavior import RoamingBehavior, clamp_position
from src.pet.preferences import PetPreferences
from src.pet.window import PetWindow


@pytest.fixture
def pet(tmp_path, monkeypatch):
    monkeypatch.setenv("MCPET_DATA_DIR", str(tmp_path))
    win = PetWindow()
    win.show()
    win._behavior_timer.stop()
    yield win
    win.close()


def mouse(pet, kind, x, y, button=Qt.LeftButton, buttons=Qt.LeftButton):
    global_point = QPoint(x, y)
    local = pet.mapFromGlobal(global_point)
    event = QMouseEvent(kind, QPointF(local), QPointF(global_point), button, buttons, Qt.NoModifier)
    QApplication.sendEvent(pet, event)


def press(pet, x=300, y=300):
    mouse(pet, QEvent.MouseButtonPress, x, y)


def move(pet, x, y=300):
    mouse(pet, QEvent.MouseMove, x, y, Qt.NoButton)


def release(pet, x=300, y=300):
    mouse(pet, QEvent.MouseButtonRelease, x, y, buttons=Qt.NoButton)


def test_click_with_small_motion_touches_without_moving(pet):
    clicked = []
    pet.clicked.connect(lambda: clicked.append(True))
    before = pet.pos()
    press(pet)
    move(pet, 301)
    release(pet, 301)
    assert pet.pos() == before
    assert clicked == []  # Wait for the OS double-click window.
    QTest.qWait(QApplication.doubleClickInterval() + 40)
    assert clicked == [True]
    assert "我在呢" in pet.bubble.label.text()


def test_double_click_emits_chat_once_and_cancels_touch(pet):
    clicks, chats = [], []
    pet.clicked.connect(lambda: clicks.append(True))
    pet.chat_requested.connect(lambda: chats.append(True))
    press(pet)
    release(pet)
    mouse(pet, QEvent.MouseButtonDblClick, 300, 300)
    release(pet)
    QTest.qWait(QApplication.doubleClickInterval() + 40)
    assert chats == [True]
    assert clicks == []
    assert not pet.bubble.isVisible()


def test_drag_release_never_clicks_and_restores_latest_work(pet):
    clicks = []
    pet.clicked.connect(lambda: clicks.append(True))
    press(pet)
    move(pet, 340)
    assert pet.machine.state == "run-right"
    pet.set_activity("working", 23, "开发中")
    assert pet.machine.state == "run-right"
    release(pet, 340)
    QTest.qWait(QApplication.doubleClickInterval() + 40)
    assert clicks == []
    assert pet.machine.state == "working"


def test_drag_reversal_uses_distance_from_extreme(pet):
    press(pet)
    move(pet, 340)
    for x in (339, 340, 339, 338, 339, 340):
        move(pet, x)
        assert pet.machine.state == "run-right"
    move(pet, 332)
    assert pet.machine.state == "run-left"
    move(pet, 333)
    assert pet.machine.state == "run-left"
    release(pet, 333)


def test_touch_chat_reopen_then_drag_before_touch_ttl(pet):
    clicks, chats = [], []
    chat = QWidget()
    pet.clicked.connect(lambda: clicks.append(True))
    pet.chat_requested.connect(lambda: (chats.append(True), chat.show()))
    try:
        press(pet)
        release(pet)
        QTest.qWait(QApplication.doubleClickInterval() + 40)
        assert clicks == [True]
        assert pet.machine.state == "greet"
        deadline = pet.machine._expires_at
        mouse(pet, QEvent.MouseButtonDblClick, 300, 300)
        release(pet)
        assert chat.isVisible()
        chat.close()
        mouse(pet, QEvent.MouseButtonDblClick, 300, 300)
        release(pet)
        assert chat.isVisible() and chats == [True, True]
        assert time.monotonic() < deadline
        press(pet)
        move(pet, 340)
        assert pet.machine.state == "run-right"
        move(pet, 339)
        assert pet.machine.state == "run-right"
        move(pet, 332)
        assert pet.machine.state == "run-left"
        release(pet, 332)
        QTest.qWait(QApplication.doubleClickInterval() + 40)
        assert clicks == [True]
    finally:
        chat.close()


@pytest.mark.parametrize("foreground", ["greet", "happy", "coupon", "progress", "remind", "error", "waiting"])
def test_explicit_drag_and_rest_override_foreground_without_renewal(pet, monkeypatch, foreground):
    clock = [10.0]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    pet.set_activity("working")
    pet.set_state(foreground)
    deadline = pet.machine._expires_at
    assert pet.machine.state == foreground
    press(pet)
    move(pet, 340)
    assert pet.machine.state == "run-right"
    pet.set_activity("thinking")
    pet._decay()
    assert pet.machine.state == "run-right"
    assert pet.machine._expires_at == deadline
    release(pet, 340)
    assert pet.machine.state == foreground
    pet.set_resting(True)
    assert pet.machine.state == "sleeping"
    pet.set_activity("working")
    pet.set_state("idle", ttl_ms=10000)  # Rejected background event cannot change suspended TTL.
    assert pet.machine.state == "sleeping"
    assert pet.machine._expires_at == deadline
    pet.set_resting(False)
    assert pet.machine.state == foreground
    assert pet.machine._expires_at == deadline


def test_rest_wake_and_drag_keep_latest_base_when_touch_expires(pet, monkeypatch):
    clock = [10.0]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    pet.set_activity("working")
    pet._touch()
    pet.set_resting(True)
    assert pet.machine.state == "sleeping"
    pet.set_activity("thinking")
    clock[0] = 12.1
    pet._decay()
    assert pet.machine.state == "sleeping"
    press(pet)
    move(pet, 340)
    assert pet.machine.state == "run-right"
    pet.set_activity("working")
    release(pet, 340)
    assert pet.resting and pet.machine.state == "sleeping"
    pet.set_resting(False)
    assert pet.machine.state == "working"


def test_rest_cancels_pending_click_and_low_motion_keeps_touch(pet):
    clicks = []
    pet.clicked.connect(lambda: clicks.append(True))
    pet._touch()
    deadline = pet.machine._expires_at
    press(pet)
    move(pet, 301)
    assert pet.machine.state == "greet"
    assert pet.machine._expires_at == deadline
    release(pet, 301)
    assert pet._click_timer.isActive()
    pet.set_resting(True)
    assert not pet._click_timer.isActive()
    QTest.qWait(QApplication.doubleClickInterval() + 40)
    assert clicks == [True]
    assert pet.machine.state == "sleeping"


def test_background_poll_keeps_touch_bubble_and_restores_new_base(pet, monkeypatch):
    clock = [10.0]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    pet.set_activity("working")
    pet._touch()
    assert pet.machine.state == "greet"
    text = pet.bubble.label.text()
    deadline = pet.machine._expires_at
    for state in ("thinking", "working", "idle", "working"):
        pet.set_activity(state, None, "巡检")
        assert pet.machine.state == "greet"
        assert pet.machine._expires_at == deadline
        assert pet.bubble.label.text() == text
    clock[0] = 12.1
    pet._decay()
    assert pet.machine.state == "working"


def test_context_unknown_and_zero_are_distinct(pet):
    anchor = pet.canvas.mapToGlobal(QPoint(0, 0))
    size = pet.size()
    for unknown in (None, float("nan"), float("inf"), -1, 101, True, "45"):
        pet.set_activity("working", unknown, "开发")
        assert pet.context_bar.isHidden()
        assert "上下文未知" in pet.activity_label.text()
    pet.set_activity("working", 0, "开发")
    assert not pet.context_bar.isHidden()
    assert pet.context_bar.value() == 0
    assert "未知" not in pet.activity_label.text()
    QApplication.processEvents()
    assert pet.size() == size
    assert pet.canvas.mapToGlobal(QPoint(0, 0)) == anchor


def test_rest_toggle_returns_to_latest_work_without_fake_completion(pet):
    pet.set_activity("working")
    pet.set_resting(True)
    assert pet.resting
    assert pet.machine.state == "sleeping"
    pet.set_activity("thinking")
    assert pet.machine.state == "sleeping"
    pet.set_resting(False)
    assert not pet.resting
    assert pet.machine.state == "thinking"


def test_elapsed_time_walking_and_pause_resume():
    a, b = RoamingBehavior(), RoamingBehavior()
    for behavior in (a, b):
        behavior.phase = "walking"
        behavior.remaining = 4
    distance_a = sum(a.advance(0.02)[0] for _ in range(50))
    distance_b = sum(b.advance(0.05)[0] for _ in range(20))
    assert distance_a == pytest.approx(28)
    assert distance_a == pytest.approx(distance_b)
    before = a.remaining
    assert a.advance(10, paused=True) == (0, "idle")
    assert a.remaining == before
    assert abs(a.advance(10)[0]) == pytest.approx(2.8)  # Suspension cannot teleport.
    a.remaining = 0.01
    assert a.advance(0.02) == (0, "sleeping")
    a.remaining = 0.01
    assert a.advance(0.02)[1] in {"run-left", "run-right"}


def test_real_window_roaming_uses_subpixel_accumulator_and_stops_for_work(pet, monkeypatch):
    clock = [20.0]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    pet._last_behavior = 20
    pet.set_roaming(True)
    pet._behavior.phase, pet._behavior.remaining = "walking", 5
    pet.move(100, 100)
    for _ in range(30):
        clock[0] += 0.03
        pet._step_behavior()
    assert pet.x() == 125
    pet.set_activity("working")
    position = pet.pos()
    remaining = pet._behavior.remaining
    clock[0] += 1
    pet._step_behavior()
    assert pet.pos() == position
    assert pet._behavior.remaining == remaining
    assert pet.machine.state == "working"


def test_negative_monitor_and_taskbar_clamping():
    areas = [QRect(-1920, 0, 1920, 1040), QRect(0, 0, 1280, 680)]
    size = QSize(180, 220)
    assert clamp_position(QPoint(-1800, 50), size, areas) == QPoint(-1800, 50)
    assert clamp_position(QPoint(-400, 1000), size, areas) == QPoint(-400, 820)
    assert clamp_position(QPoint(1200, 650), size, areas) == QPoint(1100, 460)
    assert clamp_position(QPoint(-9000, -200), size, areas) == QPoint(-1920, 0)
    assert clamp_position(QPoint(200, 200), QSize(500, 500), [QRect(0, 0, 100, 100)]) == QPoint(0, 0)


def test_position_preferences_survive_restart(pet, tmp_path):
    pet.set_roaming(True)
    pet.set_resting(True)
    pet.move(140, 120)
    pet._save_preferences()
    data = json.loads((tmp_path / "pet-preferences.json").read_text(encoding="utf-8"))
    assert data["position"] == [140, 120]
    assert data["screen"] == pet.screen().name()
    other = PetWindow()
    try:
        assert other.pos() == QPoint(140, 120)
        assert other.roaming_enabled and other.resting
    finally:
        other.close()


def test_corrupt_preferences_fall_back_without_touching_other_files(tmp_path):
    path = tmp_path / "pet-preferences.json"
    path.write_text("broken", encoding="utf-8")
    prefs = PetPreferences(path)
    assert prefs.load() == {}
    assert prefs.error
    assert prefs.save({"roaming": True})
    assert prefs.load() == {"roaming": True}
    assert set(p.name for p in tmp_path.iterdir()) == {"pet-preferences.json"}


def test_menu_actions_are_destroyed_after_every_close(pet):
    before = len(pet.findChildren(QAction))
    for _ in range(3):
        def dismiss():
            menus = pet.findChildren(QMenu)
            assert menus
            menus[-1].close()
        QTimer.singleShot(0, dismiss)
        pet.show_menu([("测试", lambda: None)], pet.pos())
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    assert pet.findChildren(QMenu) == []
    assert len(pet.findChildren(QAction)) == before


def test_close_stops_behavior_and_closes_bubble(pet):
    pet.say("测试")
    pet.close()
    assert not pet.bubble.isVisible()
    assert not pet._anim.isActive()
    assert not pet._behavior_timer.isActive()
    assert not pet._save_timer.isActive()
