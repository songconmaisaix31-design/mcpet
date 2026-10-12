"""Shared compact recursive menu for the pet and tray."""
from PySide6.QtWidgets import QMenu


def populate_menu(menu, entries):
    for entry in entries:
        if entry is None:
            menu.addSeparator()
            continue
        label, target = entry
        if isinstance(target, (list, tuple)):
            child = menu.addMenu(label)
            populate_menu(child, target)
        else:
            action = menu.addAction(label)
            action.triggered.connect(lambda checked=False, callback=target: callback())
