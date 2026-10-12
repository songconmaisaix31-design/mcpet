"""对话框：下单确认与 Token 录入。

下单确认做成「勾选 + 按钮」两步，和 brain 侧的护栏叠加——UI 层不允许一键下单。
Token 录入不写入项目目录，写到用户目录并尽量收权限。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import math
import html
import time

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QFont, QPixmap
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
    QTableWidgetItem, QHeaderView, QAbstractItemView, QProgressBar, QLayout,
)

from .. import config
from .spritesheet import AnimationSheet


def character_preview(sheet):
    # AnimationSheet.image is its already-decoded first idle frame. Calling
    # frame('idle') would evict A's active animation atlas and decode it again.
    return (QPixmap.fromImage(sheet.image)
            if isinstance(sheet, AnimationSheet) and getattr(sheet, "_base_sheet", None) is None
            else sheet.frame("idle", 0))


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
        deepseek = QLineEdit()
        deepseek.setEchoMode(QLineEdit.Password)
        self.fields["DEEPSEEK_API_KEY"] = deepseek
        self.clear_deepseek = QCheckBox("明确清除已保存的 DeepSeek 凭证")
        self.clear_credentials = {"MCD_MCP_TOKEN": self.clear_token, "DEEPSEEK_API_KEY": self.clear_deepseek}
        form.addRow("DeepSeek 余额 Key", deepseek)
        form.addRow("", self.clear_deepseek)
        self_hint = QLabel("DeepSeek Key 仅查询官方余额，不发送聊天或模型请求。")
        self_hint.setWordWrap(True)
        form.addRow(self_hint)
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
            field.setText("" if key in self.clear_credentials else os.environ.get(key, "北京" if key == "MCPET_CITY" else ""))
        for key, clear in self.clear_credentials.items():
            self.fields[key].setPlaceholderText("已配置 · 留空保留" if os.environ.get(key) else "未配置 · 可选填")
            clear.setChecked(False)
        self.message.setText("\n".join(config.root_warnings({key: field.text() for key, field in self.fields.items()})))

    def submit(self):
        values = {key: field.text().strip() for key, field in self.fields.items() if key not in self.clear_credentials}
        for key, clear in self.clear_credentials.items():
            token = self.fields[key].text().strip()
            if token or clear.isChecked():
                values[key] = "" if clear.isChecked() else token
        self.save_requested.emit(values)


class CompanionPanel(QDialog):
    """唯一非模态小窝；只展示日志观测，不向原 Agent 会话注入请求。"""
    action_requested = Signal(str)
    character_requested = Signal(str)

    def __init__(self, sheet=None, parent=None):
        super().__init__(parent, Qt.Window)
        self.setFont(QFont("Microsoft YaHei UI", 9))
        self.setWindowTitle("麦麦小窝")
        self.setModal(False)
        screen = parent.screen() if parent else QApplication.primaryScreen()
        area = screen.availableGeometry()
        self.setMinimumSize(min(560, area.width() - 40), min(560, area.height() - 50))
        self.resize(min(700, area.width() - 40), min(720, area.height() - 50))
        self.setStyleSheet("""
            QDialog { background:#fff8ee; color:#493d36; font-family:'Microsoft YaHei UI'; font-size:13px; }
            QLabel { color:#493d36; background:transparent; }
            QLabel#title { font-size:24px; font-weight:700; color:#934f2d; }
            QLabel#subtitle { color:#81756b; }
            QFrame#card { background:#fff0df; border:1px solid #eedfd1; border-radius:16px; }
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
            QComboBox { background:#fffdfa; border:1px solid #e0d4dd; border-radius:8px; padding:5px; }
            QProgressBar { border:0; background:#e5daec; border-radius:4px; height:8px; }
            QProgressBar::chunk { background:#b99bd5; border-radius:4px; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(12)
        header = QHBoxLayout()
        self.preview = QLabel()
        self.preview.setFixedSize(88, 88)
        self.preview.setAlignment(Qt.AlignCenter)
        self._preview_sheet = None
        words = QVBoxLayout()
        title = QLabel("麦麦小窝")
        title.setObjectName("title")
        words.addWidget(title)
        subtitle = QLabel("陪你把今天慢慢做好")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        words.addWidget(subtitle)
        self.character_message = QLabel()
        self.character_message.setTextFormat(Qt.PlainText)
        self.character_message.setWordWrap(True)
        header.addLayout(words, 1)
        refresh = QPushButton("刷新额度")
        refresh.clicked.connect(lambda: self.action_requested.emit("quota"))
        header.addWidget(refresh)
        layout.addLayout(header)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        self.pages = {}
        self.buttons = {}
        for key, label in (("home", "小窝"), ("sessions", "会话"), ("mcd", "麦当劳"), ("settings", "设置")):
            page = QWidget()
            column = QVBoxLayout(page)
            column.setContentsMargins(3, 10, 3, 6)
            column.setSpacing(12)
            column.setSizeConstraint(QLayout.SetMinimumSize)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self.pages[key] = self.tabs.addTab(scroll, label)
            setattr(self, key + "_layout", column)
        hero = self.card(self.home_layout, "")
        self.character_card = hero.parentWidget()
        hero_row = QHBoxLayout()
        hero_row.addWidget(self.preview)
        hero_words = QVBoxLayout()
        self.character_name = self.label(hero_words, "麦麦")
        self.character_name.setStyleSheet("font-size:18px; font-weight:700;")
        self.character_activity = self.label(hero_words, "会话状态 UNKNOWN · 等待本机日志")
        self.character_buttons = {}
        self.character_choices = QHBoxLayout()
        self.character_choices.addStretch()
        hero_words.addLayout(self.character_choices)
        hero_words.addWidget(self.character_message)
        hero_row.addLayout(hero_words, 1)
        hero.addLayout(hero_row)
        quota = self.card(self.home_layout, "账号剩余额度")
        self.quota_status = self.label(quota, "UNKNOWN · 等待账号快照")
        self.accounts_layout = QVBoxLayout()
        quota.addLayout(self.accounts_layout)
        self.account_rows = []
        # Only rows created by a real snapshot live here. During credential
        # replacement they are cleared and hidden, then reconciled by the next
        # observation; absent providers never accumulate across observations.
        self._provider_rows = {}
        self.account_placeholder = None
        self.money_placeholder = None
        self.reset_labels = []
        self._quota_snapshot = None
        self._accounts_rendered = False
        self._accounts_stale = False
        self._balance_configured = False
        self.buttons["quota"] = refresh
        money = self.card(self.home_layout, "DeepSeek API 余额")
        self.money_layout = QVBoxLayout()
        money.addLayout(self.money_layout)
        money_header = QHBoxLayout()
        self.button(money_header, "去设置", "settings")
        money_header.addStretch()
        money.addLayout(money_header)
        self.quota_timer = QTimer(self)
        self.quota_timer.setInterval(30_000)
        self.quota_timer.timeout.connect(self.update_countdowns)
        card = self.card(self.home_layout, "陪伴控制")
        controls = QHBoxLayout()
        self.roaming_button = self.button(controls, "闲逛", "roaming", checkable=True)
        self.resting_button = self.button(controls, "休息 / 唤醒", "resting", checkable=True)
        self.visibility_button = self.button(controls, "显示 / 隐藏桌宠", "visibility")
        card.addLayout(controls)
        actions = QHBoxLayout()
        self.frying_button = self.button(actions, "炸薯条 · 循环", "frying")
        self.outfit_button = self.button(actions, "换装", "outfit")
        self.stop_action_button = self.button(actions, "停止动作", "stop_animation")
        card.addLayout(actions)
        skins = QHBoxLayout()
        self.default_skin_button = self.button(skins, "默认套装", "skin_default", checkable=True)
        self.maimai_skin_button = self.button(skins, "麦麦套装", "skin_maimai", checkable=True)
        card.addLayout(skins)
        extras = QHBoxLayout()
        self.button(extras, "看看会话活动", "progress")
        self.button(extras, "安全退出 McPet", "quit")
        card.addLayout(extras)
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
        self.set_character("maimai", "麦麦", sheet, ())

    def set_character(self, character_id, name, sheet, choices):
        self.character_name.setText(name)
        for button in (self.frying_button, self.outfit_button, self.stop_action_button):
            button.setEnabled(bool(sheet)
                              and "frying" in getattr(sheet, "meta", {}).get("animations", {}))
        for skin, button in (("default", self.default_skin_button), ("maimai", self.maimai_skin_button)):
            button.setVisible(character_id == "deepseek")
            button.setChecked(bool(sheet) and sheet.meta.get("skin_id", "default") == skin)
        blue = character_id == "deepseek"
        if getattr(self, "_styled_character", None) != character_id:
            self.character_card.setStyleSheet("QFrame#card { background:" + ("#eaf4fb" if blue else "#fff0df") + "; }")
            self._styled_character = character_id
        for identifier, label in choices or ((character_id, name),):
            if identifier not in self.character_buttons:
                button = QPushButton(label)
                button.setCheckable(True)
                button.clicked.connect(lambda checked=False, value=identifier: self.character_requested.emit(value))
                button.setMaximumWidth(160)
                button.setStyleSheet("QPushButton:checked { background:" + ("#72aad7" if identifier == "deepseek" else "#ed9864") + "; }")
                self.character_choices.insertWidget(self.character_choices.count() - 1, button)
                self.character_buttons[identifier] = button
            button = self.character_buttons[identifier]
            button.setChecked(identifier == character_id)
            button.setEnabled(bool(choices))
        if sheet is not self._preview_sheet:
            self._preview_sheet = sheet
            self.preview.clear()
            if sheet:
                self.preview.setPixmap(character_preview(sheet).scaled(88, 88, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        if not sheet:
            self.preview.setText(name)
        self.resting_button.setText("唤醒" + name if self.resting_button.isChecked() else "让" + name + "休息")

    @staticmethod
    def reset_text(resets_at, now):
        if resets_at is None or not math.isfinite(resets_at):
            return "重置时间 UNKNOWN"
        seconds = resets_at - now
        if seconds <= 0:
            return "重置时间已到 · 等待刷新"
        minutes = math.ceil(seconds / 60)
        days, remainder = divmod(minutes, 1440)
        hours, minutes = divmod(remainder, 60)
        return "距重置 " + (f"{days}天 " if days else "") + (f"{hours}小时 " if hours else "") + f"{minutes}分钟"

    def update_countdowns(self, now=None):
        now = time.time() if now is None else now
        for label, reset in self.reset_labels:
            label.setText(self.reset_text(reset, now))

    def set_accounts(self, snapshot, error="", refreshing=False):
        status = "Orca 账号缓存 · 刷新中 · 保留上次快照" if refreshing and snapshot else "Orca 账号缓存 · 刷新中 · 等待账号快照" if refreshing else "Orca 账号缓存 · 各窗口分别计量"
        if error:
            status = "UNKNOWN · " + error + (" · 保留上次快照（过时）" if snapshot else "") + (" · 刷新中" if refreshing else "")
        if snapshot is None and not refreshing and not error:
            status = "UNKNOWN · 等待账号快照"
        self.quota_status.setText(config.redact(status))
        configured = bool(config.deepseek_api_key())
        if (self._accounts_rendered and snapshot is self._quota_snapshot
                and bool(error) == self._accounts_stale and configured == self._balance_configured):
            self.update_countdowns()
            return
        # Reconcile synchronously, including clearing credentials' old observations.
        # Restore the caller's repaint setting even if rendering a source fails.
        page = self.home_layout.parentWidget()
        updates = page.updatesEnabled()
        page.setUpdatesEnabled(False)
        try:
            self.reset_labels = []
            self.account_rows = []
            if snapshot is None:
                for row in self._provider_rows.values():
                    self._clear_account_widget(row["frame"])
                    row["status"] = "unknown"
                    row["bar_colors"] = [None] * len(row["buckets"])
                    self._detach_account_widget(row["frame"])
            else:
                occurrences, keys = {}, []
                for account in snapshot.accounts:
                    occurrence = occurrences.get(account.provider, 0)
                    occurrences[account.provider] = occurrence + 1
                    key = (account.provider, occurrence)
                    keys.append(key)
                    row = self._provider_rows.get(key)
                    if row is None:
                        row = self._create_account_row(account.provider)
                        self._provider_rows[key] = row
                    self._resize_account_row(row, account)
                    self.account_rows.append(row)
                # A genuine empty observation also releases retained cleared rows.
                for key in tuple(self._provider_rows):
                    if key not in keys:
                        row = self._provider_rows.pop(key)
                        self._discard_account_widget(row["frame"])
                self._update_account_rows(snapshot, error)
                positions = {self.accounts_layout: 0, self.money_layout: 0}
                for row in self.account_rows:
                    container = self.money_layout if row["provider"] == "deepseek" or row["balances"] else self.accounts_layout
                    frame, position = row["frame"], positions[container]
                    if container.indexOf(frame) != position:
                        self._detach_account_widget(frame)
                        container.insertWidget(position, frame)
                    frame.show()
                    positions[container] += 1
            empty = snapshot is not None and not snapshot.accounts
            self._set_account_placeholder("account_placeholder", self.accounts_layout,
                                          "暂无账号额度 · UNKNOWN" if empty else None)
            has_money = any(row["provider"] == "deepseek" or row["balances"] for row in self.account_rows)
            self._set_account_placeholder("money_placeholder", self.money_layout,
                                          None if has_money else "未配置余额查询密钥" if not configured else "余额 UNKNOWN · 等待查询")
            self.update_countdowns()
            self._quota_snapshot = snapshot
            self._accounts_stale = bool(error)
            self._balance_configured = configured
            self._accounts_rendered = True
        except Exception:
            self._accounts_rendered = False
            raise
        finally:
            page.setUpdatesEnabled(updates)

    @staticmethod
    def _clear_account_widget(widget):
        # Hidden widgets remain accessible objects until deletion. Erase their
        # payload too, rather than relying on visibility or deleteLater alone.
        for child in (widget, *widget.findChildren(QWidget)):
            child.setToolTip("")
            child.setAccessibleName("")
            child.setAccessibleDescription("")
            if isinstance(child, QLabel):
                child.clear()
            elif isinstance(child, QProgressBar):
                child.reset()
                child.hide()

    def _detach_account_widget(self, widget):
        widget.hide()
        self.accounts_layout.removeWidget(widget)
        self.money_layout.removeWidget(widget)

    def _discard_account_widget(self, widget):
        self._clear_account_widget(widget)
        self._detach_account_widget(widget)
        widget.deleteLater()

    def _set_account_placeholder(self, name, container, text):
        label = getattr(self, name)
        if text is None:
            if label is not None:
                label.clear()
                label.hide()
                container.removeWidget(label)
            return
        if label is None:
            label = self.label(container, text)
            setattr(self, name, label)
        else:
            label.setText(text)
            if container.indexOf(label) < 0:
                container.addWidget(label)
        label.show()

    def _create_account_row(self, provider):
        frame = QFrame(self.home_layout.parentWidget())
        frame.setStyleSheet("QFrame { background:#fffaf5; border-radius:10px; }")
        column = QVBoxLayout(frame)
        column.setContentsMargins(6, 5, 6, 5)
        column.setSpacing(3)
        column.setSizeConstraint(QLayout.SetMinimumSize)
        title = QHBoxLayout()
        icon = QLabel()
        icon.setFixedSize(24, 24)
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("background:#e9dbf4; border-radius:7px; font-weight:700;")
        title.addWidget(icon)
        heading = self.label(title, "", selectable=False)
        title.setStretchFactor(heading, 1)
        heading.setStyleSheet("font-weight:700;")
        state_label = self.label(title, "", selectable=False)
        state_label.setWordWrap(False)
        state_label.setStyleSheet("font-size:11px; color:#81756b;")
        column.addLayout(title)
        return {"provider": provider, "status": "unknown", "buckets": [], "balances": [], "frame": frame,
                "column": column, "icon": icon, "heading": heading, "state_label": state_label,
                "stamps": [], "bar_colors": [], "bucket_widgets": [], "bucket_stamps": [],
                "empty_label": None, "origin_stamp": None, "stale_label": None}

    def _resize_account_row(self, row, account):
        column = row["column"]
        while len(row["buckets"]) > len(account.buckets):
            row["buckets"].pop()
            row["bar_colors"].pop()
            row["bucket_stamps"].pop()
            widget = row["bucket_widgets"].pop()
            column.removeWidget(widget)
            self._discard_account_widget(widget)
        while len(row["buckets"]) < len(account.buckets):
            widget = QWidget()
            content = QVBoxLayout(widget)
            content.setContentsMargins(0, 0, 0, 0)
            content.setSpacing(3)
            content.setSizeConstraint(QLayout.SetMinimumSize)
            band = QHBoxLayout()
            summary = self.label(band, "")
            summary.setStyleSheet("font-size:11px; font-weight:600;")
            bar = QProgressBar()
            bar.setFixedHeight(8)
            bar.setRange(0, 1000)
            bar.setTextVisible(False)
            bar.setMinimumWidth(75)
            bar.setMaximumWidth(180)
            band.addWidget(bar, 1)
            content.addLayout(band)
            footer = QHBoxLayout()
            reset = self.label(footer, "")
            reset.setStyleSheet("color:#81756b; font-size:10px;")
            footer.setStretchFactor(reset, 1)
            stamp = None
            if not row["buckets"]:
                stamp = self.label(footer, "")
                stamp.setWordWrap(False)
                stamp.setStyleSheet("color:#81756b; font-size:10px;")
            content.addLayout(footer)
            column.insertWidget(1 + len(row["buckets"]), widget)
            row["bucket_widgets"].append(widget)
            row["bucket_stamps"].append(stamp)
            row["buckets"].append((summary, bar, reset))
            row["bar_colors"].append(None)
        while len(row["balances"]) > len(account.balances):
            label = row["balances"].pop()
            column.removeWidget(label)
            self._discard_account_widget(label)
        while len(row["balances"]) < len(account.balances):
            label = self.label(column, "", personal=False)
            column.insertWidget(1 + len(row["buckets"]) + len(row["balances"]), label)
            row["balances"].append(label)
        empty = not account.buckets and not account.balances
        if empty and row["empty_label"] is None:
            row["empty_label"] = self.label(column, "")
        elif not empty and row["empty_label"] is not None:
            label, row["empty_label"] = row["empty_label"], None
            column.removeWidget(label)
            self._discard_account_widget(label)
        if not account.buckets and row["origin_stamp"] is None:
            row["origin_stamp"] = self.label(column, "")
            row["origin_stamp"].setStyleSheet("color:#81756b; font-size:10px;")
        elif account.buckets and row["origin_stamp"] is not None:
            label, row["origin_stamp"] = row["origin_stamp"], None
            column.removeWidget(label)
            self._discard_account_widget(label)
        if row["stale_label"] is None:
            row["stale_label"] = self.label(column, "")
        # Moving only these trailing controls keeps new bucket/balance rows ahead
        # of them when a provider's observed structure grows.
        trailing = [label for label in (row["empty_label"], row["origin_stamp"], row["stale_label"]) if label is not None]
        for position, label in enumerate(trailing, 1 + len(row["buckets"]) + len(row["balances"])):
            if column.indexOf(label) != position:
                column.removeWidget(label)
                column.insertWidget(position, label)
        row["stamps"] = []
        for index, stamp in enumerate(row["bucket_stamps"]):
            if stamp is not None:
                row["stamps"].append((stamp, ""))
        if row["origin_stamp"] is not None:
            origin = "DeepSeek 官方余额" if account.provider == "deepseek" else "Orca 账号缓存"
            row["stamps"].append((row["origin_stamp"], origin + " · "))

    def _update_account_rows(self, snapshot, error):
        statuses = {"ok": "正常", "unavailable": "不可用 · UNKNOWN", "unconfigured": "未配置 · UNKNOWN", "error": "失败 · UNKNOWN", "stale": "过时 · 待刷新"}
        for row, account in zip(self.account_rows, snapshot.accounts):
            state = "stale" if error and (account.buckets or account.balances) else account.status
            row["status"] = state
            row["icon"].setText({"codex": "C", "grok": "G", "cursor": "Cu", "claude": "Cl", "deepseek": "D"}.get(account.provider, "A"))
            row["heading"].setText(config.redact(account.label))
            row["state_label"].setText(statuses.get(state, "UNKNOWN"))
            row["frame"].setToolTip(html.escape(config.redact(account.message)))
            row["stale_label"].setText("上次快照，已过时")
            row["stale_label"].setVisible(state == "stale")
            try:
                updated = "更新时间 UNKNOWN" if account.updated_at is None else "更新 " + datetime.fromtimestamp(account.updated_at).strftime("%m-%d %H:%M")
            except (ValueError, OverflowError, OSError):
                updated = "更新时间 UNKNOWN"
            for stamp, prefix in row["stamps"]:
                stamp.setText(prefix + updated)
            for index, (bucket, (summary, bar, reset)) in enumerate(zip(account.buckets, row["buckets"])):
                value = bucket.used_percent
                known = value is not None and math.isfinite(value) and 0 <= value <= 100
                text = f"{bucket.name} · 剩余 {100-value:g}% · 已用 {value:g}%" if known else f"{bucket.name} · 剩余 UNKNOWN · 已用 UNKNOWN"
                summary.setText(config.redact(text))
                bar.setAccessibleName(config.redact(text))
                if known:
                    bar.setValue(round(value * 10))
                else:
                    bar.reset()
                bar.setVisible(known)
                color = "#b7aea6" if state == "stale" else "#ae5962" if known and value >= 95 else "#ad6d39" if known and value >= 80 else "#79b69c"
                if color != row["bar_colors"][index]:
                    bar.setStyleSheet("QProgressBar::chunk { background:" + color + "; }")
                    row["bar_colors"][index] = color
                self.reset_labels.append((reset, bucket.resets_at))
            for label, balance in zip(row["balances"], account.balances):
                def amount(value):
                    return format(value, "f") if isinstance(value, Decimal) and value.is_finite() and value >= 0 else "UNKNOWN"
                text = f"{config.redact(balance.currency)} · 余额 {amount(balance.total)}\n赠送 {amount(balance.granted)} · 充值 {amount(balance.topped_up)}"
                label.setText(config.redact(text, personal=False))
            if row["empty_label"] is not None:
                row["empty_label"].setText("未配置余额查询密钥" if account.provider == "deepseek" and state == "unconfigured" else "余额 UNKNOWN" if account.provider == "deepseek" else "尚无可读取额度 · UNKNOWN")


    def showEvent(self, event):
        self.update_countdowns()
        self.quota_timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.quota_timer.stop()
        super().hideEvent(event)

    @staticmethod
    def label(layout, text, *, personal=True, selectable=True):
        label = QLabel(config.redact(text, personal=personal))
        label.setTextFormat(Qt.PlainText)
        label.setWordWrap(True)
        if selectable:
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
        if not title:
            heading.hide()
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
        if sessions:
            first = sessions[0]
            state = "UNKNOWN · 日志过时" if first.stale or error else states.get(first.record.state, "UNKNOWN")
            self.character_activity.setText(config.redact(first.record.source + " · " + state))
        else:
            self.character_activity.setText("会话状态 UNKNOWN · 等待本机日志")
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
        labels = {"MCD_MCP_TOKEN": "麦当劳 MCP Token", "STEPFUN_API_KEY": "StepFun Key", "DEEPSEEK_API_KEY": "DeepSeek 余额 Key",
                  "MCPET_CITY": "城市", "MCPET_AGENT_ROOT_CLAUDE": "Claude 日志目录",
                  "MCPET_AGENT_ROOT_CODEX": "Codex 日志目录", "MCPET_AGENT_ROOT_GENERIC": "通用日志目录"}
        for key in config.SETTINGS_KEYS:
            edit = QLineEdit()
            if key in {"MCD_MCP_TOKEN", "STEPFUN_API_KEY", "DEEPSEEK_API_KEY"}:
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
