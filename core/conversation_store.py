"""
Conversation Store - 对话持久化存储

基于 JSON 文件的对话 CRUD 管理，使用单例模式。
存储布局：
    data/conversations/
        index.json              # [{id, title, created_at, updated_at, message_count}]
        <uuid>.json             # {id, title, created_at, updated_at, messages: [...]}
"""

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Any


def _get_data_dir() -> str:
    from configures import DATA_DIR

    return DATA_DIR


def _conversations_dir() -> str:
    data_dir = _get_data_dir()
    conv_dir = os.path.join(data_dir, "conversations")
    os.makedirs(conv_dir, exist_ok=True)
    return conv_dir


def _index_path() -> str:
    return os.path.join(_conversations_dir(), "index.json")


class ConversationStore:
    """对话持久化存储单例"""

    _instance: "ConversationStore | None" = None
    _initialized: bool = False

    def __new__(cls) -> "ConversationStore":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not ConversationStore._initialized:
            ConversationStore._initialized = True

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def list_conversations(self) -> list[dict[str, Any]]:
        """列出所有对话（按更新时间降序）。

        Returns:
            [{id, title, created_at, updated_at, message_count}, ...]
        """
        idx = self._read_index()
        idx.sort(key=lambda c: c.get("updated_at", ""), reverse=True)
        return idx

    def get_conversation(self, conv_id: str) -> dict[str, Any] | None:
        """获取完整对话（含消息列表）。

        Args:
            conv_id: 对话 UUID

        Returns:
            {id, title, created_at, updated_at, messages: [...]} 或 None
        """
        file_path = self._conv_path(conv_id)
        if not os.path.exists(file_path):
            return None
        try:
            with open(file_path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def create_conversation(self, title: str | None = None) -> dict[str, Any]:
        """创建新对话。

        Args:
            title: 对话标题，为 None 时设为 "新对话"

        Returns:
            {id, title, created_at, updated_at, messages: []}
        """
        now = datetime.now(timezone.utc).isoformat()
        conv_id = str(uuid.uuid4())
        conv: dict[str, Any] = {
            "id": conv_id,
            "title": title or "新对话",
            "created_at": now,
            "updated_at": now,
            "messages": [],
        }

        self._write_conv_file(conv_id, conv)
        self._update_index(conv_id, title=conv["title"])
        return conv

    def save_conversation(self, conv_id: str, messages: list[dict[str, Any]]) -> dict[str, Any] | None:
        """保存对话消息（原子写入）。

        若对话文件不存在则自动创建，同时更新 index。

        Args:
            conv_id: 对话 UUID
            messages: 完整消息列表

        Returns:
            更新后的对话对象，或文件不存在的 None
        """
        existing = self.get_conversation(conv_id)

        if existing is None:
            # 自动创建
            now = datetime.now(timezone.utc).isoformat()
            conv: dict[str, Any] = {
                "id": conv_id,
                "title": self._generate_title(messages),
                "created_at": now,
                "updated_at": now,
                "messages": messages,
            }
        else:
            now = datetime.now(timezone.utc).isoformat()
            existing["messages"] = messages
            existing["updated_at"] = now
            if existing["title"] in ("新对话", ""):
                existing["title"] = self._generate_title(messages)
            conv = existing

        self._write_conv_file(conv_id, conv)
        self._update_index(
            conv_id,
            title=conv["title"],
            message_count=len(messages),
        )
        return conv

    def delete_conversation(self, conv_id: str) -> None:
        """删除对话（文件 + index 条目）。

        Args:
            conv_id: 对话 UUID
        """
        file_path = self._conv_path(conv_id)
        if os.path.exists(file_path):
            os.remove(file_path)

        idx = self._read_index()
        idx = [c for c in idx if c.get("id") != conv_id]
        self._write_index(idx)

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _conv_path(self, conv_id: str) -> str:
        return os.path.join(_conversations_dir(), f"{conv_id}.json")

    def _read_index(self) -> list[dict[str, Any]]:
        path = _index_path()
        if not os.path.exists(path):
            return []
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []

    def _write_index(self, index: list[dict[str, Any]]) -> None:
        path = _index_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

    def _write_conv_file(self, conv_id: str, conv: dict[str, Any]) -> None:
        """原子写入：先写临时文件再 rename"""
        file_path = self._conv_path(conv_id)
        dir_name = os.path.dirname(file_path)
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(conv, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, file_path)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    def _update_index(
        self,
        conv_id: str,
        title: str | None = None,
        message_count: int | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        idx = self._read_index()

        for entry in idx:
            if entry.get("id") == conv_id:
                if title is not None:
                    entry["title"] = title
                if message_count is not None:
                    entry["message_count"] = message_count
                entry["updated_at"] = now
                break
        else:
            idx.append(
                {
                    "id": conv_id,
                    "title": title or "新对话",
                    "created_at": now,
                    "updated_at": now,
                    "message_count": message_count or 0,
                }
            )

        self._write_index(idx)

    @staticmethod
    def _generate_title(messages: list[dict[str, Any]]) -> str:
        """从首条用户消息生成标题（前 50 字符）"""
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if len(content) > 50:
                    return content[:50] + "…"
                return content
        return "新对话"


def get_conversation_store() -> ConversationStore:
    """获取 ConversationStore 单例"""
    return ConversationStore()
