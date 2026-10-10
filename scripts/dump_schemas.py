"""导出真实 MCP 工具 schema，作为 MCP_INTEGRATION.md 的证据。

    python scripts/dump_schemas.py

产出 docs/mcp-schemas.json（全部工具）与控制台摘要（只列我们用到的）。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src import config  # noqa: E402
from src.mcd_mcp import tools as T  # noqa: E402
from src.mcd_mcp.client import McdMcpClient  # noqa: E402


def describe(schema: dict, indent: int = 2) -> list[str]:
    """递归列出字段、类型、是否必填、说明。"""
    lines: list[str] = []
    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    pad = " " * indent
    for name, spec in props.items():
        spec = spec or {}
        kind = spec.get("type", "?")
        desc = (spec.get("description") or "").strip().replace("\n", " ")[:70]
        mark = "*" if name in required else " "
        lines.append(f"{pad}{mark} {name}: {kind}" + (f"  # {desc}" if desc else ""))
        if kind == "object":
            lines.extend(describe(spec, indent + 4))
        elif kind == "array":
            items = spec.get("items") or {}
            if items.get("type") == "object":
                lines.append(f"{pad}    [数组元素]")
                lines.extend(describe(items, indent + 6))
    return lines


def main() -> int:
    config.load_env()
    token = config.mcp_token()
    if not token:
        print("缺少 MCD_MCP_TOKEN")
        return 2

    out_path = ROOT / "docs" / "mcp-schemas.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with McdMcpClient(token, config.mcp_url()) as client:
        client.initialize()
        real = {tool.name: tool for tool in client.list_tools()}
        out_path.write_text(
            json.dumps(
                {
                    name: {
                        "description": tool.description,
                        "inputSchema": tool.input_schema,
                    }
                    for name, tool in real.items()
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    print(f"共 {len(real)} 个工具，完整 schema 已写入 {out_path}\n")
    print("=" * 70)
    print("本项目用到的工具（* 表示必填）")
    print("=" * 70)
    for name in T.USED_TOOLS:
        tool = real.get(name)
        if not tool:
            print(f"\n### {name}\n  !! 服务端没有这个工具")
            continue
        print(f"\n### {name}")
        if tool.description:
            print(f"  {tool.description.strip()[:120]}")
        body = describe(tool.input_schema)
        print("\n".join(body) if body else "  （无入参）")

    missing = [n for n in T.USED_TOOLS if n not in real]
    if missing:
        print("\n未找到：", "、".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
