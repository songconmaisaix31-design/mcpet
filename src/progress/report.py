"""进度汇报文案。

同样分两档：`bubble()` 一句话给桌宠，`report()` 多行给 CLI 与详情面板。

措辞纪律：进度是**从日志推**的，不是 Agent 主动推的。所以报告里必须说清
「数据截止到多久之前」，否则用户会以为它知道当下正在发生什么。
"""

from __future__ import annotations

from .tracker import ProgressSnapshot, SessionProgress

# Agent 侧状态 -> 桌宠状态。未知状态统一落到 working/idle，不硬编。
STATE_TO_PET: dict[str, str] = {
    "working": "working",
    "thinking": "thinking",
    "idle": "idle",
    "waiting": "waiting",
    "needsinput": "waiting",
    "error": "error",
    "failed": "error",
    "done": "happy",
    "complete": "happy",
    "sleeping": "sleeping",
}

# 状态的中文短标签，给 CLI 表格用
STATE_LABEL: dict[str, str] = {
    "working": "干活中",
    "thinking": "思考中",
    "idle": "空闲",
    "waiting": "等你",
    "needsinput": "等你",
    "error": "报错",
    "failed": "失败",
    "done": "完成",
    "complete": "完成",
    "sleeping": "休眠",
}


def pet_state_for(agent_state: str) -> str:
    return STATE_TO_PET.get((agent_state or "").strip().lower(), "idle")


def state_label(agent_state: str) -> str:
    key = (agent_state or "").strip().lower()
    return STATE_LABEL.get(key, key or "未知")


def human_age(seconds: float) -> str:
    if seconds == float("inf"):
        return "未知"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds} 秒前"
    if seconds < 3600:
        return f"{seconds // 60} 分钟前"
    if seconds < 86400:
        return f"{seconds // 3600} 小时前"
    return f"{seconds // 86400} 天前"


def context_bar(percent: int | None, width: int = 10) -> str:
    if percent is None:
        return "—"
    filled = max(0, min(width, round(percent / 100 * width)))
    return "█" * filled + "░" * (width - filled)


def bubble(snapshot: ProgressSnapshot) -> str:
    """桌宠气泡：一句话说清「谁在跑、跑到哪」。"""
    if not snapshot.has_data:
        return "没读到任何 Agent 的会话。"

    active = snapshot.active
    if not active:
        newest = snapshot.sessions[0]
        return (
            f"{len(snapshot.sessions)} 个会话都停了，"
            f"最近一个 {human_age(newest.age_seconds)}。"
        )

    running = [s for s in active if pet_state_for(s.record.state) == "working"]
    parts = [f"{len(active)} 个会话活跃"]
    if running:
        parts.append(f"{len(running)} 个在干活")
    if snapshot.background_tasks:
        parts.append(f"{snapshot.background_tasks} 个后台任务")

    # 挑上下文占用最高的那个报，它是最可能卡住的
    hottest = max(
        (s for s in active if s.context_percent is not None),
        key=lambda s: s.context_percent or 0,
        default=None,
    )
    if hottest and (hottest.context_percent or 0) >= 50:
        parts.append(f"{hottest.label} 上下文已用 {hottest.context_percent}%")

    return "，".join(parts) + "。"


def report(snapshot: ProgressSnapshot, *, show_stale: bool = True) -> str:
    lines: list[str] = []
    lines.append(f"数据源：{', '.join(snapshot.sources) or '无可用数据源'}")
    if snapshot.process_sampling:
        live = snapshot.live_processes
        detail = "、".join(f"{k} {v}" for k, v in live.items()) or "未发现"
        lines.append(f"进程采样：已开启（{detail}）")
    else:
        lines.append("进程采样：未开启（设 MAIMAI_WATCH_PROCESSES=1 可开启，需 psutil）")
    lines.append("")

    active = snapshot.active
    stale = snapshot.stale

    lines.append(f"活跃会话（{snapshot.stale_minutes} 分钟内更新）：{len(active)} 个")
    if active:
        for item in active:
            lines.append(_session_line(item))
    else:
        lines.append("    无")
    lines.append("")

    if show_stale and stale:
        lines.append(f"已停下的会话：{len(stale)} 个")
        for item in stale[:5]:
            lines.append(_session_line(item))
        if len(stale) > 5:
            lines.append(f"    …另有 {len(stale) - 5} 个")
        lines.append("")

    lines.append("说明：进度由各 Agent 落盘的日志推导，天生有滞后——")
    lines.append("    滞后取决于该 Agent 多久写一次盘，不是实时推送。")
    return "\n".join(lines)


def _session_line(item: SessionProgress) -> str:
    record = item.record
    age = human_age(item.age_seconds)
    state = state_label(record.state)
    ctx = context_bar(record.context_percent)
    pct = f"{record.context_percent:>3}%" if record.context_percent is not None else "  —"
    extra = ""
    if record.background_tasks:
        extra += f" 后台×{record.background_tasks}"
    if record.model:
        extra += f" {record.model}"
    return (
        f"    [{record.source:<7}] {item.label[:22]:<22} {state:<4} "
        f"上下文 {ctx} {pct}  {age}{extra}"
    )
