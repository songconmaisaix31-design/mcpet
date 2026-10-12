"""系统托盘常驻。"""

from __future__ import annotations

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon
from .menu import populate_menu


class PetTray(QSystemTrayIcon):
    """托盘图标。项由外部传入 [(文案, 回调)]，None 表示分隔线。"""

    def __init__(self, icon: QIcon, entries: list[tuple[str, object] | None], parent=None):
        super().__init__(icon, parent)
        self.setToolTip("McPet · 今天也陪你一起")
        self._menu = QMenu()
        self._build(entries)
        self.setContextMenu(self._menu)
        self.activated.connect(self._on_activated)
        self.show()

    def _build(self, entries: list[tuple[str, object] | None]) -> None:
        self._menu.clear()
        populate_menu(self._menu, entries)

    def set_entries(self, entries):
        self._build(entries)

    def _on_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            callback = getattr(self, "on_activate", None)
            if callback:
                callback()
