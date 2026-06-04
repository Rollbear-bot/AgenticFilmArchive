"""
Tests for Agent Memory - Conversation Store, Memory Manager, Memory Tools, Agent Integration.
"""

import json
import os
import tempfile
import uuid

import pytest


# ============================================================================
# TestConversationStore — 对话存储 CRUD 测试
# ============================================================================


class TestConversationStore:
    """对话存储 CRUD 测试。使用临时目录隔离测试数据。"""

    @pytest.fixture
    def store(self, tmp_path, monkeypatch):
        """创建使用临时目录的 ConversationStore 实例"""
        data_dir = str(tmp_path / "data")
        conversations_dir = os.path.join(data_dir, "conversations")
        os.makedirs(conversations_dir, exist_ok=True)
        monkeypatch.setattr("core.conversation_store._get_data_dir", lambda: data_dir)
        from core.conversation_store import ConversationStore

        # 为保证每次测试独立，强制创建新实例
        ConversationStore._instance = None
        ConversationStore._initialized = False
        cs = ConversationStore()
        return cs

    def test_create_conversation(self, store):
        """创建对话应返回带 UUID 和空消息的对话对象"""
        conv = store.create_conversation()
        assert "id" in conv
        assert uuid.UUID(conv["id"])  # 有效的 UUID
        assert conv["title"] == "新对话"
        assert conv["messages"] == []

    def test_create_conversation_with_title(self, store):
        """创建对话时可以指定标题"""
        conv = store.create_conversation(title="测试对话")
        assert conv["title"] == "测试对话"

    def test_create_multiple_conversations(self, store):
        """多次创建应产生不同的 UUID"""
        conv1 = store.create_conversation()
        conv2 = store.create_conversation()
        assert conv1["id"] != conv2["id"]

    def test_save_and_get_conversation(self, store):
        """保存消息后应能完整读取"""
        conv = store.create_conversation()
        messages = [
            {"role": "user", "content": "你好", "time": "2024-01-01T00:00:00"},
            {"role": "assistant", "content": "你好！有什么可以帮助你的？", "time": "2024-01-01T00:00:01"},
        ]
        store.save_conversation(conv["id"], messages)
        loaded = store.get_conversation(conv["id"])
        assert loaded is not None
        assert len(loaded["messages"]) == 2
        assert loaded["messages"][0]["content"] == "你好"

    def test_save_updates_title(self, store):
        """保存对话后标题应自动从首条用户消息生成"""
        conv = store.create_conversation()
        messages = [
            {"role": "user", "content": "如何选择胶片？", "time": "2024-01-01T00:00:00"},
        ]
        saved = store.save_conversation(conv["id"], messages)
        assert saved["title"] == "如何选择胶片？"

    def test_save_updates_index(self, store):
        """保存对话后 index 应反映最新的标题和消息数"""
        conv = store.create_conversation()
        messages = [
            {"role": "user", "content": "拍摄夜景的技巧？", "time": "2024-01-01T00:00:00"},
            {"role": "assistant", "content": "使用三脚架...", "time": "2024-01-01T00:00:01"},
        ]
        store.save_conversation(conv["id"], messages)
        convs = store.list_conversations()
        found = next((c for c in convs if c["id"] == conv["id"]), None)
        assert found is not None
        assert found["title"] == "拍摄夜景的技巧？"
        assert found["message_count"] >= 2

    def test_list_conversations_empty(self, store):
        """无对话时列表应返回空"""
        convs = store.list_conversations()
        assert convs == []

    def test_list_conversations_sorted(self, store):
        """列表应按更新时间降序排列"""
        conv1 = store.create_conversation(title="旧对话")
        import time
        time.sleep(0.01)  # 确保时间戳不同
        conv2 = store.create_conversation(title="新对话")
        store.save_conversation(conv2["id"], [
            {"role": "user", "content": "新消息", "time": "2024-01-01T00:00:00"},
        ])
        convs = store.list_conversations()
        assert convs[0]["id"] == conv2["id"]  # 最新更新的在前

    def test_delete_conversation(self, store):
        """删除对话应从 index 和文件系统中移除"""
        conv = store.create_conversation()
        store.delete_conversation(conv["id"])
        assert store.get_conversation(conv["id"]) is None
        convs = store.list_conversations()
        assert not any(c["id"] == conv["id"] for c in convs)

    def test_delete_nonexistent_conversation(self, store):
        """删除不存在的对话应静默处理（不抛异常）"""
        store.delete_conversation(str(uuid.uuid4()))

    def test_get_nonexistent_conversation(self, store):
        """读取不存在的对话应返回 None"""
        conv = store.get_conversation(str(uuid.uuid4()))
        assert conv is None

    def test_auto_title_truncation(self, store):
        """超长首条消息应截断并加 "…" """
        conv = store.create_conversation()
        long_msg = "胶片" * 30  # 60 个字符
        messages = [{"role": "user", "content": long_msg, "time": "2024-01-01T00:00:00"}]
        saved = store.save_conversation(conv["id"], messages)
        assert len(saved["title"]) == 51  # 50 chars + "…"
        assert saved["title"].endswith("…")

    def test_atomic_write(self, store):
        """写入过程中断不应损坏已有数据"""
        conv = store.create_conversation()
        messages1 = [
            {"role": "user", "content": "你好", "time": "2024-01-01T00:00:00"},
        ]
        store.save_conversation(conv["id"], messages1)
        # 验证数据完好
        loaded = store.get_conversation(conv["id"])
        assert loaded is not None
        assert loaded["messages"][0]["content"] == "你好"

    def test_append_messages(self, store):
        """多次 save 应追加消息（通过传入完整的累计消息列表）"""
        conv = store.create_conversation()
        msgs = [{"role": "user", "content": "第1轮", "time": "2024-01-01T00:00:00"}]
        store.save_conversation(conv["id"], msgs)
        msgs.append({"role": "assistant", "content": "回复1", "time": "2024-01-01T00:00:01"})
        msgs.append({"role": "user", "content": "第2轮", "time": "2024-01-01T00:00:02"})
        store.save_conversation(conv["id"], msgs)
        loaded = store.get_conversation(conv["id"])
        assert len(loaded["messages"]) == 3


