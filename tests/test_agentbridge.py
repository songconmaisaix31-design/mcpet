"""agentbridge 的离线测试。

全部用合成数据，**不依赖本机是否装了 Claude Code / Codex**——这正是这一层
存在的意义，测试也必须证明这一点。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.agentbridge import build_providers, resolve_roots
from src.agentbridge.context import context_limit, context_percent
from src.agentbridge.providers.base import (
    iter_jsonl_files,
    read_from_offset,
    read_head,
    read_tail,
    recent_jsonl_files,
)
from src.agentbridge.providers.claude import ClaudeProvider
from src.agentbridge.providers.codex import CodexProvider
from src.agentbridge.providers.generic import GenericProvider


def write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    return path


# ------------------------------------------------------------------ 根目录解析


def test_env_override_beats_config(tmp_path):
    env_dir = tmp_path / "from-env"
    cfg_dir = tmp_path / "from-config"
    env_dir.mkdir()
    cfg_dir.mkdir()
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"agentRoots": {"claude": str(cfg_dir)}}), encoding="utf-8")

    roots = resolve_roots(
        config_path=cfg,
        env={"MAIMAI_AGENT_ROOT_CLAUDE": str(env_dir)},
        provider_ids=["claude"],
    )
    assert roots.for_provider("claude") == [env_dir.resolve()]
    assert roots.sources["claude"] == "MAIMAI_AGENT_ROOT_CLAUDE"


def test_config_used_when_env_absent(tmp_path):
    cfg_dir = tmp_path / "from-config"
    cfg_dir.mkdir()
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"agentRoots": {"codex": str(cfg_dir)}}), encoding="utf-8")

    roots = resolve_roots(config_path=cfg, env={}, provider_ids=["codex"])
    assert roots.for_provider("codex") == [cfg_dir.resolve()]
    assert roots.sources["codex"] == "配置文件"


def test_missing_directory_is_declared_but_not_active(tmp_path):
    """别的机器上没装某个 Agent 是常态：声明出来，但不当作可用数据源。"""
    missing = tmp_path / "nope"
    roots = resolve_roots(
        config_path=tmp_path / "none.json",
        env={"MAIMAI_AGENT_ROOT_CLAUDE": str(missing)},
        provider_ids=["claude"],
    )
    assert roots.for_provider("claude") == []
    assert roots.declared["claude"] == [missing.resolve()]
    assert roots.active_ids() == []
    assert build_providers(roots) == []
    assert any("不存在，已跳过" in line for line in roots.describe())


def test_batch_env_roots_parsing(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    roots = resolve_roots(
        config_path=tmp_path / "none.json",
        env={"MAIMAI_AGENT_ROOTS": f"claude={a},generic={b}"},
        provider_ids=["claude", "generic"],
    )
    assert roots.for_provider("claude") == [a.resolve()]
    assert roots.for_provider("generic") == [b.resolve()]


# ------------------------------------------------------------------ JSONL 工具


def test_read_from_offset_is_incremental(tmp_path):
    path = write_jsonl(tmp_path / "a.jsonl", [{"n": 1}, {"n": 2}])
    rows, offset = read_from_offset(path, 0)
    assert [row for _, row in rows] == [{"n": 1}, {"n": 2}]
    assert offset == path.stat().st_size

    # 再读一次：没有新内容
    rows2, offset2 = read_from_offset(path, offset)
    assert rows2 == []
    assert offset2 == offset

    # 追加后只读到新增的那条
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"n": 3}) + "\n")
    rows3, _ = read_from_offset(path, offset)
    assert [row for _, row in rows3] == [{"n": 3}]


def test_read_from_offset_ignores_partial_trailing_line(tmp_path):
    path = tmp_path / "a.jsonl"
    path.write_bytes(b'{"n": 1}\n{"n": 2}')  # 第二行没写完
    rows, offset = read_from_offset(path, 0)
    assert [row for _, row in rows] == [{"n": 1}]
    # 偏移只推进到完整行末尾，半行下次还能读到
    assert offset == len(b'{"n": 1}\n')


def test_read_from_offset_resets_when_file_shrinks(tmp_path):
    path = write_jsonl(tmp_path / "a.jsonl", [{"n": 1}, {"n": 2}, {"n": 3}])
    _, offset = read_from_offset(path, 0)
    path.write_text(json.dumps({"n": 9}) + "\n", encoding="utf-8")  # 被轮转
    rows, new_offset = read_from_offset(path, offset)
    assert [row for _, row in rows] == [{"n": 9}]
    assert new_offset == path.stat().st_size


def test_read_head_and_tail_split(tmp_path):
    rows = [{"i": i} for i in range(50)]
    path = write_jsonl(tmp_path / "big.jsonl", rows)
    head = read_head(path, max_bytes=64)
    tail = read_tail(path, max_bytes=64)
    assert head and tail
    assert head[0] == {"i": 0}
    assert tail[-1] == {"i": 49}


def test_recent_jsonl_files_sorted_by_mtime(tmp_path):
    import os
    import time

    old = write_jsonl(tmp_path / "old.jsonl", [{"n": 1}])
    new = write_jsonl(tmp_path / "new.jsonl", [{"n": 2}])
    os.utime(old, (time.time() - 3600, time.time() - 3600))
    assert recent_jsonl_files(tmp_path, 1) == [new]
    assert set(recent_jsonl_files(tmp_path, 10)) == {old, new}


def test_iter_jsonl_files_prunes_depth(tmp_path):
    deep = tmp_path / "a" / "b" / "c" / "d"
    deep.mkdir(parents=True)
    (deep / "deep.jsonl").write_text("{}\n", encoding="utf-8")
    assert list(iter_jsonl_files(tmp_path, max_depth=2)) == []


# ------------------------------------------------------------------ 上下文窗口


@pytest.mark.parametrize(
    "model,used,expected",
    [
        ("claude-sonnet-4-5", 1000, 200_000),
        ("claude-sonnet-4-5-1m", 1000, 1_000_000),
        ("claude-sonnet-4-5[1m]", 1000, 1_000_000),
        ("gpt-4.1", 1000, 1_000_000),
        ("deepseek-v3", 1000, 128_000),
        ("step-3.5-flash", 1000, 65_536),
        # 顶穿 200k → 必然是更大的窗口，否则这次请求发不出去
        ("unknown-model", 250_000, 1_000_000),
    ],
)
def test_context_limit(model, used, expected):
    assert context_limit(model, used) == expected


def test_context_percent_clamped():
    assert context_percent(0, 0) == 0
    assert context_percent(50, 100) == 50
    assert context_percent(500, 100) == 100


# ------------------------------------------------------------------ Claude


def claude_assistant(message_id: str, model: str, ts: str, **usage) -> dict:
    return {
        "type": "assistant",
        "sessionId": "sess-1",
        "cwd": "/home/dev/myproject",
        "timestamp": ts,
        "message": {"id": message_id, "model": model, "usage": usage},
    }


def test_claude_usage_records(tmp_path):
    path = write_jsonl(
        tmp_path / "sess.jsonl",
        [
            {"type": "user", "message": {"content": "帮我改个 bug"}, "sessionId": "sess-1"},
            claude_assistant(
                "msg_1", "claude-sonnet-4-5", "2026-10-11T02:00:00Z",
                input_tokens=100, output_tokens=50,
                cache_read_input_tokens=1000, cache_creation_input_tokens=200,
            ),
        ],
    )
    provider = ClaudeProvider([tmp_path])
    batches = list(provider.iter_usage({}))
    assert len(batches) == 1
    record = batches[0].records[0]
    assert record.key == "claude:msg_1"
    assert record.input_tokens == 100
    assert record.output_tokens == 50
    assert record.cache_read_tokens == 1000
    assert record.cache_write_tokens == 200
    assert record.total_tokens == 1350
    assert record.model == "claude-sonnet-4-5"
    assert batches[0].path == str(path)


def test_claude_skips_synthetic_messages(tmp_path):
    write_jsonl(
        tmp_path / "sess.jsonl",
        [
            claude_assistant("<synthetic>", "<synthetic>", "2026-10-11T02:00:00Z",
                             input_tokens=10, output_tokens=10),
        ],
    )
    batches = list(ClaudeProvider([tmp_path]).iter_usage({}))
    assert batches[0].records == []


def test_claude_skips_api_error_entries(tmp_path):
    entry = claude_assistant("msg_err", "claude-sonnet-4-5", "2026-10-11T02:00:00Z",
                             input_tokens=10, output_tokens=10)
    entry["isApiErrorMessage"] = True
    write_jsonl(tmp_path / "sess.jsonl", [entry])
    batches = list(ClaudeProvider([tmp_path]).iter_usage({}))
    assert batches[0].records == []


def test_claude_progress_from_tail(tmp_path):
    write_jsonl(
        tmp_path / "sess.jsonl",
        [
            {"type": "user", "sessionId": "sess-1", "cwd": "/home/dev/myproject",
             "message": {"content": "重构登录模块\n第二行"}},
            claude_assistant("msg_1", "claude-sonnet-4-5", "2026-10-11T02:00:00Z",
                             input_tokens=1000, output_tokens=10,
                             cache_read_input_tokens=50_000),
        ],
    )
    records = list(ClaudeProvider([tmp_path]).iter_progress())
    assert len(records) == 1
    record = records[0]
    assert record.session_id == "sess-1"
    assert record.project == "myproject"
    assert record.context_used == 51_000
    assert record.context_limit == 200_000
    assert record.context_percent == 26
    assert record.title == "重构登录模块"  # 只用第一行
    assert record.state == "working"


# ------------------------------------------------------------------ Codex


def codex_rollout(tmp_path: Path) -> Path:
    return write_jsonl(
        tmp_path / "2026" / "10" / "11" / "rollout-2026-10-11T02-00-00-abc.jsonl",
        [
            {"type": "session_meta", "timestamp": "2026-10-11T02:00:00Z",
             "payload": {"id": "cx-1", "cwd": "/home/dev/another"}},
            {"type": "turn_context", "timestamp": "2026-10-11T02:00:01Z",
             "payload": {"model": "gpt-5-codex"}},
            {"type": "event_msg", "timestamp": "2026-10-11T02:00:02Z",
             "payload": {"type": "token_count", "info": {
                 "total_token_usage": {"input_tokens": 10_000, "cached_input_tokens": 9_000,
                                       "output_tokens": 500},
                 "last_token_usage": {"input_tokens": 10_000, "cached_input_tokens": 9_000,
                                      "output_tokens": 500, "reasoning_output_tokens": 100},
             }}},
            {"type": "event_msg", "timestamp": "2026-10-11T02:00:05Z",
             "payload": {"type": "agent_message", "message": "改完了"}},
        ],
    )


def test_codex_usage_does_not_double_count_cached(tmp_path):
    """cached / reasoning 都是子集，归一后 input+output 必须等于 Codex 报的总量。"""
    codex_rollout(tmp_path)
    batches = list(CodexProvider([tmp_path]).iter_usage({}))
    records = [r for batch in batches for r in batch.records]
    assert len(records) == 1
    record = records[0]
    assert record.input_tokens == 1_000      # 10_000 − 9_000
    assert record.cache_read_tokens == 9_000
    assert record.output_tokens == 500       # reasoning 含在内，同价
    assert record.cache_write_tokens == 0
    assert record.total_tokens == 10_500     # 等于 Codex 的 input+output
    assert record.model == "gpt-5-codex"


def test_codex_usage_key_uses_line_offset(tmp_path):
    codex_rollout(tmp_path)
    batches = list(CodexProvider([tmp_path]).iter_usage({}))
    key = batches[0].records[0].key
    assert key.startswith("codex:")
    assert key.rsplit(":", 1)[-1].isdigit()


def test_codex_progress_reads_head_for_meta(tmp_path):
    """session_meta 在文件头、token_count 在文件尾，两边都得读。"""
    codex_rollout(tmp_path)
    records = list(CodexProvider([tmp_path]).iter_progress())
    assert len(records) == 1
    record = records[0]
    assert record.session_id == "cx-1"
    assert record.project == "another"     # 来自 cwd，不是 "11" 这种日期目录名
    assert record.model == "gpt-5-codex"
    assert record.context_used == 10_000   # input + cached
    assert record.state == "idle"          # 最后一条是 agent_message → 不是 working


def test_codex_project_label_falls_back_to_filename(tmp_path):
    """没有 cwd 时不能退到父目录名——那是 `11` 这样的日期。"""
    path = write_jsonl(
        tmp_path / "2026" / "10" / "11" / "rollout-2026-10-11T02-00-00-zzz.jsonl",
        [
            {"type": "event_msg", "timestamp": "2026-10-11T02:00:02Z",
             "payload": {"type": "token_count", "info": {
                 "last_token_usage": {"input_tokens": 100, "output_tokens": 10}}}},
        ],
    )
    records = list(CodexProvider([tmp_path]).iter_progress())
    assert records[0].project.startswith("2026-10-11T02-00-00")
    assert records[0].project != path.parent.name


# ------------------------------------------------------------------ 通用收件箱


def test_generic_usage_events(tmp_path):
    write_jsonl(
        tmp_path / "agent.jsonl",
        [
            {"kind": "usage", "ts": 1_760_000_000, "model": "step-3.5-flash",
             "input": 1200, "output": 340, "cacheRead": 100, "session": "run-42"},
            {"kind": "usage", "ts": "2026-10-11T02:00:00Z", "model": "glm-4",
             "input": 10, "output": 20, "key": "stable-1"},
        ],
    )
    batches = list(GenericProvider([tmp_path]).iter_usage({}))
    records = [r for batch in batches for r in batch.records]
    assert len(records) == 2
    assert records[0].total_tokens == 1640
    assert records[0].session_id == "run-42"
    assert records[0].key.startswith("generic:")       # 没给 key → 用文件位置
    assert records[1].key == "generic:stable-1"        # 给了 key → 用作者的


def test_generic_ignores_other_kinds_and_junk(tmp_path):
    write_jsonl(
        tmp_path / "agent.jsonl",
        [
            {"kind": "progress", "session": "x"},
            {"kind": "usage", "ts": 1_760_000_000, "model": "m", "input": 0, "output": 0},
            {"kind": "usage", "model": "m", "input": 5},   # 缺 ts
        ],
    )
    batches = list(GenericProvider([tmp_path]).iter_usage({}))
    assert [r for batch in batches for r in batch.records] == []


def test_generic_progress_append_and_snapshot(tmp_path):
    write_jsonl(
        tmp_path / "events.jsonl",
        [
            {"kind": "progress", "ts": "2026-10-11T02:00:00Z", "session": "run-1",
             "state": "thinking", "title": "旧标题", "contextUsed": 100},
            {"kind": "progress", "ts": "2026-10-11T03:00:00Z", "session": "run-1",
             "state": "working", "title": "新标题", "contextUsed": 500},
        ],
    )
    (tmp_path / "run-2.json").write_text(
        json.dumps({
            "kind": "progress", "session": "run-2", "state": "waiting",
            "project": "我的项目", "contextUsed": 150_000, "contextLimit": 200_000,
            "backgroundTasks": 2,
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    by_session = {r.session_id: r for r in GenericProvider([tmp_path]).iter_progress()}
    assert set(by_session) == {"run-1", "run-2"}
    # 追加式取最后一条
    assert by_session["run-1"].title == "新标题"
    assert by_session["run-1"].state == "working"
    # 覆盖式快照
    assert by_session["run-2"].project == "我的项目"
    assert by_session["run-2"].context_percent == 75
    assert by_session["run-2"].background_tasks == 2


def test_generic_accepts_snake_case(tmp_path):
    write_jsonl(
        tmp_path / "agent.jsonl",
        [
            {"kind": "usage", "timestamp": 1_760_000_000, "model": "m",
             "input_tokens": 7, "output_tokens": 3, "cache_read": 1},
        ],
    )
    records = [r for b in GenericProvider([tmp_path]).iter_usage({}) for r in b.records]
    assert records[0].total_tokens == 11


def test_generic_snapshot_timestamp_falls_back_to_mtime(tmp_path):
    snapshot = tmp_path / "s.json"
    snapshot.write_text(json.dumps({"kind": "progress", "session": "s"}), encoding="utf-8")
    record = next(iter(GenericProvider([tmp_path]).iter_progress()))
    assert record.updated_at > 0
