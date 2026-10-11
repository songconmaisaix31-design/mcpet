"""桌宠渲染流畅度基准测试。

用法：
    python scripts/bench_render.py            # 默认测 5 秒
    python scripts/bench_render.py 10         # 测 10 秒

为什么要专门测「抖动」而不只看平均帧率：
    平均帧率会把「偶尔卡一下」平均掉。人眼对**帧间隔的突变**远比对齐整的
    低帧率敏感——稳定 12fps 看起来是「慢」，忽快忽慢的 20fps 看起来才是「卡」。
    所以这里同时报告间隔标准差与「卡顿帧」（间隔超过目标 1.5 倍/2 倍的次数）。

注意：必须用真实平台（windows），offscreen 平台不会真正合成窗口，
      测出来的重绘成本是假的。
"""

from __future__ import annotations

import statistics
import os
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import QEvent, QPoint, QPointF, QTimer, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from src.pet.spritesheet import SpriteSheet  # noqa: E402
from src.pet.window import PetWindow  # noqa: E402


def _verdict(fps: float, jank_ratio: float, target_fps: float) -> str:
    if jank_ratio > 0.02 or fps < target_fps * 0.6:
        return "卡"
    if jank_ratio > 0.005 or fps < target_fps * 0.9:
        return "一般"
    return "流畅"


def measure_idle(app: QApplication, window: PetWindow, seconds: float) -> dict:
    """测空闲动画：帧间隔、抖动、卡顿帧。"""
    stamps: list[float] = []
    original = window._advance

    def tap() -> None:
        original()
        stamps.append(time.perf_counter())

    window._advance = tap  # type: ignore[method-assign]

    QTimer.singleShot(int(seconds * 1000), app.quit)
    app.exec()
    window._advance = original  # type: ignore[method-assign]

    gaps = [(stamps[i + 1] - stamps[i]) * 1000 for i in range(len(stamps) - 1)]
    if not gaps:
        return {"frames": 0}

    target = getattr(window, "_frame_delay_ms", None) or (
        window.sheet.frame_delay_ms if window.sheet else 80
    )
    jank = sum(1 for g in gaps if g > target * 1.5)
    return {
        "frames": len(stamps),
        "target_ms": target,
        "mean_ms": statistics.mean(gaps),
        "median_ms": statistics.median(gaps),
        "min_ms": min(gaps),
        "max_ms": max(gaps),
        "stdev_ms": statistics.pstdev(gaps),
        "jank": jank,
        "jank_ratio": jank / len(gaps),
        "fps": len(stamps) / seconds,
    }


