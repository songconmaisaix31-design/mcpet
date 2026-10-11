"""对话框：下单确认与 Token 录入。

下单确认做成「勾选 + 按钮」两步，和 brain 侧的护栏叠加——UI 层不允许一键下单。
Token 录入不写入项目目录，写到用户目录并尽量收权限。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QInputDialog,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QFormLayout, QLineEdit, QComboBox, QDoubleSpinBox, QPlainTextEdit, QPushButton,
    QApplication,
)

from .. import config


class OrderConfirmDialog(QDialog):
    """展示门店 / 商品 / 实付金额，必须勾选确认后才能下单。"""

    def __init__(self, summary: str, parent=None, *, title="McPet 要下单了", action="下单"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(360)

        self.summary_label = QLabel(config.redact(summary))
        self.summary_label.setTextFormat(Qt.PlainText)
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.confirm_box = QCheckBox(f"我已核对以上内容，确认{action}")
        self.confirm_box.stateChanged.connect(self._sync_buttons)

        hint = QLabel("此操作会提交真实账号请求。请核对内容；取消不会提交。")
        hint.setWordWrap(True)
        hint.setStyleSheet("QLabel{color:#8A6D3B;}")

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setText(action)
        self.buttons.button(QDialogButtonBox.Cancel).setText("取消")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self._sync_buttons()

        layout = QVBoxLayout(self)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.confirm_box)
        layout.addWidget(hint)
        layout.addWidget(self.buttons)

    def _sync_buttons(self) -> None:
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(self.confirm_box.isChecked())

    @property
    def confirmed(self) -> bool:
        return self.exec() == QDialog.Accepted and self.confirm_box.isChecked()


def prompt_for_token(parent=None) -> str | None:
    """首次运行或 Token 失效时录入。

    写入 ~/.mcpet/.env（不在项目目录，已尽量收成 0600），
    并明确告知用户这是本机明文存储。
    """
    text, ok = QInputDialog.getText(
        parent,
        "需要麦当劳 MCP Token",
        "在 https://open.mcd.cn/mcp 登录后在「控制台」激活获取。\n"
        "Token 会以明文存到本机用户数据目录/.env（权限尽量设为仅本人可读）。",
        echo=QLineEdit.Password,
    )
    if not ok or not text.strip():
        return None
    token = text.strip()

    config.save_settings({"MCD_MCP_TOKEN": token})
    return token


def show_error(parent, title: str, message: str) -> None:
    QMessageBox.warning(parent, title, config.redact(message))


def show_info(parent, title: str, message: str) -> None:
    QMessageBox.information(parent, title, config.redact(message))


class ReportDialog(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(650, 480)
        layout = QVBoxLayout(self)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        layout.addWidget(self.text)

    def set_report(self, text):
        self.text.setPlainText(config.redact(text))


class NutritionSelectDialog(QDialog):
    def __init__(self, facts, parent=None):
        super().__init__(parent)
        self.facts = list(facts)
        self.setWindowTitle("选择实际吃的餐品与份数")
        self.resize(480, 260)
        layout = QVBoxLayout(self)
        self.food = QComboBox()
        for fact in facts:
            self.food.addItem(config.redact(f"{fact.name} · 每份 {fact.energy_kcal:g} kcal"))
        layout.addWidget(self.food)
        self.quantity = QDoubleSpinBox()
        self.quantity.setRange(0.25, 20)
        self.quantity.setSingleStep(0.25)
        self.quantity.setValue(1)
        self.quantity.setSuffix(" 份")
        layout.addWidget(self.quantity)
        self.detail = QLabel()
        self.detail.setWordWrap(True)
        self.detail.setTextFormat(Qt.PlainText)
        layout.addWidget(self.detail)
        self.food.currentIndexChanged.connect(self.update_detail)
        self.quantity.valueChanged.connect(self.update_detail)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.Save).setEnabled(bool(facts))
        layout.addWidget(buttons)
        self.update_detail()

    def update_detail(self):
        if not self.facts:
            self.detail.setText("未查到餐品")
            return
        fact, quantity = self.facts[self.food.currentIndex()], self.quantity.value()
        self.detail.setText(config.redact(f"{fact.name} × {quantity:g} 份\n"
                            f"约 {fact.energy_kcal * quantity:g} kcal；蛋白 {fact.protein_g * quantity:g} g；"
                            f"脂肪 {fact.fat_g * quantity:g} g；碳水 {fact.carb_g * quantity:g} g；"
                            f"钠 {fact.sodium_mg * quantity:g} mg"))

    def selection(self):
        if self.exec() != QDialog.Accepted or not self.facts:
            return None
        return self.facts[self.food.currentIndex()], self.quantity.value()


class PaymentDialog(ReportDialog):
    def __init__(self, outcome, parent=None):
        super().__init__("订单 / 支付", parent)
        self.pay_url = outcome.pay_url
        self.set_report(outcome.summary + f"\n订单号：{outcome.order_no}\n支付链接：{config.redact(self.pay_url)}")
        # 只允许普通 HTTPS/HTTP 链接；不把工具输出当成本机命令。
        url = QUrl(self.pay_url)
        usable = (url.isValid() and url.scheme() in {"https", "http"} and bool(url.host())
                  and config.redact(self.pay_url) == self.pay_url and "***" not in self.pay_url)
        self.open_button = QPushButton("打开支付链接")
        self.copy_button = QPushButton("复制支付链接")
        self.open_button.setEnabled(usable)
        self.copy_button.setEnabled(usable)
        self.open_button.clicked.connect(lambda: QDesktopServices.openUrl(url))
        self.copy_button.clicked.connect(lambda: QApplication.clipboard().setText(self.pay_url))
        self.layout().addWidget(self.open_button)
        self.layout().addWidget(self.copy_button)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        import os
        super().__init__(parent)
        self.setWindowTitle("McPet 本机设置")
        self.resize(620, 450)
        layout = QVBoxLayout(self)
        hint = QLabel("凭证以明文仅存于用户数据目录 .env，尽量收紧文件权限；不会写进仓库或聊天历史。"
                      "留空保留已配置凭证；目录只读，默认候选仅限当前系统用户。")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        form = QFormLayout()
        self.fields, self.clear_credentials = {}, {}
        labels = {"MCD_MCP_TOKEN": "麦当劳 MCP Token", "STEPFUN_API_KEY": "StepFun Key",
                  "MCPET_CITY": "城市", "MCPET_AGENT_ROOT_CLAUDE": "Claude 日志目录",
                  "MCPET_AGENT_ROOT_CODEX": "Codex 日志目录", "MCPET_AGENT_ROOT_GENERIC": "通用日志目录"}
        for key in config.SETTINGS_KEYS:
            edit = QLineEdit()
            if key in {"MCD_MCP_TOKEN", "STEPFUN_API_KEY"}:
                edit.setEchoMode(QLineEdit.Password)
                edit.setPlaceholderText("已配置（留空保留）" if os.environ.get(key) else "未配置")
                clear = QCheckBox("清除此凭证")
                self.clear_credentials[key] = clear
                form.addRow(labels[key], edit)
                form.addRow("", clear)
            else:
                edit.setText(os.environ.get(key, "北京" if key == "MCPET_CITY" else ""))
                if "AGENT_ROOT" in key:
                    edit.setPlaceholderText("留空使用当前用户默认候选；修改后重启")
                form.addRow(labels[key], edit)
            self.fields[key] = edit
        layout.addLayout(form)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setTextFormat(Qt.PlainText)
        layout.addWidget(self.message)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.message.setText("\n".join(config.root_warnings({k: e.text() for k, e in self.fields.items()})))

    def save(self):
        values = {}
        for key, field in self.fields.items():
            value = field.text().strip()
            if key in self.clear_credentials:
                if self.clear_credentials[key].isChecked():
                    value = ""
                elif not value:
                    continue
            values[key] = value
        try:
            config.save_settings(values)
        except (ValueError, OSError) as exc:
            self.message.setText(config.redact(f"保存失败：{exc}"))
            return
        warnings = config.root_warnings(values)
        if warnings:
            QMessageBox.information(self, "目录配置提示", "\n".join(warnings))
        self.accept()
