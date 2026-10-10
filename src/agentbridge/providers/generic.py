"""通用 provider —— 任何 Agent 都能接入的那一档。

前两个 provider（claude / codex）是在**适配别人已有的日志格式**，属于被动兼容：
Claude Code 改了格式我们就得跟着改。真正让这个项目「不绑死某个 Agent」的是这一档——
它定义了一份**我们自己的、公开的、稳定的**收件箱规范，任何 Agent（自研的、
小众的、还没被适配的）只要往目录里写这几行 JSON，就能被麦麦小怪兽读到。

规范全文见 `docs/AGENT_BRIDGE.md`。要点：

1. 目录里放 `*.jsonl`，每行一个事件，用 `kind` 区分类型。
2. **只追加**：用量事件写进去就不再改，程序靠字节偏移去重。
3. 进度可以两种写法二选一：
   - 追加式：往 jsonl 里写 `kind: "progress"`，取最后一条；
   - 覆盖式：写 `<session>.json` 单文件快照，每次覆盖（适合只关心当前值的 Agent）。
4. 字段名同时接受 camelCase 与 snake_case，容错优先。

用量事件：

    {"kind": "usage", "ts": 1760000000, "model": "step-3.5-flash",
     "input": 1200, "output": 340, "cacheRead": 0, "cacheWrite": 0,
     "session": "run-42", "key": "可选：稳定去重键"}

进度事件：

    {"kind": "progress", "ts": "2026-10-11T02:03:04Z", "session": "run-42",
     "state": "working", "project": "我的项目", "title": "重构登录模块",
     "contextUsed": 120000, "contextLimit": 200000, "backgroundTasks": 2}
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from ..context import context_limit
from ..records import ProgressRecord, UsageRecord
from .base import UsageBatch, iter_jsonl_files, read_from_offset, to_int
from .claude import parse_timestamp

_KIND_ALIASES = {"kind", "type", "event"}


def _kind_of(entry: dict) -> str:
    for name in _KIND_ALIASES:
        value = entry.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return ""


def _pick(entry: dict, *names: str) -> object:
    for name in names:
        if entry.get(name) is not None:
            return entry[name]
    return None


def _text(entry: dict, *names: str) -> str:
    value = _pick(entry, *names)
    return value.strip() if isinstance(value, str) else ""


class GenericProvider:
    """收件箱 provider。不假设任何厂商格式，只认我们自己的规范。"""

    id = "generic"
    label = "通用收件箱"

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
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                truncated = size < offset
                entries, new_offset = read_from_offset(path, offset)
                records: list[UsageRecord] = []
                for line_offset, entry in entries:
                    record = self._to_record(entry, key, line_offset)
                    if record is not None:
                        records.append(record)
                yield UsageBatch(
                    path=key, offset=new_offset, records=records, truncated=truncated
                )

    def _to_record(
        self, entry: dict, path_key: str, line_offset: int
    ) -> UsageRecord | None:
        if _kind_of(entry) != "usage":
            return None
        ts = parse_timestamp(_pick(entry, "ts", "timestamp", "time"))
        if ts <= 0:
            return None
        model = _text(entry, "model")
        input_tokens = to_int(_pick(entry, "input", "inputTokens", "input_tokens"))
        output_tokens = to_int(_pick(entry, "output", "outputTokens", "output_tokens"))
        cache_read = to_int(_pick(entry, "cacheRead", "cache_read", "cacheReadTokens"))
        cache_write = to_int(
            _pick(entry, "cacheWrite", "cache_write", "cacheWriteTokens")
        )
        if input_tokens + output_tokens + cache_read + cache_write <= 0:
            return None
        # 稳定键优先用作者自己给的；没给就用文件位置（要求只追加）
        stable = _text(entry, "key", "id")
        key = f"generic:{stable}" if stable else f"generic:{path_key}:{line_offset}"
        return UsageRecord(
            key=key,
            ts=ts,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_write_tokens=cache_write,
            cache_read_tokens=cache_read,
            source=self.id,
            session_id=_text(entry, "session", "sessionId", "session_id"),
        )

    # ---------------------------------------------------------------- 进度
    def iter_progress(self) -> Iterator[ProgressRecord]:
        for root in self._roots:
            # 覆盖式：每个 <session>.json 是一份当前快照
            for path in sorted(root.glob("*.json")):
                record = self._progress_from_snapshot(path)
                if record is not None:
                    yield record
            # 追加式：jsonl 里的 progress 事件，取每个会话最后一条
            latest: dict[str, ProgressRecord] = {}
            for path in iter_jsonl_files(root):
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                entries, _ = read_from_offset(path, 0)
                for _, entry in entries:
                    if _kind_of(entry) != "progress":
                        continue
                    record = self._progress_from_entry(entry, path)
                    if record is None:
                        continue
                    previous = latest.get(record.session_id)
                    if previous is None or record.updated_at >= previous.updated_at:
                        latest[record.session_id] = record
                _ = size
            yield from latest.values()

    def _progress_from_entry(self, entry: dict, path: Path) -> ProgressRecord | None:
        session_id = _text(entry, "session", "sessionId", "session_id") or path.stem
        ts = parse_timestamp(_pick(entry, "ts", "timestamp", "time"))
        return self._build(entry, session_id, ts)

    def _progress_from_snapshot(self, path: Path) -> ProgressRecord | None:
        import json

        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(entry, dict):
            return None
        kind = _kind_of(entry)
        if kind and kind != "progress":
            return None
        session_id = _text(entry, "session", "sessionId", "session_id") or path.stem
        ts = parse_timestamp(_pick(entry, "ts", "timestamp", "time"))
        if ts <= 0:
            try:
                ts = path.stat().st_mtime
            except OSError:
                ts = 0.0
        return self._build(entry, session_id, ts)

    def _build(self, entry: dict, session_id: str, ts: float) -> ProgressRecord:
        model = _text(entry, "model")
        used = to_int(_pick(entry, "contextUsed", "context_used", "contextTokens"))
        limit = to_int(_pick(entry, "contextLimit", "context_limit", "contextWindow"))
        if limit <= 0 and used > 0:
            limit = context_limit(model, used)
        return ProgressRecord(
            source=self.id,
            session_id=session_id,
            state=_text(entry, "state", "status") or "idle",
            project=_text(entry, "project"),
            cwd=_text(entry, "cwd", "path"),
            title=_text(entry, "title", "task", "summary"),
            model=model,
            context_used=used,
            context_limit=limit,
            background_tasks=to_int(_pick(entry, "backgroundTasks", "background_tasks")),
            detail=_text(entry, "detail", "message"),
            updated_at=ts,
        )
