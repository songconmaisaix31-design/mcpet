"""本地冒烟检查：导入全部模块 + 加载图集 + 打印状态映射。不联网。"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MCPET_DATA_DIR", str(Path(__file__).resolve().parents[1] / ".tmp-smoke-data"))

from src import config  # noqa: E402
from src.pet import states  # noqa: E402
from src.pet.spritesheet import SpriteSheet  # noqa: E402


def main() -> int:
    import src.cli  # noqa: F401
    import src.main  # noqa: F401
    print("[1/3] 全部模块导入成功")

    base = config.PROJECT_ROOT / "assets" / "longniang"
    if not (base / "spritesheet.webp").exists():
        print("[2/3] 没有占位图集，跳过")
        return 0
    sheet = SpriteSheet.load(
        base / "spritesheet.webp",
        pet_json=base / "pet.json",
        rows_json=base / "sprite-rows.json",
    )
    print(
        f"[2/3] 图集加载成功：{sheet.columns}x{sheet.rows}，"
        f"单元 {sheet.cell_width}x{sheet.cell_height}，透明通道 {sheet.has_alpha}"
    )

    print("[3/3] 状态 → 行号映射：")
    for state in sorted(states.STATE_PRIORITY, key=lambda s: -states.STATE_PRIORITY[s]):
        row = sheet.row_for(state)
        print(f"   {state:<10} 优先级 {states.STATE_PRIORITY[state]}  行 {row}  帧 {sheet.frame_count(state)}")

    issues = getattr(sheet, "validation_issues", [])
    if issues:
        print("\n图集校验提示：")
        for issue in issues:
            print("  -", issue)
    else:
        print("\n图集校验通过，无提示。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
