"""命令行入口：用于验证真实 MCP 调用，也是 MCP_INTEGRATION.md 的证据来源。

    python -m src.cli tools        # 拉真实工具清单，核对我们推测的参数名
    python -m src.cli now          # now-time-info
    python -m src.cli coupons      # 领券汇报（会真实领券；--no-claim 只查不领）
    python -m src.cli deal         # 今天最划算的一单
    python -m src.cli order        # 下单链路（默认只展示摘要，--yes 才落单）
    python -m src.cli nutrition --keyword 巨无霸 --log
    python -m src.cli models       # 阶跃星辰可用模型
    python -m src.cli ask "..."    # 让大模型调度 MCP 工具回答

    python -m src.cli agents       # 这台机器上接了哪些 Agent 数据源
    python -m src.cli usage        # 账号余额提醒（token 用量台账）
    python -m src.cli progress     # 项目进度汇报（各 Agent 会话快照）

所有输出都过一遍 redact()，直接贴进 README 也不会漏 Token / 手机号。
"""

from __future__ import annotations

import argparse
import json
import sys

from . import config
from .mcd_mcp import tools as T
from .mcd_mcp.brain import McdBrain
from .mcd_mcp.client import McdMcpClient
from .mcd_mcp.guards import OrderGuard
from .nutrition.ledger import NutritionLedger


def _client() -> McdMcpClient:
    config.load_env()
    token = config.mcp_token()
    if not token:
        print("缺少 MCD_MCP_TOKEN。把它写进项目根目录的 .env 或设置环境变量。")
        raise SystemExit(2)
    client = McdMcpClient(token, config.mcp_url())
    client.initialize()
    return client


def cmd_tools(args: argparse.Namespace) -> int:
    with _client() as client:
        real, checks = T.verify_against(client)
    token = config.mcp_token() or ""

    print(f"真实工具数：{len(real)}\n")
    missing = [name for name in T.USED_TOOLS if name not in real]
    if missing:
        print("未在服务端找到的工具：", "、".join(missing), "\n")

    print("参数名核对（assumed 是我们推测的字段名）：")
    ok = True
    for check in checks:
        mark = "OK " if check.present else "MISS"
        if not check.present:
            ok = False
        actual = ", ".join(check.actual) if check.actual else "(无字段信息)"
        print(f"  [{mark}] {check.tool}.{check.assumed:<12} 实际字段：{actual}")

    if args.dump:
        payload = {
            name: {
                "description": tool.description,
                "required": tool.required_args,
                "properties": tool.arg_names,
            }
            for name, tool in real.items()
        }
        print("\n--- tools/list ---")
        print(config.redact(json.dumps(payload, ensure_ascii=False, indent=2), token))
    return 0 if ok else 1


def cmd_now(args: argparse.Namespace) -> int:
    with _client() as client:
        result = client.call_tool(T.TOOL_NOW_TIME)
    print(config.redact(result.text or json.dumps(result.data, ensure_ascii=False), config.mcp_token() or ""))
    return 0


def cmd_coupons(args: argparse.Namespace) -> int:
    with _client() as client:
        brain = McdBrain(client, OrderGuard())
        roundup = brain.coupon_roundup(claim=not args.no_claim)
    print(f"券中心可见：{roundup.available_count} 张（其中未领 {roundup.claimable_before} 张）")
    if args.no_claim:
        print("（--no-claim：本次不执行领取）")
    elif not roundup.claim_ok:
        print(f"一键领取失败：{roundup.claim_error}")
    else:
        print(f"一键领取：{roundup.claim_message}")
    print(f"本次新领：{len(roundup.claimed)} 张")
    for name in roundup.claimed:
        print(f"  + {name}")
    print(f"手上共：{roundup.my_coupon_count} 张")
    for name in roundup.my_coupons:
        print(f"  · {name}")
    return 0


def cmd_deal(args: argparse.Namespace) -> int:
    with _client() as client:
        brain = McdBrain(client, OrderGuard())
        store = brain.resolve_default_store()
        if not store:
            print("没能解析出默认门店（请设置 MAIMAI_CITY，或在 .env 里写 city=北京）。")
            return 1
        print(f"门店：{store.store_name} ({store.store_code}) beType={store.be_type} "
              f"营业中={store.business_status} 距离={store.distance}m")
        quotes = brain.best_deal(store, keyword=args.keyword)
    if not quotes:
        print("没有拿到任何报价。")
        return 1
    for i, quote in enumerate(quotes, 1):
        coupon = quote.coupon_name or "无可用券"
        mark = "  [可随单购]" if quote.addon_available else ""
        print(f"{i}. {quote.sentence()}  [券：{coupon}]{mark}")
    return 0


