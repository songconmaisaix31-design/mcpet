"""Host hooks: allowlisted event metadata only, never transcripts or prompts."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import time

from . import config
from .agent_local import data_lock
from .agent_service import AgentService

CLAUDE_STATES = {"SessionStart": "idle", "UserPromptSubmit": "working",
                 "PreToolUse": "working", "PostToolUse": "working",
                 "PermissionRequest": "waiting", "Stop": "idle", "SessionEnd": "idle"}


def host_event(host, payload):
    if host == "claude":
        state = CLAUDE_STATES.get(payload.get("hook_event_name"), "UNKNOWN")
        session = payload.get("session_id", "")
    else:
        state = payload.get("state", "UNKNOWN")
        session = payload.get("session_id", "")
    if state not in {"working", "thinking", "waiting", "idle", "error", "UNKNOWN"}:
        state = "UNKNOWN"
    if not isinstance(session, str) or not session or len(session) > 256:
        return {"messages": []}
    project = payload.get("cwd", "")
    project = Path(project).name if isinstance(project, str) else ""
    # Do not consume transcript_path, prompt, messages, tool_input or tool_output.
    record = {"kind": "progress", "session": f"{host}:{session}", "ts": time.time(),
              "state": state, "project": project, "title": f"{host} 会话",
              "contextUsed": 0, "contextLimit": 0}
    records = [record]
    # OpenCode exposes completed assistant usage in message.updated metadata.
    # This is not message text or task-completion evidence. Existing generic
    # provider deduplicates by the host's original message ID.
    usage = payload.get("usage") if host == "opencode" else None
    if isinstance(usage, dict):
        message = usage.get("message_id")
        model = usage.get("model")
        timestamp = usage.get("completed_at")
        fields = ("input", "output", "cacheRead", "cacheWrite")
        amounts = [usage.get(key) for key in fields]
        valid = (isinstance(message, str) and 0 < len(message) <= 256
                 and isinstance(model, str) and 0 < len(model) <= 256
                 and isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool)
                 and math.isfinite(timestamp) and timestamp > 0
                 and all(isinstance(amount, int) and not isinstance(amount, bool)
                         and 0 <= amount <= 1_000_000_000 for amount in amounts))
        if valid:
            records.append({"kind": "usage", "id": f"opencode:{message}", "session": f"opencode:{session}",
                            "ts": timestamp / 1000, "model": model, **dict(zip(fields, amounts))})
    with data_lock():
        inbox = config.data_dir() / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        # Each write is one append under the same cross-host local lock.
        with (inbox / "host-events.jsonl").open("a", encoding="utf-8") as stream:
            for item in records:
                stream.write(json.dumps(item, ensure_ascii=False) + "\n")
    # Only consume a daily reminder when the host has a delivery channel.
    if host == "opencode" or payload.get("hook_event_name") in {"SessionStart", "UserPromptSubmit"}:
        service = AgentService()
        result = service.reminders()
        if len(records) > 1:
            result["messages"].extend(service.host_usage_reminder())
        return result
    return {"messages": []}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", choices=("claude", "opencode"), required=True)
    args = parser.parse_args()
    try:
        # Bound the input. JSON hook payloads may contain private prompt data;
        # only the allowlisted fields above are used and none are echoed.
        data = sys.stdin.buffer.read(256 * 1024 + 1)
        if len(data) > 256 * 1024:
            return 0
        payload = json.loads(data.decode("utf-8"))
        if not isinstance(payload, dict):
            return 0
        config.load_env()
        reminders = host_event(args.host, payload)
        if args.host == "claude":
            if payload.get("hook_event_name") in {"UserPromptSubmit", "SessionStart"}:
                context = "McPet 已接入当前会话。需要时使用 mcpet 工具；不启动单独窗口或模型。"
                if reminders["messages"]:
                    context += "\n" + "\n".join(reminders["messages"])
                print(json.dumps({"hookSpecificOutput": {"hookEventName": payload["hook_event_name"],
                                  "additionalContext": context}}, ensure_ascii=False))
        else:
            print(json.dumps(reminders, ensure_ascii=False))
    except Exception:
        # A malformed/disconnected hook must not block the user's coding Agent.
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
