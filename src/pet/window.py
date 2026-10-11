"""桌宠窗口：无边框置顶、精灵图逐帧播放、气泡、拖拽、右键菜单。

架构参考 CeTaPet（托盘常驻 + 状态机 + 气泡 + 拖拽），代码为本项目重写：
素材从「单张 PNG 切换」换成 spritesheet 切片播放，状态机带优先级与 TTL 衰减。
"""

from __future__ import annotations

import os
import math
import time

from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QProgressBar, QVBoxLayout, QWidget

from .spritesheet import SpriteSheet
from .states import PetStateMachine
from .behavior import RoamingBehavior, clamp_position
from .preferences import PetPreferences

DEFAULT_SIZE = 180
DEFAULT_FRAME_DELAY_MS = 80
MIN_FRAME_DELAY_MS = 16  # 再快也没意义：图集本身只有 4~8 帧


def resolve_frame_delay(sheet: SpriteSheet | None) -> int:
    """帧间隔（毫秒）。优先级：环境变量 > 图集自带 > 默认。

    图集规格里没有帧时长定义（longniang 仓库只有素材与布局，不含播放规范），
    所以给一个可调默认值，方便给不同素材各自标定节奏。
    """
    raw = os.environ.get("MCPET_FRAME_DELAY_MS", "").strip()
    if raw:
        try:
            return max(MIN_FRAME_DELAY_MS, int(raw))
        except ValueError:
            pass
    if sheet is not None and sheet.frame_delay_ms:
        return max(MIN_FRAME_DELAY_MS, int(sheet.frame_delay_ms))
    return DEFAULT_FRAME_DELAY_MS