def cmd_order(args: argparse.Namespace) -> int:
    """完整下单链路验证：找最优 → 展示摘要 → 显式确认 → 真实 create-order。

    默认只到「展示摘要」这一步（等价于 needs_confirmation），加 --yes 才真正落单。
    另外 MCD_DRY_RUN=1 时即使加了 --yes 也不会提交 create-order（算价仍是真实调用）。
    """
    with _client() as client:
        brain = McdBrain(client, OrderGuard())
        store = brain.resolve_default_store()
        if not store:
            print("没能解析出默认门店（请设置 MAIMAI_CITY）。")
            return 1
        print(f"门店：{store.store_name} ({store.store_code}) beType={store.be_type}")
        quotes = brain.best_deal(store, keyword=args.keyword)
        if not quotes:
            print("没有拿到任何报价。")
            return 1
        quote = quotes[0]
        print(f"最优：{quote.sentence()}")
        print(f"     券：{quote.coupon_name or '无'}（couponId={quote.coupon_id or '-'}）")

        # 取餐方式：到店场景必传 takeWayCode
        options = brain.take_way_options(store, quote.meal_code)
        if options:
            print("取餐方式：" + "、".join(
                f"{o.get('title')}({o.get('code')})" for o in options if isinstance(o, dict)
            ))

        outcome = brain.place_order(
            store,
            [quote.meal_code],
            [quote.meal_name],
            coupon_id=quote.coupon_id or None,
            coupon_code=quote.coupon_code or None,
            coupon_name=quote.coupon_name,
            take_way_code=args.take_way,
            confirmed=args.yes,
        )

    print("\n" + outcome.summary)
    print(f"\n状态：{outcome.status}")
    if outcome.status == "needs_confirmation":
        print("（未落单。加 --yes 才会真正提交 create-order）")
    elif outcome.status == "dry_run_skipped":
        print("（MCD_DRY_RUN 已开启，未提交订单）")
    elif outcome.status == "placed":
        print(f"订单号：{outcome.order_no}")
        if outcome.pay_url:
            print(f"支付链接：{outcome.pay_url}")
    elif outcome.status == "rejected":
        print(f"原因：{outcome.reason}")
    return 0 if outcome.status != "rejected" else 1


def cmd_agents(args: argparse.Namespace) -> int:
    """如实汇报：支持几种 provider、这台机器上配了几种、各自目录在哪。"""
    from .agentbridge import available_providers, resolve_roots

    roots = resolve_roots(config_path=config.agent_config_path())
    print(f"代码里实现的 provider：{', '.join(available_providers())}")
    print(f"配置文件：{config.agent_config_path()}")
    print("")
    print("根目录解析（环境变量 > 配置文件 > 平台默认候选）：")
    lines = roots.describe()
    if not lines:
        print("    一个都没有。")
    for line in lines:
        print("   ", line)
    print("")
    active = roots.active_ids()
    if active:
        print(f"本机可用：{', '.join(active)}")
    else:
        print("本机一个数据源都没有。")
        print("    要么装一个受支持的 Agent，要么把任何 Agent 的日志按")
        print("    docs/AGENT_BRIDGE.md 的规范写进通用收件箱。")
    return 0


