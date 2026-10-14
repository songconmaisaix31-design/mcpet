# 发行包含用户明确公开的试用凭证，本机个人配置不进入发行包。
from pathlib import Path
import argparse
import json
import subprocess
import sys
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0"
ASSET_DIRS = {"longniang", "dsh-deepseek", "maimai-actions", "deepseek-actions", "deepseek-skins"}


def release_files():
    """Curate runtime files; never enumerate a home directory or local host config."""
    for folder in ("src", "integrations", ".agents/skills/mcpet"):
        for path in sorted((ROOT / folder).rglob("*")):
            if path.is_file() and path.suffix in {".py", ".js", ".md"} and "__pycache__" not in path.parts:
                yield path
    for name in sorted(ASSET_DIRS):
        for path in sorted((ROOT / "assets" / name).rglob("*")):
            if path.is_file() and (path.suffix in {".png", ".gif", ".webp", ".webm", ".json", ".md"} or path.name == "LICENSE"):
                yield path
    for name in ("requirements-agent.txt", "requirements.txt", ".env.example", ".env.trial", "assets/CREDITS.md", "assets/cetapet/actions.json", "assets/cetapet/SOURCE.md",
                 "docs/AGENT-HOST-INSTRUCTIONS.md", "scripts/agent_host.py", "scripts/agent_hook.py"):
        yield ROOT / name


def write_archive(path, files, prefix):
    with ZipFile(path, "w", ZIP_DEFLATED, compresslevel=6) as archive:
        for source, relative in files:
            archive.write(source, f"{prefix}/{relative}")
        archive.write(ROOT / "docs/RELEASE-QUICKSTART.md", f"{prefix}/README.md")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--windows", action="store_true", help="Also build the Windows x64 portable executable")
    args = parser.parse_args()
    output = ROOT / "dist" / f"v{VERSION}"
    output.mkdir(parents=True, exist_ok=True)
    source = output / f"McPet-v{VERSION}-agent.zip"
    write_archive(source, [(p, p.relative_to(ROOT).as_posix()) for p in release_files()], source.stem)
    packages = [source]
    if args.windows:
        if sys.platform != "win32":
            parser.error("Windows 包请在 Windows 构建")
        build = ROOT / "build" / f"release-v{VERSION}"
        command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onedir", "--name", "McPet",
                   "--distpath", str(build / "dist"), "--workpath", str(build / "work"),
                   "--specpath", str(build), "--paths", str(ROOT),
                   "--collect-submodules", "src", "--collect-submodules", "mcp.client",
                   "--collect-submodules", "mcp.server", "--collect-submodules", "mcp.shared",
                   "--copy-metadata", "jsonschema", "--copy-metadata", "referencing"]
        for folder in sorted(ASSET_DIRS):
            command += ["--add-data", f"{ROOT / 'assets' / folder}:assets/{folder}"]
        for relative in (".env.trial", "assets/CREDITS.md", "assets/cetapet/actions.json", "assets/cetapet/SOURCE.md", "docs/AGENT-HOST-INSTRUCTIONS.md", ".agents/skills/mcpet",
                         "integrations/opencode", "scripts/agent_hook.py"):
            path = ROOT / relative
            destination = relative if path.is_dir() else str(Path(relative).parent).replace("\\", "/")
            command += ["--add-data", f"{path}:{destination}"]
        command.append(str(ROOT / "scripts/release_entry.py"))
        subprocess.run(command, cwd=ROOT, check=True)
        native = build / "dist/McPet"
        # ASCII VBS is understood by Windows Script Host regardless of locale.
        (native / "Start-Pet.vbs").write_text(
            'Set fso = CreateObject("Scripting.FileSystemObject")\n'
            'Set shell = CreateObject("WScript.Shell")\n'
            'shell.CurrentDirectory = fso.GetParentFolderName(WScript.ScriptFullName)\n'
            'shell.Run Chr(34) & shell.CurrentDirectory & "\\McPet.exe" & Chr(34) & " --desktop", 0, False\n',
            encoding="ascii")
        windows = output / f"McPet-v{VERSION}-windows-x64.zip"
        write_archive(windows, [(p, p.relative_to(native).as_posix()) for p in sorted(native.rglob("*")) if p.is_file()], windows.stem)
        packages.append(windows)
    print(json.dumps({"version": VERSION, "packages": [{"file": p.name, "bytes": p.stat().st_size} for p in packages]}))


if __name__ == "__main__":
    main()
