"""Stable absolute launcher for MCP clients, independent of their working dir."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent_mcp import main

if __name__ == "__main__":
    main()
