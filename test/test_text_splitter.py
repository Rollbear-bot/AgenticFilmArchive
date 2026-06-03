"""
Tests for SemanticMarkdownSplitter and deduplication logic.
"""

import pytest
from langchain_core.documents import Document

from core.text_splitter import SemanticMarkdownSplitter
from core.vector_db import VectorDBService


class TestSemanticMarkdownSplitter:
    """SemanticMarkdownSplitter 单元测试"""

    @pytest.fixture
    def splitter(self):
        return SemanticMarkdownSplitter(chunk_size=100, chunk_overlap=20)

    def test_markdown_with_headers(self, splitter):
        """带多级标题的 markdown 应按标题切分"""
        content = """# 第一章
这是第一章的内容，介绍胶片摄影的基础知识。

## 1.1 胶片类型
常见的胶片类型包括彩色负片、黑白负片和反转片。

## 1.2 冲洗工艺
C-41 是最常见的彩色负片冲洗工艺。

# 第二章
第二章介绍拍摄技巧与构图方法。
"""
        doc = Document(
            page_content=content,
            metadata={"file_name": "test.md", "file_path": "/docs/test.md", "type": "text", "format": "markdown"},
        )
        chunks = splitter.split_documents([doc])

        assert len(chunks) >= 3  # 至少有三个标题对应的块
        headers = [c.metadata.get("header_1", "") for c in chunks]
        assert "第一章" in headers
        assert "第二章" in headers

        # 所有 chunk 都保留了原始 metadata
        for chunk in chunks:
            assert chunk.metadata["file_name"] == "test.md"
            assert chunk.metadata["file_path"] == "/docs/test.md"
            assert chunk.metadata["type"] == "text"
            assert chunk.metadata["format"] == "markdown"

    def test_markdown_no_headers_fallback(self, splitter):
        """无标题的 markdown 应回退到固定长度切分"""
        content = "这是没有标题的纯文本内容。" * 50  # 足够长以触发切分
        doc = Document(
            page_content=content,
            metadata={"file_name": "plain.md", "file_path": "/docs/plain.md", "type": "text", "format": "markdown"},
        )
        chunks = splitter.split_documents([doc])

        assert len(chunks) > 1  # 应该被切分成多个块
        for chunk in chunks:
            assert chunk.metadata["file_name"] == "plain.md"

    def test_long_section_fallback_split(self, splitter):
        """超长章节应被二次兜底切分"""
        # 创建一个只有一级标题但内容超长的文档
        header = "# 长章节\n"
        body = "这是一个非常长的段落内容。" * 100  # 远超 chunk_size=100
        doc = Document(
            page_content=header + body,
            metadata={"file_name": "long.md", "file_path": "/docs/long.md", "type": "text", "format": "markdown"},
        )
        chunks = splitter.split_documents([doc])

        assert len(chunks) > 1  # 超长章节被二次切分
        # 第一个 chunk 应保留标题信息
        assert "长章节" in chunks[0].page_content

    def test_chunk_id_and_primary(self, splitter):
        """chunk_id 应按顺序分配，is_primary 仅标记首个 chunk"""
        content = """# 第一节
内容A。

# 第二节
内容B。

# 第三节
内容C。
"""
        doc = Document(
            page_content=content,
            metadata={"file_name": "id_test.md", "file_path": "/docs/id_test.md", "type": "text", "format": "markdown"},
        )
        chunks = splitter.split_documents([doc])

        for idx, chunk in enumerate(chunks):
            assert chunk.metadata["chunk_id"] == idx
            if idx == 0:
                assert chunk.metadata["is_primary"] is True
            else:
                assert chunk.metadata["is_primary"] is False

    def test_non_markdown_uses_fallback(self, splitter):
        """非 markdown 文档直接使用固定长度切分"""
        content = "这是一段普通文本。" * 100
        doc = Document(
            page_content=content,
            metadata={"file_name": "plain.txt", "file_path": "/docs/plain.txt", "type": "text"},
        )
        chunks = splitter.split_documents([doc])

        assert len(chunks) > 1
        for idx, chunk in enumerate(chunks):
            assert chunk.metadata["chunk_id"] == idx
            assert chunk.metadata["file_name"] == "plain.txt"


class TestMergeDeduplicate:
    """_merge_deduplicate 去重逻辑单元测试"""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """重置 VectorDBService 单例状态，避免测试间干扰"""
        VectorDBService._instance = None
        VectorDBService._initialized = False
        yield
        VectorDBService._instance = None
        VectorDBService._initialized = False

    @pytest.fixture
    def service(self):
        return VectorDBService()

    def test_dedup_by_chunk_id(self, service):
        """使用 chunk_id 精确去重：同一块出现在两通道中保留高分"""
        doc = Document(
            page_content="胶片摄影基础知识",
            metadata={"file_path": "/docs/a.md", "type": "text", "chunk_id": 0},
        )
        doc2 = Document(
            page_content="其他内容",
            metadata={"file_path": "/docs/b.md", "type": "text", "chunk_id": 0},
        )
        # vector score 是 L2 距离，归一化后 = max(0, 1 - distance/2)
        # 1.5 -> 0.25
        vector_results = [{"document": doc, "score": 1.5}]
        # bm25 score 会被 min-max 归一化；提供两个元素使 min-max 有差异
        # 10.0 -> 1.0, 0.0 -> 0.0
        bm25_results = [{"document": doc, "score": 10.0}, {"document": doc2, "score": 0.0}]

        merged = service._merge_deduplicate(vector_results, bm25_results)
        assert len(merged) == 2  # doc 去重后 1 条 + doc2 1 条 = 2 条
        # 找到 doc 对应的结果，验证保留了高分（bm25 归一化后的 1.0）
        doc_results = [m for m in merged if m["document"].metadata.get("file_path") == "/docs/a.md"]
        assert len(doc_results) == 1
        assert doc_results[0]["score"] == 1.0

    def test_dedup_different_chunks_preserved(self, service):
        """不同 chunk_id 的块应被保留"""
        doc0 = Document(
            page_content="第一部分",
            metadata={"file_path": "/docs/a.md", "type": "text", "chunk_id": 0},
        )
        doc1 = Document(
            page_content="第二部分",
            metadata={"file_path": "/docs/a.md", "type": "text", "chunk_id": 1},
        )
        vector_results = [{"document": doc0, "score": 0.8}]
        bm25_results = [{"document": doc1, "score": 0.7}]

        merged = service._merge_deduplicate(vector_results, bm25_results)
        assert len(merged) == 2

    def test_dedup_fallback_without_chunk_id(self, service):
        """无 chunk_id 的存量数据回退到 content 前缀去重"""
        doc = Document(
            page_content="存量数据内容",
            metadata={"file_path": "/docs/legacy.md", "type": "text"},
        )
        vector_results = [{"document": doc, "score": 0.6}]
        bm25_results = [{"document": doc, "score": 0.7}]

        merged = service._merge_deduplicate(vector_results, bm25_results)
        assert len(merged) == 1
        assert merged[0]["score"] == 0.7
