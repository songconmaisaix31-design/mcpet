"""Actual Qt costume persistence/interruptions plus shared Agent preferences."""
import asyncio
import base64
import json
import os
from pathlib import Path
import sys
import time

import pytest
from PySide6.QtTest import QTest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.agent_service import AgentService
from src.pet.characters import load_character
from src.pet.preferences import PetPreferences
from src.pet.window import PetWindow

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def pet(tmp_path, monkeypatch):
    monkeypatch.setenv("MCPET_DATA_DIR", str(tmp_path))
    pet = PetWindow(load_character("deepseek"))
    pet.show()
    pet._behavior_timer.stop()
    yield pet
    pet.close()


def finish(pet):
    pet._index = len(pet._frames) - 1
    pet._next_frame = time.monotonic()
    pet._advance()


def test_outfit_persists_skin_then_reverse_restores_default(pet):
    pet.set_activity("working")
    pet.play_action("outfit")
    assert pet.character_id == "deepseek" and pet.skin_id == "default"
    assert len(pet._frames) == 48 and pet._action_target_skin == "maimai"
    finish(pet)
    assert pet.skin_id == "maimai" and pet.machine.state == "working"
    assert PetPreferences().load()["skin_id"] == "maimai"
    restored = PetWindow(load_character("maimai"))
    try:
        assert restored.character_id == "deepseek" and restored.skin_id == "maimai"
        assert restored.sheet.frame("idle", 0).toImage() == pet.sheet.frame("idle", 0).toImage()
    finally:
        restored.close()
    pet.play_action("outfit")
    assert pet.machine.state == "outfit-default" and not pet._action_loop
    finish(pet)
    assert pet.skin_id == "default" and pet.character_id == "deepseek"
    assert PetPreferences().load()["skin_id"] == "default"


@pytest.mark.parametrize("action", ["frying", "outfit"])
def test_skin_switch_any_time_cancels_action_and_late_commit(pet, action):
    pet.play_action(action, loop=True)
    pet.set_skin("default")
    assert pet.skin_id == "default" and pet._action_state is None
    assert "pending_skin_id" not in PetPreferences().load()
    QTest.qWait(180)
    assert pet.skin_id == "default"  # Timer cannot commit the cancelled target.
    pet.set_skin("maimai")
    pet.set_resting(True)
    pet.set_activity("thinking")
    assert pet.skin_id == "maimai" and pet.machine.state == "sleeping"
    assert pet.sheet.frame("sleeping", 0).toImage() == pet.sheet.frame("idle", 0).toImage()
    pet.set_resting(False)
    assert pet.skin_id == "maimai" and pet.machine.state == "thinking"


def test_frying_loop_uses_short_frames_keeps_skin_until_explicit_change(pet):
    pet.play_action("frying", loop=True)
    assert pet.skin_id == "maimai" and len(pet._frames) == 30
    QTest.qWait(180)
    assert pet._index > 0
    finish(pet)
    assert pet._action_state == "frying" and pet._index == 0
    pet.stop_action()
    assert pet.skin_id == "maimai" and pet.machine.state == "idle"
    pet.set_skin("default")
    assert pet.skin_id == "default"


def test_live_widget_receives_agent_skin_and_action_without_host_brand(pet):
    service = AgentService()
    result = service.pet(character_id="deepseek", skin_id="maimai")
    assert result["skin_id"] == "maimai"
    pet._receive_agent_command()
    assert pet.skin_id == "maimai"
    service.pet("frying", loop=True)
    pet._receive_agent_command()
    assert pet._action_state == "frying" and len(pet._frames) == 30
    service.pet(skin_id="default")
    pet._receive_agent_command()
    assert pet.skin_id == "default" and pet._action_state is None


def test_position_save_cannot_erase_an_unread_agent_command(pet):
    AgentService().pet("frying", "deepseek", loop=True)
    # A normal move/save timer fires before the next command polling timer.
    pet._save_preferences()
    assert PetPreferences().load()["action"] == "frying"
    assert PetPreferences().load()["skin_id"] == "maimai"
    pet._receive_agent_command()
    assert pet.skin_id == "maimai" and pet._action_state == "frying"


def test_agent_transition_deadline_survives_service_restart(pet, monkeypatch):
    service = AgentService()
    result = service.pet("outfit", "deepseek")
    assert result["skin_id"] == "default" and result["pending_skin_id"] == "maimai"
    assert result["animation"]["duration_seconds"] == 3.84
    deadline = PetPreferences().load()["action_until"]
    monkeypatch.setattr("time.time", lambda: deadline + 0.01)
    restarted = AgentService().status()
    assert restarted["skin_id"] == "maimai" and restarted["action"] == "idle"
    assert PetPreferences().load()["deepseek_skin_id"] == "maimai"
    restored = PetWindow(load_character("deepseek"))
    try:
        assert restored.skin_id == "maimai"
    finally:
        restored.close()


def test_real_stdio_skin_switch_and_new_transparent_resources(pet):
    async def run():
        parameters = StdioServerParameters(command=sys.executable, args=[str(ROOT / "scripts/agent_host.py")],
                                          env=dict(os.environ), cwd=str(PetPreferences().path.parent))
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                for skin in ("maimai", "default"):
                    result = await session.call_tool("mcpet_pet", {"character_id":"deepseek", "skin_id":skin})
                    assert result.structuredContent["skin_id"] == skin
                result = await session.call_tool("mcpet_pet", {"action":"frying", "loop":True})
                assert result.structuredContent["animation"]["duration_seconds"] == 2.40
                for uri in ("mcpet://animation/deepseek/frying", "mcpet://animation/deepseek/outfit",
                            "mcpet://animation/deepseek/outfit-default", "mcpet://skin/deepseek/maimai"):
                    resource = await session.read_resource(uri)
                    assert resource.contents[0].mimeType == "image/gif"
                    assert base64.b64decode(resource.contents[0].blob).startswith(b"GIF89a")
    asyncio.run(run())