def measure_drag(app: QApplication, window: PetWindow, events: int = 120) -> dict:
    """Send actual Qt mouse gestures with small reversals through the event loop."""
    seen: set[int] = set()
    timings: list[float] = []
    state_changes: list[str] = []
    clicks: list[bool] = []
    original = window._advance

    def tap() -> None:
        original()
        if window._drag_active:
            seen.add(window._index)

    window._advance = tap  # type: ignore[method-assign]

    def send(kind, point, button, buttons):
        event = QMouseEvent(kind, QPointF(window.mapFromGlobal(point)), QPointF(point),
                            button, buttons, Qt.NoModifier)
        app.sendEvent(window, event)

    window.clicked.connect(lambda: clicks.append(True))
    window.set_activity("idle")
    window.move(window.screen().availableGeometry().topLeft() + QPoint(100, 100))
    origin = window.pos() + QPoint(50, 50)
    send(QEvent.MouseButtonPress, origin, Qt.LeftButton, Qt.LeftButton)
    points = [origin + QPoint(20 + (i // 3) * 3 + (0, -1, 0)[i % 3], 0) for i in range(events)]
    count = [0]
    timer = QTimer()
    timer.setTimerType(Qt.PreciseTimer)
    timer.setInterval(8)

    def move():
        start = time.perf_counter()
        point = points[count[0]]
        send(QEvent.MouseMove, point, Qt.NoButton, Qt.LeftButton)
        # Simulated background observation must preserve the drag and its phase.
        window.set_activity("idle", None, "陪伴")
        if not state_changes or window.machine.state != state_changes[-1]:
            state_changes.append(window.machine.state)
        timings.append((time.perf_counter() - start) * 1000)
        count[0] += 1
        if count[0] == events:
            timer.stop()
            send(QEvent.MouseButtonRelease, point, Qt.LeftButton, Qt.NoButton)
            QTimer.singleShot(app.doubleClickInterval() + 50, app.quit)

    timer.timeout.connect(move)
    timer.start()
    app.exec()

    window._advance = original  # type: ignore[method-assign]
    return {
        "events": events,
        "total_ms": sum(timings),
        "per_event_ms": statistics.mean(timings),
        "distinct_frames_shown": len(seen),
        "frame_count": window.sheet.frame_count("run-right"),
        "state_changes": state_changes,
        "clicks_after_drag": len(clicks),
    }


def main() -> int:
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0
    if seconds < 1:
        raise ValueError("基准至少运行 1 秒")
    if "MCPET_DATA_DIR" not in os.environ:
        os.environ["MCPET_DATA_DIR"] = tempfile.mkdtemp(prefix="mcpet-bench-")

    app = QApplication([])
    if app.platformName() != "windows":
        print(f"需要真实 windows 平台，实际为 {app.platformName()}")
        return 2
    base = PROJECT_ROOT / "assets" / "longniang"
    sheet = SpriteSheet.load(
        base / "spritesheet.webp",
        pet_json=base / "pet.json",
        rows_json=base / "sprite-rows.json",
    )

    window = PetWindow(sheet)
    window.set_roaming(False)
    window.set_resting(False)
    window.show()
    app.processEvents()

    target_fps = 1000 / window._frame_delay_ms
    print("=" * 58)
    print("McPet 渲染流畅度基准")
    print("=" * 58)
    print(f"图集单元      : {sheet.cell_width}x{sheet.cell_height}")
    print(f"目标帧间隔    : {window._frame_delay_ms} ms  ({target_fps:.1f} fps)")
    print(f"计时器类型    : {window._anim.timerType()}")
    print(f"帧缓存条目    : {len(getattr(window, '_cache', {}))}")
    print(f"Qt 平台 / DPR : {app.platformName()} / {window.devicePixelRatioF()}")
    for state in sheet.row_of:
        bounds = sheet.anchor_bounds(state)
        if any(b is None for b in bounds):
            print(f"[atlas {state}] 存在空白帧")
            continue
        centers = [(b[0] + b[2]) / 2 for b in bounds]
        bottoms = [b[3] for b in bounds]
        print(f"[atlas {state}] 横中心范围 {max(centers)-min(centers):.1f}px / 底部范围 {max(bottoms)-min(bottoms)}px")
    # Audit cost is excluded from the timed event loop.
    window._next_frame = time.monotonic() + window._frame_delay_ms / 1000
    window._anim.start(window._frame_delay_ms)

    idle = measure_idle(app, window, seconds)
    print("-" * 58)
    print(f"[空闲动画] {seconds:.0f} 秒")
    print(f"  帧数        : {idle['frames']}")
    print(f"  实测 fps    : {idle['fps']:.1f}   (达成率 {idle['fps']/target_fps*100:.0f}%)")
    print(f"  间隔 平均   : {idle['mean_ms']:.1f} ms  (目标 {idle['target_ms']} ms)")
    print(f"  间隔 中位   : {idle['median_ms']:.1f} ms")
    print(f"  间隔 极值   : {idle['min_ms']:.1f} ~ {idle['max_ms']:.1f} ms")
    print(f"  抖动 标准差 : {idle['stdev_ms']:.1f} ms")
    print(f"  卡顿帧      : {idle['jank']} 次 ({idle['jank_ratio']*100:.1f}%)")
    print(f"  判定        : {_verdict(idle['fps'], idle['jank_ratio'], target_fps)}")

    drag = measure_drag(app, window)
    print("-" * 58)
    print(f"[真实 Qt 拖拽事件] {drag['events']} 次 mouseMove + 1px 反向 + 后台活动更新")
    print(f"  每次耗时    : {drag['per_event_ms']:.2f} ms")
    print(f"  动画推进帧  : {drag['distinct_frames_shown']} / {drag['frame_count']} 帧出现过")
    print(f"  状态切换    : {drag['state_changes']}")
    print(f"  拖拽后单击  : {drag['clicks_after_drag']}")
    if drag["frame_count"] and drag["distinct_frames_shown"] <= 1:
        print("  ⚠️ 拖拽期间动画冻结（只显示了 1 帧）")
    print("=" * 58)

    passed = (idle.get("frames", 0) > 1 and idle["jank_ratio"] <= 0.02
              and idle["fps"] >= target_fps * 0.9
              and drag["distinct_frames_shown"] > 1
              and drag["state_changes"] == ["run-right"] and drag["clicks_after_drag"] == 0)
    window.close()
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
