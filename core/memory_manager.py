"""
Memory Manager - 长期记忆管理

跨对话的持久性记忆，以 Markdown 明文存储。
文件位置由 DATA_DIR 环境变量控制，默认为 data/memory.md。
"""

import os
from datetime import datetime, timezone
from typing import Any


def _get_memory_file() -> str:
    from configures import MEMORY_FILE

    # 确保目录存在
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    return MEMORY_FILE


class MemoryManager:
    """长期记忆管理单例"""

    _instance: "MemoryManager | None" = None
    _initialized: bool = False

    def __new__(cls) -> "MemoryManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not MemoryManager._initialized:
            MemoryManager._initialized = True

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def read_memory(self) -> str:
        """读取完整长期记忆。

        Returns:
            完整 markdown 内容，文件不存在时返回空字符串
        """
        path = _get_memory_file()
        if not os.path.exists(path):
            return ""
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
            return content.strip()
        except OSError:
            return ""

    def write_memory(self, content: str) -> dict[str, Any]:
        """追加记忆（带时间戳标题）。

        Args:
            content: 要写入的 markdown 内容

        Returns:
            {"status": "success", "file": str}
        """
        path = _get_memory_file()
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        entry = f"\n\n## {timestamp}\n\n{content}\n"

        # 追加写入
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)

        return {"status": "success", "file": path}


def get_memory_manager() -> MemoryManager:
    """获取 MemoryManager 单例"""
    return MemoryManager()
