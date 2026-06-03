"""
Semantic Text Splitter - 语义文本切分器

对 Markdown 文档优先按标题层级切分，保证块内语义完整性；
章节过长时回退到固定长度切分作为兜底。
"""

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter


class SemanticMarkdownSplitter:
    """混合语义切分器：Markdown 按标题切分 + 固定长度兜底。"""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        self._markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "header_1"),
                ("##", "header_2"),
                ("###", "header_3"),
                ("####", "header_4"),
            ],
            strip_headers=False,
        )
        self._fallback_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def split_documents(self, documents: list[Document]) -> list[Document]:
        """对输入文档进行语义切分，并为同一原始文档的 chunk 分配 chunk_id。"""
        result: list[Document] = []
        for doc in documents:
            if self._is_markdown(doc):
                chunks = self._split_markdown(doc)
            else:
                chunks = self._fallback_splitter.split_documents([doc])
                # 回退切分器会复制 metadata，但不含 chunk_id
                for chunk in chunks:
                    chunk.metadata.update(doc.metadata)

            # 为同一原始文档的所有 chunk 按顺序分配 chunk_id
            for idx, chunk in enumerate(chunks):
                chunk.metadata["chunk_id"] = idx
                if idx == 0:
                    chunk.metadata["is_primary"] = True
                else:
                    chunk.metadata["is_primary"] = False

            result.extend(chunks)
        return result

    @staticmethod
    def _is_markdown(doc: Document) -> bool:
        """判断文档是否为 markdown 格式。"""
        if doc.metadata.get("format") == "markdown":
            return True
        content = doc.page_content.strip()
        return content.startswith("#")

    def _split_markdown(self, doc: Document) -> list[Document]:
        """对 markdown 文档先按标题切分，过长章节再兜底截断。"""
        header_chunks = self._markdown_splitter.split_text(doc.page_content)

        final_chunks: list[Document] = []
        for chunk in header_chunks:
            # 标题切分产出的 chunk 仅含 header 相关 metadata，需合并原始 metadata
            chunk.metadata.update(doc.metadata)

            if len(chunk.page_content) > self.chunk_size:
                # 章节过长，使用兜底切分器二次切分
                sub_chunks = self._fallback_splitter.split_documents([chunk])
                for sub in sub_chunks:
                    # 保留标题信息（如 header_1 / header_2 等）和原始 metadata
                    sub.metadata.update(chunk.metadata)
                final_chunks.extend(sub_chunks)
            else:
                final_chunks.append(chunk)

        return final_chunks
