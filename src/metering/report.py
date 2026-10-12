"""余额提醒文案。

分两档输出，对应两个使用场景：

    bubble()   一句话，给桌宠气泡（宽度有限，只放最该看的那件事）
    report()   多行，给 CLI 与详情面板（口径、分项、趋势、可信度全摊开）

**口径纪律**（这个项目的底线）：本机台账 ≠ 厂商账单。报告里必须出现这句话，
并且把「哪些模型是估算的」列出来。宁可显得啰嗦，也不让一个估算数字冒充账单。
"""

from __future__ import annotations

from ..agentbridge.records import UsageTotals
from .usage import UsageSnapshot, recent_days


def format_tokens(value: float) -> str:
    n = float(value)
    if n >= 1e9:
        return f"{n / 1e9:.2f}B"
    if n >= 1e6:
        return f"{n / 1e6:.2f}M"
    if n >= 1e3:
        return f"{n / 1e3:.1f}k"
    return str(int(n))


def format_usd(value: float) -> str:
    if value >= 100:
        return f"${value:,.0f}"
    if value >= 1:
        return f"${value:.2f}"
    return f"${value:.4f}"


def reminder_level(snapshot: UsageSnapshot, projected: float) -> str:
    """把用量分成四档，供桌宠选表情与是否弹气泡。

    阈值是**本机经验值**，不是厂商配额——所以档位只用于「要不要提一句」，
    不用来宣称「你还能用多少」。
    """
    if not snapshot.has_data or snapshot.errors:
        return "unknown"
    if snapshot.window.calls == 0:
        return "idle"
    if projected >= 2_000_000:
        return "heavy"
    if projected >= 500_000:
        return "busy"
    return "ok"


def bubble(snapshot: UsageSnapshot, projected: float, sample_ok: bool) -> str:
    """桌宠气泡：一句话。没有数据时如实说没有，不编。"""
    if not snapshot.has_data:
        return "用量小本本还没收到 Agent 的记录哦（UNKNOWN）。"
    if snapshot.errors:
        return "这次没读到完整用量（UNKNOWN），旧小本本不能当成最新结果哦。"
    if snapshot.window.calls == 0:
        return (
            f"近 {snapshot.window_hours:g} 小时没动过。"
            f"今天累计 {format_tokens(snapshot.today.tokens)} token。"
        )

    head = (
        f"近 {snapshot.window_hours:g} 小时用了 "
        f"{format_tokens(snapshot.window.tokens)} token"
    )
    if sample_ok:
        tail = f"，照这个速度大概到 {format_tokens(projected)}。"
    else:
        tail = "，记录还少，我先不乱猜啦。"
    return f"{head}{tail}今天累计 {format_tokens(snapshot.today.tokens)} token。"


def _totals_lines(title: str, totals: UsageTotals, indent: str = "  ") -> list[str]:
    if totals.tokens == 0 and totals.calls == 0:
        return [f"{indent}{title}: 无"]
    lines = [
        f"{indent}{title}: {format_tokens(totals.tokens)} token"
        f" / {format_usd(totals.cost_usd)} / {totals.calls} 次调用"
    ]
    if totals.tokens > 0:
        parts = []
        if totals.input_tokens:
            parts.append(f"输入 {format_tokens(totals.input_tokens)}")
        if totals.output_tokens:
            parts.append(f"输出 {format_tokens(totals.output_tokens)}")
        if totals.cache_write_tokens:
            parts.append(f"缓存写 {format_tokens(totals.cache_write_tokens)}")
        if totals.cache_read_tokens:
            parts.append(f"缓存读 {format_tokens(totals.cache_read_tokens)}")
        if parts:
            lines.append(f"{indent}  " + " · ".join(parts))
    return lines


def sparkline(values: list[float]) -> str:
    """24 小时柱状条。纯 ASCII，任何终端都画得出来。"""
    blocks = "▁▂▃▄▅▆▇█"
    if not values:
        return ""
    peak = max(values)
    if peak <= 0:
        return blocks[0] * len(values)
    out = []
    for value in values:
        index = int(value / peak * (len(blocks) - 1))
        out.append(blocks[max(0, min(len(blocks) - 1, index))])
    return "".join(out)


def proportional_bar(value: float, peak: float, width: int = 12) -> str:
    """按峰值归一的比例条。峰值当天占满 width 格，其余按比例。"""
    if peak <= 0 or value <= 0:
        return ""
    filled = max(1, round(float(value) / peak * width))
    return "█" * min(width, filled)


def report(
    snapshot: UsageSnapshot,
    projected: float,
    remaining: float,
    sample_ok: bool,
    *,
    days: int = 7,
) -> str:
    """完整报告。CLI 与详情面板共用。"""
    lines: list[str] = []
    lines.append(f"数据源：{', '.join(snapshot.sources) or '无可用数据源'}")
    lines.append(f"观测状态：{snapshot.status}")
    lines.extend(f"读取失败：{error}" for error in snapshot.errors)
    lines.append("")

    lines.extend(_totals_lines(f"近 {snapshot.window_hours:g} 小时（滚动窗口）", snapshot.window))
    if snapshot.window.calls > 0:
        if sample_ok:
            lines.append(
                f"    外推：按当前速率 5 小时约 {format_tokens(projected)} token"
                f"（最早一条记录还有 {remaining / 60:.0f} 分钟滚出窗口）"
            )
        else:
            lines.append("    外推：样本不足（窗口内有效观测 < 10 分钟），暂不推算")
    lines.append("")

    lines.extend(_totals_lines("今天", snapshot.today))
    if any(snapshot.hourly_tokens_today):
        lines.append(f"    今日分时 token：{sparkline([float(v) for v in snapshot.hourly_tokens_today])}")
        lines.append("                   0时                          23时")
    lines.append("")

    lines.extend(_totals_lines("本机留存历史（终生）", snapshot.lifetime))
    lines.append("")

    trend = recent_days(snapshot, days)
    if any(row["tokens"] for _, row in trend):
        peak = max(float(row.get("tokens", 0)) for _, row in trend)
        lines.append(f"最近 {days} 天：")
        for day, row in trend:
            tokens = int(row.get("tokens", 0))
            cost = float(row.get("cost", 0.0))
            lines.append(
                f"    {day}  {format_tokens(tokens):>8}  {format_usd(cost):>9}  "
                f"{proportional_bar(tokens, peak)}"
            )
        lines.append("")

    lines.append(f"计价来源：{snapshot.pricing_source}")
    if snapshot.estimated_models:
        shown = ", ".join(snapshot.estimated_models[:6])
        more = f" 等 {len(snapshot.estimated_models)} 个" if len(snapshot.estimated_models) > 6 else ""
        lines.append(f"    按家族估算（金额为量级参考）：{shown}{more}")
    if snapshot.unknown_models:
        shown = ", ".join(snapshot.unknown_models[:6])
        more = f" 等 {len(snapshot.unknown_models)} 个" if len(snapshot.unknown_models) > 6 else ""
        lines.append(f"    未识别模型（已按默认单价兜底）：{shown}{more}")
    lines.append("")
    lines.append("口径说明：以上是本机日志的 token 台账，**不等于厂商账单**。")
    lines.append("    历史用量不是厂商账号余额，也不能推导剩余配额。")
    lines.append("    仅统计本机留存日志覆盖的范围；日志被清理的部分不在此列。")
    return "\n".join(lines)
