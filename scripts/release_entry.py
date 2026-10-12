"""Frozen entry: standard stdio by default, desktop/install only when requested."""
import multiprocessing
from pathlib import Path
import sys


def main():
    multiprocessing.freeze_support()
    if "--version" in sys.argv:
        print("McPet 0.1.0")
        return 0
    if "--install" in sys.argv:
        sys.argv.remove("--install")
        from src.agent_install import main as install
        install()
        return 0
    # Native host adapters pass the hook file as the first argument, just as
    # they do for Python. Dispatch it without trying to interpret Python code.
    if len(sys.argv) > 1 and Path(sys.argv[1]).name == "agent_hook.py":
        sys.argv.pop(1)
        from src.agent_hook import main as hook
        return hook()
    if "--desktop" in sys.argv:
        from src.main import main as desktop
        return desktop()
    from src.agent_mcp import main as agent
    agent()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
