"""桌宠窗口：无边框置顶、精灵图逐帧播放、气泡、拖拽、右键菜单。

架构参考 CeTaPet（托盘常驻 + 状态机 + 气泡 + 拖拽），代码为本项目重写：
素材从「单张 PNG 切换」换成 spritesheet 切片播放，状态机带优先级与 TTL 衰减。
"""

from __future__ import annotations

import os
import math
import time
from collections.abc import Sequence

from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal, QEventLoop
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QVBoxLayout, QWidget, QPushButton, QLineEdit, QScrollArea, QSizePolicy
from .menu import populate_menu

from .spritesheet import AnimationSheet, ScaledAnimationFrames, SpriteLoadError, SpriteSheet
from .states import PetStateMachine
from .behavior import RoamingBehavior, clamp_position
from .preferences import PetPreferences
from .characters import CHARACTER_IDS, load_character
from .identity import DEFAULT_CHARACTER
from .skins import validate_skin
from .cetapet import ACTIONS as CETAPET_ACTIONS, require_pose
from ..agent_local import data_lock

DEFAULT_SIZE = 180
DEFAULT_FRAME_DELAY_MS = 80
MIN_FRAME_DELAY_MS = 16  # 再快也没意义：图集本身只有 4~8 帧


def resolve_frame_delay(sheet: SpriteSheet | None, state: str = "idle") -> int:
    """帧间隔（毫秒）。优先级：环境变量 > 待机专用配置 > 图集自带 > 默认。

    图集规格里没有帧时长定义（longniang 仓库只有素材与布局，不含播放规范），
    所以给一个可调默认值，方便给不同素材各自标定节奏。
    """
    raw = os.environ.get("MCPET_FRAME_DELAY_MS", "").strip()
    if raw:
        try:
            return max(MIN_FRAME_DELAY_MS, int(raw))
        except ValueError:
            pass
    if sheet is not None and sheet.row_for(state) == sheet.row_for("idle"):
        idle_delay = sheet.meta.get("idle_frame_delay_ms")
        if isinstance(idle_delay, int) and idle_delay > 0:
            return max(MIN_FRAME_DELAY_MS, idle_delay)
    if sheet is not None and sheet.frame_delay_ms:
        return max(MIN_FRAME_DELAY_MS, int(sheet.frame_delay_ms))
    return DEFAULT_FRAME_DELAY_MS


def resolve_frame_hold(sheet: SpriteSheet | None, state: str) -> int:
    if sheet is not None and sheet.row_for(state) == sheet.row_for("idle"):
        hold = sheet.meta.get("idle_open_eye_hold_ms", 0)
        if isinstance(hold, int) and hold > 0:
            return hold
    return 0


