"""Real bundled character assets, not network or generated fixtures."""
import pytest
from pathlib import Path
import json
from PySide6.QtGui import QImage, QPixmap, QTransform

from src.pet.characters import CHARACTER_IDS, character_name, load_character
from src.pet.spritesheet import SpriteLoadError, SpriteSheet
from src.pet.spritesheet import AnimationSheet


def test_shared_character_contract():
    assert CHARACTER_IDS == ("maimai", "deepseek")
    assert character_name("maimai") == "麦麦"
    assert character_name("deepseek") == "DeepSeek 娘"
    for identity in CHARACTER_IDS:
        sheet = load_character(identity)
        assert isinstance(sheet, SpriteSheet)
        assert sheet.has_alpha
        assert not sheet.frame("idle", 0).isNull()
    with pytest.raises(SpriteLoadError):
        load_character("unknown")


def test_every_real_deepseek_frame_has_alpha_content_and_fixed_canvas():
    sheet = load_character("deepseek")
    assert sheet.frame_delay_ms == 80
    assert sheet.meta["upstream_sha"] == "92662190cdd4dee05e38a5151584cc6254cd7a43"
    assert sheet.meta["fixed_crop"] == [111, 0, 366, 360]
    for state in sheet.meta["animations"]:
        bounds = sheet.anchor_bounds(state)
        assert len(bounds) == sheet.frame_count(state)
        assert all(bound is not None and 0 < bound[0] <= bound[2] < 191 and 0 < bound[1] <= bound[3] < 191 for bound in bounds)
        for frame in sheet.frames(state):
            image = frame.toImage().convertToFormat(QImage.Format_RGBA8888)
            assert image.size().width() == image.size().height() == 192
            assert image.pixelColor(0, 0).alpha() == 0
            assert max(bytes(image.constBits())[3::4]) > 240
    idle = sheet.anchor_bounds("idle")
    assert max(b[3] for b in idle) - min(b[3] for b in idle) <= 1
    happy = sheet.anchor_bounds("happy")
    assert max(b[3] for b in happy) - min(b[3] for b in happy) >= 15  # Preserve the real jump.
    assert len(sheet._atlases) <= 1


def test_direction_is_mirrored_with_same_timing_and_no_new_asset():
    sheet = load_character("deepseek")
    assert sheet.frame_count("run-left") == sheet.frame_count("run-right") == 126
    for index in (0, 23, 70, 125):
        left = sheet.frame("run-left", index).toImage()
        right = sheet.frame("run-right", index).toImage()
        assert right == left.transformed(QTransform().scale(-1, 1))
    for alias, original in (("progress", "working"), ("remind", "greet"), ("failed", "error")):
        assert sheet.row_for(alias) == sheet.row_for(original)
        assert sheet.frame(alias, 15).toImage() == sheet.frame(original, 15).toImage()
    assert sheet.frame("unknown", 0).toImage() == sheet.frame("idle", 0).toImage()


def test_missing_animation_fails_at_load_before_switch(tmp_path):
    root = Path(__file__).resolve().parents[1] / "assets/dsh-deepseek"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(SpriteLoadError):
        AnimationSheet(tmp_path)


def test_corrupt_maimai_metadata_reports_shared_error(tmp_path, monkeypatch):
    from src.pet import characters
    root = Path(__file__).resolve().parents[1] / "assets/longniang"
    import shutil
    directory = tmp_path / "longniang"
    directory.mkdir()
    shutil.copyfile(root / "spritesheet.webp", directory / "spritesheet.webp")
    (directory / "pet.json").write_text("broken", encoding="utf-8")
    monkeypatch.setattr(characters, "ASSETS", tmp_path)
    with pytest.raises(SpriteLoadError):
        load_character("maimai")


def test_maimai_stays_original_atlas():
    sheet = load_character("maimai")
    assert (sheet.image.width(), sheet.image.height()) == (1536, 2288)
    assert (sheet.cell_width, sheet.cell_height, sheet.frame_count("idle")) == (192, 208, 6)


def test_preview_does_not_decode_any_action_and_current_page_is_bounded():
    sheet = load_character("deepseek")
    assert not sheet._atlases
    preview = sheet.image.copy()
    presented_preview = QPixmap.fromImage(preview).toImage()
    assert sheet.frame("idle", 0).toImage() == presented_preview
    sheet.frame("working", 0)
    paths = tuple(sheet._atlases)
    from src.pet.dialogs import character_preview
    assert character_preview(sheet).toImage() == presented_preview
    assert tuple(sheet._atlases) == paths
    assert all("working" in path.name for path in paths)
    assert sum(image.sizeInBytes() for image in sheet._atlases.values()) <= 12 * 192 * 192 * 4


def test_page_boundaries_aliases_last_frame_and_loop_preserve_pixels():
    sheet = load_character("deepseek")
    for state, entry in sheet.meta["animations"].items():
        assert len(entry["pages"]) == (entry["frames"] + 11) // 12
        for page, filename in enumerate(entry["pages"]):
            source = QImage(str(Path(__file__).resolve().parents[1] / "assets/dsh-deepseek" / filename))
            for column in range(min(12, entry["frames"] - page * 12)):
                index = page * 12 + column
                expected = QPixmap.fromImage(source.copy(column * 192, 0, 192, 192)).toImage()
                assert sheet.frame(state, index).toImage() == expected
            assert len(sheet._atlases) == 1
        assert sheet.frame(state, entry["frames"]).toImage() == sheet.frame(state, 0).toImage()


def test_alpha_validation_keeps_sampling_threshold_and_empty_cell_semantics():
    image = QImage(24, 8, QImage.Format_RGBA8888)
    image.fill(0)
    from PySide6.QtGui import QColor
    image.setPixelColor(0, 0, QColor(10, 20, 30, 8))
    image.setPixelColor(8, 0, QColor(10, 20, 30, 9))
    image.setPixelColor(17, 1, QColor(10, 20, 30, 255))  # Off the existing 4px sample grid.
    sheet = SpriteSheet(image, 3, 1, 8, 8, row_of={"idle": 0}, frames_by_row={0: 3})
    assert sheet._empty_cells() == ["idle#0", "idle#2"]