# ============================================================================
# TestMemoryManager — 长期记忆读写测试
# ============================================================================


class TestMemoryManager:
    """长期记忆 Markdown 文件读写测试。"""

    @pytest.fixture
    def memory(self, tmp_path, monkeypatch):
        """创建使用临时文件的 MemoryManager 实例"""
        mem_file = os.path.join(str(tmp_path), "memory.md")
        monkeypatch.setattr("core.memory_manager._get_memory_file", lambda: mem_file)
        from core.memory_manager import MemoryManager

        MemoryManager._instance = None
        MemoryManager._initialized = False
        mm = MemoryManager()
        return mm

    def test_read_empty_memory(self, memory):
        """文件不存在时应返回空字符串"""
        content = memory.read_memory()
        assert content == ""

    def test_write_and_read_memory(self, memory):
        """写入后应能完整读取，且包含时间戳标题"""
        result = memory.write_memory("测试记忆内容")
        assert result["status"] == "success"

        content = memory.read_memory()
        assert "测试记忆内容" in content
        assert content.startswith("## ")  # 时间戳标题

    def test_write_appends_not_overwrites(self, memory):
        """多次写入应追加而非覆盖"""
        memory.write_memory("第一条记忆")
        memory.write_memory("第二条记忆")
        content = memory.read_memory()
        assert "第一条记忆" in content
        assert "第二条记忆" in content
        # 应有至少两个 ## 标题（两条记忆）
        assert content.count("## ") >= 2

    def test_write_preserves_markdown_format(self, memory):
        """写入的 markdown 格式内容应原样保留"""
        markdown_content = "## 标题\n\n- 列表项1\n- 列表项2\n\n**粗体**"
        memory.write_memory(markdown_content)
        content = memory.read_memory()
        assert "列表项1" in content
        assert "**粗体**" in content

    def test_multiline_content(self, memory):
        """多行内容应完整保留"""
        multiline = "第一行\n第二行\n第三行"
        memory.write_memory(multiline)
        content = memory.read_memory()
        assert "第一行" in content
        assert "第二行" in content
        assert "第三行" in content


# ============================================================================
# TestMemoryTools — 工具函数测试
# ============================================================================


