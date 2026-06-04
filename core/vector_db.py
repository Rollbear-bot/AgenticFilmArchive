"""
Vector Database Service - 向量数据库服务层
"""

import os
import concurrent.futures
from collections import defaultdict
from volcenginesdkarkruntime import Ark
from langchain_core.embeddings import Embeddings
from langchain_core.documents import Document
from langchain_chroma import Chroma
from configures import (
    ARK_API_KEY,
    ARK_ENDPOINT,
    BM25_ENABLED,
    CHAT_MODEL,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    EMBED_MODEL,
    MULTI_QUERY_COUNT,
    MULTI_QUERY_ENABLED,
    RES_DIR,
    VECTOR_DB_PATH,
)
from core.pdf_processor import PDFContentBlock, PDFProcessor
from core.services import image_to_base64, generate_photo_tags
from core.bm25_index import Bm25Index
from core.text_splitter import SemanticMarkdownSplitter


class ArkImageEmbeddings(Embeddings):
    def __init__(self):
        self.client = Ark(api_key=ARK_API_KEY)
        self.model_name = EMBED_MODEL

    def _get_image_embedding(self, image_data_url):
        try:
            input_item = {"type": "image_url", "image_url": {"url": image_data_url}}
            resp = self.client.multimodal_embeddings.create(
                model=self.model_name, encoding_format="float", input=[input_item]
            )
            return resp.data.embedding if hasattr(resp, "data") else []
        except Exception as e:
            print(f"获取图像嵌入失败: {e}")
            return []

    def _get_text_embedding(self, text):
        try:
            input_item = {"type": "text", "text": text}
            resp = self.client.multimodal_embeddings.create(
                model=self.model_name, encoding_format="float", input=[input_item]
            )
            return resp.data.embedding if hasattr(resp, "data") else []
        except Exception as e:
            print(f"获取文本嵌入失败: {e}")
            return []

    def embed_documents(self, texts, **kwargs):
        embeddings = []
        for text in texts:
            if text.startswith("data:image/"):
                embedding = self._get_image_embedding(text)
            else:
                embedding = self._get_text_embedding(text)
            embeddings.append(embedding)
        return embeddings

    def embed_query(self, text, **kwargs):
        if text.startswith("data:image/"):
            return self._get_image_embedding(text)
        return self._get_text_embedding(text)


