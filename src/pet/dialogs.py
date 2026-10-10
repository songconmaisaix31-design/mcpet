"""对话框：下单确认与 Token 录入。

下单确认做成「勾选 + 按钮」两步，和 brain 侧的护栏叠加——UI 层不允许一键下单。
Token 录入不写入项目目录，写到用户目录并尽量收权限。
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QInputDialog,
    QLabel,
    QMessageBox,
    QVBoxLayout,
)

from .. import config


class OrderConfirmDialog(QDialog):
    """展示门店 / 商品 / 实付金额，必须勾选确认后才能下单。"""

    def __init__(self, summary: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("麦麦小怪兽要下单了")
        self.setModal(True)
        self.setMinimumWidth(360)

        self.summary_label = QLabel(summary)
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.confirm_box = QCheckBox("我已核对门店、商品与实付金额，确认下单")
        self.confirm_box.stateChanged.connect(self._sync_buttons)

        hint = QLabel("下单会产生真实订单与真实支付。取消不会有任何副作用。")
        hint.setWordWrap(True)
        hint.setStyleSheet("QLabel{color:#8A6D3B;}")

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setText("下单")
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

    写入 ~/.maimai-monster/.env（不在项目目录，已尽量收成 0600），
    并明确告知用户这是本机明文存储。
    """
    text, ok = QInputDialog.getText(
        parent,
        "需要麦当劳 MCP Token",
        "在 https://open.mcd.cn/mcp 登录后在「控制台」激活获取。\n"
        "Token 会以明文存到本机 ~/.maimai-monster/.env（权限尽量设为仅本人可读）。",
        echo=QInputDialog.Password,
    )
    if not ok or not text.strip():
        return None
    token = text.strip()

    path = config.data_dir() / ".env"
    path.write_text(f"MCD_MCP_TOKEN={token}\n", encoding="utf-8")
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    config.load_env()
    return token


def show_error(parent, title: str, message: str) -> None:
    QMessageBox.warning(parent, title, message)


def show_info(parent, title: str, message: str) -> None:
    QMessageBox.information(parent, title, message)
