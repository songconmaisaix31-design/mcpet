"""Provider 协议与共享的 JSONL 读写工具。

这里沉淀的是从 LLMPET 的 `transcript.js` / `metering.js` 里提炼出来的、
**与具体 Agent 无关**的那部分机制：

    read_tail()        只读文件尾部 N KB（进度只需要当前轮，不必扫全量）
    read_from_offset() 从字节偏移续读（计量要增量，避免每次重扫 GB 级日志）
    iter_jsonl_files() 递归找 JSONL，深度封顶（subagent 会嵌好几层）

三个 provider 共用这些，差异只留在「怎么把一行 JSON 翻译成 UsageRecord」。
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from ..records import ProgressRecord, UsageRecord

# 进度只需要当前轮，读尾部即可。256 KB 足够容纳一整个长回答。
TAIL_BYTES = 256 * 1024

# 头部只需拿到会话元信息（session_meta / turn_context），64 KB 绰绰有余。
HEAD_BYTES = 64 * 1024

# 计量必须扫全量，但 subagent 嵌套深度封顶，避免病态目录把 IO 打满。
# LLMPET 用 6：projects/<proj>/<session>/subagents/workflows/<wf>/
MAX_DEPTH = 6


@dataclass
class UsageBatch:
    """一个文件的增量扫描结果。

    按「文件」而不是「记录」为粒度返回，是因为偏移必须**每个文件推进一次**——
    哪怕这个文件这轮没有新记录，偏移也得记住，否则下一轮还会从头扫。
    早先按记录粒度返回、用 None 当哨兵推进偏移，读起来像 bug 现场，已改掉。
    """

    path: str
    offset: int = 0
    records: list[UsageRecord] = field(default_factory=list)
    truncated: bool = False   # 文件变小被重读，调用方可据此记一笔诊断


@runtime_checkable
class Provider(Protocol):
    """一个数据源适配器。无状态：不碰持久化，偏移由调用方写回。"""

    id: str
    label: str

    def roots(self) -> list[Path]:
        ...

    def iter_usage(self, cursors: dict[str, int]) -> Iterator[UsageBatch]:
        """增量产出一批用量记录，附带每个文件的新字节偏移。"""
        ...

    def iter_progress(self) -> Iterator[ProgressRecord]:
        ...


def read_tail(path: Path, max_bytes: int = TAIL_BYTES) -> list[dict]:
    """读文件尾部并解析 JSONL。解析失败的行静默丢弃（写一半的行很常见）。"""
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            start = max(0, size - max_bytes)
            handle.seek(start)
            blob = handle.read()
    except OSError:
        return []

    text = blob.decode("utf-8", errors="replace")
    lines = text.split("\n")
    if size > max_bytes and lines:
        lines = lines[1:]  # 丢掉被截断的首行

    out: list[dict] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def read_head(path: Path, max_bytes: int = HEAD_BYTES) -> list[dict]:
    """读文件头部并解析 JSONL。

    必须单独有一个读头函数：Codex rollout 把 `session_meta` / `turn_context`
    写在**文件最前面**，而进度快照要的 `token_count` 在**最后面**。只读尾部
    会拿不到会话 id 和模型名——表现就是所有会话都显示成所在目录名。
    """
    try:
        with path.open("rb") as handle:
            blob = handle.read(max_bytes)
    except OSError:
        return []

    text = blob.decode("utf-8", errors="replace")
    lines = text.split("\n")
    if len(lines) > 1:
        lines = lines[:-1]  # 最后一行可能是半行，丢掉

    out: list[dict] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def read_from_offset(path: Path, offset: int) -> tuple[list[tuple[int, dict]], int]:
    """从字节偏移续读 JSONL，返回 ([(行起始偏移, 对象)], 新偏移)。

    带上「行起始偏移」是必须的：Codex 的 rollout 里每个 `token_count` 事件都是
    只追加、只计一次，去重键只能从文件位置推。不给偏移的话，同一个事件在
    两次扫描之间就分不清了。

    文件变小（被轮转 / 截断）时从 0 重读，否则会永久漏掉内容。
    """
    try:
        size = path.stat().st_size
    except OSError:
        return [], offset
    if size < offset:
        offset = 0
    if size == offset:
        return [], offset

    try:
        with path.open("rb") as handle:
            handle.seek(offset)
            blob = handle.read()
    except OSError:
        return [], offset

    # 只消费到最后一个换行，避免把半行写进状态导致丢数据
    last_newline = blob.rfind(b"\n")
    if last_newline < 0:
        return [], offset
    consumed = blob[: last_newline + 1]
    new_offset = offset + len(consumed)

    out: list[tuple[int, dict]] = []
    cursor = offset
    for raw_line in consumed.split(b"\n"):
        line_start = cursor
        cursor += len(raw_line) + 1  # +1 补回被 split 吃掉的 \n
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict):
            out.append((line_start, obj))
    return out, new_offset


def iter_jsonl_files(root: Path, max_depth: int = MAX_DEPTH) -> Iterator[Path]:
    """递归产出 root 下的 .jsonl 文件，深度封顶。

    用 os.walk 而非 Path.rglob，是为了能在超深目录处及时剪枝——rglob 会把
    整棵树先走完，遇到 subagent 展开很深的项目会明显变慢。
    """
    root = Path(root)
    if not root.is_dir():
        return
    root_depth = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root):
        depth = len(Path(dirpath).parts) - root_depth
        if depth >= max_depth:
            dirnames[:] = []
        # 跳过明显是缓存/版本控制的目录，减少无谓 IO
        dirnames[:] = [
            d for d in dirnames if d not in {".git", "node_modules", "__pycache__", ".venv"}
        ]
        for name in filenames:
            if name.endswith(".jsonl"):
                yield Path(dirpath) / name


def recent_jsonl_files(root: Path, limit: int, max_depth: int = MAX_DEPTH) -> list[Path]:
    """按修改时间倒序取最近 limit 个 JSONL。

    进度只需要「最近有哪些会话在动」，不需要扫全量历史。一台机器上可能躺着
    几千个历史 rollout，全读一遍是 2 秒起步；只看最近几十个是几十毫秒。
    列表页最多显示十几个会话，留 5 倍余量足够覆盖「活跃的排在后面」的情况。
    """
    if limit <= 0:
        return []
    files: list[tuple[float, Path]] = []
    for path in iter_jsonl_files(root, max_depth):
        try:
            files.append((path.stat().st_mtime, path))
        except OSError:
            continue
    files.sort(key=lambda row: row[0], reverse=True)
    return [path for _, path in files[:limit]]


def to_float(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def to_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0
