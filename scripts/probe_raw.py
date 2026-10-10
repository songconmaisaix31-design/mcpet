"""一次性把关键工具的真实返回结构打出来（只读，无副作用）。

    python scripts/probe_raw.py

输出经过脱敏，用于确定 _pick() / 解析器该取哪些字段名。
比 probe.py 更激进：直接打印 raw text 与 JSON 结构，不做任何裁剪猜测。
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


def dump(label: str, result, *, head: int = 3000) -> None:
    print(f"\n{'=' * 70}\n### {label}\n{'=' * 70}")
    print(f"is_error={result.is_error} | raw_text_len={len(result.text)} | data_type={type(result.data).__name__}")
    if isinstance(result.data, (dict, list)):
        text = json.dumps(result.data, ensure_ascii=False, indent=2)
    else:
        text = result.text
    print(config.redact(text, config.mcp_token() or "")[:head])


def main() -> int:
    config.load_env()
    token = config.mcp_token()
    if not token:
        print("缺少 MCD_MCP_TOKEN")
        return 2
    city = os.environ.get("MAIMAI_CITY", "北京").strip()

    with McdMcpClient(token, config.mcp_url()) as client:
        # ---- 1. 附近门店（找营业中的） ----
        r = client.call_tool(
            T.TOOL_NEARBY_STORES,
            {"beType": 1, "orderType": 1, "searchType": 2, "city": city, "keyword": "麦当劳"},
        )
        dump("query-nearby-stores (raw)", r, head=6000)

        stores = r.as_list()
        open_stores = [s for s in stores if isinstance(s, dict) and s.get("businessStatus")]
        print(f"\n>>> 门店总数={len(stores)} | 营业中={len(open_stores)}")
        for s in stores[:8]:
            if isinstance(s, dict):
                print(
                    f"    code={s.get('storeCode')} name={s.get('storeName')} "
                    f"open={s.get('businessStatus')} dist={s.get('distance')}"
                )

        if not open_stores:
            print("没有营业中的门店，退出")
            return 1
        store = open_stores[0]
        store_code = str(store.get("storeCode"))
        print(f"\n>>> 选用门店: {store.get('storeName')} ({store_code})")

        base = {"storeCode": store_code, "beType": 1, "orderType": 1}

        # ---- 2. 菜单 ----
        meals_r = client.call_tool(T.TOOL_MEALS, base)
        dump("query-meals (raw text head)", meals_r, head=4000)

        # ---- 3. 门店券 ----
        sc_r = client.call_tool(T.TOOL_STORE_COUPONS, base)
        dump("query-store-coupons (raw)", sc_r, head=6000)

        # ---- 4. 我的券 ----
        mc_r = client.call_tool(T.TOOL_MY_COUPONS)
        dump("query-my-coupons (raw)", mc_r, head=4000)

        # ---- 5. 可领券 ----
        ac_r = client.call_tool(T.TOOL_AVAILABLE_COUPONS)
        dump("available-coupons (raw)", ac_r, head=4000)

        # ---- 6. 营养表 ----
        nt_r = client.call_tool(T.TOOL_NUTRITION)
        dump("list-nutrition-foods (raw text)", nt_r, head=2500)

        # ---- 7. 算价（无券 / 带券） ----
        # 先取菜单里第一个 productCode
        meals_text = meals_r.text
        try:
            meals_json = json.loads(meals_text)
        except json.JSONDecodeError:
            meals_json = None
        first_code = None
        if isinstance(meals_json, dict):
            inner = meals_json.get("data", meals_json)
            meals_map = inner.get("meals") if isinstance(inner, dict) else None
            if isinstance(meals_map, dict):
                first_code = next(iter(meals_map), None)
        print(f"\n>>> 菜单首个 productCode = {first_code}")

        if first_code:
            p = client.call_tool(
                T.TOOL_CALCULATE_PRICE,
                {**base, "items": [{"productCode": first_code, "quantity": 1}]},
            )
            dump("calculate-price (no coupon)", p, head=2500)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
