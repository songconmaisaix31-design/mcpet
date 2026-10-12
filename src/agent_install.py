"""Export a portable stdio definition, or explicitly install native adapters."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/mcpet"


def read_json(path):
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"配置不是 JSON 对象: {path.name}")
    return value


def write(path, text):
    if path.is_symlink():
        raise ValueError(f"不覆盖配置符号链接: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8-sig") == text:
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent,
                                         prefix="mcpet-", suffix=".tmp", delete=False) as stream:
            stream.write(text)
            temporary = stream.name
        os.replace(temporary, path)
    finally:
        if temporary:
            Path(temporary).unlink(missing_ok=True)


def server_definition(python=None):
    """Common stdio fields; clients may use their own configuration container."""
    return {"type": "stdio", "command": str(Path(python or sys.executable).resolve()),
            "args": [str(ROOT / "scripts/agent_host.py")]}


def skill_files(directory):
    """Copy the portable skill, including relative references, without host paths."""
    target = Path(directory) / "mcpet"
    return {target / path.relative_to(SKILL): path.read_text(encoding="utf-8")
            for path in sorted(SKILL.rglob("*.md"))}


def install(project, client="generic", python=None, skill_dir=None):
    if client not in {"generic", "both", "claude", "opencode"}:
        raise ValueError("未知接入适配")
    project = Path(project).resolve()
    if not project.is_dir():
        raise ValueError("接入目标必须是已存在的项目目录")
    definition = server_definition(python)
    python = definition["command"]
    host = definition["args"][0]
    hook = str(ROOT / "scripts/agent_hook.py")
    files = {}
    if client in {"both", "claude"}:
        path = project / ".mcp.json"
        settings = read_json(path)
        settings.setdefault("mcpServers", {})["mcpet"] = definition
        files[path] = json.dumps(settings, ensure_ascii=False, indent=2) + "\n"
        path = project / ".claude/settings.local.json"
        settings = read_json(path)
        # Claude command hooks run through its shell (Git Bash on Windows).
        # Forward slashes plus shell quoting prevent backslash loss and injection.
        command_args = [python.replace("\\", "/"), hook.replace("\\", "/"), "--host", "claude"]
        command = shlex.join(command_args)
        hooks = settings.setdefault("hooks", {})
        for event in ("SessionStart", "UserPromptSubmit", "Stop", "SessionEnd"):
            groups = hooks.setdefault(event, [])
            # Idempotent: replace only this integration's command handlers.
            for group in groups:
                group["hooks"] = [handler for handler in group.get("hooks", [])
                                  if "scripts/agent_hook.py" not in str(handler.get("command", "")).replace("\\", "/")]
            groups[:] = [group for group in groups if group.get("hooks")]
            groups.append({"hooks": [{"type": "command", "command": command, "timeout": 5}]})
        files[path] = json.dumps(settings, ensure_ascii=False, indent=2) + "\n"
        files[project / ".claude/rules/mcpet.md"] = (ROOT / "docs/AGENT-HOST-INSTRUCTIONS.md").read_text(encoding="utf-8")
        files.update(skill_files(project / ".claude/skills"))
    if client in {"both", "opencode"}:
        if (project / "opencode.jsonc").exists():
            raise ValueError("项目已有 opencode.jsonc；请按接入文档将 mcpet 合入现有文件，避免覆盖 JSONC 注释")
        path = project / "opencode.json"
        settings = read_json(path)
        settings.setdefault("$schema", "https://opencode.ai/config.json")
        settings.setdefault("mcp", {})["mcpet"] = {"type": "local", "command": [python, host],
                                                   "enabled": True, "timeout": 15000}
        guide = str(ROOT / "docs/AGENT-HOST-INSTRUCTIONS.md")
        instructions = settings.setdefault("instructions", [])
        if guide not in instructions:
            instructions.append(guide)
        files[path] = json.dumps(settings, ensure_ascii=False, indent=2) + "\n"
        template = (ROOT / "integrations/opencode/mcpet.js").read_text(encoding="utf-8")
        files[project / ".opencode/plugins/mcpet.js"] = template.replace("__MCPET_PYTHON__", json.dumps(python)).replace("__MCPET_HOOK__", json.dumps(hook))
        files.update(skill_files(project / ".opencode/skills"))
    if skill_dir is not None:
        directory = Path(skill_dir).expanduser()
        if not directory.is_absolute():
            directory = project / directory
        files.update(skill_files(directory))
    # Validate/read every input before mutating any config. Native permissions
    # and other MCP servers are never granted or removed by this installer.
    for path in files:
        if any(part.is_symlink() for part in (path, *path.parents)):
            raise ValueError(f"不通过符号链接安装: {path.name}")
        if path.exists() and not path.is_file():
            raise ValueError(f"安装目标不是文件: {path.name}")
        if any(part.exists() and not part.is_dir() for part in path.parents):
            raise ValueError(f"安装目标的上级不是目录: {path.name}")
    for path, text in files.items():
        write(path, text)
    return [str(path.relative_to(project)) if path.is_relative_to(project) else str(path)
            for path in files]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--client", choices=("generic", "both", "claude", "opencode"), default="generic")
    parser.add_argument("--skill-dir", type=Path,
                        help="显式安装到宿主的 skills 目录（内建 mcpet 子目录）；相对路径以 --project 为准")
    args = parser.parse_args()
    print(json.dumps({"server_name": "mcpet", "server": server_definition(),
                      "skill": {"name": "mcpet", "source": str(SKILL)},
                      "installed": install(args.project, args.client, skill_dir=args.skill_dir),
                      "next": ("将 command/args 填入当前宿主的 MCP stdio 接入设置；配置容器由宿主决定，无需插件"
                               if args.client == "generic" else
                               "在此项目重开原 Agent，会沿用宿主原生初次信任/工具审批")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
