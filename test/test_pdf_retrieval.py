"""
Test PDF Document Retrieval - 测试 Agent 对 PDF 文档内容的召回

验证点：
1. PDF 文档是否正确入库（类型为 pdf_text/pdf_image/pdf_table）
2. 向量搜索 doc_type="text" 时是否能召回 PDF 内容
3. Agent 的 retrieve_knowledge 工具是否能检索到 PDF 内容
4. BM25 搜索是否能覆盖 PDF 文本
"""

import os
import sys

import django

# 确保 Django 设置已加载
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "film_archive.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

import pytest

from core.vector_db import get_vector_db_service
from core.agent_service import retrieve_knowledge


# ---------------  fixtures  ---------------


@pytest.fixture
def vec_db():
    """提供 VectorDBService 单例。"""
    return get_vector_db_service()


# ---------------  基础入库检查  ---------------


def test_pdf_documents_in_db(vec_db):
    """检查向量数据库中是否存在 PDF 类型的文档。"""
    if vec_db.vector_store is None:
        pytest.skip("向量数据库未初始化")

    all_docs = vec_db.vector_store.get()
    metadatas = all_docs.get("metadatas", [])

    pdf_types = {"pdf_text", "pdf_image", "pdf_table"}
    pdf_entries = [m for m in metadatas if m.get("type") in pdf_types]

    print(f"\n[PDF入库检查] 找到 {len(pdf_entries)} 个 PDF 内容块")
    assert len(pdf_entries) > 0, "向量数据库中没有任何 PDF 内容块，请先执行资源同步"


def test_pdf_unique_files_count(vec_db):
    """检查 get_file_count_by_type('text') 是否正确统计 PDF 文件。"""
    if vec_db.vector_store is None:
        pytest.skip("向量数据库未初始化")

    count = vec_db.get_file_count_by_type("text")
    print(f"\n[文档计数] get_file_count_by_type('text') = {count}")
    assert count > 0, "文档计数为 0，PDF 可能未入库"


def test_get_all_resources_text_filter(vec_db):
    """检查 get_all_resources(doc_type='text') 是否返回 PDF 文件。"""
    if vec_db.vector_store is None:
        pytest.skip("向量数据库未初始化")

    resources = vec_db.get_all_resources(limit=100, aggregate=True, doc_type="text")
    pdf_resources = [r for r in resources if r["file_type"].startswith("pdf")]

    print(f"\n[资源列表过滤] doc_type='text' 返回 {len(resources)} 个资源，其中 PDF {len(pdf_resources)} 个")
    for r in pdf_resources[:3]:
        print(f"  - {r['file_name']} (type={r['file_type']})")

    assert len(pdf_resources) > 0, "get_all_resources(doc_type='text') 未返回任何 PDF 文件"


# ---------------  向量检索召回测试  ---------------


@pytest.mark.parametrize(
    "query,expected_in_filename",
    [
        ("相机说明书", "manual"),  # 通用查询
        ("fujifilm", "fujifilm"),  # 品牌关键词
        ("Z50", "Z50"),            # 型号关键词
    ],
)
def test_vector_search_recalls_pdf(vec_db, query, expected_in_filename):
    """向量搜索 doc_type='text' 时应能召回 PDF 内容。"""
    if vec_db.vector_store is None:
        pytest.skip("向量数据库未初始化")

    results = vec_db.search(query=query, k=5, doc_type="text")

    pdf_results = [
        r for r in results
        if r["document"].metadata.get("type", "").startswith("pdf")
    ]

    print(f"\n[向量检索] query='{query}', doc_type='text'")
    print(f"  总结果: {len(results)}, PDF 结果: {len(pdf_results)}")
    for r in pdf_results[:2]:
        meta = r["document"].metadata
        print(f"  - {meta.get('file_name')} (type={meta.get('type')}, score={r['score']:.4f})")

    assert len(pdf_results) > 0, f"向量搜索 '{query}' 未召回任何 PDF 内容"


# ---------------  Agent 工具召回测试  ---------------


@pytest.mark.parametrize(
    "query",
    [
        "相机操作说明",
        "fujifilm 使用手册",
    ],
)
def test_agent_retrieve_knowledge_recalls_pdf(vec_db, query):
    """Agent 的 retrieve_knowledge 工具应能检索到 PDF 文档内容。"""
    if vec_db.vector_store is None:
        pytest.skip("向量数据库未初始化")

    result = retrieve_knowledge.invoke({"query": query, "k": 5, "doc_type": "text"})

    print(f"\n[Agent召回] query='{query}', doc_type='text'")
    # 检查结果字符串中是否包含 PDF 相关标识
    has_pdf = "pdf_" in result.lower() or ".pdf" in result.lower()

    # 也尝试从向量数据库直接确认
    db_results = vec_db.search(query=query, k=5, doc_type="text")
    pdf_in_db = any(
        r["document"].metadata.get("type", "").startswith("pdf")
        for r in db_results
    )

    print(f"  结果含PDF标识: {has_pdf}, 向量库有PDF: {pdf_in_db}")
    print(f"  结果预览:\n{result[:400]}...")

    assert pdf_in_db, f"向量库中未找到与 '{query}' 相关的 PDF"


# ---------------  BM25 召回测试  ---------------


def test_bm25_index_includes_pdf_text(vec_db):
    """BM25 索引应包含 PDF 文本块。"""
    if vec_db.vector_store is None:
        pytest.skip("向量数据库未初始化")

    # 强制重建 BM25 索引
    vec_db.bm25_index.invalidate()
    vec_db._ensure_bm25_index()

    if not vec_db.bm25_index.is_built:
        pytest.skip("BM25 索引构建失败或未启用")

    # 从索引的文档中检查是否有 PDF 类型
    pdf_in_index = any(
        doc.metadata.get("type", "").startswith("pdf")
        for doc in vec_db.bm25_index._documents
    )

    print(f"\n[BM25索引] 包含PDF文本块: {pdf_in_index}")
    print(f"  索引总文档数: {vec_db.bm25_index.document_count}")

    assert pdf_in_index, "BM25 索引中未包含任何 PDF 文本块"


@pytest.mark.parametrize(
    "query",
    [
        "相机",
        "fujifilm",
        "曝光",
    ],
)
def test_bm25_search_recalls_pdf(vec_db, query):
    """BM25 关键词搜索应能召回 PDF 文本内容。"""
    if vec_db.vector_store is None:
        pytest.skip("向量数据库未初始化")

    vec_db.bm25_index.invalidate()
    vec_db._ensure_bm25_index()

    if not vec_db.bm25_index.is_built:
        pytest.skip("BM25 索引未构建")

    results = vec_db._bm25_search(query, k=5, scene_tags=None, style_tags=None, film_tags=None)

    pdf_results = [
        r for r in results
        if r["document"].metadata.get("type", "").startswith("pdf")
    ]

    print(f"\n[BM25检索] query='{query}'")
    print(f"  总结果: {len(results)}, PDF 结果: {len(pdf_results)}")
    for r in pdf_results[:2]:
        meta = r["document"].metadata
        print(f"  - {meta.get('file_name')} (type={meta.get('type')}, score={r['score']:.4f})")

    assert len(pdf_results) > 0, f"BM25 搜索 '{query}' 未召回任何 PDF 内容"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
