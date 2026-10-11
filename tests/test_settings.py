"""Settings UI/config tests use memory dotenv readers; never read any .env."""
import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QLineEdit

from src import config
from src.pet.dialogs import SettingsForm


def test_deepseek_masked_blank_preserves_clear_cancel_and_close(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "balance-fixture-secret")
    form = SettingsForm()
    saved = []
    form.save_requested.connect(saved.append)
    field = form.fields["DEEPSEEK_API_KEY"]
    assert field.echoMode() == QLineEdit.Password and field.text() == ""
    assert "已配置" in field.placeholderText()
    form.submit()
    assert "DEEPSEEK_API_KEY" not in saved[-1]
    field.setText("discard-fixture-key")
    form.clear_deepseek.setChecked(True)
    form.cancel_button.click()
    assert field.text() == "" and not form.clear_deepseek.isChecked()
    form.clear_deepseek.setChecked(True)
    form.submit()
    assert saved[-1]["DEEPSEEK_API_KEY"] == ""
    assert os.environ["DEEPSEEK_API_KEY"] == "balance-fixture-secret"
    form.close()


def test_save_preserves_legacy_env_without_reading_files_and_reloads(monkeypatch, tmp_path):
    monkeypatch.setenv("MCPET_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "before-fixture")
    previous = {"STEPFUN_API_KEY": "legacy-fixture", "MCD_MCP_TOKEN": "mcd-fixture"}
    monkeypatch.setattr(config, "dotenv_values", lambda *args, **kwargs: dict(previous))
    exists = Path.exists
    monkeypatch.setattr(Path, "exists", lambda path: True if path == tmp_path / ".env" else exists(path))
    writes = []
    monkeypatch.setattr(Path, "write_text", lambda path, text, **kwargs: writes.append((path, text)))
    monkeypatch.setattr(config.os, "chmod", lambda *args: None)
    replacements = []
    monkeypatch.setattr(Path, "replace", lambda path, target: replacements.append((path, target)))
    config.save_settings({"DEEPSEEK_API_KEY": "balance-fixture", "MCPET_CITY": "杭州"})
    assert 'STEPFUN_API_KEY="legacy-fixture"' in writes[0][1]
    assert 'DEEPSEEK_API_KEY="balance-fixture"' in writes[0][1]
    assert replacements[0][1] == tmp_path / ".env"
    assert config.deepseek_api_key() == "balance-fixture"
    calls = []
    monkeypatch.setattr(config, "load_dotenv", lambda path, **kw: calls.append((path, kw)))
    config.load_env()
    assert [path for path, kw in calls] == [tmp_path / ".env", config.PROJECT_ROOT / ".env"]
    assert all(kw == {"override": False, "interpolate": False} for path, kw in calls)


@pytest.mark.parametrize("value", ["", "YOUR_API_KEY", "CHANGEME", "null"])
def test_deepseek_placeholder_is_unconfigured(monkeypatch, value):
    monkeypatch.setenv("DEEPSEEK_API_KEY", value)
    assert config.deepseek_api_key() == ""


def test_deepseek_exact_secret_redacted_even_without_sk_prefix(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "arbitrary-fixture-key")
    assert "arbitrary-fixture-key" not in config.redact("failed arbitrary-fixture-key")
    assert config.redact("unsaved-fixture", token="unsaved-fixture") == "***"
    assert config.redact("123.456789012345678901", personal=False) == "123.456789012345678901"
    assert "arbitrary-fixture-key" not in config.redact("arbitrary-fixture-key", personal=False)
