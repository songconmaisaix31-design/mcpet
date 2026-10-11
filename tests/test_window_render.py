"""桌宠渲染流畅度的回归测试。

修这一轮之前，「画面很卡」其实是三个独立缺陷叠出来的，而且都不报错：

1. **计时器用了默认的 CoarseTimer** —— Windows 上被 ~15.6ms 的系统节拍量化，
   80ms 的帧间隔实际跑成 ~94ms，帧率白掉 16%，观感是「慢半拍」。
2. **run-right / run-left 没写进 STATE_PRIORITY** —— 默认优先级 0 低于 idle 的 1，
   pick_state 永远把跑动状态挡回去，拖拽时一直播待机动画。
3. **同一状态重复设置会把动画打回第 0 帧** —— 拖拽时每个 mousemove 都调一次
   set_state，于是跑动动画被反复归零，看起来就是「拖的时候画面不动」。

下面把这些逐条钉住。另外还测了帧缓存（避免每次切状态都重新切片+平滑缩放）。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QGuiApplication, QMouseEvent

from src import config
from src.pet.spritesheet import SpriteSheet
from src.pet.states import PetStateMachine
from src.pet.window import (
    DEFAULT_FRAME_DELAY_MS,
    MIN_FRAME_DELAY_MS,
    PetWindow,
    resolve_frame_delay,
)

ASSETS = config.PROJECT_ROOT / "assets" / "longniang"
HAS_ASSETS = (ASSETS / "spritesheet.webp").exists()
needs_assets = pytest.mark.skipif(not HAS_ASSETS, reason="缺少占位图集")


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    return QGuiApplication.instance() or QGuiApplication([])


@pytest.fixture()
def sheet():
    return SpriteSheet.load(
        ASSETS / "spritesheet.webp",
        pet_json=ASSETS / "pet.json",
        rows_json=ASSETS / "sprite-rows.json",
    )


@pytest.fixture()
def window(sheet):
    win = PetWindow(sheet)
    yield win
    win.close()


# ---------- 帧间隔解析 ----------


def test_frame_delay_env_override(monkeypatch):
    monkeypatch.setenv("MCPET_FRAME_DELAY_MS", "50")
    assert resolve_frame_delay(None) == 50


def test_frame_delay_has_a_floor(monkeypatch):
    """下限 16ms：图集只有 4~8 帧，比 60fps 更快没有意义。"""
    monkeypatch.setenv("MCPET_FRAME_DELAY_MS", "1")
    assert resolve_frame_delay(None) == MIN_FRAME_DELAY_MS


def test_frame_delay_ignores_garbage(monkeypatch):
    monkeypatch.setenv("MCPET_FRAME_DELAY_MS", "不是数字")
    assert resolve_frame_delay(None) == DEFAULT_FRAME_DELAY_MS


def test_frame_delay_defaults_without_sheet(monkeypatch):
    monkeypatch.delenv("MCPET_FRAME_DELAY_MS", raising=False)
    assert resolve_frame_delay(None) == DEFAULT_FRAME_DELAY_MS


# ---------- 计时器精度 ----------


@needs_assets
def test_animation_timer_is_precise(window):
    """必须是 PreciseTimer，否则帧间隔会被系统节拍量化。"""
    assert window._anim.timerType() == Qt.PreciseTimer


@needs_assets
def test_animation_interval_matches_resolved_delay(window):
    assert window._anim.interval() == window._frame_delay_ms


# ---------- 帧缓存 ----------


@needs_assets
def test_frames_are_cached_per_state(window):
    window.set_state("idle")
    cached = window._cache.get("idle")
    assert cached, "切到某状态后应把它切片缩放的结果缓存下来"
    assert window._frames is cached


@needs_assets
def test_repeated_same_state_does_not_rebuild_frames(window):
    window.set_state("idle")
    cached = window._cache["idle"]
    window.set_state("idle")
    window.set_state("idle")
    assert window._cache["idle"] is cached, "同一状态不应反复重新切片"


@needs_assets
def test_different_states_have_separate_cache_entries(window):
    window.set_state("idle")
    window.set_state("waiting")  # waiting 优先级 5 > idle 1，能切过去
    assert "waiting" in window._cache
    assert window._cache["waiting"] is not window._cache["idle"]


# ---------- 动画不被拖拽打断 ----------


@needs_assets
def test_same_state_does_not_reset_frame_index(window):
    """拖拽时每个 mousemove 都会 set_state 同一个状态，动画不能被归零。"""
    window.set_state("idle")
    window._advance()
    window._advance()
    assert window._index == 2

    window.set_state("idle")
    assert window._index == 2, "重复设置同一状态把动画打回了第 0 帧"


@needs_assets
def test_state_change_does_reset_frame_index(window):
    window.set_state("idle")
    window._advance()
    window._advance()
    window.set_state("waiting")
    assert window._index == 0, "真正换状态时应当从头播"


# ---------- 跑动状态优先级 ----------


def test_run_states_can_override_idle():
    machine = PetStateMachine("idle")
    assert machine.set("run-right") == "run-right", "拖拽右移必须能切进跑动状态"
    assert machine.set("run-left") == "run-left"


def test_release_can_return_to_idle_from_run():
    machine = PetStateMachine("idle")
    machine.set("run-right")
    assert machine.set("idle") == "idle", "松手后必须能切回待机"


def test_run_does_not_clobber_notifications():
    """拖拽不该把正在显示的提醒/报错顶掉。"""
    machine = PetStateMachine("idle")
    machine.set("remind")
    assert machine.set("run-right") == "remind"


# ---------- 拖拽方向 ----------


def _press(x: int, y: int) -> QMouseEvent:
    return QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(x, y),
        QPointF(x, y),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def _move(x: int, y: int) -> QMouseEvent:
    return QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(x, y),
        QPointF(x, y),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


@needs_assets
def test_drag_direction_follows_cursor(window):
    """方向要按「光标这一帧往哪挪」判断，不能拿窗口当前位置比。"""
    window.mousePressEvent(_press(300, 300))
    window.mouseMoveEvent(_move(340, 300))
    assert window.machine.state == "run-right"

    window.mouseMoveEvent(_move(280, 300))
    assert window.machine.state == "run-left"


@needs_assets
def test_drag_without_horizontal_movement_keeps_state(window):
    window.mousePressEvent(_press(300, 300))
    window.mouseMoveEvent(_move(340, 300))
    assert window.machine.state == "run-right"

    # 纯纵向移动：不该反复切状态
    window.mouseMoveEvent(_move(340, 360))
    assert window.machine.state == "run-right"


@needs_assets
def test_placeholder_fallback_when_no_sheet():
    win = PetWindow(None)
    assert win._frames == []
    assert not win._anim.isActive()
    win.close()
