"""Human-facing receipts; protocol status values remain untouched."""
STATUS_LABELS = {
    "placed": "订单创建好了，付款还要你亲自确认哦",
    "cancelled": "官方已确认撤单",
    "needs_confirmation": "请先核对，再确认这一步",
    "delivery_unknown": "提交结果尚未核实，先别重复点啦，请到官方 App 核对",
    "expired": "报价已经过期，请重新预览确认",
    "dry_run_skipped": "这是演示，实际没有下单",
    "error": "这一步没办成，看看下面的原因吧",
}


def order_receipt(result, provider):
    status = result.get("status", "unknown")
    lines = [f"{provider}小回执", STATUS_LABELS.get(status, f"订单状态待核实（{status}）")]
    if result.get("summary"):
        lines.append(str(result["summary"]))
    order = result.get("order_id") or result.get("order_no")
    if order:
        lines.append(f"订单号：{order}")
    for key in ("reason", "warning"):
        if result.get(key):
            lines.append(str(result[key]))
    if status == "placed" and result.get("pay_url"):
        lines.append("付款入口收在右键菜单里啦。")
    return "\n".join(lines)