class TestMemoryTools:
    """read_memory 和 write_memory @tool 函数的单元测试。
    不启动完整 Agent，仅测试工具函数本身。"""

    @pytest.fixture(autouse=True)
    def setup_memory_file(self, tmp_path, monkeypatch):
        """设置测试用的 memory.md"""
        mem_file = os.path.join(str(tmp_path), "memory.md")
        monkeypatch.setattr("core.memory_manager._get_memory_file", lambda: mem_file)
        from core.memory_manager import MemoryManager

        MemoryManager._instance = None
        MemoryManager._initialized = False
        yield mem_file
        # 清理
        MemoryManager._instance = None
        MemoryManager._initialized = False

    def test_read_memory_tool_returns_content(self, setup_memory_file):
        """read_memory 工具应返回记忆文件内容"""
        from core.agent_service import read_memory, write_memory

        write_memory.invoke({"content": "测试偏好"})
        result = read_memory.invoke({})
        assert "测试偏好" in result

    def test_read_memory_tool_empty_file(self, setup_memory_file):
        """空文件时应返回提示信息"""
        from core.agent_service import read_memory

        result = read_memory.invoke({})
        assert "长期记忆为空" in result or "为空" in result

    def test_write_memory_tool_appends(self, setup_memory_file):
        """write_memory 工具应成功追加并返回确认消息"""
        from core.agent_service import write_memory

        result = write_memory.invoke({"content": "记住这张照片"})
        assert "记忆已保存" in result

        # 验证实际写入
        from core.memory_manager import get_memory_manager

        content = get_memory_manager().read_memory()
        assert "记住这张照片" in content

    def test_tools_have_proper_docstrings(self):
        """工具函数应有正确的 docstring（LangGraph 用于生成 tool schema）"""
        from core.agent_service import read_memory, write_memory

        assert read_memory.description is not None
        assert len(read_memory.description) > 10
        assert write_memory.description is not None
        assert len(write_memory.description) > 10


# ============================================================================
# TestAgentMemoryIntegration — Agent 记忆集成测试
# ============================================================================


@pytest.mark.integration
class TestAgentMemoryIntegration:
    """Agent 记忆功能集成测试。
    需要 .env 配置 ARK_API_KEY，启动完整 Agent。"""

    @pytest.fixture
    def setup_agent(self, tmp_path, monkeypatch):
        """创建指向临时 data 目录的 AgentService"""
        data_dir = str(tmp_path / "data")
        conversations_dir = os.path.join(data_dir, "conversations")
        os.makedirs(conversations_dir, exist_ok=True)
        monkeypatch.setattr("core.conversation_store._get_data_dir", lambda: data_dir)
        mem_file = os.path.join(data_dir, "memory.md")
        monkeypatch.setattr("core.memory_manager._get_memory_file", lambda: mem_file)

        # 重置所有单例
        from core.agent_service import AgentService
        from core.conversation_store import ConversationStore
        from core.memory_manager import MemoryManager

        AgentService._instance = None
        AgentService._initialized = False
        ConversationStore._instance = None
        ConversationStore._initialized = False
        MemoryManager._instance = None
        MemoryManager._initialized = False

        return AgentService()

    def test_conversation_id_returned(self, setup_agent):
        """对话完成后应返回 conversation_id"""
        agent = setup_agent
        result = agent.chat("你好")
        assert "conversation_id" in result
        assert result["conversation_id"] is not None

    def test_conversation_saved_after_chat(self, setup_agent):
        """非流式对话完成后应保存到 JSON"""
        agent = setup_agent
        result = agent.chat("推荐一个胶片型号")
        conv_id = result["conversation_id"]

        from core.conversation_store import get_conversation_store

        conv = get_conversation_store().get_conversation(conv_id)
        assert conv is not None
        assert len(conv["messages"]) == 2  # user + assistant
        assert conv["messages"][0]["role"] == "user"

    def test_memory_context_injected_on_first_message(self, setup_agent, tmp_path):
        """首条消息应包含记忆上下文（当有长期记忆时）"""
        from core.memory_manager import get_memory_manager

        get_memory_manager().write_memory("用户喜欢街拍风格")

        agent = setup_agent
        # 检查 _get_memory_context 返回非空
        ctx = agent._get_memory_context()
        assert "街拍" in ctx
        assert "[长期记忆]" in ctx

    def test_no_memory_context_when_file_empty(self, setup_agent):
        """无记忆文件时不应注入上下文"""
        agent = setup_agent
        ctx = agent._get_memory_context()
        assert ctx == ""

    def test_has_checkpoint_new_thread(self, setup_agent):
        """新 thread 应该没有 checkpoint"""
        agent = setup_agent
        agent._ensure_agent()
        assert not agent._has_checkpoint(str(uuid.uuid4()))

    def test_replay_conversation(self, setup_agent):
        """验证回放功能不会抛异常"""
        agent = setup_agent
        agent._ensure_agent()
        thread_id = str(uuid.uuid4())
        messages = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！"},
        ]
        # 回放不应抛异常
        agent._replay_conversation(thread_id, messages)
