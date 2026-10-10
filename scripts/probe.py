"""探查真实返回结构（只读工具，不产生副作用）。

    python scripts/probe.py addresses
    python scripts/probe.py stores
    python scripts/probe.py coupons
    python scripts/probe.py mycoupons
    python scripts/probe.py nutrition
    python scripts/probe.py meals
    python scripts/probe.py storecoupons

输出经过脱敏，用于确定代码里 _pick() 该取哪些字段名。
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
from src.mcd_mcp.brain import _pick  # noqa: E402


def show(label: str, obj, limit: int = 2) -> None:
    print(f"\n===== {label} =====")
    text = json.dumps(obj, ensure_ascii=False, indent=2)
    print(config.redact(text, config.mcp_token() or "")[: 4000 * limit])


def main() -> int:
    config.load_env()
    token = config.mcp_token()
    if not token:
        print("缺少 MCD_MCP_TOKEN")
        return 2
    what = sys.argv[1] if len(sys.argv) > 1 else "addresses"

    with McdMcpClient(token, config.mcp_url()) as client:
        if what == "addresses":
            result = client.call_tool(T.TOOL_DELIVERY_ADDRESSES)
            show("delivery-query-addresses", result.as_list())
        elif what == "stores":
            addresses = client.call_tool(T.TOOL_DELIVERY_ADDRESSES).as_list()
            if not addresses:
                print("没有配送地址")
                return 1
            address_id = str(_pick(addresses[0], "addressId", "id", default="") or "")
            print("addressId =", address_id)
            result = client.call_tool(
                T.TOOL_DELIVERY_STORES, {"addressId": address_id, "beType": 2}
            )
            show("delivery-query-stores", result.as_list()[:3])
        elif what == "coupons":
            show("available-coupons", client.call_tool(T.TOOL_AVAILABLE_COUPONS).as_list()[:3])
        elif what == "mycoupons":
            show("query-my-coupons", client.call_tool(T.TOOL_MY_COUPONS).as_list()[:3])
        elif what == "nutrition":
            show("list-nutrition-foods", client.call_tool(T.TOOL_NUTRITION).as_list()[:3])
        elif what in {"meals", "storecoupons"}:
            addresses = client.call_tool(T.TOOL_DELIVERY_ADDRESSES).as_list()
            if not addresses:
                print("没有配送地址")
                return 1
            address_id = str(_pick(addresses[0], "addressId", "id", default="") or "")
            stores = client.call_tool(
                T.TOOL_DELIVERY_STORES, {"addressId": address_id, "beType": 2}
            ).as_list()
            if not stores:
                print("没有可配送门店")
                return 1
            store = stores[0]
            store_code = str(_pick(store, "storeCode", "storeId", "id", default="") or "")
            be_code = str(_pick(store, "beCode", default="") or "")
            print("storeCode =", store_code, "| beCode =", be_code)
            args = {"storeCode": store_code, "beType": 2, "orderType": 2}
            if be_code:
                args["beCode"] = be_code
            if what == "meals":
                show("query-meals", client.call_tool(T.TOOL_MEALS, args).as_list()[:3])
            else:
                show("query-store-coupons", client.call_tool(T.TOOL_STORE_COUPONS, args).as_list()[:3])
        else:
            print("未知选项")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
