"""Actual Qt dual-character gestures, persistence, deadlines and render probe."""
import json
import os
import sys
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt, QTimer
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.pet.characters import load_character
from src.pet.preferences import PetPreferences
from src.pet.spritesheet import SpriteLoadError
from src.pet.window import PetWindow


@pytest.fixture
def pet(tmp_path, monkeypatch):
    monkeypatch.setenv("MCPET_DATA_DIR", str(tmp_path))
    window = PetWindow(load_character("maimai"))
    window.show()
    window.set_roaming(False)
    yield window
    window.close()


def send(window, kind, point, button=Qt.LeftButton, buttons=Qt.LeftButton):
    event = QMouseEvent(kind, QPointF(window.mapFromGlobal(point)), QPointF(point),
                        button, buttons, Qt.NoModifier)
    QApplication.sendEvent(window, event)


def test_switch_preserves_touch_deadline_latest_base_position_and_bubble(pet):
    pet._touch()
    expires = pet.machine._expires_at
    position = pet.pos()
    text = pet.bubble.label.text()
    pet.set_activity("working", None, "Agent")
    pet.set_character("deepseek")
    assert pet.character_id == "deepseek" and pet.machine.state == "greet"
    assert pet.machine._expires_at == expires
    assert pet.pos() == position and pet.bubble.label.text() == text
    assert pet.context_bar.isHidden() and "未知" in pet.activity_label.text()
    assert not pet.canvas.pixmap().isNull()
    pet.machine._expires_at = time.monotonic() - 1
    pet._decay()
    assert pet.machine.state == "working"
    pet.set_character("maimai")
    assert pet.machine.state == "working" and pet.pos() == position
    assert pet.canvas.pixmap().toImage().hasAlphaChannel()


def test_real_timer_expiry_after_switch_returns_to_latest_agent_base(pet):
    pet.set_state("greet", ttl_ms=1200)
    deadline = pet.machine._expires_at
    pet.set_character("deepseek")
    pet.set_activity("working", None, "后台")
    assert pet.machine.state == "greet" and pet.machine._expires_at == deadline
    QTest.qWait(1250)
    assert pet.machine.state == "working" and pet._current_state == "working"
    assert pet.machine._expires_at is None


@pytest.mark.parametrize("state", ["greet", "error", "waiting", "happy"])
def test_switch_during_actual_drag_and_rest_preserves_interaction_priority(pet, state):
    clicks = []
    pet.clicked.connect(lambda: clicks.append(True))
    pet.set_state(state, ttl_ms=4000)
    deadline = pet.machine._expires_at
    origin = pet.pos() + QPoint(50, 70)
    send(pet, QEvent.MouseButtonPress, origin)
    send(pet, QEvent.MouseMove, origin + QPoint(40, 0), Qt.NoButton)
    assert pet.machine.state == "run-right"
    pet.set_character("deepseek")
    pet.set_activity("working", 0, "开发")
    assert pet.machine.state == "run-right" and pet.machine._expires_at == deadline
    before = pet._index
    pet._next_frame = time.monotonic() - 0.01
    pet._advance()
    assert pet._index != before
    index = pet._index
    send(pet, QEvent.MouseMove, origin + QPoint(39, 0), Qt.NoButton)
    assert pet.machine.state == "run-right" and pet._index == index
    send(pet, QEvent.MouseButtonRelease, origin + QPoint(39, 0), buttons=Qt.NoButton)
    assert pet.machine.state == state
    assert not pet._click_timer.isActive()
    pet.set_resting(True)
    pet.set_character("maimai")
    pet.set_activity("thinking", None, "后台")
    assert pet.machine.state == "sleeping" and pet.machine._expires_at == deadline
    pet.set_character("deepseek")
    assert pet.machine.state == "sleeping"
    pet.set_resting(False)
    assert pet.machine.state == state
    pet.machine._expires_at = time.monotonic() - 1
    pet._decay()
    assert pet.machine.state == "thinking"
    QTest.qWait(QApplication.doubleClickInterval() + 20)
    assert not clicks


