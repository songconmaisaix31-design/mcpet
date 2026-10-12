"""Real imported pages, Qt playback and panel actions; no external services."""
import time
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest

from src.pet.characters import load_character
from src.pet.dialogs import CompanionPanel, character_preview
from src.pet.spritesheet import ScaledAnimationFrames, SpriteLoadError, SpriteSheet
from src.pet.window import PetWindow


@pytest.fixture
def pet(tmp_path, monkeypatch):
    monkeypatch.setenv("MCPET_DATA_DIR", str(tmp_path))
    window = PetWindow(load_character("maimai"))
    window.show()
    window._behavior_timer.stop()
    yield window
    window.close()


def test_original_states_and_preview_keep_exact_pixels():
    root = Path(__file__).resolve().parents[1] / "assets/longniang"
    original = SpriteSheet.load(root / "spritesheet-runtime.png", pet_json=root / "pet.json",
                                rows_json=root / "sprite-rows.json")
    supplemented = load_character("maimai")
    for state in original.row_of:
        assert supplemented.frame_count(state) == original.frame_count(state)
        for index in range(original.frame_count(state)):
            assert supplemented.frame(state, index).toImage() == original.frame(state, index).toImage()
    assert character_preview(supplemented).toImage() == original.frame("idle", 0).toImage()


@pytest.mark.parametrize("state", ["frying", "outfit"])
def test_imported_frames_are_transparent_nonempty_and_pages_bounded(state):
    sheet = load_character("maimai")
    assert sheet.frame_count(state) == 127
    for index in range(sheet.frame_count(state)):
        image = sheet.frame(state, index).toImage().convertToFormat(QImage.Format_RGBA8888)
        assert (image.width(), image.height()) == (192, 192)
        assert image.pixelColor(0, 0).alpha() == 0
        assert max(bytes(image.constBits())[3::4]) == 255
        assert len(sheet._atlases) == 1
    assert sheet.frame(state, 127).toImage() == sheet.frame(state, 0).toImage()
    assert sheet.frame(state, 0).toImage() != sheet.frame(state, 25).toImage()


def test_actual_qt_timer_advances_and_loop_restores_latest_base_on_stop(pet):
    pet.play_action("frying", loop=True)
    assert isinstance(pet._frames, ScaledAnimationFrames)
    QTest.qWait(180)
    assert pet._index > 0
    pet.set_activity("working", 25, "Agent")
    assert pet.machine.state == "frying"
    assert pet._index > 0
    pet._index = len(pet._frames) - 1
    pet._next_frame = time.monotonic()
    pet._advance()
    assert pet._index == 0 and pet.machine.state == "frying"
    assert len(pet._frames.resident) <= 2
    pet.stop_action()
    assert pet.machine.state == "working"
    assert pet._current_state == "working"


def test_outfit_ends_once_preserves_event_deadline_and_new_base(pet):
    pet.set_state("greet", ttl_ms=4000)
    deadline = pet.machine._expires_at
    pet.play_action("outfit")
    pet.set_activity("thinking")
    assert pet.machine.state == "outfit"
    assert pet.machine._expires_at == deadline
    pet._index = len(pet._frames) - 1
    pet._next_frame = time.monotonic()
    pet._advance()
    assert pet._action_state is None
    assert pet.machine.state == "greet" and pet.machine._expires_at == deadline
    pet.machine._expires_at = time.monotonic() - 1
    pet._decay()
    assert pet.machine.state == "thinking"


def test_replay_rest_touch_and_character_switch_cancel_manual_action(pet):
    pet.play_action("outfit")
    pet._index = 50
    pet.play_action("outfit")
    assert pet._index == 0
    pet.set_resting(True)
    assert pet.machine.state == "sleeping" and pet._action_state is None
    pet.play_action("frying", loop=True)
    assert not pet.resting and pet.machine.state == "frying"
    pet._touch()
    assert pet._action_state is None and pet.machine.state == "greet"
    pet.play_action("frying", loop=True)
    pet.set_character("deepseek")
    assert pet._action_state is None and pet.machine.state == "greet"
    with pytest.raises(SpriteLoadError):
        pet.play_action("outfit")


def test_panel_has_clickable_actions_and_disables_them_for_deepseek(pet):
    panel = CompanionPanel(sheet=pet.sheet)
    def action(name):
        if name == "frying":
            pet.play_action(name, loop=True)
        elif name == "outfit":
            pet.play_action(name)
        elif name == "stop_animation":
            pet.stop_action()
    panel.action_requested.connect(action)
    try:
        panel.show()
        QTest.mouseClick(panel.frying_button, Qt.LeftButton)
        assert pet.machine.state == "frying"
        QTest.mouseClick(panel.stop_action_button, Qt.LeftButton)
        assert pet.machine.state == "idle"
        QTest.mouseClick(panel.outfit_button, Qt.LeftButton)
        assert pet.machine.state == "outfit"
        panel.set_character("deepseek", "DeepSeek 娘", load_character("deepseek"), ())
        assert not panel.frying_button.isEnabled() and not panel.outfit_button.isEnabled()
    finally:
        panel.close()
