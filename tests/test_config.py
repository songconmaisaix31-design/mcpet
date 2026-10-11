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


def test_user_settings_roundtrip_and_environment_priority(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr(config, "PROJECT_ROOT", project)
    monkeypatch.setenv("MCPET_DATA_DIR", str(tmp_path / "user"))
    # 所有凭证都是测试字符串；不读取仓库根 .env。
    (project / ".env").write_text("MCD_MCP_TOKEN=project-test\nSTEPFUN_API_KEY=project-key\n", encoding="utf-8")
    config.save_settings({"MCD_MCP_TOKEN": "user-test", "STEPFUN_API_KEY": "user-key",
                          "MCPET_CITY": "上海", "MCPET_AGENT_ROOT_CODEX": 'C:\\logs\\"test"'})
    for key in config.SETTINGS_KEYS:
        monkeypatch.delenv(key, raising=False)
    config.load_env()
    assert config.mcp_token() == "user-test"
    assert config.stepfun_api_key() == "user-key"
    assert config.city() == "上海"
    import os
    assert os.environ["MCPET_AGENT_ROOT_CODEX"] == 'C:\\logs\\"test"'
    monkeypatch.setenv("MCD_MCP_TOKEN", "environment-test")
    config.load_env()
    assert config.mcp_token() == "environment-test"


def test_settings_preserve_other_fields_and_can_clear_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("MCPET_DATA_DIR", str(tmp_path))
    config.save_settings({"STEPFUN_API_KEY": "fake-old-key", "MCPET_CITY": "广州"})
    config.save_settings({"MCD_MCP_TOKEN": "fake-token"})
    from dotenv import dotenv_values
    assert dotenv_values(tmp_path / ".env")["STEPFUN_API_KEY"] == "fake-old-key"
    config.save_settings({"STEPFUN_API_KEY": ""})
    assert config.stepfun_api_key() is None
    assert dotenv_values(tmp_path / ".env")["MCPET_CITY"] == "广州"


def test_bad_settings_and_nonexistent_roots_are_explicit(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setenv("MCPET_DATA_DIR", str(tmp_path))
    with pytest.raises(ValueError):
        config.save_settings({"UNKNOWN": "value"})
    with pytest.raises(ValueError):
        config.save_settings({"MCD_MCP_TOKEN": "bad\ninjected=value"})
    warnings = config.root_warnings({"MCPET_AGENT_ROOT_CODEX": str(tmp_path / "missing")})
    assert "不存在" in warnings[0]
    assert not (tmp_path / "missing").exists()


def test_credential_dollar_text_is_not_interpolated_on_reopen(tmp_path, monkeypatch):
    monkeypatch.setenv("MCPET_DATA_DIR", str(tmp_path / "user"))
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path / "empty-project")
    config.save_settings({"STEPFUN_API_KEY": "literal-${PATH}-key"})
    monkeypatch.delenv("STEPFUN_API_KEY", raising=False)
    config.load_env()
    assert config.stepfun_api_key() == "literal-${PATH}-key"