def test_restart_keeps_character_roaming_resting_position_and_old_preferences(pet):
    pet.set_character("deepseek")
    pet.set_roaming(True)
    pet.set_resting(True)
    position = pet.pos()
    pet._save_preferences()
    saved = PetPreferences().load()
    assert saved["character_id"] == "deepseek"
    restored = PetWindow(load_character("maimai"))  # Existing main startup still passes maimai.
    try:
        assert restored.character_id == "deepseek"
        assert restored.roaming_enabled and restored.resting
        assert restored.machine.state == "sleeping" and restored.pos() == position
    finally:
        restored.close()
    saved.pop("character_id")
    PetPreferences().save(saved)
    legacy = PetWindow(load_character("maimai"))
    try:
        assert legacy.character_id == "maimai" and legacy.resting
        assert legacy.pos() == position
    finally:
        legacy.close()


def test_failed_switch_is_transactional_and_repeated_switch_keeps_phase(pet, monkeypatch):
    pet.set_character("deepseek")
    pet._index = 12
    before = (pet.sheet, pet._frames, pet.canvas.pixmap().cacheKey(), pet.pos(),
              pet.machine._expires_at, PetPreferences().path.read_bytes())
    pet.set_character("deepseek")
    assert pet._index == 12
    with pytest.raises(SpriteLoadError):
        pet.set_character("unknown")
    def broken(identity):
        sheet = load_character("maimai")
        sheet.frames = lambda state: (_ for _ in ()).throw(SpriteLoadError("broken asset"))
        return sheet
    monkeypatch.setattr("src.pet.window.load_character", broken)
    with pytest.raises(SpriteLoadError):
        pet.set_character("maimai")
    after = (pet.sheet, pet._frames, pet.canvas.pixmap().cacheKey(), pet.pos(),
             pet.machine._expires_at, PetPreferences().path.read_bytes())
    assert after == before and pet.character_id == "deepseek" and pet._index == 12


def test_deepseek_alias_polling_and_full_loop_keep_phase_with_bounded_cache(pet):
    pet.set_character("deepseek")
    pet.set_activity("working")
    pet._index = 39
    frames = pet._frames
    pet.set_activity("progress")
    assert pet._frames is frames and pet._index == 39
    for state in ("idle", "thinking", "eating", "sleeping", "working", "run-left", "run-right"):
        pet.set_activity(state)
        assert len(pet._visual_cache) <= 2
        assert len({id(frames) for frames in pet._cache.values()}) <= 2
        assert len(pet.sheet._atlases) <= 1
        assert {frame.devicePixelRatioF() for frame in pet._frames} == {pet.devicePixelRatioF()}
        assert len(pet._frames.resident) <= 2
    pet.set_activity("idle")
    pet._index = len(pet._frames) - 1
    pet._next_frame = time.monotonic() - 0.001
    pet._advance()
    assert pet._index == 0
    assert pet.canvas.pixmap().toImage() == pet._frames[0].toImage()
    assert pet.canvas.pixmap().toImage().pixelColor(0, 0).alpha() == 0


def test_native_action_sweep_residency_is_frames_not_entire_sequences(pet):
    pet.set_character("deepseek")
    for state in list(pet.sheet.meta["animations"]) * 2:
        pet._load_frames(state)
        for _ in range(3):
            pet._next_frame = time.monotonic() - 0.001
            pet._advance()
        QApplication.processEvents()
        assert pet._frames and not pet.canvas.pixmap().isNull()
        if state in ("frying", "outfit", "outfit-default"):
            assert len(pet._frames) == (30 if state == "frying" else 48)
        else:
            assert len(pet._frames) in (61, 126)
        assert sum(len(sequence.resident) for sequence in pet._visual_cache.values()) <= 4
        assert sum(image.sizeInBytes() for image in pet.sheet._atlases.values()) < 20_000_000


