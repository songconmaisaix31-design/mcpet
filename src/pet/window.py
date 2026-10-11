"""桌宠窗口：无边框置顶、精灵图逐帧播放、气泡、拖拽、右键菜单。

架构参考 CeTaPet（托盘常驻 + 状态机 + 气泡 + 拖拽），代码为本项目重写：
素材从「单张 PNG 切换」换成 spritesheet 切片播放，状态机带优先级与 TTL 衰减。
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QFont, QPixmap
from PySide6.QtWidgets import QLabel, QMenu, QVBoxLayout, QWidget

from .spritesheet import SpriteSheet
from .states import PetStateMachine

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
        layout.addWidget(self.label)

    def show_text(self, text: str, anchor: QWidget) -> None:
        self.label.setText(text)
        self.adjustSize()
        x = anchor.x() + anchor.width() // 2 - self.width() // 2
        y = anchor.y() - self.height() - 6
        self.move(max(x, 4), max(y, 4))
        self.show()
        self.raise_()


class PetWindow(QWidget):
    """桌宠主窗口。"""

    clicked = Signal()
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
        self.sheet = sheet
        self.bubble = Bubble()

        self.canvas = QLabel(self)
        self.canvas.setFixedSize(size, size)
        self.canvas.setAlignment(Qt.AlignCenter)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)
        self.setLayout(layout)

        self._frames: list[QPixmap] = []
        self._cache: dict[str, list[QPixmap]] = {}  # state -> 已缩放帧，切状态不再重算
        self._current_state: str | None = None
        self._index = 0
        self._anim = QTimer(self)
        # PreciseTimer 很关键：默认的 CoarseTimer 在 Windows 上被 ~15.6ms 的系统节拍
        # 量化，80ms 会被抬到 ~94ms（实测），帧率白掉 16%，观感就是「慢半拍」。
        self._anim.setTimerType(Qt.PreciseTimer)
        self._anim.timeout.connect(self._advance)
        self._bubble_timer = QTimer(self)
        self._bubble_timer.setSingleShot(True)
        self._bubble_timer.timeout.connect(self.bubble.hide)
        self._decay_timer = QTimer(self)
        self._decay_timer.setInterval(1000)
        self._decay_timer.timeout.connect(self._decay)
        self._decay_timer.start()

        self._drag_offset = None
        self._drag_x: int | None = None
        self.set_state("idle")
        self._render_placeholder()

    # ---------- 素材 ----------

    def set_spritesheet(self, sheet: SpriteSheet) -> None:
        self.sheet = sheet
        self._frame_delay_ms = resolve_frame_delay(sheet)
        self._cache.clear()
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
        if state == self._current_state and not force and self._frames:
            # 同一状态被重复设置（拖拽时每个 mousemove 都来一次）：
            # 既不重建帧、也**不把帧号归零**——否则跑动动画会被永远冻在第 0 帧。
            return

        frames = self._cache.get(state)
        if frames is None:
            try:
                frames = [
                    frame.scaled(
                        self.pet_size,
                        self.pet_size,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                    for frame in self.sheet.frames(state)
                ]
            except Exception:
                frames = []
            self._cache[state] = frames

        self._current_state = state
        self._frames = frames
        if not frames:
            self._render_placeholder()
            self._anim.stop()
            return
        self._index = 0
        self.canvas.setPixmap(frames[0])
        if not self._anim.isActive():
            self._anim.start(self._frame_delay_ms)

    def _advance(self) -> None:
        if not self._frames:
            self._anim.stop()
            return
        self._index = (self._index + 1) % len(self._frames)
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

    # ---------- 交互 ----------

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            point = event.globalPosition().toPoint()
            self._drag_offset = point - self.pos()
            self._drag_x = point.x()
        event.accept()

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            point = event.globalPosition().toPoint()
            previous_x = self._drag_x
            self.move(point - self._drag_offset)
            self._drag_x = point.x()
            self.bubble.hide()
            # 方向必须跟「上一个鼠标事件的 x」比。原来拿 move() 之后的 self.pos() 去比，
            # 那等价于拿拖拽偏移量比，方向基本是随机的，还会在相邻事件之间反复翻转——
            # 每翻转一次就换一套帧并把动画归零，观感就是拖拽时画面在抖。
            if previous_x is not None and point.x() != previous_x:
                self.set_state("run-right" if point.x() > previous_x else "run-left")
        event.accept()

    def mouseReleaseEvent(self, event):  # noqa: N802
        moved = self._drag_offset is not None
        self._drag_offset = None
        self._drag_x = None
        if event.button() == Qt.LeftButton:
            if moved:
                self.set_state("idle")
            self.clicked.emit()
        elif event.button() == Qt.RightButton:
            self.menu_requested.emit(event.globalPosition().toPoint())
        event.accept()

    def show_menu(self, actions: list[tuple[str, object]], point) -> None:
        menu = QMenu(self)
        for label, callback in actions:
            action = QAction(label, self)
            action.triggered.connect(callback)  # type: ignore[arg-type]
            menu.addAction(action)
        menu.exec(point)
