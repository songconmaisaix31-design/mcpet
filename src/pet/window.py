"""桌宠窗口：无边框置顶、精灵图逐帧播放、气泡、拖拽、右键菜单。

架构参考 CeTaPet（托盘常驻 + 状态机 + 气泡 + 拖拽），代码为本项目重写：
素材从「单张 PNG 切换」换成 spritesheet 切片播放，状态机带优先级与 TTL 衰减。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QFont, QPixmap
from PySide6.QtWidgets import QLabel, QMenu, QVBoxLayout, QWidget

from .spritesheet import SpriteSheet
from .states import PetStateMachine

DEFAULT_SIZE = 180


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
        self.setWindowTitle("麦麦小怪兽")
        self.size = size

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
        self._index = 0
        self._anim = QTimer(self)
        self._anim.timeout.connect(self._advance)
        self._bubble_timer = QTimer(self)
        self._bubble_timer.setSingleShot(True)
        self._bubble_timer.timeout.connect(self.bubble.hide)
        self._decay_timer = QTimer(self)
        self._decay_timer.setInterval(1000)
        self._decay_timer.timeout.connect(self._decay)
        self._decay_timer.start()

        self._drag_offset = None
        self.set_state("idle")
        self._render_placeholder()

    # ---------- 素材 ----------

    def set_spritesheet(self, sheet: SpriteSheet) -> None:
        self.sheet = sheet
        self.set_state(self.machine.state)

    def _render_placeholder(self) -> None:
        """没有素材时的兜底：一个纯色圆角方块，保证程序不崩。"""
        pixmap = QPixmap(self.size, self.size)
        pixmap.fill(Qt.transparent)
        self.canvas.setPixmap(pixmap)

    # ---------- 状态与动画 ----------

    def set_state(self, state: str, ttl_ms: int | None = None) -> None:
        resolved = self.machine.set(state, ttl_ms)
        self._load_frames(resolved)

    def _load_frames(self, state: str) -> None:
        if not self.sheet:
            self._render_placeholder()
            return
        try:
            self._frames = [
                frame.scaled(
                    self.size,
                    self.size,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                for frame in self.sheet.frames(state)
            ]
        except Exception:
            self._frames = []
            self._render_placeholder()
            return
        self._index = 0
        if self._frames:
            self.canvas.setPixmap(self._frames[0])
            if not self._anim.isActive():
                self._anim.start(self.sheet.frame_delay_ms)
        else:
            self._anim.stop()

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
            self._drag_offset = event.globalPosition().toPoint() - self.pos()
        event.accept()

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            self.bubble.hide()
            self.set_state(
                "run-right"
                if event.globalPosition().toPoint().x() >= self.pos().x()
                else "run-left"
            )
        event.accept()

    def mouseReleaseEvent(self, event):  # noqa: N802
        moved = self._drag_offset is not None
        self._drag_offset = None
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
