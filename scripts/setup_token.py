"""一条命令完成 Token 配置 + 全链路真实验证。

用法：在 https://open.mcd.cn/mcp 登录激活后复制 Token，然后直接跑

    python scripts/setup_token.py

它会先读剪贴板；读不到再让你粘贴。写进 .env 之后立刻真实调用一遍全部工具，
把结果（已脱敏）写成 docs/verification-report.md —— 那份报告可以直接贴进
README 和 MCP_INTEGRATION.md，把「待验证」翻成「已验证」。

非交互模式（Token 已在 .env / 环境变量里时）：

    python scripts/setup_token.py --reuse        # 复用已有 Token，只跑验证
    python scripts/setup_token.py --token <TOKEN>  # 直接指定 Token
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src import config  # noqa: E402

ENV_PATH = ROOT / ".env"
REPORT_PATH = ROOT / "docs" / "verification-report.md"

# 验证命令：(说明, 参数, 是否必须有 MCP)
CHECKS: list[tuple[str, list[str], bool]] = [
    ("工具清单与参数名核对", ["tools"], True),
    ("服务端时间", ["now"], True),
    ("营养数据（含自定义表格解析）", ["nutrition", "--keyword", "巨无霸", "--limit", "3"], True),
    ("领券汇报（会真实领券）", ["coupons"], True),
    ("今天最划算的一单（真实比价）", ["deal"], True),
    ("下单链路（演练：不落单）", ["order"], True),
    ("Skill：让模型自己调工具", ["ask", "今天最划算的是哪个？"], True),
]


def read_clipboard() -> str:
    try:
        from PySide6.QtGui import QGuiApplication

        app = QGuiApplication.instance() or QGuiApplication([])
        return (app.clipboard().text() or "").strip()
    except Exception:
        return ""


def write_env(token: str) -> None:
    """写 .env，保留已有的其它键（比如 STEPFUN_API_KEY）。"""
    lines: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key, _, value = line.partition("=")
                lines[key.strip()] = value.strip()
    lines["MCD_MCP_TOKEN"] = token
    ENV_PATH.write_text(
        "\n".join(f"{key}={value}" for key, value in lines.items()) + "\n", encoding="utf-8"
    )
    os.environ["MCD_MCP_TOKEN"] = token


def run_check(args: list[str], timeout: int = 180) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "src.cli", *args],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 124, f"超时（{timeout}s）"
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, output.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="麦麦小怪兽 Token 配置与全链路验证")
    parser.add_argument("--reuse", action="store_true", help="复用已有 .env / 环境变量里的 Token，只跑验证")
    parser.add_argument("--token", default=None, help="直接指定 Token")
    args = parser.parse_args()

    print("=" * 60)
    print("麦麦小怪兽 · Token 配置与全链路验证")
    print("=" * 60)

    config.load_env()
    token = (args.token or "").strip()

    if not token and args.reuse:
        existing = config.mcp_token()
        if not existing:
            print("--reuse 指定了，但 .env / 环境变量里没有可用的 MCD_MCP_TOKEN。")
            return 2
        print(f"\n复用已有 Token（{existing[:6]}…{existing[-4:]}），跳过录入。")
        token = existing

    if not token:
        candidate = read_clipboard()
        if candidate and not config._is_placeholder(candidate) and len(candidate) > 8:
            print(f"\n剪贴板里读到 Token（{candidate[:6]}…{candidate[-4:]}），直接用？")
            use = input("回车确认，或输入 n 改为手动粘贴：").strip().lower()
            if use != "n":
                token = candidate
        if not token:
            token = input("\n请粘贴 MCP Token：").strip()

    if not token or config._is_placeholder(token):
        print("没有拿到有效 Token，退出。")
        return 2

    write_env(token)
    print(f"\n已写入 {ENV_PATH}（该文件已被 .gitignore 排除，不会入库）\n")

    config.load_env()
    results: list[tuple[str, int, str]] = []
    for label, args, _ in CHECKS:
        print(f"[验证] {label} …")
        started = time.time()
        code, output = run_check(args)
        elapsed = time.time() - started
        status = "通过" if code == 0 else "失败"
        print(f"       {status}（{elapsed:.1f}s）")
        results.append((label, code, output))

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    safe_token = config.mcp_token() or ""
    lines = [
        "# 麦当劳 MCP 真实调用验证报告",
        "",
        f"- 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- MCP Server：`{config.mcp_url()}`",
        f"- 大模型：`{config.stepfun_model()}`（阶跃星辰）",
        "",
        "以下输出均已过脱敏（Token / 手机号 / 邮箱）。地址类信息需人工核对后再公开。",
        "",
    ]
    for label, code, output in results:
        lines.append(f"## {label}")
        lines.append("")
        lines.append(f"退出码：`{code}`（{'通过' if code == 0 else '失败'}）")
        lines.append("")
        lines.append("```")
        lines.append(config.redact(output or "(无输出)", safe_token))
        lines.append("```")
        lines.append("")

    passed = sum(1 for _, code, _ in results if code == 0)
    lines.insert(4, f"- 结果：**{passed}/{len(results)} 项通过**")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")

    print("\n" + "=" * 60)
    print(f"结果：{passed}/{len(results)} 项通过")
    print(f"报告已写入：{REPORT_PATH}")
    print("=" * 60)
    if passed < len(results):
        print("\n有失败项。常见原因：")
        print("  - 401：Token 无效或过期，重新去控制台激活")
        print("  - 参数名不匹配：按报告里 tools 一节的实际字段名改 src/mcd_mcp/tools.py 的 ARG_KEYS")
        print("  - 价格单位不对：改 src/mcd_mcp/guards.py 的 to_cents()")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