def cmd_usage(args: argparse.Namespace) -> int:
    """账号余额提醒：扫台账 → 出报告。"""
    from pathlib import Path

    from .metering import build_meter, bubble, format_tokens, reminder_level, report

    state_path = Path(args.state) if args.state else None
    meter = build_meter(state_path=state_path)
    if not meter.providers:
        print("没有可用的数据源，先跑 `python -m src.cli agents` 看看。")
        return 1

    if args.no_scan:
        snapshot = meter.snapshot()
    else:
        if state_path is None and not meter.state_path.exists():
            print("首次回填，需要扫一遍历史日志，可能要几十秒…", file=sys.stderr)
        result = meter.scan()
        print(result.describe(), file=sys.stderr)
        snapshot = meter.snapshot()

    projected, remaining, sample_ok = meter.window_projection(snapshot)
    if args.json:
        payload = {
            "sources": snapshot.sources,
            "windowHours": snapshot.window_hours,
            "window": snapshot.window.to_dict(),
            "today": snapshot.today.to_dict(),
            "lifetime": snapshot.lifetime.to_dict(),
            "projectedTokens": round(projected),
            "sampleOk": sample_ok,
            "level": reminder_level(snapshot, projected),
            "estimatedModels": snapshot.estimated_models,
            "unknownModels": snapshot.unknown_models,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(config.redact(report(snapshot, projected, remaining, sample_ok, days=args.days)))
    print("")
    print(f"气泡文案：{config.redact(bubble(snapshot, projected, sample_ok))}")
    print(f"提醒档位：{reminder_level(snapshot, projected)}")
    return 0


def cmd_progress(args: argparse.Namespace) -> int:
    """项目进度汇报：读各 Agent 的会话快照。"""
    from .progress import build_tracker, bubble, report

    tracker = build_tracker(stale_minutes=args.stale, max_sessions=args.limit)
    if not tracker.providers:
        print("没有可用的数据源，先跑 `python -m src.cli agents` 看看。")
        return 1

    snapshot = tracker.snapshot()
    if args.json:
        payload = {
            "sources": snapshot.sources,
            "staleMinutes": snapshot.stale_minutes,
            "processSampling": snapshot.process_sampling,
            "sessions": [
                {
                    "source": item.record.source,
                    "sessionId": item.record.session_id,
                    "state": item.record.state,
                    "project": item.record.project,
                    "title": item.record.title,
                    "model": item.record.model,
                    "contextPercent": item.context_percent,
                    "backgroundTasks": item.record.background_tasks,
                    "stale": item.stale,
                    "ageSeconds": round(item.age_seconds, 1),
                }
                for item in snapshot.sessions
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(config.redact(report(snapshot, show_stale=not args.active_only)))
    print("")
    print(f"气泡文案：{config.redact(bubble(snapshot))}")
    return 0


def cmd_models(args: argparse.Namespace) -> int:
    """列出阶跃星辰可用对话模型（真实调用 /v1/models）。"""
    config.load_env()
    from .llm.stepfun import StepFunClient

    with StepFunClient() as llm:
        models = llm.models()
    print(f"阶跃星辰可用对话模型 {len(models)} 个：")
    for item in models:
        print(f"  {item['id']:<24} 上下文 {item.get('max_input_tokens')}  "
              f"视觉 {item.get('enable_vision_input')}  推理 {item.get('enable_reason')}")
    print(f"\n当前默认：{config.stepfun_model()}")
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    """让大模型调度麦当劳 MCP 工具回答一个问题（真实调用）。

    没有 MCD_MCP_TOKEN 时退化为纯问答，用于验证阶跃星辰链路本身。
    """
    config.load_env()
    from .llm.stepfun import StepFunClient
    from .mcd_mcp.guards import OrderGuard
    from .mcd_mcp.skill import run_skill

    with StepFunClient() as llm:
        token = config.mcp_token()
        if not token:
            reply = llm.chat([{"role": "user", "content": args.question}])
            print("[无 MCP Token，纯问答模式]")
            print(config.redact(reply.text or "(空回复)", ""))
            print("usage:", reply.usage)
            return 0
        from .mcd_mcp.brain import McdBrain
        from .mcd_mcp.client import McdMcpClient, McpError

        try:
            with McdMcpClient(token, config.mcp_url()) as client:
                brain = McdBrain(client, OrderGuard())
                result = run_skill(
                    args.question,
                    brain,
                    llm,
                    allow_write=args.allow_write,
                    on_step=lambda step: print(f"  · 调用 {step.tool} {step.arguments}"),
                )
        except McpError as exc:
            print(f"[MCP 不可用：{exc}]\n退化为纯问答模式。\n")
            reply = llm.chat([{"role": "user", "content": args.question}])
            print(config.redact(reply.text or "(空回复)", ""))
            return 1
    for step in result.steps:
        print(f"[已调用] {step.tool} → {step.result_preview[:200]}")
    if result.needs_confirmation:
        print("\n需要确认：", result.pending_reason)
        print("参数：", result.pending_write.arguments if result.pending_write else "")
        return 0
    print("\n回答：", config.redact(result.answer, config.mcp_token() or ""))
    return 0


def cmd_nutrition(args: argparse.Namespace) -> int:
    with _client() as client:
        brain = McdBrain(client, OrderGuard())
        facts = brain.nutrition(keyword=args.keyword or "")
    if not facts:
        print("没查到营养数据。")
        return 1
    print(f"共 {len(facts)} 条营养数据（本地过滤 keyword={args.keyword or '无'}）")
    ledger = NutritionLedger()
    shown = facts[: args.limit]
    for fact in shown:
        note = f" | {fact.note}" if fact.note else ""
        print(
            f"{fact.name}: {fact.energy_kcal:.0f} kcal（{fact.energy_kj:.0f} kJ）| "
            f"蛋白 {fact.protein_g:.1f} g | 脂肪 {fact.fat_g:.1f} g | "
            f"碳水 {fact.carb_g:.1f} g | 钠 {fact.sodium_mg:.0f} mg | "
            f"钙 {fact.calcium_mg:.0f} mg{note}"
        )
    if args.log and shown:
        entry = ledger.add_fact(shown[0])
        print(f"\n已记入台账：{entry.meal_name}（{entry.date}）")
        print(ledger.summary())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="maimai", description="麦麦小怪兽命令行验证工具")
    sub = parser.add_subparsers(dest="command", required=True)

    p_tools = sub.add_parser("tools", help="拉取真实工具清单并核对参数名")
    p_tools.add_argument("--dump", action="store_true", help="打印完整工具清单")
    p_tools.set_defaults(func=cmd_tools)

    p_now = sub.add_parser("now", help="now-time-info")
    p_now.set_defaults(func=cmd_now)

    p_coupons = sub.add_parser("coupons", help="领券汇报（真实领券）")
    p_coupons.add_argument("--no-claim", action="store_true", help="只查不领")
    p_coupons.set_defaults(func=cmd_coupons)

    p_deal = sub.add_parser("deal", help="今天最划算的一单")
    p_deal.add_argument("--keyword", default=None, help="只考虑名字包含该关键词的餐品")
    p_deal.set_defaults(func=cmd_deal)

    p_order = sub.add_parser("order", help="完整下单链路（默认只展示摘要，加 --yes 才落单）")
    p_order.add_argument("--keyword", default=None, help="只在名字含该关键词的餐品里挑")
    p_order.add_argument("--take-way", default=None,
                         choices=["eat-in", "take-in-store"], help="取餐方式（默认外带）")
    p_order.add_argument("--yes", action="store_true", help="真正提交 create-order")
    p_order.set_defaults(func=cmd_order)

    p_nut = sub.add_parser("nutrition", help="营养查询")
    p_nut.add_argument("--keyword", default="", help="按名字过滤（如 巨无霸）")
    p_nut.add_argument("--limit", type=int, default=10)
    p_nut.add_argument("--log", action="store_true", help="把第一项记入营养台账")
    p_nut.set_defaults(func=cmd_nutrition)

    p_models = sub.add_parser("models", help="列出阶跃星辰可用对话模型")
    p_models.set_defaults(func=cmd_models)

    p_ask = sub.add_parser("ask", help="问小怪兽（大模型调度 MCP 工具）")
    p_ask.add_argument("question")
    p_ask.add_argument("--allow-write", action="store_true",
                       help="允许大模型直接执行领券/下单等写操作（默认需人工确认）")
    p_ask.set_defaults(func=cmd_ask)

    p_agents = sub.add_parser("agents", help="看看这台机器上接了哪些 Agent 数据源")
    p_agents.set_defaults(func=cmd_agents)

    p_usage = sub.add_parser("usage", help="账号余额提醒（token 用量台账）")
    p_usage.add_argument("--days", type=int, default=7, help="趋势展示最近几天")
    p_usage.add_argument("--state", default=None, help="台账文件路径（默认在数据目录下）")
    p_usage.add_argument("--no-scan", action="store_true", help="只读现有台账，不重新扫描")
    p_usage.add_argument("--json", action="store_true", help="输出 JSON")
    p_usage.set_defaults(func=cmd_usage)

    p_progress = sub.add_parser("progress", help="项目进度汇报（各 Agent 会话快照）")
    p_progress.add_argument("--stale", type=int, default=None, help="多少分钟没更新算「停了」")
    p_progress.add_argument("--limit", type=int, default=12, help="最多显示几个会话")
    p_progress.add_argument("--active-only", action="store_true", help="只显示活跃会话")
    p_progress.add_argument("--json", action="store_true", help="输出 JSON")
    p_progress.set_defaults(func=cmd_progress)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
