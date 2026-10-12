"""Portable skill installation and execution against isolated, real MCP stdio."""
import asyncio
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import jsonschema
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import pytest

from src.agent_install import ROOT, SKILL, install


@pytest.mark.parametrize("client, directories", [
    ("claude", [".claude/skills"]),
    ("opencode", [".opencode/skills"]),
    ("both", [".claude/skills", ".opencode/skills"]),
])
def test_native_adapters_install_portable_skill_and_preserve_other_skills(tmp_path, client, directories):
    for directory in directories:
        other = tmp_path / directory / "other/SKILL.md"
        other.parent.mkdir(parents=True)
        other.write_text("user skill", encoding="utf-8")
    install(tmp_path, client)
    install(tmp_path, client)
    for directory in directories:
        target = tmp_path / directory / "mcpet"
        for source in SKILL.rglob("*.md"):
            assert (target / source.relative_to(SKILL)).read_bytes() == source.read_bytes()
        assert (tmp_path / directory / "other/SKILL.md").read_text() == "user skill"
        assert (target / "references/orders.md").is_file()


@pytest.mark.parametrize("absolute", [False, True])
def test_generic_skill_copy_does_not_read_brand_configs(tmp_path, absolute):
    project = tmp_path / "project"
    project.mkdir()
    native = project / ".mcp.json"
    native.write_text("not json", encoding="utf-8")
    directory = tmp_path / "external-skills" if absolute else Path("custom-skills")
    installed = install(project, skill_dir=directory)
    target = directory if absolute else project / directory
    assert (target / "mcpet/SKILL.md").is_file()
    assert native.read_text() == "not json"
    assert not (project / "opencode.json").exists()
    assert not (project / ".claude").exists()
    assert len(installed) == len(list(SKILL.rglob("*.md")))


def test_invalid_skill_target_is_refused_before_native_configuration_changes(tmp_path):
    target = tmp_path / "skills/mcpet/references"
    target.parent.mkdir(parents=True)
    target.write_text("existing file", encoding="utf-8")
    with pytest.raises(ValueError, match="上级不是目录"):
        install(tmp_path, "both", skill_dir="skills")
    assert not (tmp_path / ".mcp.json").exists()
    assert not (tmp_path / "opencode.json").exists()
    assert target.read_text() == "existing file"


def test_skill_symlink_preflight_refuses_before_native_configuration_changes(tmp_path, monkeypatch):
    actual = tmp_path / "other-skill"
    actual.mkdir()
    link = tmp_path / "skills"
    # Fixture the filesystem response: Windows may deny creation of a symlink.
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == link or original(path))
    with pytest.raises(ValueError, match="符号链接"):
        install(tmp_path, "both", skill_dir="skills")
    assert not (tmp_path / ".mcp.json").exists()
    assert list(actual.iterdir()) == []


def test_exported_skill_operates_over_real_stdio_from_other_project(tmp_path, monkeypatch):
    project = tmp_path / "consumer"
    project.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    settings = data / "config.json"
    settings.write_text(json.dumps({"agentRoots": {name: str(tmp_path / ("absent-" + name))
                                                  for name in ("claude", "codex", "generic")}}))
    monkeypatch.setenv("MCPET_DATA_DIR", str(data))
    monkeypatch.setenv("MCPET_CONFIG_PATH", str(settings))
    for key in ("MCD_MCP_TOKEN", "LUCKIN_MCP_TOKEN", "DEEPSEEK_API_KEY"):
        monkeypatch.setenv(key, "")
    output = subprocess.run([sys.executable, "-m", "src.agent_install", "--project", str(project),
                             "--skill-dir", "skills"], cwd=ROOT, env=dict(os.environ),
                            capture_output=True, text=True, encoding="utf-8", timeout=15)
    assert output.returncode == 0, output.stderr
    exported = json.loads(output.stdout)
    installed = project / "skills/mcpet"
    entry = (installed / "SKILL.md").read_text(encoding="utf-8")
    documents = entry + (installed / "references/orders.md").read_text(encoding="utf-8")
    documented_tools = set(re.findall(r"\bmcpet_[a-z_]+\b", documents))
    examples = [json.loads(block) for block in re.findall(r"```json\n(.*?)\n```", entry, re.S)]

    async def run():
        definition = exported["server"]
        parameters = StdioServerParameters(command=definition["command"], args=definition["args"],
                                          cwd=str(project), env=dict(os.environ))
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = {tool.name: tool for tool in (await session.list_tools()).tools}
                # Detect stale or invented routes against the actual server catalog.
                assert documented_tools == tools.keys()
                for example in examples:
                    jsonschema.validate(example["arguments"], tools[example["tool"]].inputSchema)
                    result = await session.call_tool(example["tool"], example["arguments"])
                    assert not result.isError
                    assert result.structuredContent["separate_window"] is False
                    assert result.structuredContent["character_id"] == "deepseek"
                state = (await session.call_tool("mcpet_status", {})).structuredContent
                assert state["separate_window"] is False
                assert state["character_id"] == "deepseek"
                assert state["skin_id"] == "default"
                # Confirm after fresh connection with no reviewed order must not submit.
                for tool in ("mcpet_confirm_order", "mcpet_luckin_confirm"):
                    denied = (await session.call_tool(tool, {"confirmed": True})).structuredContent
                    assert denied["status"] == "error"
    asyncio.run(run())