class VectorDBService:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not VectorDBService._initialized:
            self.db_path = VECTOR_DB_PATH
            self.res_dir = RES_DIR
            self.embeddings = ArkImageEmbeddings()
            self.vector_store = None
            self.bm25_index = Bm25Index()
            self._bm25_enabled = BM25_ENABLED
            self._init_db()
            VectorDBService._initialized = True

    def _init_db(self):
        print(f"[初始化] 向量数据库服务...")
        if os.path.exists(self.db_path):
            print(f"[初始化] 加载现有向量数据库: {self.db_path}")
            self.vector_store = Chroma(persist_directory=self.db_path, embedding_function=self.embeddings)
        else:
            print(f"[初始化] 向量数据库不存在")

    def _generate_query_terms(self, query: str, doc_type: str | None) -> list[str]:
        """使用 LLM 生成多查询词。原始查询始终放在第一位。

        注意：此处直接使用 Ark SDK 而非 LangChain ChatOpenAI，
        避免在 LangGraph Agent 的工具执行期间产生额外的 on_chat_model_stream
        事件，导致查询词被误送到前端 SSE 流。
        """
        from configures import PROMPTS

        try:
            client = Ark(base_url=ARK_ENDPOINT, api_key=ARK_API_KEY)
            prompt = PROMPTS.QUERY_EXPANDER.format(
                count=MULTI_QUERY_COUNT,
                query=query,
                doc_type=doc_type or "any",
            )
            completion = client.chat.completions.create(
                model=CHAT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=256,
            )
            content = completion.choices[0].message.content
            terms = [line.strip() for line in content.strip().split("\n") if line.strip()]
            # 去重并确保原始查询在首位
            unique_terms = [query]
            for t in terms:
                if t != query and t not in unique_terms:
                    unique_terms.append(t)
            return unique_terms[:MULTI_QUERY_COUNT]
        except Exception as e:
            print(f"[多查询] 生成查询词失败: {e}")
            return [query]

    def load_images(self, img_dir):
        print(f"\n开始加载图片: {img_dir}")

        image_files = []
        for root, dirs, files in os.walk(img_dir):
            for file_name in files:
                if file_name.endswith((".jpg", ".jpeg", ".png")):
                    image_files.append(os.path.join(root, file_name))

        if not image_files:
            return {"status": "warning", "message": "未找到图片文件", "count": 0}

        existing_file_paths = set()
        if self.vector_store is not None:
            existing_docs = self.vector_store.get()
            for metadata in existing_docs.get("metadatas", []):
                if metadata and "file_path" in metadata:
                    existing_file_paths.add(metadata["file_path"])

        new_image_files = [f for f in image_files if f not in existing_file_paths]
        skipped_count = len(image_files) - len(new_image_files)

        documents = []
        if new_image_files:

            def process_image(image_path):
                file_name = os.path.basename(image_path)
                try:
                    image_data_url = image_to_base64(image_path)
                    tags = generate_photo_tags(image_path)

                    try:
                        if ";" in tags and not tags.startswith("生成照片标签时出错"):
                            parts = tags.split(";", 2)
                            scene_tags = parts[0].strip() if len(parts) > 0 else "未知"
                            style_tags = parts[1].strip() if len(parts) > 1 else "未知"
                            film_tags = parts[2].strip() if len(parts) > 2 else "未知"
                        else:
                            scene_tags = style_tags = film_tags = "未知"
                    except:
                        scene_tags = style_tags = film_tags = "未知"

                    doc = Document(
                        page_content=image_data_url,
                        metadata={
                            "file_name": file_name,
                            "file_path": image_path,
                            "type": "image",
                            "scene_tags": scene_tags,
                            "style_tags": style_tags,
                            "film_tags": film_tags,
                            "full_tags": tags,
                            "is_primary": True,  # 图片的primary标记
                        },
                    )
                    return doc
                except Exception as e:
                    print(f"处理失败: {os.path.basename(image_path)}: {e}")
                    return None

            with concurrent.futures.ThreadPoolExecutor() as executor:
                results = list(executor.map(process_image, new_image_files))
                documents = [r for r in results if r is not None]

        if not documents:
            return {"status": "success", "message": "没有新图片", "count": 0, "skipped": skipped_count}

        if self.vector_store is not None:
            self.vector_store.add_documents(documents)
        else:
            self.vector_store = Chroma.from_documents(
                documents=documents, embedding=self.embeddings, persist_directory=self.db_path
            )

        return {
            "status": "success",
            "message": f"成功添加 {len(documents)} 张图片",
            "count": len(documents),
            "skipped": skipped_count,
        }

    def load_text_documents(self, doc_dir):
        print(f"\n开始加载文档: {doc_dir}")

        text_files = [os.path.join(doc_dir, f) for f in os.listdir(doc_dir) if f.endswith(".md")]

        if not text_files:
            return {"status": "warning", "message": "未找到markdown文件", "count": 0}

        existing_file_paths = set()
        if self.vector_store is not None:
            existing_docs = self.vector_store.get()
            for metadata in existing_docs.get("metadatas", []):
                if metadata and "file_path" in metadata:
                    existing_file_paths.add(metadata["file_path"])

        all_documents = []
        skipped_count = 0

        for file_path in text_files:
            file_name = os.path.basename(file_path)
            if file_path in existing_file_paths:
                skipped_count += 1
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                doc = Document(
                    page_content=content,
                    metadata={
                        "file_name": file_name,
                        "file_path": file_path,
                        "type": "text",
                        "format": "markdown",
                    },
                )

                text_splitter = SemanticMarkdownSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
                chunks = text_splitter.split_documents([doc])
                all_documents.extend(chunks)
            except Exception as e:
                print(f"处理文档失败 {file_name}: {e}")

        if not all_documents:
            return {"status": "success", "message": "没有新文档", "count": 0, "skipped": skipped_count}

        if self.vector_store is not None:
            self.vector_store.add_documents(all_documents)
        else:
            self.vector_store = Chroma.from_documents(
                documents=all_documents, embedding=self.embeddings, persist_directory=self.db_path
            )

        # 新文档入库后，使 BM25 索引失效，下次搜索时重建
        self.bm25_index.invalidate()
        print(f"[BM25] 索引已失效，将在下次搜索时重建")

        return {
            "status": "success",
            "message": f"成功添加 {len(all_documents)} 个文档块",
            "count": len(all_documents),
            "skipped": skipped_count,
        }

    def load_pdf_documents(self, doc_dir):
        """加载PDF文档到向量数据库。

        对PDF中的文本、图片、表格分别提取并结构化处理：
        - 文本：按段落提取后切分chunk，保留页码和源PDF路径
        - 图片：提取后由多模态模型生成描述文本，type="pdf_image"
        - 表格：转为Markdown+JSON格式，type="pdf_table"

        所有内容块的metadata均包含source_pdf指向源文件，便于聚合展示。
        PDF图片与知识库照片性质不同，严禁使用type="image"。
        """
        print(f"\n开始加载PDF文档: {doc_dir}")

        if not os.path.exists(doc_dir):
            return {"status": "warning", "message": "PDF目录不存在", "count": 0}

        pdf_files = []
        for root, dirs, files in os.walk(doc_dir):
            for file_name in files:
                if file_name.lower().endswith(".pdf"):
                    pdf_files.append(os.path.join(root, file_name))

        if not pdf_files:
            return {"status": "warning", "message": "未找到PDF文件", "count": 0}

        existing_file_paths = set()
        if self.vector_store is not None:
            existing_docs = self.vector_store.get()
            for metadata in existing_docs.get("metadatas", []):
                if metadata and "file_path" in metadata:
                    existing_file_paths.add(metadata["file_path"])

        all_documents = []
        skipped_count = 0

        for file_path in pdf_files:
            file_name = os.path.basename(file_path)
            if file_path in existing_file_paths:
                skipped_count += 1
                continue

            try:
                processor = PDFProcessor(file_path)
                blocks, report = processor.process()

                if report["errors"]:
                    print(f"[PDF] {file_name} 处理报告: {report}")

                if not blocks:
                    print(f"[PDF] {file_name} 未提取到有效内容")
                    continue

                # 分离文本块、图片描述块、表格块
                text_blocks = [b for b in blocks if b.type == "pdf_text"]
                image_blocks = [b for b in blocks if b.type == "pdf_image"]
                table_blocks = [b for b in blocks if b.type == "pdf_table"]

                # 处理文本块：合并后切分
                text_documents = []
                if text_blocks:
                    # 按页码排序后合并为单一文本（保留页码分隔）
                    text_blocks.sort(key=lambda b: b.page_number)
                    full_text = "\n\n".join(
                        f"[第{b.page_number}页]\n{b.content}" for b in text_blocks
                    )

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
                    text_documents.extend(chunks)

                # 处理图片描述块：每个描述作为独立Document
                image_documents = []
                for block in image_blocks:
                    image_documents.append(
                        Document(
                            page_content=block.content,
                            metadata={
                                "file_name": file_name,
                                "file_path": file_path,
                                "type": "pdf_image",
                                "source_pdf": file_path,
                                "page_number": block.page_number,
                                "is_primary": False,
                            },
                        )
                    )

                # 处理表格块：每个表格作为独立Document
                table_documents = []
                for block in table_blocks:
                    table_documents.append(
                        Document(
                            page_content=block.content,
                            metadata={
                                "file_name": file_name,
                                "file_path": file_path,
                                "type": "pdf_table",
                                "source_pdf": file_path,
                                "page_number": block.page_number,
                                "is_primary": False,
                            },
                        )
                    )

                all_documents.extend(text_documents)
                all_documents.extend(image_documents)
                all_documents.extend(table_documents)

                print(
                    f"[PDF] {file_name}: "
                    f"文本块={len(text_documents)}, "
                    f"图片描述={len(image_documents)}, "
                    f"表格={len(table_documents)}"
                )

            except Exception as e:
                print(f"处理PDF失败 {file_name}: {e}")

        if not all_documents:
            return {"status": "success", "message": "没有新PDF文档", "count": 0, "skipped": skipped_count}

        if self.vector_store is not None:
            self.vector_store.add_documents(all_documents)
        else:
            self.vector_store = Chroma.from_documents(
                documents=all_documents, embedding=self.embeddings, persist_directory=self.db_path
            )

        # 新文档入库后，使 BM25 索引失效
        self.bm25_index.invalidate()
        print(f"[BM25] 索引已失效，将在下次搜索时重建")

        return {
            "status": "success",
            "message": f"成功添加 {len(all_documents)} 个PDF内容块",
            "count": len(all_documents),
            "skipped": skipped_count,
        }

    # 被视为"文档"的所有类型（Markdown + PDF 内容块）
    _TEXT_DOC_TYPES = {"text", "pdf_text", "pdf_image", "pdf_table"}

    def _retrieve_raw(
        self,
        query: str,
        k: int,
        doc_type: str | None,
        scene_tags: list | None,
        style_tags: list | None,
        film_tags: list | None,
    ) -> tuple[list[dict], list[dict]]:
        """执行原始检索：向量搜索 + BM25（如适用），返回未归一化的原始结果。"""
        filter_clause = {}
        if doc_type:
            if doc_type == "text":
                # 文档类型需同时覆盖 Markdown 和 PDF 的各种内容块
                filter_clause["type"] = {"$in": list(self._TEXT_DOC_TYPES)}
            else:
                filter_clause["type"] = doc_type

        vector_results = self._vector_search(
            query, k, filter_clause, scene_tags, style_tags, film_tags
        )

        bm25_results = []
        if self._bm25_enabled and doc_type in (None, "text"):
            self._ensure_bm25_index()
            if self.bm25_index.is_built:
                bm25_results = self._bm25_search(
                    query, k, scene_tags, style_tags, film_tags
                )

        return vector_results, bm25_results

    def search(
        self,
        query,
        k=10,
        doc_type=None,
        scene_tags=None,
        style_tags=None,
        film_tags=None,
        rerank_enabled=True,
        rerank_top_n=None,
        multi_query=None,
    ):
        """多路召回检索：向量匹配 + BM25 关键词匹配，合并去重后送入精排。

        支持多查询召回：对原始查询生成多个查询词，每个查询词独立检索，
        最后合并所有结果去重，再用原始查询精排。

        BM25 通道仅在 doc_type 为 None (any) 或 "text" 时触发；
        doc_type="image" 时仅使用向量检索。
        """
        if self.vector_store is None:
            return []

        use_multi_query = multi_query if multi_query is not None else MULTI_QUERY_ENABLED
        coarse_k = k * 2 if rerank_enabled else k

        if use_multi_query:
            query_terms = self._generate_query_terms(query, doc_type)
            print(f"[多查询] 查询词列表: {query_terms}")

            all_vector_results = []
            all_bm25_results = []

            for term in query_terms:
                v_results, b_results = self._retrieve_raw(
                    term, coarse_k, doc_type, scene_tags, style_tags, film_tags
                )
                all_vector_results.extend(v_results)
                all_bm25_results.extend(b_results)
                print(f"[多查询] 查询词 '{term}': 向量={len(v_results)} 条, BM25={len(b_results)} 条")

            # 打印 BM25 检索结果
            if all_bm25_results:
                self._print_log_bm25_results(all_bm25_results)

            merged = self._merge_deduplicate(all_vector_results, all_bm25_results)
            self._print_log_merged_results(merged, all_vector_results, all_bm25_results)
        else:
            vector_results, bm25_results = self._retrieve_raw(
                query, coarse_k, doc_type, scene_tags, style_tags, film_tags
            )

            if bm25_results:
                self._print_log_bm25_results(bm25_results)

            merged = self._merge_deduplicate(vector_results, bm25_results)
            self._print_log_merged_results(merged, vector_results, bm25_results)

        # ---- 精排前安全截断（避免多查询导致候选数超载） ----
        if rerank_enabled and merged:
            safe_limit = 35 if doc_type == "image" else 80
            if len(merged) > safe_limit:
                print(f"[多查询] 结果数 {len(merged)} 超过安全上限 {safe_limit}，截断后精排")
                merged = merged[:safe_limit]

            top_n = rerank_top_n if rerank_top_n is not None else k
            merged = self._apply_rerank(query, merged, top_n)
        elif not rerank_enabled:
            merged = merged[:k]

        return merged

    def _vector_search(
        self, query, k, filter_clause, scene_tags, style_tags, film_tags
    ) -> list[dict]:
        """向量相似度检索 + tag 后过滤。

        Returns:
            [{"document": Document, "score": float}, ...]
            score 为 L2 距离（越低越相似）。
        """
        results_with_scores = self.vector_store.similarity_search_with_score(
            query=query, k=k, filter=filter_clause if filter_clause else None
        )

        filtered = []
        for result, score in results_with_scores:
            match = True

            if scene_tags:
                result_scene = result.metadata.get("scene_tags", "")
                for tag in scene_tags:
                    if tag not in result_scene:
                        match = False
                        break

            if match and style_tags:
                result_style = result.metadata.get("style_tags", "")
                for tag in style_tags:
                    if tag not in result_style:
                        match = False
                        break

            if match and film_tags:
                result_film = result.metadata.get("film_tags", "")
                for tag in film_tags:
                    if tag not in result_film:
                        match = False
                        break

            if match:
                filtered.append({"document": result, "score": float(score)})

        return filtered

    def _ensure_bm25_index(self) -> None:
        """懒加载：首次搜索时从 Chroma 构建 BM25 索引。

        索引范围包含 Markdown 文档 (type="text") 和 PDF 文本块 (type="pdf_text")，
        使 BM25 关键词检索能覆盖所有可阅读的文本内容。
        """
        if self.bm25_index.is_built or not self._bm25_enabled:
            return
        if self.vector_store is None:
            return

        all_docs = self.vector_store.get()
        documents = all_docs.get("documents", [])
        metadatas = all_docs.get("metadatas", [])

        text_docs = []
        for doc_str, meta in zip(documents, metadatas):
            if meta and meta.get("type") in ("text", "pdf_text"):
                text_docs.append(Document(page_content=doc_str, metadata=meta))

        if text_docs:
            print(f"[BM25] 构建索引: {len(text_docs)} 个文本块")
            self.bm25_index.build(text_docs)
        else:
            print("[BM25] 没有文本文档，跳过索引构建")

    def _bm25_search(
        self, query, k, scene_tags, style_tags, film_tags
    ) -> list[dict]:
        """BM25 关键词检索 + tag 后过滤。

        Returns:
            [{"document": Document, "score": float}, ...]
            score 为原始 BM25 分数（越高越相关）。
        """
        results = self.bm25_index.search(query, k=k)

        if not any([scene_tags, style_tags, film_tags]):
            return results

        # tag 过滤（text 文档通常无 tag，但保持接口一致）
        filtered = []
        for item in results:
            meta = item["document"].metadata
            match = True
            if scene_tags:
                result_scene = meta.get("scene_tags", "")
                for tag in scene_tags:
                    if tag not in result_scene:
                        match = False
                        break
            if match and style_tags:
                result_style = meta.get("style_tags", "")
                for tag in style_tags:
                    if tag not in result_style:
                        match = False
                        break
            if match and film_tags:
                result_film = meta.get("film_tags", "")
                for tag in film_tags:
                    if tag not in result_film:
                        match = False
                        break
            if match:
                filtered.append(item)
        return filtered

    def _merge_deduplicate(
        self, vector_results: list[dict], bm25_results: list[dict]
    ) -> list[dict]:
        """合并两个通道的结果并去重。

        - 向量距离 (L2, 越低越好) → [0, 1] 相关性分数 (越高越好)
        - BM25 原始分 (越高越好) → [0, 1] min-max 归一化
        - 去重 key = (file_path, page_content[:200])，区分同一文件的不同块；
          重复条目（同一块出现在两通道中）保留分数较高者。
        """
        # --- 归一化向量分数：L2 距离 → [0, 1] 相关性 ---
        for r in vector_results:
            distance = r["score"]
            r["score"] = max(0.0, 1.0 - distance / 2.0)

        # --- 归一化 BM25 分数：min-max → [0, 1] ---
        if bm25_results:
            scores = [r["score"] for r in bm25_results]
            lo, hi = min(scores), max(scores)
            rng = hi - lo
            if rng > 0:
                for r in bm25_results:
                    r["score"] = (r["score"] - lo) / rng
            else:
                for r in bm25_results:
                    r["score"] = 0.5
        # 裁切防溢出
        for r in bm25_results:
            r["score"] = min(1.0, max(0.0, r["score"]))

        # --- 去重：优先使用 (type, normalized_path, chunk_id)，兼容存量数据回退到 content[:200] ---
        seen: dict[tuple, dict] = {}
        all_items = vector_results + bm25_results
        for item in all_items:
            doc = item["document"]
            path = self.normalize_path(doc.metadata.get("file_path", ""))
            doc_type = doc.metadata.get("type", "")
            chunk_id = doc.metadata.get("chunk_id")

            if chunk_id is not None:
                key = (doc_type, path, chunk_id)
            else:
                # 存量数据兼容：无 chunk_id 时回退到旧逻辑
                content_prefix = doc.page_content[:200] if doc.page_content else ""
                key = (doc_type, path, content_prefix)

            if key not in seen or item["score"] > seen[key]["score"]:
                seen[key] = item

        merged = sorted(seen.values(), key=lambda x: x["score"], reverse=True)
        return merged

    def _print_log_bm25_results(self, results: list[dict]) -> None:
        """在控制台打印 BM25 检索结果。"""
        print(f"\n{'='*60}")
        print(f"[BM25] 检索结果: {len(results)} 条")
        print(f"{'-'*60}")
        for i, item in enumerate(results):
            doc = item["document"]
            file_name = doc.metadata.get("file_name", "?")
            content_preview = doc.page_content[:80].replace("\n", " ")
            print(f"  [{i+1}] score={item['score']:.4f}  file={file_name}")
            print(f"      content: {content_preview}...")
        if not results:
            print("  (无结果)")
        print(f"{'='*60}\n")

    def _print_log_merged_results(
        self,
        merged: list[dict],
        vector_results: list[dict],
        bm25_results: list[dict],
    ) -> None:
        """在控制台打印合并去重后的结果。"""
        print(f"\n{'='*60}")
        print(f"[MERGE] 合并去重结果")
        print(f"  向量通道: {len(vector_results)} 条  |  BM25通道: {len(bm25_results)} 条")
        print(f"  合并去重后: {len(merged)} 条")
        print(f"{'-'*60}")
        for i, item in enumerate(merged):
            doc = item["document"]
            file_name = doc.metadata.get("file_name", "?")
            doc_type = doc.metadata.get("type", "?")
            content_preview = doc.page_content[:80].replace("\n", " ") if doc.page_content else "(img)"
            print(f"  [{i+1}] score={item['score']:.4f}  type={doc_type}  file={file_name}")
            if doc_type != "image":
                print(f"      content: {content_preview}...")
        if not merged:
            print("  (无结果)")
        print(f"{'='*60}\n")

    def _apply_rerank(self, query: str, documents: list[dict], top_n: int) -> list[dict]:
        """应用精排器对文档重排序"""
        from core.reranker import get_reranker

        try:
            reranker = get_reranker()
            print(f"[INFO] Apply reranker {reranker.name}: k = {len(documents)} -> {top_n}")
            return reranker.rerank(query, documents, top_n)
        except (ValueError, RuntimeError) as e:
            print(f"[WARN] 精排失败，回退到粗排结果: {e}")
            return documents[:top_n]

    def normalize_path(self, path):
        """规范化文件路径"""
        if not path:
            return ""
        # 统一使用正斜杠
        path = path.replace("\\", "/")
        # 去除 ./ 和 ../
        path = path.lstrip("./").lstrip("../")
        # 去除多余斜杠
        while "//" in path:
            path = path.replace("//", "/")
        return path

    def get_all_resources(self, limit=100, offset=0, aggregate=True, doc_type=None):
        """获取资源列表

        Args:
            limit: 返回数量限制
            offset: 偏移量
            aggregate: 是否按文件路径聚合（避免重复显示分块文档）
            doc_type: 类型过滤，"image"（图片）或 "text"（文档，含 Markdown 和 PDF）
        """
        if self.vector_store is None:
            return []

        all_docs = self.vector_store.get()
        documents = all_docs.get("documents", [])
        metadatas = all_docs.get("metadatas", [])

        # 如果需要聚合，按file_path分组，收集每个文件下的所有类型
        if aggregate:
            file_entries = {}

            for i, (doc, meta) in enumerate(zip(documents, metadatas)):
                raw_path = meta.get("file_path", "")
                file_path = self.normalize_path(raw_path)

                if file_path not in file_entries:
                    file_entries[file_path] = {
                        "index": i,
                        "meta": meta,
                        "doc": doc,
                        "types": {meta.get("type", "")},
                    }
                else:
                    file_entries[file_path]["types"].add(meta.get("type", ""))

            # 按 doc_type 过滤
            text_types = self._TEXT_DOC_TYPES
            filtered_entries = []
            for file_path, info in file_entries.items():
                types = info["types"]
                if doc_type is None:
                    filtered_entries.append((file_path, info))
                elif doc_type == "image" and "image" in types:
                    filtered_entries.append((file_path, info))
                elif doc_type == "text" and types & text_types:
                    filtered_entries.append((file_path, info))

            # 构建结果列表
            unique_resources = []
            for file_path, info in filtered_entries:
                meta = info["meta"]
                doc = info["doc"]
                file_type = meta.get("type", "")

                unique_resources.append(
                    {
                        "id": info["index"],  # 使用实际的索引
                        "file_name": meta.get("file_name", ""),
                        "file_path": file_path,
                        "file_type": file_type,
                        "scene_tags": meta.get("scene_tags", ""),
                        "style_tags": meta.get("style_tags", ""),
                        "film_tags": meta.get("film_tags", ""),
                        "full_tags": meta.get("full_tags", ""),
                        # 图片存储完整的base64内容，文档截断
                        "content": doc if file_type == "image" else (doc[:200] if len(doc) > 200 else doc),
                        "is_primary": meta.get("is_primary", False),
                    }
                )

            # 按文件类型和文件名排序
            unique_resources.sort(key=lambda x: (x["file_type"], x["file_name"]))

            # 应用分页
            resources = unique_resources[offset : offset + limit] if offset < len(unique_resources) else []
            return resources
        else:
            # 不聚合，返回所有块（逐块过滤）
            resources = []
            for i, (doc, meta) in enumerate(zip(documents, metadatas)):
                if i < offset:
                    continue
                if len(resources) >= limit:
                    break

                item_type = meta.get("type", "")
                if doc_type == "image" and item_type != "image":
                    continue
                if doc_type == "text" and item_type not in self._TEXT_DOC_TYPES:
                    continue

                resources.append(
                    {
                        "id": i,
                        "file_name": meta.get("file_name", ""),
                        "file_path": meta.get("file_path", ""),
                        "file_type": item_type,
                        "scene_tags": meta.get("scene_tags", ""),
                        "style_tags": meta.get("style_tags", ""),
                        "film_tags": meta.get("film_tags", ""),
                        "full_tags": meta.get("full_tags", ""),
                        "content": doc[:200] if len(doc) > 200 else doc,
                    }
                )

            return resources

    def get_unique_file_count(self):
        """获取唯一文件数量"""
        if self.vector_store is None:
            return 0

        all_docs = self.vector_store.get()
        metadatas = all_docs.get("metadatas", [])

        unique_paths = set()
        for meta in metadatas:
            file_path = meta.get("file_path", "")
            if file_path:
                unique_paths.add(file_path)

        return len(unique_paths)

    def get_file_count_by_type(self, file_type):
        """获取指定类型的唯一文件数量

        当 file_type="text" 时，统计包含 Markdown 或 PDF 内容块的所有唯一文件。
        """
        if self.vector_store is None:
            return 0

        all_docs = self.vector_store.get()
        metadatas = all_docs.get("metadatas", [])

        # 先按文件路径聚合所有类型
        file_types = {}
        for meta in metadatas:
            path = meta.get("file_path", "")
            if not path:
                continue
            t = meta.get("type", "")
            file_types.setdefault(path, set()).add(t)

        text_types = self._TEXT_DOC_TYPES
        unique_paths = set()
        for path, types in file_types.items():
            if file_type == "text":
                if types & text_types:
                    unique_paths.add(path)
            elif file_type in types:
                unique_paths.add(path)

        return len(unique_paths)

    def get_resource_by_id(self, resource_id):
        """根据ID获取资源详情"""
        if self.vector_store is None:
            return None

        all_docs = self.vector_store.get()
        documents = all_docs.get("documents", [])
        metadatas = all_docs.get("metadatas", [])

        if resource_id < len(documents):
            doc = documents[resource_id]
            meta = metadatas[resource_id]

            return {
                "id": resource_id,
                "file_name": meta.get("file_name", ""),
                "file_path": meta.get("file_path", ""),
                "file_type": meta.get("type", ""),
                "scene_tags": meta.get("scene_tags", ""),
                "style_tags": meta.get("style_tags", ""),
                "film_tags": meta.get("film_tags", ""),
                "full_tags": meta.get("full_tags", ""),
                "content": doc,
                "is_primary": meta.get("is_primary", False),
            }
        return None

    def get_resource_by_file_path(self, file_path):
        """根据文件路径获取主资源（返回primary块）"""
        if self.vector_store is None:
            return None

        all_docs = self.vector_store.get()
        documents = all_docs.get("documents", [])
        metadatas = all_docs.get("metadatas", [])

        # 先找primary块
        for i, (doc, meta) in enumerate(zip(documents, metadatas)):
            if meta.get("file_path") == file_path and meta.get("is_primary", False):
                return {
                    "id": i,
                    "file_name": meta.get("file_name", ""),
                    "file_path": file_path,
                    "file_type": meta.get("type", ""),
                    "scene_tags": meta.get("scene_tags", ""),
                    "style_tags": meta.get("style_tags", ""),
                    "film_tags": meta.get("film_tags", ""),
                    "full_tags": meta.get("full_tags", ""),
                    "content": doc,
                    "is_primary": True,
                }

        # 如果没有primary块，返回第一个块
        for i, (doc, meta) in enumerate(zip(documents, metadatas)):
            if meta.get("file_path") == file_path:
                return {
                    "id": i,
                    "file_name": meta.get("file_name", ""),
                    "file_path": file_path,
                    "file_type": meta.get("type", ""),
                    "scene_tags": meta.get("scene_tags", ""),
                    "style_tags": meta.get("style_tags", ""),
                    "film_tags": meta.get("film_tags", ""),
                    "full_tags": meta.get("full_tags", ""),
                    "content": doc,
                    "is_primary": meta.get("is_primary", False),
                }

        return None


def get_vector_db_service():
    return VectorDBService()
