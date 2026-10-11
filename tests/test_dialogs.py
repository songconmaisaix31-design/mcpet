from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QMessageBox, QLineEdit
from PySide6.QtGui import QDesktopServices

from src import config
from src.mcd_mcp.brain import NutritionFact, OrderOutcome
from src.pet.dialogs import OrderConfirmDialog, NutritionSelectDialog, PaymentDialog, SettingsDialog


def test_confirmation_requires_checkbox_and_reject_means_no_write():
    dialog = OrderConfirmDialog("门店：测试\n商品：汉堡\n用券：无\n实付：10.00\n取餐：外带")
    assert not dialog.buttons.button(QDialogButtonBox.Ok).isEnabled()
    dialog.confirm_box.setChecked(True)
    assert dialog.buttons.button(QDialogButtonBox.Ok).isEnabled()
    dialog.reject()
    assert dialog.result() == QDialog.Rejected
    dialog.close()


def test_food_ui_selects_actual_second_fact_and_fractional_quantity(monkeypatch):
    facts = [NutritionFact("甲", energy_kcal=10), NutritionFact("乙", energy_kcal=100, protein_g=2)]
    dialog = NutritionSelectDialog(facts)
    dialog.food.setCurrentIndex(1)
    dialog.quantity.setValue(2.5)
    assert "乙 × 2.5" in dialog.detail.text() and "250 kcal" in dialog.detail.text()
    monkeypatch.setattr(dialog, "exec", lambda: QDialog.Accepted)
    assert dialog.selection() == (facts[1], 2.5)
    monkeypatch.setattr(dialog, "exec", lambda: QDialog.Rejected)
    assert dialog.selection() is None
    dialog.close()


def test_payment_link_opens_or_copies_and_rejects_local_commands(monkeypatch):
    outcome = OrderOutcome("placed", "测试订单", 990, "O", "https://pay.example/order?a=1")
    dialog = PaymentDialog(outcome)
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))
    dialog.open_button.click()
    dialog.copy_button.click()
    assert opened == [outcome.pay_url]
    assert QApplication.clipboard().text() == outcome.pay_url
    dialog.close()
    unsafe = PaymentDialog(OrderOutcome("placed", pay_url="file:///C:/bad.exe"))
    assert not unsafe.open_button.isEnabled() and not unsafe.copy_button.isEnabled()
    unsafe.close()
    monkeypatch.setenv("MCD_MCP_TOKEN", "plain-test-credential")
    credential_link = PaymentDialog(OrderOutcome("placed", pay_url="https://pay.example/?key=plain-test-credential"))
    assert "plain-test-credential" not in credential_link.text.toPlainText()
    assert not credential_link.copy_button.isEnabled()
    credential_link.close()


def test_settings_ui_keeps_secrets_masked_and_saves_local_file(tmp_path, monkeypatch):
    monkeypatch.setenv("MCPET_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MCD_MCP_TOKEN", "fake-current-secret")
    monkeypatch.setenv("STEPFUN_API_KEY", "fake-step-secret")
    monkeypatch.delenv("MCPET_AGENT_ROOTS", raising=False)
    for key in config.SETTINGS_KEYS:
        if "AGENT_ROOT" in key:
            monkeypatch.delenv(key, raising=False)
    dialog = SettingsDialog()
    assert dialog.fields["MCD_MCP_TOKEN"].text() == ""
    assert dialog.fields["MCD_MCP_TOKEN"].echoMode() == QLineEdit.Password
    dialog.fields["STEPFUN_API_KEY"].setText("fake-new-step-key")
    dialog.fields["MCPET_CITY"].setText("深圳")
    dialog.save()
    assert config.stepfun_api_key() == "fake-new-step-key" and config.city() == "深圳"
    assert (tmp_path / ".env").exists()
    assert not (tmp_path / "chat.json").exists()
    dialog.close()
