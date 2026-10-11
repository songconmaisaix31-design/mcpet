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
import os
import time
import json
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


def _smoke_environment(tmp_path):
    env = os.environ.copy()
    env["MCPET_DATA_DIR"] = str(tmp_path)
    env["QT_QPA_PLATFORM"] = "windows" if sys.platform == "win32" else "offscreen"
    env["MCD_MCP_TOKEN"] = "mock-token-only"
    env["STEPFUN_API_KEY"] = "mock-key-only"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


@pytest.mark.parametrize("mode", ["normal", "active", "external-quit"])
def test_real_qt_start_and_safe_exit_subprocess(tmp_path, mode):
    proc = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--qt-smoke", mode],
                          cwd=MAIN_SRC.parents[1], env=_smoke_environment(tmp_path),
                          capture_output=True, text=True, encoding="utf-8", timeout=20)
    assert proc.returncode == 0, proc.stderr
    assert "QThread: Destroyed" not in proc.stderr
    result = json.loads(proc.stdout.strip().splitlines()[-1])
    assert result["qt_platform"] == ("windows" if sys.platform == "win32" else "offscreen")
    assert result["thread_running"] is False
    if mode != "normal":
        assert result["mcp_init_count"] == 1
        assert result["heartbeat_ticks"] >= 10
        assert result["max_tick_gap_ms"] < 150


def test_duplicate_launch_does_not_initialize_or_scan(tmp_path):
    env = _smoke_environment(tmp_path)
    command = [sys.executable, str(Path(__file__).resolve()), "--qt-smoke"]
    primary = subprocess.Popen(command + ["hold"], cwd=MAIN_SRC.parents[1], env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    try:
        deadline = time.monotonic() + 10
        while not (tmp_path / "ready").exists() and primary.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert (tmp_path / "ready").exists()
        secondary = subprocess.run(command + ["secondary"], cwd=MAIN_SRC.parents[1], env=env,
                                   capture_output=True, text=True, encoding="utf-8", timeout=10)
        assert secondary.returncode == 0, secondary.stderr
        result = json.loads(secondary.stdout.strip().splitlines()[-1])
        assert result == {"secondary": True, "has_tasks": False, "has_window": False}
        stdout, stderr = primary.communicate(timeout=10)
        assert primary.returncode == 0, stderr
        assert "QThread: Destroyed" not in stderr
        assert not (tmp_path / "app.lock").exists()
    finally:
        if primary.poll() is None:
            primary.terminate()
            primary.wait(timeout=5)


def qt_smoke(mode):
    """可复现 Windows Qt 实测命令；联网只用 MockTransport，绝不读根 .env。"""
    sys.path.insert(0, str(MAIN_SRC.parents[1]))
    import threading
    import httpx
    from PySide6.QtCore import QObject, QTimer, Signal
    from PySide6.QtWidgets import QApplication
    from src import config, main
    from test_app_actions import AccountMonitorOfflineStub

    class MonitorStub(QObject):
        progress_ready = Signal(object)
        usage_ready = Signal(object)
        failed = Signal(str)
        task_completed = Signal(object)
        def start(self): pass
        def stop(self): pass
        def refresh_progress(self): pass
        def refresh_usage(self): pass

    config.load_env = lambda: None
    entered = threading.Event()
    initializations = []
    class MockClient(main.McdMcpClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._http.close()
            self._http = httpx.Client(transport=httpx.MockTransport(self.handle))
        def handle(self, request):
            body = json.loads(request.content)
            if body["method"] == "initialize":
                initializations.append(1)
                entered.set()
                time.sleep(0.376)  # 已知卡顿大小的注入延迟，不冒充真实网络测量。
            if "id" not in body:
                return httpx.Response(202)
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {}})

    main.McdMcpClient = MockClient
    monster = main.MonsterApp([], monitor_factory=MonitorStub,
                              account_monitor_factory=AccountMonitorOfflineStub)
    if monster.secondary:
        result = monster.app.exec()
        print(json.dumps({"secondary": True, "has_tasks": hasattr(monster, "tasks"),
                          "has_window": hasattr(monster, "window")}), flush=True)
        return result
    ticks = []
    heartbeat = QTimer()
    heartbeat.setInterval(10)
    heartbeat.timeout.connect(lambda: ticks.append(time.monotonic()))
    heartbeat.start()
    if mode in {"active", "external-quit"}:
        monster.run_mcp("smoke", lambda b: "initialized", lambda r: None)
        poll = QTimer()
        poll.setInterval(5)
        def close_when_entered():
            if entered.is_set():
                poll.stop()
                if mode == "external-quit":
                    monster.app.quit()
                else:
                    monster.quit()
        poll.timeout.connect(close_when_entered)
        poll.start()
    else:
        if mode == "hold":
            (config.data_dir() / "ready").write_text("ready", encoding="utf-8")
        QTimer.singleShot(2200 if mode == "hold" else 180, monster.quit)
    QTimer.singleShot(10000, monster.quit)
    result = monster.app.exec()
    heartbeat.stop()
    gaps = [1000 * (b - a) for a, b in zip(ticks, ticks[1:])]
    print(json.dumps({"qt_platform": QApplication.platformName(), "thread_running": monster.tasks.thread.isRunning(),
                      "mcp_init_count": len(initializations), "heartbeat_ticks": len(ticks),
                      "max_tick_gap_ms": round(max(gaps, default=0), 2)}), flush=True)
    return result


if __name__ == "__main__" and len(sys.argv) > 2 and sys.argv[1] == "--qt-smoke":
    raise SystemExit(qt_smoke(sys.argv[2]))
