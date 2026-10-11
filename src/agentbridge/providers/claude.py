"""Claude Code transcript provider。

数据形态（Claude Code 自己写的 JSONL，属于**公开的数据接口**，不是私有实现）：
每个会话一个文件，路径形如 `<root>/<encoded-cwd>/<session-id>.jsonl`，
子代理 transcript 嵌在 `<root>/<proj>/<session>/subagents/**.jsonl`。

每一行是一个事件，assistant 行携带：

    {"type": "assistant",
     "sessionId": "...", "cwd": "...", "timestamp": "2026-10-11T02:03:04.000Z",
     "message": {"id": "msg_...", "model": "claude-sonnet-4-5",
                 "usage": {"input_tokens": 4, "output_tokens": 812,
                           "cache_read_input_tokens": 18322,
                           "cache_creation_input_tokens": 4096}}}

**流式修正**：同一个 `message.id` 会随响应流式写入多行，后面的行 output_tokens
更大。provider 只负责产出「原始快照」，去重取最大值留给聚合层——
provider 保持无状态，聚合层统一处理（见 metering/usage.py）。
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from ..context import context_limit
from ..records import ProgressRecord, UsageRecord
from .base import (
    UsageBatch,
    iter_jsonl_files,
    iter_offset_batches,
    read_tail,
    recent_jsonl_files,
    to_float,
    to_int,
)

_TITLE_TYPES = {"custom-title", "agent-name"}
_SECRET_RE = re.compile(
    r"\b(api[_-]?key|authorization|bearer|password|passwd|secret|token|private[_-]?key)\b"
    r"|sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}",
    re.IGNORECASE,
)
_TITLE_MAX = 80


def _is_subagent(entry: dict) -> bool:
    return (
        entry.get("isSidechain") is True
        or entry.get("isSubagent") is True
        or entry.get("is_subagent") is True
    )


def _usage_of(entry: dict) -> dict | None:
    message = entry.get("message")
    if not isinstance(message, dict):
        return None
    usage = message.get("usage")
    return usage if isinstance(usage, dict) else None


def _text_of(content: object) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") in {"text", "output_text"}:
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n\n".join(parts)


def parse_timestamp(value: object) -> float:
    """ISO-8601（含 Z）→ Unix 秒。各 provider 都用这个，别各写一份。"""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if not isinstance(value, str) or not value.strip():
        return 0.0
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return to_float(value)


class ClaudeProvider:
    id = "claude"
    label = "Claude Code"

    # 进度扫描只看最近多少个会话文件。见 base.recent_jsonl_files 的说明。
    PROGRESS_FILE_LIMIT = 80

    def __init__(self, roots: list[Path]) -> None:
        self._roots = [Path(r) for r in roots]

    def roots(self) -> list[Path]:
        return list(self._roots)

    # ---------------------------------------------------------------- 用量
    def iter_usage(self, cursors: dict[str, int]) -> Iterator[UsageBatch]:
        for root in self._roots:
            for path in iter_jsonl_files(root):
                key = str(path)
                offset = cursors.get(key, 0)
                truncated = path.stat().st_size < offset
                for entries, new_offset in iter_offset_batches(path, offset):
                    records = []
                    for line_offset, entry in entries:
                        record = self._to_record(entry)
                        if record is not None:
                            records.append(record)
                    yield UsageBatch(
                        path=key, offset=new_offset, records=records, truncated=truncated
                    )
                    truncated = False

    def _to_record(self, entry: dict) -> UsageRecord | None:
        if entry.get("type") != "assistant" or entry.get("isApiErrorMessage") is True:
            return None
        usage = _usage_of(entry)
        if not usage:
            return None
        message = entry.get("message") or {}
        message_id = message.get("id")
        if not message_id:
            return None
        model = str(message.get("model") or "")
        # Claude Code 用 `<synthetic>` 标记自己注入的消息（如自动继续），
        # 不是真实模型调用。计入会凭空多出一个「模型」，也会虚增用量。
        if model.startswith("<"):
            return None
        ts = parse_timestamp(entry.get("timestamp"))
        if ts <= 0:
            return None
        return UsageRecord(
            key=f"claude:{message_id}",
            ts=ts,
            model=model,
            input_tokens=to_int(usage.get("input_tokens")),
            output_tokens=to_int(usage.get("output_tokens")),
            cache_write_tokens=to_int(usage.get("cache_creation_input_tokens")),
            cache_read_tokens=to_int(usage.get("cache_read_input_tokens")),
            source=self.id,
            session_id=str(entry.get("sessionId") or ""),
        )

    # ---------------------------------------------------------------- 进度
    def iter_progress(self) -> Iterator[ProgressRecord]:
        for root in self._roots:
            for path in recent_jsonl_files(root, self.PROGRESS_FILE_LIMIT):
                entries = read_tail(path)
                if not entries:
                    continue
                record = self._progress_from(entries, path)
                if record is not None:
                    yield record

    def _progress_from(self, entries: list[dict], path: Path) -> ProgressRecord | None:
        session_id = _last_str(entries, "sessionId") or path.stem
        cwd = _last_str(entries, "cwd")
        title = _title_of(entries)

        used = limit = 0
        model = ""
        ts = 0.0
        for entry in reversed(entries):
            if entry.get("type") != "assistant" or entry.get("isApiErrorMessage") is True:
                continue
            if _is_subagent(entry):
                continue
            usage = _usage_of(entry)
            if not usage:
                continue
            candidate = (
                to_int(usage.get("input_tokens"))
                + to_int(usage.get("cache_read_input_tokens"))
                + to_int(usage.get("cache_creation_input_tokens"))
            )
            if candidate <= 0:
                continue
            model = str((entry.get("message") or {}).get("model") or "")
            used = candidate
            limit = context_limit(model, candidate)
            ts = parse_timestamp(entry.get("timestamp"))
            break

        if used <= 0 and not title and entries[-1].get("type") != "task_complete":
            return None

        last_type = entries[-1].get("type") if entries else ""
        latest_ts = max((parse_timestamp(e.get("timestamp")) for e in entries), default=0.0)
        complete = last_type == "task_complete"
        return ProgressRecord(
            source=self.id,
            session_id=session_id,
            state="done" if complete else "working" if last_type == "assistant" else "idle",
            project=_project_name(cwd, path),
            cwd=cwd,
            title=title,
            model=model,
            context_used=used,
            context_limit=limit,
            updated_at=latest_ts or ts or _mtime(path),
            completed_at=latest_ts if complete else 0.0,
            completion_id=str(entries[-1].get("task_id") or latest_ts) if complete else "",
            context_limit_estimated=limit > 0,
        )


def _last_str(entries: list[dict], field: str) -> str:
    for entry in reversed(entries):
        value = entry.get(field)
        if isinstance(value, str) and value:
            return value
    return ""


def _title_of(entries: list[dict]) -> str:
    title = ""
    for entry in entries:
        if entry.get("type") not in _TITLE_TYPES:
            continue
        for field in ("customTitle", "title", "custom_title", "agentName", "agent_name"):
            value = entry.get(field)
            if isinstance(value, str) and value.strip():
                title = value.strip()[:_TITLE_MAX]
    if title:
        return title
    return _prompt_title(entries)


def _prompt_title(entries: list[dict]) -> str:
    for entry in entries:
        if entry.get("type") != "user":
            continue
        text = _text_of((entry.get("message") or {}).get("content"))
        for line in text.splitlines():
            line = line.strip()
            if not line or _SECRET_RE.search(line):
                continue
            return line[:40] + "…" if len(line) > 40 else line
    return ""


def _project_name(cwd: str, path: Path) -> str:
    if cwd:
        return Path(cwd).name
    # Claude 把 cwd 里的 / 和 _ 都编码成 -，无法无损还原，取末段做个近似
    return path.parent.name


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0
