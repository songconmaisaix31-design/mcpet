"""持续聊天窗口：模式明确，错误与 pending 可见，偏好由用户主动维护。"""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QComboBox,
                              QPlainTextEdit, QPushButton, QLabel, QListWidget,
                              QLineEdit, QMessageBox)

from .. import config


class MemoryDialog(QDialog):
    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("本机偏好 · 仅保存你主动填写的内容")
        self.resize(500, 350)
        layout = QVBoxLayout(self)
        hint = QLabel("这些偏好会随聊天发给 StepFun，不读取其他个人文件。清除偏好不会删除聊天历史；聊天内容请在聊天窗口单独清空。")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.items = QListWidget()
        self.items.addItems(store.memories)
        layout.addWidget(self.items)
        self.input = QLineEdit()
        self.input.setMaxLength(500)
        self.input.setPlaceholderText("例如：请叫我小王；聊天回答简短一些")
        layout.addWidget(self.input)
        row = QHBoxLayout()
        for title, fn in (("保存偏好", self.save), ("删除选中", self.delete), ("清空偏好", self.clear)):
            button = QPushButton(title)
            button.clicked.connect(fn)
            row.addWidget(button)
        layout.addLayout(row)

    def reload(self):
        self.items.clear()
        self.items.addItems(self.store.memories)

    def save(self):
        try:
            self.store.remember(self.input.text())
            self.input.clear()
            self.reload()
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "保存失败", config.redact(str(exc)))

    def delete(self):
        index = self.items.currentRow()
        if index >= 0:
            try:
                self.store.forget(index)
                self.reload()
            except OSError as exc:
                QMessageBox.warning(self, "删除失败", config.redact(str(exc)))

    def clear(self):
        if QMessageBox.question(self, "清空偏好", "删除全部主动保存的偏好？") == QMessageBox.Yes:
            try:
                self.store.clear_memories()
                self.reload()
            except OSError as exc:
                QMessageBox.warning(self, "清空失败", config.redact(str(exc)))


class ChatDialog(QDialog):
    send_requested = Signal(str, bool)

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("问桌宠 · 持续聊天")
        self.resize(580, 560)
        layout = QVBoxLayout(self)
        self.mode = QComboBox()
        self.mode.addItems(["日常陪伴（仅 StepFun，不调用麦当劳工具）", "麦当劳实时查询（价格 / 餐品 / 券 / 门店）"])
        layout.addWidget(self.mode)
        self.transcript = QPlainTextEdit()
        self.transcript.setReadOnly(True)
        layout.addWidget(self.transcript)
        self.status = QLabel("聊天保存在本机；每次仅发送有界上下文和主动偏好。")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.input = QPlainTextEdit()
        self.input.setMaximumHeight(90)
        self.input.setPlaceholderText("输入消息，再点发送")
        layout.addWidget(self.input)
        row = QHBoxLayout()
        self.send = QPushButton("发送")
        self.send.clicked.connect(self.submit)
        row.addWidget(self.send)
        self.memory_button = QPushButton("查看 / 保存 / 清除偏好")
        self.memory_button.clicked.connect(self.open_memories)
        row.addWidget(self.memory_button)
        self.clear_button = QPushButton("清空聊天历史")
        self.clear_button.clicked.connect(self.clear_history)
        row.addWidget(self.clear_button)
        layout.addLayout(row)
        self.reload()
        if store.messages and store.messages[-1]["role"] == "user":
            self.status.setText("上一条消息没有保存回复，可能被上次退出中断；可以重新发送。")

    def reload(self):
        self.transcript.setPlainText("\n\n".join(
            ("你：" if m["role"] == "user" else "搭子：") + m["content"] for m in self.store.messages))
        self.transcript.verticalScrollBar().setValue(self.transcript.verticalScrollBar().maximum())

    def submit(self):
        question = self.input.toPlainText().strip()
        if not question or not self.send.isEnabled():
            return
        if len(question) > 4000:
            self.status.setText("消息最多 4000 字，请缩短后发送。")
            return
        self.input.clear()
        self.set_pending(True)
        self.send_requested.emit(question, self.mode.currentIndex() == 1)

    def set_pending(self, pending, error=""):
        for widget in (self.send, self.mode, self.clear_button, self.memory_button):
            widget.setEnabled(not pending)
        self.status.setText(config.redact(error) if error else ("发送中 / 排队中…" if pending else "已回复 · 对话保存在本机"))

    def open_memories(self):
        MemoryDialog(self.store, self).exec()

    def clear_history(self):
        if QMessageBox.question(self, "清空聊天", "删除本机聊天历史？主动偏好可单独清除。") == QMessageBox.Yes:
            try:
                self.store.clear_history()
                self.reload()
                self.status.setText("本机聊天历史已清空。")
            except OSError as exc:
                self.status.setText(config.redact(f"清空失败：{exc}"))
