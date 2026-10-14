import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import dotenv_values
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src import config
from src.mcd_mcp.client import McdMcpClient
from src.luckin import LuckinClient
from scripts.build_release import release_files, write_archive


def check_config():
    trial = config.trial_tokens()
    personal = {key: os.environ.get(key) for key in config.TRIAL_KEYS}
    config.load_env()
    assert all(config.mcp_token() if key == "MCD_MCP_TOKEN" else config.luckin_token() for key in trial)
    for key, value in personal.items():
        if value and not config._is_placeholder(value):
            assert os.environ[key] == value
    assert all(config.redact(value) == "***" for value in (config.mcp_token(), config.luckin_token()))
    return {"configured": True, "mcd_mode": config.credential_mode("MCD_MCP_TOKEN"),
            "luckin_mode": config.credential_mode("LUCKIN_MCP_TOKEN"), "output_redaction": True}


def check_personal_config():
    # 使用同一组真实凭证验证带空格的本机输入、保存和优先级，不生成假 Token。
    tokens = {"MCD_MCP_TOKEN": config.mcp_token(), "LUCKIN_MCP_TOKEN": config.luckin_token()}
    values = {key: " " + value + " " for key, value in tokens.items()}
    config.save_settings(values)
    for key in tokens:
        os.environ.pop(key)
    config.load_env()
    assert all(os.environ[key] == values[key] for key in tokens)
    assert config.mcp_token() == tokens["MCD_MCP_TOKEN"]
    assert config.luckin_token() == tokens["LUCKIN_MCP_TOKEN"]
    assert all(config.redact(value) == "***" for value in tokens.values())
    return {"real_settings_saved": True, "personal_config_precedes_trial": True, "whitespace_normalized_for_requests": True}


async def check_stdio(work):
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "scripts/agent_host.py")], env=dict(os.environ))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("mcpet_settings", {})
            assert not result.isError
            settings = result.structuredContent
            assert settings["mcd_configured"] and settings["luckin_configured"]
            encoded = json.dumps(settings)
            assert all(value not in encoded for value in config.trial_tokens().values())
            return {"settings_available": True, "tokens_absent_from_settings": True}


def check_online(provider):
    if provider == "mcd":
        client = McdMcpClient(config.mcp_token(), config.mcp_url(), max_retries_on_429=0, timeout=25)
    else:
        client = LuckinClient(config.luckin_token())
    with client:
        client.ensure_initialized()
        tools = client.list_tools()
        assert tools
        if provider == "mcd":
            result = client.call_tool("now-time-info", {})
            result.raise_for_error()
            assert result.ok
    return {"provider": provider, "tools": len(tools), "initialized": True}


def check_archive(work):
    files = [(path, path.relative_to(ROOT).as_posix()) for path in release_files()]
    assert ".env.trial" in {relative for _, relative in files}
    assert ".env" not in {relative for _, relative in files}
    path = work / "McPet-trial-agent.zip"
    write_archive(path, files, "McPet-trial-agent")
    with ZipFile(path) as archive:
        assert archive.read("McPet-trial-agent/.env.trial") == config.TRIAL_PATH.read_bytes()
        assert "McPet-trial-agent/.env" not in archive.namelist()
        extracted = work / "extracted"
        archive.extractall(extracted)
    env = dict(os.environ)
    for key in config.TRIAL_KEYS:
        env.pop(key, None)
    env["MCPET_DATA_DIR"] = str(work / "archive-profile")
    result = subprocess.run([sys.executable, "-c",
        "from src import config; config.load_env(); "
        "assert config.mcp_token() and config.luckin_token(); "
        "assert config.credential_mode('MCD_MCP_TOKEN') == 'trial'; "
        "assert config.credential_mode('LUCKIN_MCP_TOKEN') == 'trial'"],
        cwd=extracted / "McPet-trial-agent", env=env, capture_output=True, text=True)
    assert result.returncode == 0, "解压后的试用配置加载失败"
    return {"archive_built": True, "trial_included": True, "personal_config_excluded": True, "extracted_startup": True}


def main():
    parser = argparse.ArgumentParser(description="实际试用凭证、MCP 服务与发行文件验证")
    parser.add_argument("--online", choices=("mcd", "luckin"))
    parser.add_argument("--archive", action="store_true")
    args = parser.parse_args()
    work = ROOT / ".tmp-test-data/credential-binding/verification" / (args.online or "stdio")
    work.mkdir(parents=True, exist_ok=True)
    os.environ["MCPET_DATA_DIR"] = str(work / "profile")
    result = {"config": check_config()}
    result["personal_config"] = check_personal_config()
    if args.online:
        result["online"] = check_online(args.online)
    else:
        result["stdio"] = asyncio.run(check_stdio(work))
    if args.archive:
        result["archive"] = check_archive(work)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
