"""精灵图加载与切片测试。需要真实图集文件（assets/longniang）。"""

from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication

from src import config
from src.pet.spritesheet import SpriteLoadError, SpriteSheet

ASSETS = config.PROJECT_ROOT / "assets" / "longniang"


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QGuiApplication.instance() or QGuiApplication([])
    return app


@pytest.mark.skipif(not (ASSETS / "spritesheet.webp").exists(), reason="缺少占位图集")
def test_load_reads_atlas_geometry():
    sheet = SpriteSheet.load(
        ASSETS / "spritesheet.webp",
        pet_json=ASSETS / "pet.json",
        rows_json=ASSETS / "sprite-rows.json",
    )
    # longniang 规格：8 列 × 11 行，单元 192×208
    assert sheet.columns == 8
    assert sheet.rows == 11
    assert sheet.cell_width == 192
    assert sheet.cell_height == 208


@pytest.mark.skipif(not (ASSETS / "spritesheet.webp").exists(), reason="缺少占位图集")
def test_frames_are_sliced_with_alpha():
    sheet = SpriteSheet.load(
        ASSETS / "spritesheet.webp",
        pet_json=ASSETS / "pet.json",
        rows_json=ASSETS / "sprite-rows.json",
    )
    assert sheet.has_alpha, "桌宠素材必须带透明通道"
    frames = sheet.frames("idle")
    assert len(frames) == 6
    assert all(not frame.isNull() for frame in frames)
    assert frames[0].width() == 192


@pytest.mark.skipif(not (ASSETS / "spritesheet.webp").exists(), reason="缺少占位图集")
def test_unknown_state_falls_back_to_idle_row():
    sheet = SpriteSheet.load(
        ASSETS / "spritesheet.webp",
        pet_json=ASSETS / "pet.json",
        rows_json=ASSETS / "sprite-rows.json",
    )
    assert sheet.row_for("eating") == sheet.row_for("idle")  # 占位图集没有吃饭动作


def test_missing_file_raises():
    with pytest.raises(SpriteLoadError):
        SpriteSheet.load(Path("assets/does-not-exist.webp"))


def test_row_alias_covers_all_target_states():
    from src.pet import states

    for state in states.STATE_PRIORITY:
        assert state in states.LONGNIANG_ROW_ALIAS
