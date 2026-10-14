"""早期姿态的导入、显示、原 Agent 调用与分类导出；业务账号未使用。"""
import asyncio
import base64
import os
from pathlib import Path
import subprocess
import sys

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter, QColor, QPixmap
from PySide6.QtTest import QTest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from scripts.import_cetapet import import_assets
from src.pet import cetapet
from src.pet.characters import load_character
from src.pet.window import PetWindow
from src.agent_service import AgentService
from src.pet.functions import PetFunctions

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def pack(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    for index, row in enumerate(cetapet.CATALOG["actions"]):
        path = source / "CetaPet/asset_library" / row["file"]
        path.parent.mkdir(parents=True, exist_ok=True)
        image = QImage(90 + index * 2, 120 + index * 2, QImage.Format_RGBA8888)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.fillRect(5, 5, image.width() - 10, image.height() - 10, QColor.fromHsv(index * 30, 200, 200, 100 + index * 15))
        painter.end()
        assert image.save(str(path), "PNG")
    (source / "LICENSE").write_text("Fixture license\n", encoding="utf-8")
    (source / "README.md").write_text("Fixture source\n", encoding="utf-8")
    def git(*args):
        return subprocess.run(["git", "-C", str(source), *args], check=True, capture_output=True, text=True).stdout.strip()
    git("init", "-q")
    git("add", ".")
    git("-c", "user.name=McPet fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false", "commit", "-qm", "pose fixtures")
    monkeypatch.setitem(cetapet.CATALOG, "commit", git("rev-parse", "HEAD"))
    destination = tmp_path / "pack"
    exported = tmp_path / "desktop"
    assert import_assets(source, destination, exported) == 9
    monkeypatch.setattr(cetapet, "ROOT", destination)
    monkeypatch.setenv("MCPET_CETAPET_DIR", str(destination))
    monkeypatch.setenv("MCPET_DATA_DIR", str(tmp_path / "data"))
    return source, destination, exported


def test_all_originals_and_named_export_are_exact(pack):
    source, destination, exported = pack
    assert len(list(exported.iterdir())) == 12  # 九个动作文件夹与三个来源/索引文件。
    for action, row in cetapet.ACTIONS.items():
        original = (source / "CetaPet/asset_library" / row["file"]).read_bytes()
        assert (destination / "original/asset_library" / row["file"]).read_bytes() == original
        assert (exported / row["label"] / Path(row["file"]).name).read_bytes() == original
        assert action in (exported / "动作索引.md").read_text(encoding="utf-8")


def test_all_poses_render_in_existing_qt_sheet_and_restore_base(pack):
    source, destination, _ = pack
    pet = PetWindow(load_character("deepseek"))
    pet.show()
    pet._behavior_timer.stop()
    try:
        idle = pet.sheet.frame("idle", 0).toImage()
        for action, row in cetapet.ACTIONS.items():
            original = QImage(str(source / "CetaPet/asset_library" / row["file"]))
            expected = QImage(192, 192, QImage.Format_RGBA8888)
            expected.fill(Qt.transparent)
            painter = QPainter(expected)
            painter.drawImage((192 - original.width()) // 2, 192 - original.height(), original)
            painter.end()
            prepared = QImage(str(destination / "runtime" / (action + "-000.png"))).copy(0, 0, 192, 192)
            assert prepared.convertToFormat(QImage.Format_RGBA8888) == expected
            assert pet.sheet.frame(action, 0).toImage() == QPixmap.fromImage(expected).toImage()
            pet.play_action(action)
            QTest.qWait(110)
            assert pet._action_state == action and pet._current_state == action
            assert pet._action_loop and len(pet._frames) == 1
            pet.stop_action()
            assert pet._action_state is None
        assert pet.sheet.frame("idle", 0).toImage() == idle
    finally:
        pet.close()


def test_agent_commands_apply_to_existing_pet_and_reject_wrong_character(pack):
    pet = PetWindow(load_character("deepseek"))
    try:
        service = AgentService()
        for action in cetapet.ACTIONS:
            result = service.pet(action, "deepseek")
            pet._receive_agent_command()
            assert pet._action_state == action
            assert result["action"] == action and result["animation"]["kind"] == "pose"
        with pytest.raises(ValueError):
            service.pet("ceta_eat", "maimai")
        service.pet("stop")
        pet._receive_agent_command()
        assert pet._action_state is None
    finally:
        pet.close()


def test_real_stdio_schema_commands_and_all_pose_resources(pack):
    async def run():
        params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "scripts/agent_host.py")], env=dict(os.environ))
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                schema = next(tool for tool in tools.tools if tool.name == "mcpet_pet").inputSchema
                assert set(cetapet.ACTIONS) <= set(schema["properties"]["action"]["enum"])
                for action in cetapet.ACTIONS:
                    result = await session.call_tool("mcpet_pet", {"action": action, "character_id": "deepseek"})
                    assert not result.isError
                    assert result.structuredContent["action"] == action
                    resource = await session.read_resource(result.structuredContent["animation"]["uri"])
                    assert resource.contents[0].mimeType == "image/png"
                    assert base64.b64decode(resource.contents[0].blob) == cetapet.require_pose(action).read_bytes()
    asyncio.run(run())


def test_right_click_menu_captures_each_pose_action(pack):
    class MenuHarness(PetFunctions):
        def __init__(self, window):
            self.window, self.called = window, []

        def _reminders_enabled(self):
            return False

        def _play_pet_action(self, state, *, loop=False):
            self.called.append((state, loop))

        def __getattr__(self, name):
            return lambda *args, **kwargs: None

    pet = PetWindow(load_character("deepseek"))
    try:
        harness = MenuHarness(pet)
        roles = next(entries for label, entries in harness.menu_entries() if label == "角色与动作")
        poses = next(entry[1] for entry in roles if entry and entry[0] == "早期鲸鲸姿态")
        assert [label for label, _ in poses] == [row["label"] for row in cetapet.ACTIONS.values()]
        for _, callback in poses:
            callback()
        assert harness.called == [(key, True) for key in cetapet.ACTIONS]
    finally:
        pet.close()


def test_release_contains_catalog_and_excludes_local_images(pack):
    from scripts.build_release import release_files
    paths = {path.relative_to(ROOT).as_posix() for path in release_files()}
    assert "assets/cetapet/actions.json" in paths
    assert not any(path.startswith(("assets/cetapet/original/", "assets/cetapet/runtime/")) for path in paths)
