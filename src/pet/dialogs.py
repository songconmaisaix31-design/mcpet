"""对话框：下单确认与 Token 录入。

下单确认做成「勾选 + 按钮」两步，和 brain 侧的护栏叠加——UI 层不允许一键下单。
Token 录入不写入项目目录，写到用户目录并尽量收权限。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
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
    QWidget, QFrame, QHBoxLayout, QTabWidget, QScrollArea, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView,
)

from .. import config


class SettingsForm(QWidget):
    """面板内编辑；不回填凭证，取消只丢弃尚未保存的输入。"""
    save_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        hint = QLabel("MCP 用于麦当劳功能；领券、下单、撤单需你确认。凭证以明文保存在本机用户数据目录，不进入会话或仓库。留空保留原凭证。")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.fields = {}
        form = QFormLayout()
        token = QLineEdit()
        token.setEchoMode(QLineEdit.Password)
        self.fields["MCD_MCP_TOKEN"] = token
        self.clear_token = QCheckBox("明确清除已保存的 MCP 凭证")
        form.addRow("麦当劳 MCP Token", token)
        form.addRow("", self.clear_token)
        city = QLineEdit()
        self.fields["MCPET_CITY"] = city
        form.addRow("所在城市", city)
        layout.addLayout(form)
        self.advanced = QPushButton("高级 · Agent 日志目录（展开）")
        self.advanced.setCheckable(True)
        layout.addWidget(self.advanced)
        self.roots = QWidget()
        roots_form = QFormLayout(self.roots)
        for source, label in (("CLAUDE", "Claude"), ("CODEX", "Codex"), ("GENERIC", "通用")):
            field = QLineEdit()
            field.setPlaceholderText("显式目录；修改后退出并重启")
            self.fields[f"MCPET_AGENT_ROOT_{source}"] = field
            roots_form.addRow(label, field)
        roots_hint = QLabel("只读取指定目录；不会扫描其他账户。留空使用当前用户候选。目录修改后必须重启，不会另开监控写入者。")
        roots_hint.setWordWrap(True)
        roots_form.addRow(roots_hint)
        layout.addWidget(self.roots)
        self.roots.hide()
        self.advanced.toggled.connect(self.roots.setVisible)
        self.advanced.toggled.connect(lambda checked: self.advanced.setText("高级 · Agent 日志目录 " + ("（收起）" if checked else "（展开）")))
        self.message = QLabel()
        self.message.setTextFormat(Qt.PlainText)
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        row = QHBoxLayout()
        self.save_button = QPushButton("保存设置")
        self.cancel_button = QPushButton("取消修改")
        row.addWidget(self.save_button)
        row.addWidget(self.cancel_button)
        layout.addLayout(row)
        self.save_button.clicked.connect(self.submit)
        self.cancel_button.clicked.connect(self.reset)
        layout.addStretch()
        self.reset()

    def reset(self):
        import os
        for key, field in self.fields.items():
            field.setText("" if key == "MCD_MCP_TOKEN" else os.environ.get(key, "北京" if key == "MCPET_CITY" else ""))
        self.fields["MCD_MCP_TOKEN"].setPlaceholderText("已配置 · 留空保留" if os.environ.get("MCD_MCP_TOKEN") else "未配置 · 可选填")
        self.clear_token.setChecked(False)
        self.message.setText("\n".join(config.root_warnings({key: field.text() for key, field in self.fields.items()})))

    def submit(self):
        values = {key: field.text().strip() for key, field in self.fields.items() if key != "MCD_MCP_TOKEN"}
        token = self.fields["MCD_MCP_TOKEN"].text().strip()
        if token or self.clear_token.isChecked():
            values["MCD_MCP_TOKEN"] = "" if self.clear_token.isChecked() else token
        self.save_requested.emit(values)


class CompanionPanel(QDialog):
    """唯一非模态小窝；只展示日志观测，不向原 Agent 会话注入请求。"""
    action_requested = Signal(str)

    def __init__(self, sheet=None, parent=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("麦麦小窝")
        self.setModal(False)
        self.setMinimumSize(340, 390)
        screen = parent.screen() if parent else QApplication.primaryScreen()
        area = screen.availableGeometry()
        self.resize(min(560, area.width() - 40), min(700, area.height() - 50))
        self.setStyleSheet("""
            QDialog { background:#fff8ee; color:#493b49; font-family:'Microsoft YaHei UI'; font-size:13px; }
            QLabel { color:#493b49; background:transparent; }
            QLabel#title { font-size:24px; font-weight:700; color:#934f2d; }
            QLabel#subtitle { color:#826d80; }
            QFrame#card { background:#f1eafa; border:1px solid #e6daed; border-radius:16px; }
            QTabWidget::pane { border:0; }
            QTabBar::tab { background:#f1e9df; padding:10px 15px; margin:2px; border-radius:10px; }
            QTabBar::tab:selected { background:#ffd8b6; color:#743c23; }
            QPushButton { background:#ffd6af; border:1px solid #efc29b; border-radius:10px; padding:9px 12px; color:#673d2b; }
            QPushButton:hover { background:#ffc791; }
            QPushButton:checked { background:#dac7f0; border-color:#bba2d6; }
            QPushButton:disabled { color:#968c86; background:#eee7df; border-color:#e4dad1; }
            QLineEdit,QPlainTextEdit,QTableWidget { background:#fffdfa; color:#493b49; border:1px solid #e0d4dd; border-radius:8px; padding:6px; selection-background-color:#f6c49c; }
            QHeaderView::section { background:#ece1f5; border:0; padding:6px; color:#594665; }
            QScrollArea,QScrollArea>QWidget>QWidget { background:transparent; border:0; }
            QCheckBox { spacing:8px; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        header = QHBoxLayout()
        preview = QLabel()
        preview.setFixedSize(88, 88)
        if sheet:
            preview.setPixmap(sheet.frame("idle", 0).scaled(88, 88, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            preview.setText("麦麦")
            preview.setAlignment(Qt.AlignCenter)
        header.addWidget(preview)
        words = QVBoxLayout()
        title = QLabel("麦麦小窝")
        title.setObjectName("title")
        words.addWidget(title)
        subtitle = QLabel("陪你看会话活动，也记得好好吃饭。")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        words.addWidget(subtitle)
        header.addLayout(words, 1)
        layout.addLayout(header)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        self.pages = {}
        self.buttons = {}
        for key, label in (("home", "陪伴"), ("sessions", "会话"), ("mcd", "麦当劳"), ("settings", "设置")):
            page = QWidget()
            column = QVBoxLayout(page)
            column.setContentsMargins(3, 10, 3, 6)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self.pages[key] = self.tabs.addTab(scroll, label)
            setattr(self, key + "_layout", column)
        card = self.card(self.home_layout, "今天也一起慢慢来")
        self.label(card, "桌宠跟随本机 Agent 日志显示工作、等待与异常。上下文占用不是任务完成百分比；日志停更也不代表成功。")
        self.roaming_button = self.button(card, "闲逛", "roaming", checkable=True)
        self.resting_button = self.button(card, "休息 / 唤醒", "resting", checkable=True)
        self.visibility_button = self.button(card, "显示 / 隐藏桌宠", "visibility")
        self.button(card, "看看会话活动", "progress")
        note = self.card(self.home_layout, "留一点轻松给自己")
        self.label(note, "单击摸摸麦麦，拖动找个舒服的位置。双击打开这个小窝；关掉小窝，麦麦仍会陪伴。")
        self.button(note, "安全退出 McPet", "quit")
        self.home_layout.addStretch()
        session = self.card(self.sessions_layout, "Agent 会话 · 日志观测")
        self.progress_status = self.label(session, "UNKNOWN · 正在等待本机日志快照")
        self.session_table = QTableWidget(0, 5)
        self.session_table.setHorizontalHeaderLabels(["来源", "会话", "状态", "上下文", "更新"])
        self.session_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.session_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.session_table.verticalHeader().hide()
        self.session_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.session_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.session_table.setMinimumHeight(125)
        self.session_table.setMaximumHeight(140)
        session.addWidget(self.session_table)
        self.button(session, "刷新会话快照", "progress")
        self.progress_detail = self.details(session, "详细会话报告")
        usage = self.card(self.sessions_layout, "本机用量 · 不是厂商余额")
        self.usage_status = self.label(usage, "UNKNOWN · 等待用量台账")
        self.button(usage, "刷新本机用量", "balance")
        self.usage_detail = self.details(usage, "详细用量报告")
        self.label(self.sessions_layout, "在这里查看活动；继续在原 Agent 应用操作即可。")
        self.sessions_layout.addStretch()
        queries = self.card(self.mcd_layout, "麦当劳快捷功能")
        self.label(queries, "按需连接 MCP。饭点自动汇报只查询券与报价，不领取、不下单。")
        for text, action in (("优惠券 · 只查询", "coupon_report"), ("今天最划算 · 查报价", "best_deal"),
                             ("主动领取优惠券…", "claim_coupons"), ("核对报价后下单…", "place_order"),
                             ("确认撤销上一单…", "cancel_last_order"), ("选择真实餐品 / 份数…", "log_meal"),
                             ("今日营养台账", "nutrition_summary")):
            self.button(queries, text, action)
        self.mcd_result = self.label(queries, "尚未查询实时数据。")
        payment = self.card(self.mcd_layout, "订单与付款")
        self.payment_card = payment.parentWidget()
        self.payment_text = self.label(payment, "")
        self.open_button = QPushButton("打开支付链接")
        self.copy_button = QPushButton("复制支付链接")
        payment.addWidget(self.open_button)
        payment.addWidget(self.copy_button)
        self.open_button.clicked.connect(self.open_payment)
        self.copy_button.clicked.connect(self.copy_payment)
        self.payment_card.hide()
        self.pay_url = ""
        self.mcd_layout.addStretch()
        self.settings = SettingsForm()
        self.settings_layout.addWidget(self.settings)
        self.status = QLabel("麦麦在这里 · 会话只读观测")
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.set_business_state(False, False)

    @staticmethod
    def label(layout, text):
        label = QLabel(config.redact(text))
        label.setTextFormat(Qt.PlainText)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(label)
        return label

    @classmethod
    def card(cls, layout, title):
        frame = QFrame()
        frame.setObjectName("card")
        column = QVBoxLayout(frame)
        column.setContentsMargins(14, 12, 14, 12)
        heading = cls.label(column, title)
        heading.setStyleSheet("font-weight:700; font-size:15px;")
        layout.addWidget(frame)
        return column

    def button(self, layout, text, action, checkable=False):
        button = QPushButton(text)
        button.setCheckable(checkable)
        button.clicked.connect(lambda: self.action_requested.emit(action))
        layout.addWidget(button)
        self.buttons[action] = button
        return button

    @staticmethod
    def details(layout, title):
        # 常用中文替代装饰符号，避免 Windows 首次显示时的昂贵字体回退。
        toggle = QPushButton(title + "（展开）")
        toggle.setCheckable(True)
        detail = QPlainTextEdit()
        detail.setReadOnly(True)
        detail.setMinimumHeight(160)
        detail.hide()
        toggle.toggled.connect(detail.setVisible)
        toggle.toggled.connect(lambda checked: toggle.setText(title + ("（收起）" if checked else "（展开）")))
        layout.addWidget(toggle)
        layout.addWidget(detail)
        return detail

    def select_page(self, page="home"):
        self.tabs.setCurrentIndex(self.pages[page])

    def set_controls(self, roaming, resting, visible):
        for button, checked, text in ((self.roaming_button, roaming, "闲逛 · " + ("开启" if roaming else "关闭")),
                                      (self.resting_button, resting, "唤醒麦麦" if resting else "让麦麦休息")):
            button.blockSignals(True)
            button.setChecked(checked)
            button.setText(text)
            button.blockSignals(False)
        self.visibility_button.setText("隐藏桌宠" if visible else "显示桌宠")

    def set_progress(self, snapshot, text, error=""):
        from ..progress.report import human_age
        self.progress_detail.setPlainText(config.redact(text))
        status = "UNKNOWN" if error or snapshot is None else snapshot.status
        self.progress_status.setText(config.redact(status + " · " + (error or "仅表示日志可观测性")))
        sessions = snapshot.sessions if snapshot else []
        self.session_table.setRowCount(len(sessions))
        states = {"working": "工作中", "thinking": "思考中", "needsinput": "待输入", "waiting": "等待", "idle": "空闲", "done": "已完成", "error": "异常", "failed": "失败"}
        for row, session in enumerate(sessions):
            record = session.record
            state = states.get(record.state, record.state or "UNKNOWN")
            if session.stale or error:
                state += " · 过时 / 结果UNKNOWN"
            context = "UNKNOWN" if session.context_percent is None else f"{session.context_percent}%"
            if getattr(record, "context_limit_estimated", False):
                context += " · 上限估算"
            for col, value in enumerate((record.source, session.label, state, context, human_age(session.age_seconds))):
                item = QTableWidgetItem(config.redact(str(value)))
                item.setToolTip(config.redact(str(value)))
                self.session_table.setItem(row, col, item)

    def set_usage(self, payload, text, error=""):
        self.usage_detail.setPlainText(config.redact(text))
        if not payload or error:
            summary = "UNKNOWN · " + (error or "等待用量台账")
        else:
            snapshot, projected, sample_ok = payload
            summary = snapshot.status + f" · 近窗口 {snapshot.window.tokens:,} token · 今日 {snapshot.today.tokens:,} token · 留存累计 {snapshot.lifetime.tokens:,} token"
            summary += "\n窗口外推：" + (f"约 {projected:,.0f} token" if sample_ok else "UNKNOWN · 样本不足")
        self.usage_status.setText(config.redact(summary))

    def set_busy(self, busy, label=""):
        self.status.setText(config.redact(label + "…" if busy else "麦麦在这里 · 会话只读观测"))
        self.settings.save_button.setEnabled(not busy)

    def set_business_state(self, has_quote, has_order):
        self.buttons["place_order"].setEnabled(has_quote)
        self.buttons["cancel_last_order"].setEnabled(has_order)

    def show_payment(self, outcome):
        self.pay_url = outcome.pay_url
        self.payment_text.setText(config.redact(outcome.summary + "\n" + outcome.reason + "\n订单号：" + outcome.order_no + "\n支付链接：" + self.pay_url))
        url = QUrl(self.pay_url)
        usable = url.isValid() and url.scheme() in {"https", "http"} and bool(url.host()) and config.redact(self.pay_url) == self.pay_url and "***" not in self.pay_url
        self.open_button.setEnabled(usable)
        self.copy_button.setEnabled(usable)
        self.payment_card.show()

    def clear_payment(self):
        self.pay_url = ""
        self.payment_card.hide()
        self.payment_text.clear()

    def open_payment(self):
        if self.open_button.isEnabled():
            QDesktopServices.openUrl(QUrl(self.pay_url))

    def copy_payment(self):
        if self.copy_button.isEnabled():
            QApplication.clipboard().setText(self.pay_url)

    def closeEvent(self, event):
        self.settings.reset()
        super().closeEvent(event)

    def reject(self):
        self.settings.reset()  # Escape 与标题栏关闭有相同的取消语义。
        super().reject()


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
