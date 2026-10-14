"""GIF 完整周期、复用与真实 MCP 读取；使用隔离的 Qt 素材。"""
import asyncio
import base64
import json
import os
from pathlib import Path
import sys
import subprocess

import pytest
from PIL import Image, ImageSequence
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from scripts import record_deepseek_gifs as recorder
from src.pet import recordings
from src.pet.spritesheet import AnimationSheet
from src.agent_service import AgentService

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def album(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    page = QImage(2304, 192, QImage.Format_RGBA8888)
    page.fill(Qt.transparent)
    painter = QPainter(page)
    painter.fillRect(30, 40, 45, 75, QColor("#ffbc0d"))
    painter.fillRect(192 + 80, 50, 45, 75, QColor("#2b5aed"))
    painter.end()
    assert page.save(str(source / "motion.png"))
    assert page.copy(0, 0, 192, 192).save(str(source / "preview.png"))
    required = ("idle", "run-left", "working", "thinking", "greet", "happy", "error", "sleeping", "eating")
    manifest = {"cell_size": 192, "columns": 12, "frame_delay_ms": 80, "preview": "preview.png",
                "animations": {state: {"frames": 2, "pages": ["motion.png"]} for state in required}}
    (source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    sheet = AnimationSheet(source)
    poses = tmp_path / "poses"
    poses.mkdir()
    assert page.save(str(poses / "pose.png"))
    (poses / "manifest.json").write_text(json.dumps({"cell_size": 192, "columns": 12,
        "animations": {"ceta_nothing": {"frames": 1, "pages": ["pose.png"]}}}), encoding="utf-8")
    sheet = AnimationSheet(poses, base_sheet=sheet)
    sheet.meta["idle_open_eye_hold_ms"] = 400
    monkeypatch.delenv("MCPET_FRAME_DELAY_MS", raising=False)
    monkeypatch.setattr(recorder, "load_character", lambda character, skin: sheet)
    output, desktop = tmp_path / "album", tmp_path / "desktop"
    index = recorder.record(output, desktop)
    monkeypatch.setattr(recordings, "ROOT", output)
    monkeypatch.setenv("MCPET_RECORDINGS_DIR", str(output))
    monkeypatch.setenv("MCPET_DATA_DIR", str(tmp_path / "data"))
    return output, desktop, index, sheet


def test_full_cycle_cadence_direction_pose_and_classified_files(album):
    output, desktop, index, sheet = album
    assert len(index["actions"]) == 2 * len(sheet.row_of)
    for row in index["actions"]:
        for size in (192, 512):
            path = output / row["files"][str(size)]["path"]
            expected = recorder.cadence(sheet, row["action"])
            check = recorder.audit(path, sum(expected), animated=row["kind"] == "animation")
            with Image.open(path) as image:
                assert image.size == (size, size)
                assert check["changed"] == (row["kind"] == "animation")
            copies = list((desktop / recorder.SKINS[row["skin"]] / f"{row['label']}_{row['action']}").glob(f"*{size}.gif"))
            assert len(copies) == 1 and copies[0].read_bytes() == path.read_bytes()
    with Image.open(output / "default/idle/192.gif") as image:
        assert [frame.info["duration"] for frame in ImageSequence.Iterator(image)] == [480, 80]
    with Image.open(output / "default/run-left/192.gif") as left, Image.open(output / "default/run-right/192.gif") as right:
        assert left.convert("RGBA").transpose(Image.Transpose.FLIP_LEFT_RIGHT).tobytes() == right.convert("RGBA").tobytes()
    assert (desktop / "打开动作预览.html").is_file()
    assert "左右镜像" in next(row for row in index["actions"] if row["skin"] == "maimai" and row["action"] == "run-right")["note"]


def test_existing_export_is_protected_and_bad_resource_paths_rejected(album):
    output, desktop, index, _ = album
    first = next(desktop.rglob("*.gif"))
    first.write_bytes(b"user file")
    with pytest.raises(FileExistsError):
        recorder.export_folder(desktop, output, index["actions"])
    assert first.read_bytes() == b"user file"
    for skin, action, size in [("../default", "idle", 512), ("default", "../idle", 512), ("default", "idle", 1080)]:
        with pytest.raises(ValueError):
            recordings.image_path(skin, action, size)


def test_gif_time_quantization_preserves_total():
    assert recorder.gif_cadence([16] * 10) == [20, 10, 20, 10, 20, 20, 10, 20, 10, 20]
    assert sum(recorder.gif_cadence([83] * 126)) == 10460


def test_real_stdio_album_and_all_gifs(album):
    output, _, index, _ = album
    assert AgentService.animation_info("deepseek", "idle")["uri"] == "mcpet://recording/deepseek/default/idle/512"
    assert AgentService.animation_info("deepseek", "outfit")["uri"] == "mcpet://animation/deepseek/outfit"
    async def run():
        params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "scripts/agent_host.py")], env=dict(os.environ))
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                actual = await session.read_resource("mcpet://recordings/deepseek")
                assert json.loads(actual.contents[0].text) == index
                status = await session.call_tool("mcpet_pet", {"character_id": "deepseek", "action": "idle"})
                assert not status.isError
                assert status.structuredContent["animation"]["recording"]["native_size"] == 192
                for row in index["actions"]:
                    for size in (192, 512):
                        uri = f"mcpet://recording/deepseek/{row['skin']}/{row['action']}/{size}"
                        resource = await session.read_resource(uri)
                        assert resource.contents[0].mimeType == "image/gif"
                        assert base64.b64decode(resource.contents[0].blob) == (output / row["files"][str(size)]["path"]).read_bytes()
    asyncio.run(run())


def test_missing_album_keeps_original_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(recordings, "ROOT", tmp_path)
    assert recordings.catalog()["installed"] is False
    assert "uri" not in AgentService.animation_info("deepseek", "idle")
    assert AgentService.animation_info("deepseek", "frying")["uri"] == "mcpet://animation/deepseek/frying"
    from scripts.build_release import release_files
    assert not any(path.is_relative_to(ROOT / "assets/deepseek-recordings") for path in release_files())


def test_agent_recording_reader_does_not_import_desktop_or_encoder():
    result = subprocess.run([sys.executable, "-c",
        "import sys; from src.agent_mcp import create_server; create_server(); "
        "assert not any(name.startswith(('PySide6', 'PIL')) for name in sys.modules)"],
        cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
