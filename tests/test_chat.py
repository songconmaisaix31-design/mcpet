from PySide6.QtWidgets import QDialog, QMessageBox

from src.chat.store import ChatStore, MAX_MESSAGES, MAX_CONTEXT_CHARS
from src.chat.dialog import ChatDialog, MemoryDialog


def test_history_reopens_bounded_and_clear_is_persistent(tmp_path):
    path = tmp_path / "chat.json"
    store = ChatStore(path)
    for n in range(60):
        store.append("user" if n % 2 == 0 else "assistant", f"{n}:" + "字" * 2000)
    reopened = ChatStore(path)
    assert len(reopened.messages) == MAX_MESSAGES
    assert reopened.messages[-1]["content"].startswith("59:")
    assert sum(len(m["content"]) for m in reopened.context()) <= MAX_CONTEXT_CHARS
    reopened.clear_history()
    assert ChatStore(path).messages == []


def test_user_operates_memory_save_delete_clear_and_reopen(tmp_path, monkeypatch):
    store = ChatStore(tmp_path / "chat.json")
    dialog = MemoryDialog(store)
    dialog.input.setText("请叫我阿王")
    dialog.save()
    dialog.input.setText("喜欢短回复")
    dialog.save()
    assert ChatStore(store.path).memories == ["请叫我阿王", "喜欢短回复"]
    dialog.items.setCurrentRow(0)
    dialog.delete()
    assert ChatStore(store.path).memories == ["喜欢短回复"]
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.Yes)
    dialog.clear()
    assert ChatStore(store.path).memories == []
    assert dialog.items.count() == 0
    dialog.close()


def test_chat_pending_close_reopen_and_failed_status(tmp_path):
    store = ChatStore(tmp_path / "chat.json")
    store.append("user", "你好")
    store.append("assistant", "我在呢")
    dialog = ChatDialog(store)
    sent = []
    dialog.send_requested.connect(lambda *a: sent.append(a))
    dialog.input.setPlainText("今天很累")
    dialog.submit()
    assert sent == [("今天很累", False)]
    assert not dialog.send.isEnabled()
    assert "发送中" in dialog.status.text()
    dialog.close()
    dialog.show()
    assert not dialog.send.isEnabled()
    dialog.set_pending(False, "发送失败：网络不可用")
    assert dialog.send.isEnabled()
    assert "网络不可用" in dialog.status.text()
    dialog.close()
    reopened = ChatDialog(ChatStore(store.path))
    assert "我在呢" in reopened.transcript.toPlainText()
    reopened.close()


def test_credentials_are_removed_before_disk_and_context(tmp_path, monkeypatch):
    monkeypatch.setenv("STEPFUN_API_KEY", "plain-secret-value")
    monkeypatch.setenv("MCD_MCP_TOKEN", "another-secret-value")
    store = ChatStore(tmp_path / "chat.json")
    store.append("user", "plain-secret-value another-secret-value")
    store.remember("plain-secret-value")
    raw = store.path.read_text(encoding="utf-8")
    assert "plain-secret-value" not in raw and "another-secret-value" not in raw
    assert store.context()[0]["content"] == "*** ***"


def test_corrupt_store_still_opens_ui(tmp_path):
    path = tmp_path / "chat.json"
    path.write_text("broken", encoding="utf-8")
    store = ChatStore(path)
    dialog = ChatDialog(store)
    assert dialog.transcript.toPlainText() == ""
    dialog.close()


def test_failed_clear_rolls_back_memory_and_disk(tmp_path, monkeypatch):
    import pytest
    store = ChatStore(tmp_path / "chat.json")
    store.remember("偏好一")
    original = store.path.read_text(encoding="utf-8")
    monkeypatch.setattr(store, "_save", lambda: (_ for _ in ()).throw(OSError("read-only")))
    with pytest.raises(OSError):
        store.clear_memories()
    assert store.memories == ["偏好一"]
    assert store.path.read_text(encoding="utf-8") == original