def test_switch_prepares_actual_phase_and_failure_keeps_previous_character(pet, monkeypatch):
    pet.set_activity("working")
    pet._index = 3  # Six maimai frames -> frame 63, on DeepSeek page five.
    candidate = load_character("deepseek")
    calls = []
    original = candidate.frame
    def frame(state, index):
        calls.append(index)
        if index == 63:
            raise SpriteLoadError("corrupt actual phase page")
        return original(state, index)
    candidate.frame = frame
    monkeypatch.setattr("src.pet.window.load_character", lambda identity: candidate)
    before = (pet.sheet, pet._frames, pet.canvas.pixmap().cacheKey(), pet._index,
              pet.machine.state, pet.machine._expires_at, PetPreferences().path.read_bytes())
    with pytest.raises(SpriteLoadError):
        pet.set_character("deepseek")
    assert (pet.sheet, pet._frames, pet.canvas.pixmap().cacheKey(), pet._index,
            pet.machine.state, pet.machine._expires_at, PetPreferences().path.read_bytes()) == before
    assert calls == [63]  # No unnecessary frame-zero page decode first.


def test_saved_current_character_reuses_supplied_sheet_without_reload(pet, monkeypatch):
    pet._save_preferences()
    def unexpected(identity):
        raise AssertionError("already supplied and validated character must not reload")
    monkeypatch.setattr("src.pet.window.load_character", unexpected)
    restored = PetWindow(pet.sheet)
    try:
        assert restored.sheet is pet.sheet and restored.character_id == "maimai"
        assert not restored.canvas.pixmap().isNull()
    finally:
        restored.close()


def test_switch_with_same_cadence_preserves_live_timer_and_advances_in_callback(pet):
    pet.set_activity("working")
    before_deadline, before_timer = pet._next_frame, pet._anim.timerId()
    observed = []
    def click():
        pet.set_character("deepseek")
        observed.append((pet._next_frame, pet._anim.timerId()))
        before = pet._index
        QTest.qWait(110)  # Existing native combination's actual nested timer path.
        observed.append(pet._index != before)
    QTimer.singleShot(0, click)
    QTest.qWait(180)
    assert observed[0] == (before_deadline, before_timer)
    assert observed[1]


def native_probe():
    """Uses only our own window; never captures or controls the user's desktop."""
    from scripts.bench_render import measure_idle, measure_drag
    app = QApplication.instance() or QApplication([])
    assert app.platformName() == "windows"
    output = Path(os.environ["MCPET_DATA_DIR"])
    output.mkdir(parents=True, exist_ok=True)
    window = PetWindow(load_character("maimai"))
    window.set_roaming(False)
    window.set_resting(False)
    window.show()
    results = {}
    try:
        for identity in ("maimai", "deepseek"):
            window.machine.clear("greet")
            start = time.perf_counter()
            window.set_character(identity)
            switch_ms = (time.perf_counter() - start) * 1000
            window.set_activity("idle", 37, "开发陪伴")
            QTest.qWait(200)
            assert window.grab().save(str(output / (identity + "-native.png")))
            idle = measure_idle(app, window, 5)
            drag = measure_drag(app, window)
            # Count live pixel storage, including source atlas and all unique
            # scaled sequences, not alias dictionary entries.
            cache_bytes = sum(frame.width() * frame.height() * 4
                              for sequence in window._visual_cache.values()
                              for frame in (sequence.resident.values() if hasattr(sequence, "resident") else sequence))
            source_bytes = sum(image.sizeInBytes() for image in getattr(window.sheet, "_atlases", {}).values())
            results[identity] = {"switch_ms": round(switch_ms, 2), "idle": idle, "drag": drag,
                                 "scaled_cache_bytes": cache_bytes, "source_cache_bytes": source_bytes}
            assert idle["fps"] >= 11.25 and idle["jank_ratio"] <= 0.02
            assert drag["state_changes"] == ["run-right"] and drag["clicks_after_drag"] == 0
            assert drag["distinct_frames_shown"] > 1
            if identity == "deepseek":
                cold = {}
                for state in window.sheet.meta["animations"]:
                    started = time.perf_counter()
                    window._load_frames(state)
                    cold[state] = round((time.perf_counter() - started) * 1000, 2)
                    assert window._frames and not window.canvas.pixmap().isNull()
                    assert len(window._visual_cache) <= 2 and len(window.sheet._atlases) <= 1
                    assert len(window._frames.resident) <= 2
                results[identity]["cold_action_ms"] = cold
        print(json.dumps({"platform": app.platformName(), "dpr": window.devicePixelRatioF(),
                          "results": results}, ensure_ascii=False))
    finally:
        window.close()


if __name__ == "__main__":
    native_probe()