class Bubble(QWidget):
    """气泡。跟随桌宠窗口上沿，纯展示，不抢焦点。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self.label)

    def show_text(self, text: str, anchor: QWidget) -> None:
        self.label.setText(text)
        self.adjustSize()
        x = anchor.x() + anchor.width() // 2 - self.width() // 2
        y = anchor.y() - self.height() - 6
        if y < anchor.screen().availableGeometry().top():
            y = anchor.y() + anchor.height() + 6
        self.move(clamp_position(QPoint(x, y), self.size(),
                                 [anchor.screen().availableGeometry()]))
        self.show()
        self.raise_()


class PetWindow(QWidget):
    """桌宠主窗口。"""

    clicked = Signal()
    chat_requested = Signal()
    menu_requested = Signal(object)  # 全局坐标 QPoint

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
        self._preferences = PetPreferences()
        saved = self._preferences.load()
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
        layout.setSpacing(2)
        self.activity_label = QLabel(self)
        self.activity_label.setAlignment(Qt.AlignCenter)
        self.activity_label.setStyleSheet("color:#614819;background:#FFF8E7;border-radius:4px;")
        self.activity_label.setFixedHeight(20)
        self.context_bar = QProgressBar(self)
        self.context_bar.setRange(0, 100)
        self.context_bar.setFormat("上下文 %p%")
        self.context_bar.setFixedHeight(18)
        self.context_bar.setStyleSheet(
            "QProgressBar{background:#FFF8E7;color:#3A2A12;border:1px solid #E0B24C;"
            "border-radius:4px;text-align:center;}"
            "QProgressBar::chunk{background:#F0C34D;border-radius:3px;}"
        )
        # Reserve fixed header space: UNKNOWN -> measured context must not move
        # the sprite's screen anchor on every background refresh.
        for control in (self.activity_label, self.context_bar):
            policy = control.sizePolicy()
            policy.setRetainSizeWhenHidden(True)
            control.setSizePolicy(policy)
        self.activity_label.hide()
        self.context_bar.hide()
        layout.addWidget(self.activity_label)
        layout.addWidget(self.context_bar)
        layout.addWidget(self.canvas)
        self.setLayout(layout)
        self.setFixedSize(size, size + 42)

        self._frames: list[QPixmap] = []
        self._cache: dict[str, list[QPixmap]] = {}  # state -> 已缩放帧，切状态不再重算
        self._visual_cache: dict[tuple, list[QPixmap]] = {}
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

    # ---------- 素材 ----------

    def set_spritesheet(self, sheet: SpriteSheet) -> None:
        self.sheet = sheet
        self._frame_delay_ms = resolve_frame_delay(sheet)
        self._cache.clear()
        self._visual_cache.clear()
        self._visual_key = None
        self._current_state = None
        self.set_state(self.machine.state, force=True)

    def _render_placeholder(self) -> None:
        """没有素材时的兜底：一张透明底，保证程序不崩。"""
        pixmap = QPixmap(self.pet_size, self.pet_size)
        pixmap.fill(Qt.transparent)
        self.canvas.setPixmap(pixmap)

    # ---------- 状态与动画 ----------

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
                frames = [
                    frame.scaled(
                        round(self.pet_size * key[3]),
                        round(self.pet_size * key[3]),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                    for frame in self.sheet.frames(state)
                ]
                for frame in frames:
                    frame.setDevicePixelRatio(key[3])
            except (ValueError, RuntimeError):
                frames = []
            self._visual_cache[key] = frames
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
            self._next_frame = time.monotonic() + self._frame_delay_ms / 1000
            self._anim.start(self._frame_delay_ms)
        self.canvas.setPixmap(frames[self._index % len(frames)])

    def _advance(self) -> None:
        if not self._frames:
            self._anim.stop()
            return
        delay = self._frame_delay_ms / 1000
        steps = max(1, math.floor((time.monotonic() - self._next_frame) / delay) + 1)
        self._next_frame += steps * delay
        self._index = (self._index + steps) % len(self._frames)
        self.canvas.setPixmap(self._frames[self._index])

    def _decay(self) -> None:
        new_state = self.machine.tick()
        if new_state is not None:
            self._load_frames(new_state)

    # ---------- 说话 ----------

    def say(self, text: str, ttl_ms: int = 8000) -> None:
        self.bubble.show_text(text, self)
        self._bubble_timer.start(ttl_ms)

    def say_state(self, state: str, text: str, ttl_ms: int = 8000) -> None:
        self.set_state(state)
        self.say(text, ttl_ms)

    def set_activity(self, state: str, context_percent=None, label: str = "") -> None:
        self._activity_state = state
        valid = (isinstance(context_percent, (int, float)) and not isinstance(context_percent, bool)
                 and math.isfinite(context_percent) and 0 <= context_percent <= 100)
        self.context_bar.setVisible(valid)
        if valid:
            self.context_bar.setValue(round(context_percent))
        text = label if valid else (f"{label} · 上下文未知" if label else "上下文未知")
        self.activity_label.setText(text)
        self.activity_label.setVisible(bool(text))
        self._apply_base()
        self._clamp()

    def _apply_base(self) -> None:
        self.machine.set_base(self._activity_state)
        if self._drag_active:
            interaction = ("run-right" if self._drag_direction > 0 else
                           "run-left" if self._drag_direction < 0 else "idle")
        else:
            interaction = "sleeping" if self.resting else None
        self._load_frames(self.machine.set_interaction(interaction))

    def set_roaming(self, enabled: bool) -> None:
        self.roaming_enabled = bool(enabled)
        self._motion_x = None
        self._apply_base()
        self._save_preferences()

    def set_resting(self, enabled: bool) -> None:
        self.resting = bool(enabled)
        if self.resting:
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
                  or self._bubble_timer.isActive() or self.machine.state != self.machine.base_state
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
        self._preferences.save({"position": [self.x(), self.y()], "screen": screen.name(),
                                "available_geometry": [area.x(), area.y(), area.width(), area.height()],
                                "roaming": self.roaming_enabled, "resting": self.resting})

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
            self._next_frame = time.monotonic() + self._frame_delay_ms / 1000
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
        self.set_state("greet", ttl_ms=2000)
        self.say("我在呢，陪你一起。双击打开麦麦小窝。", 3000)
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
            for label, callback in actions:
                action = menu.addAction(label)
                action.triggered.connect(callback)  # type: ignore[arg-type]
            menu.exec(point)
        finally:
            self._menu_open = False
            menu.deleteLater()
