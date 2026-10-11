"""系统托盘常驻。"""

from __future__ import annotations

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


class PetTray(QSystemTrayIcon):
    """托盘图标。项由外部传入 [(文案, 回调)]，None 表示分隔线。"""

    def __init__(self, icon: QIcon, entries: list[tuple[str, object] | None], parent=None):
        super().__init__(icon, parent)
        self.setToolTip("McPet（麦麦搭子）")
        self._menu = QMenu()
        self._build(entries)
        self.setContextMenu(self._menu)
        self.activated.connect(self._on_activated)
        self.show()

    def _build(self, entries: list[tuple[str, object] | None]) -> None:
        self._menu.clear()
        for entry in entries:
            if entry is None:
                self._menu.addSeparator()
                continue
            label, callback = entry
            action = QAction(label, self._menu)
            action.triggered.connect(callback)  # type: ignore[arg-type]
            self._menu.addAction(action)

    def set_entries(self, entries):
        self._build(entries)

    def _on_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            callback = getattr(self, "on_activate", None)
            if callback:
                callback()