class Bubble(QWidget):
    """气泡。跟随桌宠窗口上沿，纯展示，不抢焦点。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.label = QLabel(self)
        self.label.setWordWrap(True)
        self.label.setFont(QFont("Microsoft YaHei UI", 10))
        self.label.setStyleSheet(
            "QLabel{background:#FFF8E7;color:#3A2A12;border:1px solid #E0B24C;"
            "border-radius:10px;padding:8px 10px;}"
        )
        self.label.setMaximumWidth(260)
        self.label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.setFixedWidth(260)
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.viewport().setAutoFillBackground(False)
        self.scroll.setWidget(self.label)
        layout.addWidget(self.scroll)
        self.controls = QWidget(self)
        self.controls_layout = QVBoxLayout(self.controls)
        self.controls_layout.setContentsMargins(4, 0, 4, 4)
        layout.addWidget(self.controls)
        self.controls.hide()
        self.interacting = False
        self._loop = None
        self.result = None
        self.buttons = []
        self.input = None
        self.label.setTextFormat(Qt.PlainText)

    def show_text(self, text: str, anchor: QWidget) -> None:
        if not self.interacting:
            self.label.setText(text)
        self.position(anchor)

    def position(self, anchor):
        height = self.label.heightForWidth(240)
        self.scroll.setFixedHeight(min(190, max(48, height + 8)))
        self.adjustSize()
        x = anchor.x() + anchor.width() // 2 - self.width() // 2
        y = anchor.y() - self.height() - 6
        if y < anchor.screen().availableGeometry().top():
            y = anchor.y() + anchor.height() + 6
        self.move(clamp_position(QPoint(x, y), self.size(),
                                 [anchor.screen().availableGeometry()]))
        self.show()
        self.raise_()

    def _finish(self, result=None):
        self.result = result
        if self._loop is not None:
            self._loop.quit()

    def ask(self, text, anchor, choices, *, placeholder=None, secret=False):
        if self.interacting:
            return None
        self.interacting = True
        self.label.setText(text)
        self.result = None
        self.buttons = []
        self.input = None
        while self.controls_layout.count():
            item = self.controls_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if placeholder is not None:
            self.input = QLineEdit(self.controls)
            self.input.setPlaceholderText(placeholder)
            self.input.setEchoMode(QLineEdit.Password if secret else QLineEdit.Normal)
            self.controls_layout.addWidget(self.input)
            self.input.returnPressed.connect(lambda: self._finish(self.input.text()))
        for label, value in choices:
            button = QPushButton(label, self.controls)
            button.clicked.connect(lambda checked=False, v=value: self._finish(self.input.text() if v == "__input__" else v))
            self.controls_layout.addWidget(button)
            self.buttons.append(button)
        cancel = QPushButton("取消", self.controls)
        cancel.clicked.connect(lambda: self._finish())
        self.controls_layout.addWidget(cancel)
        self.buttons.append(cancel)
        self.controls.show()
        self.position(anchor)
        if self.input:
            self.activateWindow()
            self.input.setFocus()
        self._loop = QEventLoop(self)
        try:
            self._loop.exec()
            return self.result
        finally:
            self._loop = None
            self.interacting = False
            if self.input:
                self.input.clear()
            self.controls.hide()
            self.hide()

    def hideEvent(self, event):
        if self.interacting:
            self._finish()
        super().hideEvent(event)


class PetWindow(QWidget):
    """桌宠主窗口。"""

    clicked = Signal()
    chat_requested = Signal()
    menu_requested = Signal(object)  # 全局坐标 QPoint
    appearance_changed = Signal()

    def __init__(self, sheet: SpriteSheet | None = None, size: int = DEFAULT_SIZE):
        super().__init__(
            None,
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool,
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowTitle("McPet（麦麦搭子）")
        # 不叫 self.size —— 那会盖掉 QWidget.size()，外部调 w.size() 会直接 TypeError。
        self.pet_size = size
        self._frame_delay_ms = resolve_frame_delay(sheet)

        self.machine = PetStateMachine("idle")
        self._activity_state = "idle"
        self._action_state: str | None = None
        self._action_loop = False
        self._action_target_skin: str | None = None
        self._preferences = PetPreferences()
        saved = self._preferences.load()
        self._last_agent_command = saved.get("pet_command_at", 0)
        self._deepseek_skin_id = saved.get("deepseek_skin_id", saved.get("skin_id", "default"))
        if self._deepseek_skin_id not in ("default", "maimai"):
            self._deepseek_skin_id = "default"
        self._character_id = (sheet.meta.get("character_id", "maimai") if sheet else DEFAULT_CHARACTER)
        saved_character = saved.get("character_id", self._character_id)
        saved_skin = self._deepseek_skin_id if saved_character == "deepseek" else "default"
        if saved_character in CHARACTER_IDS and (sheet is None or saved_character != self._character_id
                or saved_skin != sheet.meta.get("skin_id", "default")):
            try:
                sheet = load_character(saved_character, saved_skin)
                self._character_id = saved_character
            except (SpriteLoadError, ValueError):
                self._preferences.error = "无法恢复角色，使用默认素材"
        self._frame_delay_ms = resolve_frame_delay(sheet)
        self.roaming_enabled = saved.get("roaming") is True
        self.resting = saved.get("resting") is True
        self._behavior = RoamingBehavior()
        self._motion_x: float | None = None
        self._last_behavior = time.monotonic()
        self.sheet = sheet
        self.bubble = Bubble()

        self.canvas = QLabel(self)
        self.canvas.setFixedSize(size, size)
        self.canvas.setAlignment(Qt.AlignCenter)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.canvas)
        self.setLayout(layout)
        self.setFixedSize(size, size)

        self._frames: Sequence[QPixmap] = []
        self._cache: dict[str, Sequence[QPixmap]] = {}
        self._visual_cache: dict[tuple, Sequence[QPixmap]] = {}
        self._visual_key: tuple | None = None
        self._current_state: str | None = None
        self._index = 0
        self._anim = QTimer(self)
        # PreciseTimer 很关键：默认的 CoarseTimer 在 Windows 上被 ~15.6ms 的系统节拍
        # 量化，80ms 会被抬到 ~94ms（实测），帧率白掉 16%，观感就是「慢半拍」。
        self._anim.setTimerType(Qt.PreciseTimer)
        self._anim.timeout.connect(lambda: self._advance())
        self._next_frame = time.monotonic()
        self._bubble_timer = QTimer(self)
        self._bubble_timer.setSingleShot(True)
        self._bubble_timer.timeout.connect(self.bubble.hide)
        self._decay_timer = QTimer(self)
        self._decay_timer.setInterval(50)
        self._decay_timer.timeout.connect(self._decay)
        self._decay_timer.start()

        self._drag_offset = None
        self._press_point = None
        self._drag_active = False
        self._direction_extreme: int | None = None
        self._drag_direction = 0
        self._suppress_release = False
        self._menu_open = False
        self._screen_handle = None
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._touch)
        self._behavior_timer = QTimer(self)
        self._behavior_timer.setTimerType(Qt.PreciseTimer)
        self._behavior_timer.setInterval(30)
        self._behavior_timer.timeout.connect(self._step_behavior)
        self._behavior_timer.start()
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._save_preferences)
        self.set_state("idle")
        self._restore_position(saved)
        self._apply_base()
        self._watched_screens = []
        self._watch_screens()
        QApplication.instance().screenAdded.connect(self._watch_screens)
        QApplication.instance().screenRemoved.connect(self._watch_screens)
        self._preference_timer = QTimer(self)
        self._preference_timer.setInterval(1000)
        self._preference_timer.timeout.connect(self._receive_agent_command)
        self._preference_timer.start()

    # ---------- 素材 ----------

    @property
    def character_id(self) -> str:
        return self._character_id

    @property
    def skin_id(self) -> str:
        return self.sheet.meta.get("skin_id", "default") if self.sheet else "default"

    def set_skin(self, skin_id: str) -> None:
        validate_skin(self.character_id, skin_id)
        # Selecting even the currently worn skin cancels any transition.
        if self.skin_id == skin_id:
            self.stop_action()
            self._save_preferences()
            return
        self.set_character(self.character_id, skin_id=skin_id)

    def set_character(self, character_id: str, *, skin_id: str | None = None) -> None:
        selected_skin = (skin_id if skin_id is not None else
                         self._deepseek_skin_id if character_id == "deepseek" else "default")
        if character_id == self.character_id and selected_skin == self.skin_id and self.sheet is not None:
            return
        sheet = load_character(character_id) if selected_skin == "default" else load_character(character_id, selected_skin)
        # Prepare real current-state frames before changing any visible or saved
        # state, so a broken asset leaves the previous character fully usable.
        key = (sheet.row_for(self.machine.state), sheet.frame_count(self.machine.state),
               self.pet_size, self.devicePixelRatioF())
        old_count = max(1, len(self._frames))
        index = (self._index * key[1] // old_count) % key[1]
        frames = self._scaled_frames(sheet, self.machine.state, key[3], initial_index=index)
        if not frames:
            raise SpriteLoadError("角色动作为空")
        # A preserved phase may live on a different page than frame zero.
        # Decode and scale that actual frame before committing the switch too.
        presented = frames[index]
        if presented.isNull():
            raise SpriteLoadError("角色动作为空")
        delay = resolve_frame_delay(sheet, self.machine.state)
        preserve_clock = (self._anim.isActive() and delay == self._frame_delay_ms
                          and resolve_frame_hold(sheet, self.machine.state)
                          == resolve_frame_hold(self.sheet, self.machine.state))
        self._index = index
        self.sheet, self._character_id = sheet, character_id
        if character_id == "deepseek":
            self._deepseek_skin_id = selected_skin
        self._frame_delay_ms = delay
        self._cache = {self.machine.state: frames}
        self._visual_cache = {key: frames}
        self._visual_key, self._current_state, self._frames = key, self.machine.state, frames
        self.canvas.setPixmap(presented)
        # Character selection preserves the current cadence too. Restarting an
        # active timer with the same interval postpones its next frame, and on
        # Windows can prevent delivery inside the current Qt timer callback.
        if not preserve_clock:
            self._next_frame = time.monotonic() + self._frame_duration_ms(self._index) / 1000
        if self.isVisible() and not preserve_clock:
            self._anim.start(self._frame_delay_ms)
        self.stop_action()
        self._save_preferences()
        self.appearance_changed.emit()

    def _scaled_frames(self, sheet: SpriteSheet, state: str, dpr: float, *, initial_index: int = 0):
        if isinstance(sheet, AnimationSheet) and sheet.is_paged(state):
            frames = ScaledAnimationFrames(sheet, state, self.pet_size, dpr)
            # Decode the current source now, allowing transactional switching.
            if frames[initial_index].isNull():
                raise SpriteLoadError("角色动作为空")
            return frames
        frames = [frame.scaled(round(self.pet_size * dpr), round(self.pet_size * dpr),
                               Qt.KeepAspectRatio, Qt.SmoothTransformation)
                  for frame in sheet.frames(state)]
        for frame in frames:
            frame.setDevicePixelRatio(dpr)
        return frames

    def set_spritesheet(self, sheet: SpriteSheet) -> None:
        self.sheet = sheet
        self._frame_delay_ms = resolve_frame_delay(sheet, self.machine.state)
        self._cache.clear()
        self._visual_cache.clear()
        self._visual_key = None
        self._current_state = None
        self._character_id = sheet.meta.get("character_id", "maimai")
        self._load_frames(self.machine.state, force=True)

    def _render_placeholder(self) -> None:
        """没有素材时的兜底：一张透明底，保证程序不崩。"""
        pixmap = QPixmap(self.pet_size, self.pet_size)
        pixmap.fill(Qt.transparent)
        self.canvas.setPixmap(pixmap)

    # ---------- 状态与动画 ----------

    def play_action(self, state: str, *, loop: bool = False) -> None:
        if (self.sheet is None
                or state not in ({"frying", "outfit"} | set(CETAPET_ACTIONS))
                or state not in self.sheet.meta.get("animations", {})):
            raise SpriteLoadError("此角色没有该动作")
        target_skin = None
        if state in CETAPET_ACTIONS:
            require_pose(state)
            loop = True  # 原始姿态只有一帧，保持到用户切换或停止。
        if self.character_id == "deepseek":
            if state == "frying":
                self.set_skin("maimai")
            elif state == "outfit":
                target_skin = "maimai" if self.skin_id == "default" else "default"
                state = "outfit" if target_skin == "maimai" else "outfit-default"
                loop = False
        self._click_timer.stop()
        self.resting = False
        self._action_state, self._action_loop = state, loop
        self._action_target_skin = target_skin
        self._apply_base()
        self._load_frames(self.machine.state, force=True)
        self._save_preferences()

    def stop_action(self) -> None:
        if self._action_state is not None:
            self._action_state = None
            self._action_target_skin = None
            self._action_loop = False
            self._apply_base()
            self._save_preferences()

    def set_state(self, state: str, ttl_ms: int | None = None, *, force: bool = False) -> None:
        resolved = self.machine.set(state, ttl_ms)
        self._load_frames(resolved, force=force)

    def _load_frames(self, state: str, *, force: bool = False) -> None:
        if not self.sheet:
            self._render_placeholder()
            return
        key = (self.sheet.row_for(state), self.sheet.frame_count(state), self.pet_size,
               self.devicePixelRatioF())
        same_row = self._visual_key is not None and key[:2] == self._visual_key[:2]
        if key == self._visual_key and not force and self._frames:
            # 同一状态被重复设置（拖拽时每个 mousemove 都来一次）：
            # 既不重建帧、也**不把帧号归零**——否则跑动动画会被永远冻在第 0 帧。
            self._current_state = state
            self._cache[state] = self._frames
            return

        frames = self._visual_cache.get(key)
        if frames is None:
            try:
                frames = self._scaled_frames(self.sheet, state, key[3], initial_index=(
                    self._index % key[1] if same_row and not force else 0))
            except (ValueError, RuntimeError):
                frames = []
            self._visual_cache[key] = frames
            # Two sequences bound decoded/scaled memory, including DPR changes.
            while len(self._visual_cache) > 2:
                oldest = next(iter(self._visual_cache))
                del self._visual_cache[oldest]
            retained = {id(value) for value in self._visual_cache.values()}
            self._cache = {name: value for name, value in self._cache.items() if id(value) in retained}
        else:
            self._visual_cache.pop(key)
            self._visual_cache[key] = frames
            if isinstance(frames, ScaledAnimationFrames):
                # A cached preview frame can outlive its source atlas. Load the
                # selected source during the action change, not the next tick.
                self.sheet.frame(state, self._index % key[1] if same_row and not force else 0)
        self._cache[state] = frames

        self._current_state = state
        self._visual_key = key
        self._frames = frames
        if not frames:
            self._render_placeholder()
            self._anim.stop()
            return
        if force or not same_row:
            self._index = 0
            self._frame_delay_ms = resolve_frame_delay(self.sheet, state)
            self._next_frame = time.monotonic() + self._frame_duration_ms(0) / 1000
            self._anim.start(self._frame_delay_ms)
        self.canvas.setPixmap(frames[self._index % len(frames)])

    def _frame_duration_ms(self, index: int) -> int:
        hold = resolve_frame_hold(self.sheet, self._current_state or "idle") if index == 0 else 0
        return self._frame_delay_ms + hold

    def _advance(self) -> None:
        if not self._frames:
            self._anim.stop()
            return
        now = time.monotonic()
        hold = resolve_frame_hold(self.sheet, self._current_state or "idle")
        if hold:
            if now < self._next_frame:
                return
            # Skip complete cycles after a delayed callback; do not replay them
            # rapidly or lose the dwell when the short atlas wraps to frame zero.
            cycle = (len(self._frames) * self._frame_delay_ms + hold) / 1000
            self._next_frame += math.floor((now - self._next_frame) / cycle) * cycle
            while now >= self._next_frame:
                self._index = (self._index + 1) % len(self._frames)
                self._next_frame += self._frame_duration_ms(self._index) / 1000
            self.canvas.setPixmap(self._frames[self._index])
            return
        delay = self._frame_delay_ms / 1000
        steps = max(1, math.floor((now - self._next_frame) / delay) + 1)
        self._next_frame += steps * delay
        if (self._current_state == self._action_state and not self._action_loop
                and self._index + steps >= len(self._frames)):
            target = self._action_target_skin
            self.stop_action()
            if target is not None:
                self.set_skin(target)
            return
        self._index = (self._index + steps) % len(self._frames)
        self.canvas.setPixmap(self._frames[self._index])

    def _decay(self) -> None:
        new_state = self.machine.tick()
        if new_state is not None:
            self._load_frames(new_state)

    # ---------- 说话 ----------

    def say(self, text: str, ttl_ms: int = 8000) -> None:
        if self.bubble.interacting:
            return
        self.bubble.show_text(text, self)
        self._bubble_timer.start(ttl_ms)

    def ask(self, text, choices, **kwargs):
        self._bubble_timer.stop()
        return self.bubble.ask(text, self, choices, **kwargs)

    def say_state(self, state: str, text: str, ttl_ms: int = 8000) -> None:
        self.set_state(state)
        self.say(text, ttl_ms)

    def set_activity(self, state: str, context_percent=None, label: str = "") -> None:
        # Progress details stay in the menu/Agent; polling only drives animation.
        self._activity_state = state
        self._apply_base()
        self._clamp()

    def _apply_base(self) -> None:
        self.machine.set_base(self._activity_state)
        if self._drag_active:
            interaction = ("run-right" if self._drag_direction > 0 else
                           "run-left" if self._drag_direction < 0 else "idle")
        else:
            interaction = "sleeping" if self.resting else self._action_state
        self._load_frames(self.machine.set_interaction(interaction))

    def set_roaming(self, enabled: bool) -> None:
        self.roaming_enabled = bool(enabled)
        self._motion_x = None
        self._apply_base()
        self._save_preferences()

    def set_resting(self, enabled: bool) -> None:
        self.resting = bool(enabled)
        if self.resting:
            self._action_state = None
            self._action_target_skin = None
            self._click_timer.stop()
            self.bubble.hide()
        self._apply_base()
        self._save_preferences()

    def _step_behavior(self) -> None:
        now = time.monotonic()
        elapsed, self._last_behavior = now - self._last_behavior, now
        paused = (not self.isVisible() or not self.roaming_enabled or self.resting
                  or self._press_point is not None or self._click_timer.isActive()
                  or self._menu_open
                  or self._bubble_timer.isActive() or self.bubble.interacting or self.machine.state != self.machine.base_state
                  or self._activity_state != "idle")
        dx, state = self._behavior.advance(elapsed, paused=paused)
        if paused:
            return
        self._load_frames(self.machine.set_base(state))
        if dx:
            if self._motion_x is None:
                self._motion_x = float(self.x())
            self._motion_x += dx
            target = QPoint(round(self._motion_x), self.y())
            bounded = clamp_position(target, self.size(), self._areas())
            if bounded.x() != target.x():
                self._behavior.turn()
                self._motion_x = float(bounded.x())
            self.move(bounded)

    def _areas(self) -> list[QRect]:
        return [screen.availableGeometry() for screen in QApplication.screens()]

    def _watch_screens(self, *args) -> None:
        for screen in QApplication.screens():
            if screen not in self._watched_screens:
                screen.availableGeometryChanged.connect(self._on_geometry_changed)
                screen.logicalDotsPerInchChanged.connect(self._on_geometry_changed)
        self._watched_screens = QApplication.screens()
        self._on_geometry_changed()

    def _on_geometry_changed(self, *args) -> None:
        self._clamp()
        self._motion_x = None
        self._load_frames(self.machine.state)

    def _clamp(self) -> None:
        self.adjustSize()
        self.move(clamp_position(self.pos(), self.size(), self._areas()))

    def _restore_position(self, saved: dict) -> None:
        self.adjustSize()
        screens = QApplication.screens()
        if not screens:
            return
        area = screens[0].availableGeometry()
        point = QPoint(area.right() - self.width() - 24, area.bottom() - self.height() - 24)
        xy = saved.get("position")
        if isinstance(xy, list) and len(xy) == 2 and all(type(v) is int for v in xy):
            point = QPoint(*xy)
            for screen in screens:
                if screen.name() == saved.get("screen"):
                    new = screen.availableGeometry()
                    old = saved.get("available_geometry")
                    if isinstance(old, list) and len(old) == 4 and all(type(v) is int for v in old) and old[2] > 0 and old[3] > 0:
                        point = QPoint(new.x() + round((xy[0] - old[0]) * new.width() / old[2]),
                                       new.y() + round((xy[1] - old[1]) * new.height() / old[3]))
                    break
        self.move(clamp_position(point, self.size(), self._areas()))

    def _save_preferences(self) -> None:
        screen = self.screen()
        area = screen.availableGeometry()
        with data_lock():
            saved = self._preferences.load()
            incoming = saved.get("pet_command_at", 0)
            if isinstance(incoming, (int, float)) and incoming > self._last_agent_command:
                # A position save can run before the 1s command poll. Keep the
                # unread Agent command, rather than overwriting its costume/action.
                saved.update(position=[self.x(), self.y()], screen=screen.name(),
                             available_geometry=[area.x(), area.y(), area.width(), area.height()],
                             roaming=self.roaming_enabled)
                self._preferences.save(saved)
                return
            saved.update(position=[self.x(), self.y()], screen=screen.name(),
                         available_geometry=[area.x(), area.y(), area.width(), area.height()],
                         roaming=self.roaming_enabled, resting=self.resting,
                         character_id=self.character_id, skin_id=self.skin_id,
                         deepseek_skin_id=self._deepseek_skin_id)
            saved.update(action=("outfit" if self._action_state == "outfit-default" else
                                 self._action_state or ("sleeping" if self.resting else self._activity_state)),
                         action_loop=self._action_loop)
            if self._action_target_skin:
                saved["pending_skin_id"] = self._action_target_skin
            else:
                saved.pop("pending_skin_id", None)
            if self._action_state:
                saved["action_animation"] = self._action_state
                if not self._action_loop and "action_until" not in saved:
                    saved["action_until"] = time.time() + self.sheet.frame_count(self._action_state) * self._frame_delay_ms / 1000
            else:
                saved.pop("action_animation", None)
                saved.pop("action_until", None)
            self._preferences.save(saved)

    def _receive_agent_command(self) -> None:
        saved = self._preferences.load()
        stamp = saved.get("pet_command_at", 0)
        if not isinstance(stamp, (int, float)) or stamp <= self._last_agent_command:
            return
        self._last_agent_command = stamp
        try:
            character = saved.get("character_id", self.character_id)
            skin = saved.get("skin_id", "default")
            self.set_character(character, skin_id=skin)
            self.stop_action()
            action = saved.get("action", "idle")
            if saved.get("action_until", 0) and saved["action_until"] <= time.time():
                if saved.get("pending_skin_id"):
                    self.set_skin(saved["pending_skin_id"])
                return
            if action in ({"frying", "outfit"} | set(CETAPET_ACTIONS)):
                self.play_action(action, loop=saved.get("action_loop") is True)
            elif action == "sleeping":
                self.set_resting(True)
            else:
                self.set_resting(False)
                self.set_activity(action)
        except (SpriteLoadError, ValueError, TypeError):
            self._preferences.error = "无法应用 Agent 的桌宠动作"

    def moveEvent(self, event):  # noqa: N802
        super().moveEvent(event)
        if hasattr(self, "_save_timer"):
            self._save_timer.start(500)
        if hasattr(self, "bubble") and self.bubble.isVisible():
            self.bubble.show_text(self.bubble.label.text(), self)

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self._clamp()
        self._last_behavior = time.monotonic()
        self._behavior_timer.start()
        if self._frames:
            self._next_frame = time.monotonic() + self._frame_duration_ms(self._index) / 1000
            self._anim.start(self._frame_delay_ms)
        if self.windowHandle() and self._screen_handle is None:
            self._screen_handle = self.windowHandle()
            self._screen_handle.screenChanged.connect(self._screen_changed)

    def hideEvent(self, event):  # noqa: N802
        self._anim.stop()
        self._behavior_timer.stop()
        self.bubble.hide()
        super().hideEvent(event)

    def _screen_changed(self, screen) -> None:
        self._clamp()
        self._motion_x = None
        self._load_frames(self.machine.state)

    def closeEvent(self, event):  # noqa: N802
        self._preference_timer.stop()
        self._save_preferences()
        for timer in (self._anim, self._decay_timer, self._behavior_timer, self._bubble_timer,
                      self._click_timer, self._save_timer):
            timer.stop()
        self.bubble.close()
        for screen in self._watched_screens:
            try:
                screen.availableGeometryChanged.disconnect(self._on_geometry_changed)
                screen.logicalDotsPerInchChanged.disconnect(self._on_geometry_changed)
            except RuntimeError:
                pass
        app = QApplication.instance()
        try:
            app.screenAdded.disconnect(self._watch_screens)
            app.screenRemoved.disconnect(self._watch_screens)
        except RuntimeError:
            pass
        if self._screen_handle is not None:
            try:
                self._screen_handle.screenChanged.disconnect(self._screen_changed)
            except RuntimeError:
                pass
            self._screen_handle = None
        super().closeEvent(event)

    # ---------- 交互 ----------

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            point = event.globalPosition().toPoint()
            self._drag_offset = point - self.pos()
            self._press_point = point
            self._drag_active = False
            self._direction_extreme = point.x()
            self._drag_direction = 0
            self._suppress_release = False
        event.accept()

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            point = event.globalPosition().toPoint()
            if not self._drag_active:
                if (point - self._press_point).manhattanLength() < QApplication.startDragDistance():
                    event.accept()
                    return
                self._drag_active = True
                self._action_state = None
                self._action_target_skin = None
                self._click_timer.stop()
            self.move(clamp_position(point - self._drag_offset, self.size(), self._areas()))
            self._motion_x = None
            self.bubble.hide()
            # Reverse only after 8 logical pixels from the directional extreme;
            # accumulating genuine reversals still works with many 1px events.
            delta = point.x() - self._direction_extreme
            if (self._drag_direction >= 0 and delta > 0) or (self._drag_direction <= 0 and delta < 0):
                self._direction_extreme = point.x()
            if abs(delta) >= 8 and (delta > 0) != (self._drag_direction > 0):
                self._drag_direction = 1 if delta > 0 else -1
                self._direction_extreme = point.x()
            elif self._drag_direction == 0 and abs(delta) >= 8:
                self._drag_direction = 1 if delta > 0 else -1
            self._apply_base()
        event.accept()

    def mouseReleaseEvent(self, event):  # noqa: N802
        pressed = self._press_point is not None
        moved = self._drag_active
        self._drag_offset = None
        self._press_point = None
        self._drag_active = False
        if event.button() == Qt.LeftButton:
            if moved:
                self._apply_base()
                self._save_preferences()
            elif pressed and not self._suppress_release:
                self._click_timer.start(QApplication.doubleClickInterval())
            self._suppress_release = False
        elif event.button() == Qt.RightButton:
            self.menu_requested.emit(event.globalPosition().toPoint())
        event.accept()

    def _touch(self) -> None:
        self.stop_action()
        self.set_state("greet", ttl_ms=2000)
        self.say("我在呢～右键戳戳我，今天也陪你一起。", 3000)
        self.clicked.emit()

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._click_timer.stop()
            self._suppress_release = True
            self._press_point = None
            self._drag_offset = None
            self.chat_requested.emit()
        event.accept()

    def show_menu(self, actions: list[tuple[str, object]], point) -> None:
        menu = QMenu(self)
        self._menu_open = True
        try:
            populate_menu(menu, actions)
            menu.exec(point)
        finally:
            self._menu_open = False
            menu.deleteLater()
