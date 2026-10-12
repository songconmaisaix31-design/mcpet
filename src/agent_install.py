"""Install native project-scoped host config; preserve unrelated settings."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


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
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix="mcpet-", suffix=".tmp", delete=False) as stream:
            stream.write(text)
            temporary = stream.name
        os.replace(temporary, path)
    finally:
        if temporary:
            Path(temporary).unlink(missing_ok=True)


def install(project, client="both", python=None):
    project = Path(project).resolve()
    if not project.is_dir():
        raise ValueError("接入目标必须是已存在的项目目录")
    python = str(Path(python or sys.executable).resolve())
    host = str(ROOT / "scripts/agent_host.py")
    hook = str(ROOT / "scripts/agent_hook.py")
    files = {}
    if client in {"both", "claude"}:
        path = project / ".mcp.json"
        settings = read_json(path)
        settings.setdefault("mcpServers", {})["mcpet"] = {"type": "stdio", "command": python, "args": [host]}
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
    # Validate/read every input before mutating any config. Native permissions
    # and other MCP servers are never granted or removed by this installer.
    for path, text in files.items():
        write(path, text)
    return [str(path.relative_to(project)) for path in files]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--client", choices=("both", "claude", "opencode"), default="both")
    args = parser.parse_args()
    print(json.dumps({"installed": install(args.project, args.client),
                      "next": "在此项目重开原 Agent，会沿用宿主原生初次信任/工具审批"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
