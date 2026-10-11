"""不扫描其他文件，不用模型提取个人画像。"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from .. import config

MAX_MESSAGES = 40
MAX_CONTENT = 4000
MAX_CONTEXT_CHARS = 12000
MAX_MEMORIES = 30


def bounded_history(history, *, char_limit=MAX_CONTEXT_CHARS):
    result, remaining = [], char_limit
    for item in list(history)[-MAX_MESSAGES:][::-1]:
        if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
            continue
        content = config.redact(str(item.get("content", "")))[:MAX_CONTENT]
        if len(content) > remaining:
            break
        remaining -= len(content)
        result.append({"role": item["role"], "content": content})
    return result[::-1]


class ChatStore:
    def __init__(self, path: Path | None = None):
        self.path = path or config.data_dir() / "chat.json"
        self.messages, self.memories = [], []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("invalid chat data")
            self.messages = bounded_history(data.get("messages", []), char_limit=MAX_MESSAGES * MAX_CONTENT)
            self.memories = [config.redact(m)[:500] for m in data.get("memories", [])
                             if isinstance(m, str) and m.strip()][:MAX_MEMORIES]
        except (OSError, ValueError, TypeError):
            pass

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"messages": self.messages, "memories": self.memories},
                                        ensure_ascii=False), encoding="utf-8")
        os.chmod(temporary, stat.S_IRUSR | stat.S_IWUSR)
        temporary.replace(self.path)

    def _commit(self, messages, memories):
        previous = self.messages, self.memories
        self.messages, self.memories = messages, memories
        try:
            self._save()
        except OSError:
            self.messages, self.memories = previous
            raise

    def append(self, role, text):
        if role not in {"user", "assistant"}:
            raise ValueError("无效聊天角色")
        messages = self.messages + [{"role": role, "content": config.redact(text)[:MAX_CONTENT]}]
        self._commit(messages[-MAX_MESSAGES:], list(self.memories))

    def context(self):
        return bounded_history(self.messages)

    def remember(self, text):
        text = config.redact(text.strip())[:500]
        if text and text not in self.memories:
            if len(self.memories) >= MAX_MEMORIES:
                raise ValueError("偏好已达 30 条，请先删除")
            self._commit(list(self.messages), self.memories + [text])

    def forget(self, index):
        memories = list(self.memories)
        del memories[index]
        self._commit(list(self.messages), memories)

    def clear_memories(self):
        self._commit(list(self.messages), [])

    def clear_history(self):
        self._commit([], list(self.memories))
