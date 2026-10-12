"""Real stdio transport and fixture-only business safety, with isolated data."""
import asyncio
import base64
from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src import config
from src.agent_hook import host_event
from src.agent_install import install
from src.agent_service import AgentService, public
from src.mcd_mcp.brain import DealQuote, McdBrain, NutritionFact, StoreInfo
from src.mcd_mcp.client import ToolResult
from src.mcd_mcp.guards import OrderGuard
from src.mcd_mcp import tools as T

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("MCPET_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MCPET_CONFIG_PATH", str(tmp_path / "config.json"))
    (tmp_path / "config.json").write_text(json.dumps({"agentRoots": {
        "claude": str(tmp_path / "absent-claude"), "codex": str(tmp_path / "absent-codex"),
        "generic": str(tmp_path / "inbox")}}), encoding="utf-8")
    for key in ("MCPET_AGENT_ROOTS", "MCPET_AGENT_ROOT_CLAUDE", "MCPET_AGENT_ROOT_CODEX", "MCPET_AGENT_ROOT_GENERIC"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("MCPET_LUNCH_TIME", "11:30")
    monkeypatch.setenv("MCD_DRY_RUN", "false")
    monkeypatch.setattr(config, "load_env", lambda: None)
    return tmp_path


class Upstream:
    """A fixture, never a live order or price probe."""
    def __init__(self, prices=(990, 990), ambiguous=False, missing_id=False):
        self.prices = iter(prices)
        self.calls = []
        self.ambiguous = ambiguous
        self.missing_id = missing_id

    def call_tool(self, name, arguments=None):
        self.calls.append(name)
        if name == T.TOOL_CALCULATE_PRICE:
            data = {"price": next(self.prices)}
        elif name == T.TOOL_CREATE_ORDER:
            if self.ambiguous:
                raise OSError("connection lost after submit")
            data = {"orderNo": "fixture-123", "payUrl": "https://example.invalid/pay"}
            if self.missing_id:
                data = {}
        else:
            data = []
        return ToolResult(name=name, raw={}, text="", data={"success": True, "code": 200, "data": data})


def ordering(upstream):
    service = AgentService()
    @contextmanager
    def brain():
        yield McdBrain(upstream, OrderGuard())
    service.brain = brain
    store = StoreInfo("fixture-store", "Fixture Store")
    service.deal_options = (store, [DealQuote("Fixture Meal", "fixture-meal")])
    return service, store


def prepare(service, store):
    return service.prepare_order(["fixture-meal"], ["Fixture Meal"], {"store_code": store.store_code})


def test_no_confirm_never_creates_order(isolated):
    upstream = Upstream()
    service, store = ordering(upstream)
    assert prepare(service, store)["status"] == "needs_confirmation"
    assert service.confirm_order()["status"] == "needs_confirmation"
    assert upstream.calls == [T.TOOL_CALCULATE_PRICE]
    assert service.claim_coupons()["status"] == "needs_confirmation"
    assert service.cancel_order("fixture-123")["status"] == "needs_confirmation"


def test_confirm_places_once_using_reviewed_price(isolated):
    upstream = Upstream()
    service, store = ordering(upstream)
    assert prepare(service, store)["amount_cents"] == 990
    assert service.confirm_order(True)["status"] == "placed"
    assert upstream.calls.count(T.TOOL_CALCULATE_PRICE) == 2
    assert upstream.calls.count(T.TOOL_CREATE_ORDER) == 1
    with pytest.raises(ValueError, match="没有待确认"):
        service.confirm_order(True)


def test_price_change_needs_fresh_confirmation(isolated):
    upstream = Upstream((990, 1200))
    service, store = ordering(upstream)
    prepare(service, store)
    assert service.confirm_order(True)["status"] == "needs_confirmation"
    assert T.TOOL_CREATE_ORDER not in upstream.calls
    assert service.pending_order is None


def test_unknown_submit_is_recorded_and_cannot_replay(isolated):
    upstream = Upstream(ambiguous=True)
    service, store = ordering(upstream)
    prepare(service, store)
    assert service.confirm_order(True)["status"] == "delivery_unknown"
    assert OrderGuard().entries[-1].status == "delivery_unknown"
    with pytest.raises(ValueError):
        service.confirm_order(True)
    assert upstream.calls.count(T.TOOL_CREATE_ORDER) == 1


def test_missing_order_identity_is_unknown_in_response_and_audit(isolated):
    upstream = Upstream(missing_id=True)
    service, store = ordering(upstream)
    prepare(service, store)
    assert service.confirm_order(True)["status"] == "delivery_unknown"
    assert OrderGuard().entries[-1].status == "delivery_unknown"
    assert service.pending_order is None


@pytest.mark.parametrize("mutation", ["meal", "store", "name", "takeway"])
def test_order_rejects_invented_selections(isolated, mutation):
    service, store = ordering(Upstream())
    args = {"product_codes": ["fixture-meal"], "meal_names": ["Fixture Meal"],
            "store": {"store_code": store.store_code}, "take_way_code": "eat-in"}
    if mutation == "meal": args["product_codes"] = ["invented"]
    if mutation == "store": args["store"] = {"store_code": "invented"}
    if mutation == "name": args["meal_names"] = ["Invented Name"]
    if mutation == "takeway": args["take_way_code"] = "delivery"
    with pytest.raises(ValueError): service.prepare_order(**args)


def test_nutrition_uses_real_selection_and_quantity(isolated):
    service = AgentService()
    with pytest.raises(ValueError): service.nutrition_log("Invented", confirmed=True)
    service.pending_nutrition = {"Fixture Meal": NutritionFact("Fixture Meal", energy_kcal=200)}
    assert service.nutrition_log("Fixture Meal", 1.5)["status"] == "needs_confirmation"
    assert not (isolated / "nutrition.json").exists()
    service.nutrition_log("Fixture Meal", 1.5, True)
    assert service.nutrition_today()["totals"]["energy_kcal"] == 300
    with pytest.raises(ValueError): service.nutrition_log("Fixture Meal", float("nan"), True)


def test_hooks_drop_private_content_and_stop_is_idle(isolated):
    secret = "private-marker-do-not-store"
    host_event("claude", {"session_id": "fixture", "hook_event_name": "Stop", "cwd": str(isolated),
                          "prompt": secret, "transcript_path": secret, "tool_input": {"secret": secret}})
    text = (isolated / "inbox/host-events.jsonl").read_text(encoding="utf-8")
    assert secret not in text and "transcript" not in text
    snapshot = AgentService().progress()
    assert snapshot["sessions"][0]["state"] == "idle"
    assert snapshot["sessions"][0]["context_percent"] is None
    assert "completion" not in text


def test_reminder_delivered_once_across_services(isolated):
    at = datetime(2026, 10, 12, 11, 30)
    assert len(AgentService().reminders(at)["messages"]) == 1
    assert AgentService().reminders(at)["messages"] == []


def test_silent_stop_does_not_consume_reminder(isolated, monkeypatch):
    calls = []
    monkeypatch.setattr(AgentService, "reminders", lambda self: calls.append(True) or {"messages": []})
    host_event("claude", {"session_id": "fixture", "hook_event_name": "Stop"})
    assert calls == []
    host_event("claude", {"session_id": "fixture", "hook_event_name": "UserPromptSubmit"})
    assert calls == [True]


def test_configuration_preserves_servers_permissions_hooks(isolated):
    (isolated / ".mcp.json").write_text('{"mcpServers":{"other":{"command":"other"}}}')
    (isolated / ".claude").mkdir()
    other = {"type": "command", "command": "other-hook"}
    settings = {"permissions": {"deny": ["Bash(rm *)"]},
                "hooks": {"Stop": [{"hooks": [other]}]}}
    (isolated / ".claude/settings.local.json").write_text(json.dumps(settings))
    install(isolated, "both")
    install(isolated, "both")
    mcp = json.loads((isolated / ".mcp.json").read_text())
    assert mcp["mcpServers"]["other"] == {"command": "other"}
    actual = json.loads((isolated / ".claude/settings.local.json").read_text())
    assert actual["permissions"] == settings["permissions"]
    assert len(actual["hooks"]["Stop"]) == 2
    assert actual["hooks"]["Stop"][0]["hooks"][0] == other
    command = actual["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert "\\" not in command


def test_jsonc_refusal_does_not_partially_change_claude(isolated):
    (isolated / "opencode.jsonc").write_text("// custom\n{}")
    with pytest.raises(ValueError, match="jsonc"): install(isolated, "both")
    assert not (isolated / ".mcp.json").exists()


def test_fresh_process_does_not_import_qt_or_llm(isolated):
    result = subprocess.run([sys.executable, "-c",
        "from src.agent_mcp import create_server; import sys; create_server(); "
        "assert not any(x.startswith('PySide6') for x in sys.modules); "
        "assert 'src.llm' not in sys.modules; print('headless-ok')"], cwd=ROOT, env=dict(os.environ),
        capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert "headless-ok" in result.stdout


def test_default_export_connects_without_native_host_configs(isolated):
    # Deliberately provide malformed native configs: generic integration never reads them.
    (isolated / "opencode.jsonc").write_text("// existing native config\n{}")
    (isolated / ".mcp.json").write_text("native-config-is-not-json")
    before = {path: path.read_bytes() for path in isolated.iterdir() if path.is_file()}
    output = subprocess.run([sys.executable, "-m", "src.agent_install", "--project", str(isolated)],
                            cwd=ROOT, env=dict(os.environ), capture_output=True, text=True,
                            encoding="utf-8", timeout=15)
    assert output.returncode == 0, output.stderr
    exported = json.loads(output.stdout)
    assert exported["installed"] == []
    assert {path: path.read_bytes() for path in isolated.iterdir() if path.is_file()} == before
    assert not (isolated / ".claude").exists()
    assert not (isolated / ".opencode").exists()

    async def run():
        server = exported["server"]
        parameters = StdioServerParameters(command=server["command"], args=server["args"],
                                          cwd=str(isolated), env=dict(os.environ))
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                assert len((await session.list_tools()).tools) == 21
                for action in ("frying", "outfit"):
                    result = await session.call_tool("mcpet_pet", {"action": action, "character_id": "maimai"})
                    assert result.structuredContent["animation"]["uri"].endswith("/" + action)
                    resource = await session.read_resource("mcpet://animation/maimai/" + action)
                    assert resource.contents[0].mimeType == "image/gif"
                    assert base64.b64decode(resource.contents[0].blob).startswith(b"GIF89a")
    asyncio.run(run())


@pytest.mark.parametrize("entry", ["launcher", "default"])
def test_real_stdio_roundtrip_and_resource(isolated, entry):
    async def run():
        args = [str(ROOT / "scripts/agent_host.py")] if entry == "launcher" else ["-m", "src.main"]
        parameters = StdioServerParameters(command=sys.executable, args=args, env=dict(os.environ),
                                          cwd=str(isolated if entry == "launcher" else ROOT))
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                assert len(listed.tools) == 21
                assert not any(tool.name == "create-order" for tool in listed.tools)
                assert next(t for t in listed.tools if t.name == "mcpet_confirm_order").annotations.destructiveHint
                status = await session.call_tool("mcpet_status", {})
                assert status.structuredContent["separate_window"] is False
                assert status.structuredContent["character_name"] == "DeepSeek 娘"
                denied = await session.call_tool("mcpet_confirm_order", {"confirmed": True})
                assert denied.structuredContent["status"] == "error"
                usage = await session.call_tool("mcpet_usage", {})
                assert usage.structuredContent["status"] != "error"
                result = await session.call_tool("mcpet_pet", {"action": "frying", "loop": True})
                assert result.structuredContent["animation"]["uri"].endswith("/frying")
                resource = await session.read_resource("mcpet://animation/maimai/frying")
                assert base64.b64decode(resource.contents[0].blob).startswith(b"GIF89a")
                prompt = await session.get_prompt("mcpet_assistant")
                assert "delivery_unknown" in prompt.messages[0].content.text
    asyncio.run(run())


def test_parallel_hosts_do_not_lose_nutrition_updates(isolated):
    code = ("from src.agent_service import AgentService; from src.mcd_mcp.brain import NutritionFact; "
            "s=AgentService(); s.pending_nutrition={'Fixture':NutritionFact('Fixture', energy_kcal=10)}; "
            "s.nutrition_log('Fixture', 1, True)")
    children = [subprocess.Popen([sys.executable, "-c", code], cwd=ROOT, env=dict(os.environ),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(4)]
    for child in children:
        _, error = child.communicate(timeout=20)
        assert child.returncode == 0, error.decode(errors="replace")
    assert AgentService().nutrition_today()["totals"]["items"] == 4


def test_public_results_remove_secrets_and_raw(isolated, monkeypatch):
    monkeypatch.setenv("MCD_MCP_TOKEN", "fixture-secrettoken-123456")
    result = public({"text": "fixture-secrettoken-123456", "raw": {"secret": "raw"}, "raw_claim": "private"})
    assert result == {"text": "***"}


def test_opencode_usage_metadata_deduplicates_without_private_text(isolated):
    payload = {"session_id": "fixture", "state": "idle", "usage": {
        "message_id": "message-fixture", "model": "fixture-model", "completed_at": 1791801000000,
        "input": 120, "output": 30, "cacheRead": 10, "cacheWrite": 0, "text": "private-marker"}}
    host_event("opencode", payload)
    host_event("opencode", payload)
    text = (isolated / "inbox/host-events.jsonl").read_text(encoding="utf-8")
    assert "private-marker" not in text
    result = AgentService().usage(refresh=True)
    assert result["snapshot"]["lifetime"]["tokens"] == 160
    assert result["snapshot"]["lifetime"]["calls"] == 1


def test_native_usage_alert_uses_existing_threshold_and_no_repeated_toast(isolated):
    payload = {"session_id": "fixture", "state": "UNKNOWN", "usage": {
        "message_id": "message-heavy", "model": "fixture-model", "completed_at": int(__import__("time").time() * 1000),
        "input": 500_000, "output": 0, "cacheRead": 0, "cacheWrite": 0}}
    first = host_event("opencode", payload)["messages"]
    assert any("500" in text and "厂商余额" in text for text in first)
    assert host_event("opencode", payload)["messages"] == []


def test_conversation_settings_persist_without_credential_output(isolated, monkeypatch):
    monkeypatch.setenv("MCPET_CITY", "北京")
    service = AgentService()
    result = service.configure(city="上海", lunch_time="12:15", reminders_enabled=False)
    assert result["city"] == "上海" and result["lunch_time"] == "12:15"
    assert "token" not in result and "key" not in result
    assert "上海" in (isolated / ".env").read_text(encoding="utf-8")
    assert service.reminders(datetime(2026, 10, 12, 12, 15))["messages"] == []


def test_settings_reject_implicit_or_missing_log_directories(isolated):
    service = AgentService()
    with pytest.raises(ValueError): service.configure(agent_roots={"claude": ""})
    with pytest.raises(ValueError): service.configure(agent_roots={"codex": str(isolated / "absent")})
    with pytest.raises(ValueError): service.configure(lunch_time="1:30")
    assert not (isolated / ".env").exists()


def test_native_opencode_plugin_routes_only_allowlisted_fields(isolated, monkeypatch):
    import shutil
    node = shutil.which("node")
    if not node:
        pytest.skip("Node unavailable; real plugin fixture not run")
    monkeypatch.setenv("MCPET_LUNCH_TIME", datetime.now().strftime("%H:%M"))
    install(isolated, "opencode")
    plugin = isolated / "plugin.mjs"
    plugin.write_text((isolated / ".opencode/plugins/mcpet.js").read_text(encoding="utf-8"), encoding="utf-8")
    script = '''import { McPet } from __PLUGIN__;
const toasts=[];
const hooks=await McPet({directory:__DIRECTORY__,client:{tui:{showToast:async(x)=>toasts.push(x)}}});
await hooks.event({event:{type:"session.status",properties:{sessionID:"fixture-plugin",status:{type:"busy"},prompt:"private-marker"}}});
await hooks.event({event:{type:"message.part.updated",properties:{part:{text:"private-marker"}}}});
await hooks.event({event:{type:"session.idle",properties:{sessionID:"fixture-plugin"}}});
console.log(JSON.stringify({toasts:toasts.length,message:toasts[0]?.body?.message}));'''.replace("__PLUGIN__", json.dumps(plugin.as_uri())).replace("__DIRECTORY__", json.dumps(str(isolated)))
    result = subprocess.run([node, "--input-type=module"], input=script, text=True,
                            encoding="utf-8", capture_output=True, timeout=20, env=dict(os.environ))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["toasts"] == 1
    assert json.loads(result.stdout)["message"].startswith("饭点到啦")
    text = (isolated / "inbox/host-events.jsonl").read_text(encoding="utf-8")
    assert "private-marker" not in text
    records = [json.loads(line) for line in text.splitlines()]
    assert [row["state"] for row in records] == ["working", "idle"]
