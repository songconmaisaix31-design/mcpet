from PySide6.QtCore import QPoint, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QWidget

from src.pet.window import Bubble, PetWindow


def test_bubble_has_transparent_corners_and_one_continuous_surface():
    anchor = QWidget()
    anchor.resize(180, 180)
    anchor.move(300, 350)
    bubble = Bubble()
    try:
        bubble.show_text("右键 → 设置，查看饭点和咖啡时间。", anchor)
        QApplication.processEvents()
        image = bubble.grab().toImage()
        ratio = image.devicePixelRatio()
        assert image.pixelColor(0, 0).alpha() == 0
        assert image.pixelColor(image.width() - 1, image.height() - 1).alpha() == 0
        assert image.pixelColor(int(2 * ratio), int(image.height() / 2)) == QColor("#FFF8E7")
        assert bubble.scroll.viewport().width() == bubble.width() - 28
        assert bubble.scroll.verticalScrollBar().maximum() == 0
        assert bubble.height() == bubble.scroll.height() + 24
    finally:
        bubble.close()
        anchor.close()


def test_interactive_bubble_keeps_controls_inside_surface_and_cancels():
    anchor = QWidget()
    anchor.resize(180, 180)
    anchor.move(300, 350)
    bubble = Bubble()
    observed = {}

    def cancel():
        try:
            image = bubble.grab().toImage()
            observed["corner_alpha"] = image.pixelColor(0, image.height() - 1).alpha()
            observed["controls_inside"] = bubble.surface.rect().contains(bubble.controls.geometry())
            observed["input_width"] = bubble.input.geometry().width()
            observed["scroll_width"] = bubble.scroll.width()
        finally:
            bubble.buttons[-1].click()

    try:
        QTimer.singleShot(30, cancel)
        assert bubble.ask("咖啡时间", anchor, [("确定", "__input__")], placeholder="HH:MM") is None
        assert observed["corner_alpha"] == 0
        assert observed["controls_inside"]
        assert observed["input_width"] == observed["scroll_width"]
        assert not bubble.interacting
        assert not bubble.isVisible()
    finally:
        bubble.close()
        anchor.close()


def test_new_report_resets_scroll_and_short_report_shrinks():
    anchor = QWidget()
    anchor.resize(180, 180)
    anchor.move(300, 350)
    bubble = Bubble()
    try:
        bubble.show_text("\n".join(["会话进度 · 本机用量 · 账号额度 / 余额"] * 30), anchor)
        QApplication.processEvents()
        scroll = bubble.scroll.verticalScrollBar()
        assert scroll.maximum() > 0
        scroll.setValue(scroll.maximum())
        bubble.show_text("今日营养", anchor)
        QApplication.processEvents()
        assert scroll.value() == 0
        assert scroll.maximum() == 0
        assert bubble.scroll.height() < 190
    finally:
        bubble.close()
        anchor.close()


def test_moving_pet_preserves_report_scroll():
    window = PetWindow()
    try:
        window.move(300, 350)
        window.show()
        window.say("\n".join(["会话进度 · 本机用量 · 账号额度 / 余额"] * 30), 60000)
        QApplication.processEvents()
        scroll = window.bubble.scroll.verticalScrollBar()
        scroll.setValue(scroll.maximum() // 2)
        value = scroll.value()
        previous_x = window.bubble.x()
        window.move(window.pos() + QPoint(40, 0))
        QApplication.processEvents()
        assert scroll.value() == value
        assert window.bubble.x() == previous_x + 40
    finally:
        window.close()
