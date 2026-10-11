"""启动顺序的回归测试。

背景：`QSystemTrayIcon.isSystemTrayAvailable()` 如果在 QApplication 存在之前调用，
在 Windows 上**不是**返回 False，而是直接 access violation（SIGSEGV）。整个程序会
在 `main()` 的第一行就崩掉，而且崩在 C 层——Python 侧连异常都捕获不到，
只会看到 `Segmentation fault`，极难定位。

所以这里用两层测试把它钉死：

1. 源码级断言：`main()` 里不许再出现这个调用；`MonsterApp.__init__` 里它必须排在
   `QApplication(...)` 之后。谁把检查挪回 `main()`，测试立刻变红。
2. 行为级断言：在子进程里复现「无 QApplication 就调用」会崩，证明上面那条约束
   不是拍脑袋来的，而是这个 Qt 版本的真实行为。
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

MAIN_SRC = Path(__file__).resolve().parents[1] / "src" / "main.py"
TREE = ast.parse(MAIN_SRC.read_text(encoding="utf-8"))

TRAY_CALL = "isSystemTrayAvailable"
QAPP_CALL = "QApplication"


def _attr_name(call: ast.Call) -> str | None:
    """取出被调用者的名字：`a.b()` 取 `b`，`c()` 取 `c`。"""
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _calls(node: ast.AST, name: str) -> list[ast.Call]:
    return [
        call
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and _attr_name(call) == name
    ]


def _find_function(name: str, cls: str | None = None) -> ast.FunctionDef | None:
    if cls is None:
        for node in TREE.body:
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return node
        return None
    for node in TREE.body:
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for member in node.body:
                if isinstance(member, ast.FunctionDef) and member.name == name:
                    return member
    return None


def test_main_function_exists():
    assert _find_function("main") is not None


def test_tray_check_is_not_called_in_main():
    """`main()` 里不能出现托盘可用性检查——那时 QApplication 还没创建。"""
    main_fn = _find_function("main")
    assert main_fn is not None
    offenders = _calls(main_fn, TRAY_CALL)
    assert not offenders, (
        f"src/main.py 的 main() 第 {[c.lineno for c in offenders]} 行调用了 "
        f"{TRAY_CALL}()，但那时 QApplication 还不存在，会直接段错误。"
        "请把检查放进 MonsterApp.__init__ 里 QApplication 之后。"
    )


def test_tray_check_runs_after_qapplication_is_created():
    init_fn = _find_function("__init__", cls="MonsterApp")
    assert init_fn is not None, "没找到 MonsterApp.__init__"

    qapp_lines = [call.lineno for call in _calls(init_fn, QAPP_CALL)]
    tray_lines = [call.lineno for call in _calls(init_fn, TRAY_CALL)]

    assert qapp_lines, "MonsterApp.__init__ 应当创建 QApplication"
    assert tray_lines, "MonsterApp.__init__ 应当做托盘可用性检查"
    assert min(tray_lines) > min(qapp_lines), (
        f"托盘检查在第 {min(tray_lines)} 行，QApplication 在第 {min(qapp_lines)} 行——"
        "顺序反了，必须先创建 QApplication。"
    )


@pytest.mark.skipif(sys.platform != "win32", reason="该崩溃只在 Windows 上复现")
def test_calling_tray_check_without_qapplication_crashes():
    """把这个 Qt 行为本身钉成测试，证明上面两条约束的依据。

    子进程会以非零码退出（访问冲突），这正是我们当初看到的那个段错误。
    """
    code = (
        "from PySide6.QtWidgets import QSystemTrayIcon;"
        "QSystemTrayIcon.isSystemTrayAvailable()"
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:  # pragma: no cover - 环境限制
        pytest.skip(f"无法派生测试子进程：{exc}")

    assert proc.returncode != 0, (
        "预期「无 QApplication 时调用 isSystemTrayAvailable」会崩溃，"
        "但它正常返回了——说明该 Qt 版本行为已变，请重新评估 src/main.py 的启动顺序。"
    )
