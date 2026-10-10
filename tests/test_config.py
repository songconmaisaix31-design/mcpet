from src import config


def test_redact_masks_token():
    token = "mcp_abcdef1234567890"
    text = f"Authorization: Bearer {token}"
    out = config.redact(text, token)
    assert token not in out
    assert "***" in out


def test_redact_masks_bearer_without_knowing_token():
    out = config.redact("Authorization: Bearer sk-abcdef123456")
    assert "sk-abcdef123456" not in out


def test_redact_masks_phone():
    out = config.redact("收货人 13812345678")
    assert "13812345678" not in out
    assert "****" in out


def test_redact_masks_email():
    out = config.redact("邮箱 someone@example.com")
    assert "someone@example.com" not in out


def test_redact_leaves_normal_text_alone():
    text = "巨无霸套餐 25.9 元"
    assert config.redact(text) == text


def test_dry_run_flag(monkeypatch):
    monkeypatch.setenv("MCD_DRY_RUN", "true")
    assert config.dry_run() is True
    monkeypatch.setenv("MCD_DRY_RUN", "0")
    assert config.dry_run() is False
