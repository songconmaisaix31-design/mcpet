"""OpenAI Codex rollout provider。

数据形态（Codex CLI 自己写的 rollout JSONL，只读）：
    <root>/<YYYY>/<MM>/<DD>/rollout-<ts>-<uuid>.jsonl

每行 `{timestamp, type, payload}`。我们关心的两类：

    {"type": "turn_context", "payload": {"model": "gpt-5-codex", ...}}
    {"type": "event_msg",
     "payload": {"type": "token_count",
                 "info": {"total_token_usage": {...},   # 累计，会因压缩而重置
                          "last_token_usage": {...}}}}  # 本次请求的精确用量

**为什么记 `last_token_usage` 而不是累计差值**：LLMPET 的注释写得很清楚——累计
计数器在 compaction / 上下文重建后会重置，用「累计正增量」会把同一天的用量
放大 10 倍以上。所以每个只追加的 `token_count` 事件记一次 `last_token_usage`，
去重键取该事件在文件中的字节偏移（只追加，偏移天然唯一）。

**为什么要把 cached / reasoning 拆出去**：Codex 的 `cached_input_tokens` 是
`input_tokens` 的子集、`reasoning_output_tokens` 是 `output_tokens` 的子集。
直接相加会重复计数。这里归一成互斥桶：

    input_tokens      = 未命中缓存的输入（input − cached）
    cache_read_tokens = cached_input_tokens
    output_tokens     = 全部输出（含 reasoning，两者同价）
    cache_write       = 0（Codex 不报缓存写入）

这样 `input + output == total_tokens`，与 Codex 自己报的总量对得上。
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from ..context import context_limit
from ..records import ProgressRecord, UsageRecord
from .base import (
    UsageBatch,
    iter_jsonl_files,
    read_from_offset,
    read_head,
    read_tail,
    recent_jsonl_files,
    to_int,
)
from .claude import parse_timestamp


def _usage_from(raw: object) -> dict[str, int] | None:
    if not isinstance(raw, dict):
        return None

    def pick(*names: str) -> int:
        for name in names:
            if raw.get(name) is not None:
                return to_int(raw.get(name))
        return 0

    total_input = pick("input_tokens", "inputTokens")
    cached = pick("cached_input_tokens", "cachedInputTokens")
    output = pick("output_tokens", "outputTokens")
    if total_input <= 0 and output <= 0:
        return None
    return {
        "input": max(0, total_input - cached),
        "cached": max(0, cached),
        "output": max(0, output),
    }


class CodexProvider:
    id = "codex"
    label = "OpenAI Codex"

    # 进度扫描只看最近多少个 rollout。见 base.recent_jsonl_files 的说明。
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
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                truncated = size < offset
                entries, new_offset = read_from_offset(path, offset)

                # 模型名可能出现在 token_count 之前的 turn_context 里；
                # 增量扫描时它可能在上一批就已经消费掉了，所以回读一次文件头。
                model = _model_hint(path)
                records: list[UsageRecord] = []
                for line_offset, entry in entries:
                    record = self._to_record(entry, key, line_offset, model)
                    if record is not None:
                        records.append(record)
                yield UsageBatch(
                    path=key, offset=new_offset, records=records, truncated=truncated
                )

    def _to_record(
        self, entry: dict, path_key: str, line_offset: int, model_hint: str
    ) -> UsageRecord | None:
        if entry.get("type") != "event_msg":
            return None
        payload = entry.get("payload")
        if not isinstance(payload, dict) or payload.get("type") != "token_count":
            return None
        info = payload.get("info")
        if not isinstance(info, dict):
            return None
        usage = _usage_from(info.get("last_token_usage") or info.get("lastTokenUsage"))
        if usage is None:
            return None
        ts = parse_timestamp(entry.get("timestamp"))
        if ts <= 0:
            return None
        return UsageRecord(
            key=f"codex:{path_key}:{line_offset}",
            ts=ts,
            model=model_hint,
            input_tokens=usage["input"],
            output_tokens=usage["output"],
            cache_write_tokens=0,
            cache_read_tokens=usage["cached"],
            source=self.id,
        )

    # ---------------------------------------------------------------- 进度
    def iter_progress(self) -> Iterator[ProgressRecord]:
        for root in self._roots:
            for path in recent_jsonl_files(root, self.PROGRESS_FILE_LIMIT):
                # 头拿会话元信息，尾拿最新用量——两个都在才有完整快照
                head = read_head(path)
                tail = read_tail(path)
                if not head and not tail:
                    continue
                record = self._progress_from(head, tail, path)
                if record is not None:
                    yield record

    def _progress_from(
        self, head: list[dict], tail: list[dict], path: Path
    ) -> ProgressRecord | None:
        session_id = ""
        cwd = ""
        model = ""
        used = 0
        limit = 0
        ts = 0.0
        title = ""

        # session_meta / turn_context 在文件头
        for entry in head:
            payload = entry.get("payload")
            if not isinstance(payload, dict):
                continue
            kind = entry.get("type")
            if kind == "session_meta":
                session_id = str(payload.get("id") or payload.get("session_id") or session_id)
                cwd = str(payload.get("cwd") or payload.get("workdir") or cwd)
            elif kind == "turn_context":
                model = str(payload.get("model") or model)

        # 最新用量与标题在文件尾
        for entry in tail:
            payload = entry.get("payload")
            if not isinstance(payload, dict):
                continue
            kind = entry.get("type")
            if kind == "session_meta":
                session_id = str(payload.get("id") or payload.get("session_id") or session_id)
                cwd = str(payload.get("cwd") or payload.get("workdir") or cwd)
            elif kind == "turn_context":
                model = str(payload.get("model") or model)
            elif kind == "event_msg" and payload.get("type") == "token_count":
                info = payload.get("info")
                info = info if isinstance(info, dict) else {}
                usage = _usage_from(
                    info.get("last_token_usage") or info.get("lastTokenUsage")
                )
                if usage is not None:
                    used = usage["input"] + usage["cached"]
                    limit = context_limit(model, used)
                    ts = parse_timestamp(entry.get("timestamp")) or ts
            elif kind == "event_msg" and payload.get("type") == "user_message":
                text = payload.get("message") or payload.get("text")
                if isinstance(text, str) and text.strip() and not title:
                    first = text.strip().splitlines()[0]
                    title = first[:40] + "…" if len(first) > 40 else first

        if not session_id:
            session_id = path.stem
        if used <= 0 and not title:
            return None

        last_kind = _last_decisive_kind(tail)
        return ProgressRecord(
            source=self.id,
            session_id=session_id,
            state=_state_for(last_kind),
            project=_project_label(cwd, path),
            cwd=cwd,
            title=title,
            model=model,
            context_used=used,
            context_limit=limit,
            updated_at=ts or _mtime(path),
        )


def _project_label(cwd: str, path: Path) -> str:
    """会话显示名。

    有 cwd 就用它的末段（真实项目名）；没有就退到文件名——但**不能退到父目录名**，
    Codex 的 rollout 按 `<年>/<月>/<日>/` 存放，父目录名会变成 "10" 这种日期数字，
    列表里一排 "10" 谁也认不出谁。
    """
    if cwd:
        return Path(cwd).name
    stem = path.stem
    if stem.startswith("rollout-"):
        stem = stem[len("rollout-"):]
    return stem[:24] or path.parent.name


# 决定会话状态的事件类型。从尾部往前找第一条**有判定力**的事件，
# 而不是简单看最后一条——中间可能夹着 token_count 这类不表态的记录。
_WORKING_KINDS = frozenset({
    "exec_command", "apply_patch", "function_call", "custom_tool_call", "reasoning",
})
_IDLE_KINDS = frozenset({
    "agent_message", "task_complete", "turn_aborted", "user_message", "error",
})


def _last_decisive_kind(entries: list[dict]) -> str:
    for entry in reversed(entries):
        payload = entry.get("payload")
        if isinstance(payload, dict):
            kind = str(payload.get("type") or "")
        else:
            kind = str(entry.get("type") or "")
        if kind in _WORKING_KINDS or kind in _IDLE_KINDS:
            return kind
    return ""


def _state_for(kind: str) -> str:
    if kind in _WORKING_KINDS:
        return "working"
    if kind == "error":
        return "error"
    return "idle"


def _model_hint(path: Path) -> str:
    """从文件头找一次模型名（turn_context 通常在最前面几行）。"""
    for entry in read_head(path):
        payload = entry.get("payload")
        if isinstance(payload, dict) and payload.get("model"):
            return str(payload["model"])
    return ""


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0
