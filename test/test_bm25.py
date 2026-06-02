"""
Tests for BM25 keyword search engine and multi-channel recall.
"""

import pytest
import unittest

from langchain_core.documents import Document

from core.bm25_index import Bm25Index


class TestBm25Index:
    """Unit tests for Bm25Index."""

    @pytest.fixture
    def sample_docs(self):
        return [
            Document(
                page_content="胶片摄影是一种使用胶卷作为感光材料的摄影方式。",
                metadata={"file_name": "doc1.md", "file_path": "/docs/doc1.md", "type": "text"},
            ),
            Document(
                page_content="迫冲是指在冲洗过程中延长显影时间来提高胶片的感光度。",
                metadata={"file_name": "doc2.md", "file_path": "/docs/doc2.md", "type": "text"},
            ),
            Document(
                page_content="彩色负片是最常见的彩色胶片类型，使用C-41工艺冲洗。",
                metadata={"file_name": "doc3.md", "file_path": "/docs/doc3.md", "type": "text"},
            ),
        ]

    @pytest.fixture
    def index(self, sample_docs):
        idx = Bm25Index()
        idx.build(sample_docs)
        return idx

    def test_initial_state(self):
        """New index should not be built."""
        idx = Bm25Index()
        assert not idx.is_built
        assert idx.document_count == 0

    def test_build(self, sample_docs):
        """Build should set the index state."""
        idx = Bm25Index()
        idx.build(sample_docs)
        assert idx.is_built
        assert idx.document_count == 3

    def test_build_empty(self):
        """Build with empty list should not set built state."""
        idx = Bm25Index()
        idx.build([])
        assert not idx.is_built

    def test_search_returns_correct_format(self, index):
        """Search should return list of dicts with 'document' and 'score'."""
        results = index.search("胶片", k=3)
        assert isinstance(results, list)
        for r in results:
            assert "document" in r
            assert "score" in r
            assert isinstance(r["document"], Document)
            assert isinstance(r["score"], float)

    def test_search_empty_query(self, index):
        """Empty query should return empty list."""
        assert index.search("", k=3) == []
        assert index.search("   ", k=3) == []

    def test_search_on_empty_index(self):
        """Search on un-built index should return empty list."""
        idx = Bm25Index()
        assert idx.search("film", k=3) == []

    def test_search_score_ordering(self, index):
        """Results should be sorted by score descending (most relevant first)."""
        results = index.search("胶片", k=3)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_chinese_keyword(self, index):
        """Chinese keyword search should find relevant documents."""
        results = index.search("迫冲", k=3)
        assert len(results) > 0
        # The doc about 迫冲 should be top-ranked
        assert "迫冲" in results[0]["document"].page_content

    def test_search_english_mixed_text(self):
        """Search should work with English/mixed text."""
        docs = [
            Document(page_content="Push processing increases effective film speed.", metadata={"type": "text"}),
            Document(page_content="胶片迫冲处理提高感光度.", metadata={"type": "text"}),
            Document(page_content="Standard C-41 development recipe.", metadata={"type": "text"}),
        ]
        idx = Bm25Index()
        idx.build(docs)

        results = idx.search("push film", k=3)
        assert len(results) > 0

    def test_invalidate(self, index):
        """Invalidate should reset the index state."""
        assert index.is_built
        index.invalidate()
        assert not index.is_built
        assert index.document_count == 0
        assert index.search("胶片", k=3) == []

    def test_rebuild_after_invalidate(self, index):
        """After invalidate, rebuild should work."""
        index.invalidate()
        docs = [Document(page_content="new content", metadata={"type": "text"})]
        index.build(docs)
        assert index.is_built
        assert index.document_count == 1

    def test_search_k_limit(self, index):
        """k parameter should limit results."""
        results = index.search("胶片", k=1)
        assert len(results) <= 1

    def test_score_range(self, index):
        """BM25 scores should be non-negative."""
        results = index.search("胶片", k=3)
        for r in results:
            assert r["score"] >= 0

    def test_no_results_for_unrelated_query(self, index):
        """Query with no matching terms should return empty list."""
        results = index.search("zzz_unrelated_term_xyz", k=3)
        assert len(results) == 0


class TestBm25IndexParameters:
    """Test BM25 parameter customization."""

    def test_custom_k1_b(self):
        """Should accept custom k1 and b parameters."""
        idx = Bm25Index(k1=2.0, b=0.5)
        docs = [Document(page_content="test document content", metadata={"type": "text"})]
        idx.build(docs)
        results = idx.search("test", k=3)
        assert len(results) > 0


class TestBm25IndexLargeDocuments:
    """Tests with larger document sets simulating real-world chunks."""

    def test_many_similar_documents(self):
        """BM25 should handle many documents with varied content."""
        topics = [
            "胶片摄影基础 相机操作 guide for beginners",
            "迫冲处理 push processing 提高感光度 development time",
            "彩色负片 C-41工艺 color negative film developing",
            "黑白胶片 暗房技术 black and white darkroom printing",
            "中画幅相机 medium format camera 120 film",
            "大画幅摄影 large format 4x5 sheet film technique",
            "街拍技巧 street photography 35mm 胶卷推荐",
            "人像摄影 portrait 灯光 setup 胶片选择",
            "风光摄影 landscape 日出日落 滤镜使用",
            "微距摄影 macro photography 近摄 胶片",
        ]
        docs = []
        for i in range(100):
            topic = topics[i % len(topics)]
            content = f"文档{i} {topic} 额外内容 filler text for diversity."
            docs.append(Document(page_content=content, metadata={"file_path": f"/doc/doc{i}.md", "type": "text"}))
        idx = Bm25Index()
        idx.build(docs)
        results = idx.search("迫冲 push", k=5)
        assert len(results) > 0
        for r in results:
            assert r["score"] >= 0


if __name__ == '__main__':
    unittest.main()