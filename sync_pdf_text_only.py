"""
PDF Text-only Sync Script - 仅同步 PDF 文本内容（跳过图片处理以加速）

用于快速将 PDF 文档的文本内容导入向量数据库，
跳过耗时较长的多模态图片描述生成步骤。
"""

import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "film_archive.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django

django.setup()

from langchain_core.documents import Document

from configures import CHUNK_OVERLAP, CHUNK_SIZE, RES_DIR
from core.text_splitter import SemanticMarkdownSplitter
from core.vector_db import get_vector_db_service


def sync_pdf_text_only(pdf_dir: str):
    """仅提取 PDF 文本并入库，跳过图片和表格。"""
    import fitz

    vec_db = get_vector_db_service()

    pdf_files = []
    for root, dirs, files in os.walk(pdf_dir):
        for f in files:
            if f.lower().endswith(".pdf"):
                pdf_files.append(os.path.join(root, f))

    print(f"找到 {len(pdf_files)} 个 PDF 文件")

    if not pdf_files:
        print("未找到 PDF 文件")
        return

    # 获取已入库的文件路径
    existing_paths = set()
    if vec_db.vector_store is not None:
        all_docs = vec_db.vector_store.get()
        for meta in all_docs.get("metadatas", []):
            if meta and "file_path" in meta:
                existing_paths.add(meta["file_path"])

    all_documents = []
    skipped = 0

    for file_path in pdf_files:
        file_name = os.path.basename(file_path)
        if file_path in existing_paths:
            print(f"[跳过] {file_name} 已入库")
            skipped += 1
            continue

        try:
            doc = fitz.open(file_path)
            full_text_parts = []
            for page_idx in range(len(doc)):
                page = doc.load_page(page_idx)
                text = page.get_text().strip()
                if text:
                    full_text_parts.append(f"[第{page_idx + 1}页]\n{text}")
            doc.close()

            if not full_text_parts:
                print(f"[警告] {file_name} 未提取到文本")
                continue

            full_text = "\n\n".join(full_text_parts)

            text_doc = Document(
                page_content=full_text,
                metadata={
                    "file_name": file_name,
                    "file_path": file_path,
                    "type": "pdf_text",
                    "source_pdf": file_path,
                    "is_primary": True,
                },
            )

            text_splitter = SemanticMarkdownSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
            chunks = text_splitter.split_documents([text_doc])
            all_documents.extend(chunks)

            print(f"[处理] {file_name}: {len(chunks)} 个文本块")

        except Exception as e:
            print(f"[错误] {file_name}: {e}")

    if not all_documents:
        print("没有新文档需要入库")
        return

    if vec_db.vector_store is not None:
        vec_db.vector_store.add_documents(all_documents)
    else:
        from core.vector_db import ArkImageEmbeddings, Chroma
        vec_db.vector_store = Chroma.from_documents(
            documents=all_documents,
            embedding=ArkImageEmbeddings(),
            persist_directory=vec_db.db_path,
        )

    # 使 BM25 索引失效
    vec_db.bm25_index.invalidate()

    print(f"\n成功添加 {len(all_documents)} 个 PDF 文本块 (跳过 {skipped} 个)")


if __name__ == "__main__":
    sync_pdf_text_only(os.path.join(RES_DIR, "pdf"))
