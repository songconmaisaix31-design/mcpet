"""First-run identity, readable receipts, and portable packaging boundaries."""
from pathlib import Path
import sys

from src.agent_service import AgentService
from src.agent_install import server_definition, install
from src.pet.preferences import PetPreferences
from src.pet.characters import character_name
from src.presentation import order_receipt
from scripts.build_release import release_files


def test_new_profile_defaults_to_deepseek_and_saved_chatgpt_still_works(tmp_path, monkeypatch):
    monkeypatch.setenv("MCPET_DATA_DIR", str(tmp_path))
    service = AgentService()
    assert service.status()["character_id"] == "deepseek"
    assert service.status()["character_name"] == "DeepSeek 娘"
    assert service.status()["skin_id"] == "default"
    assert character_name("maimai") == "ChatGPT 娘"
    assert PetPreferences().save({"character_id": "maimai", "action": "idle"})
    assert service.status()["character_name"] == "ChatGPT 娘"
    assert service.pet(action="idle")["character_id"] == "maimai"
    result = service.pet(character_id="deepseek", skin_id="maimai")
    assert result["skin_name"] == "麦麦套装"
    assert service.pet(skin_id="default")["skin_id"] == "default"


def test_receipts_preserve_unknown_and_payment_semantics():
    unknown = order_receipt({"status": "delivery_unknown", "reason": "请到官方核对", "order_id": "known-17"}, "瑞幸")
    assert "known-17" in unknown and "未核实" in unknown and "别重复" in unknown
    assert "创建好了" not in unknown
    placed = order_receipt({"status": "placed", "order_id": "known-18", "summary": "实付 ¥16.00", "pay_url": "https://example.invalid/pay"}, "瑞幸")
    assert "¥16.00" in placed and "付款还要你亲自确认" in placed
    assert "https://" not in placed  # Pay links remain in the explicit payment flow.
    assert "官方已确认撤单" in order_receipt({"status": "cancelled", "order_id": "known-18"}, "瑞幸")


def test_frozen_installer_uses_executable_not_python_script(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    executable = tmp_path / "McPet.exe"
    monkeypatch.setattr(sys, "executable", str(executable))
    definition = server_definition()
    assert definition["command"] == str(executable) and definition["args"] == []
    install(tmp_path, "both")
    import json
    settings = json.loads((tmp_path / "opencode.json").read_text(encoding="utf-8"))
    assert settings["mcp"]["mcpet"]["command"] == [str(executable)]


def test_release_file_selection_contains_runtime_without_local_or_unlicensed_files():
    files = list(release_files())
    relative = {p.relative_to(Path(__file__).resolve().parents[1]).as_posix() for p in files}
    assert "src/pet/identity.py" in relative and ".agents/skills/mcpet/SKILL.md" in relative
    assert "assets/dsh-deepseek/LICENSE" in relative
    assert any(name.startswith("assets/deepseek-skins/") for name in relative)
    assert not any("cetapet-whale" in name or "__pycache__" in name for name in relative)
    assert not any(name.endswith(".env") or name.startswith((".claude/", ".opencode/", "data/", "logs/")) for name in relative)
