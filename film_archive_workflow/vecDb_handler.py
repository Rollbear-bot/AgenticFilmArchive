import os
from volcenginesdkarkruntime import Ark
from langchain_core.embeddings import Embeddings
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter  # 添加分块器导入
from configures import ARK_API_KEY, EMBED_MODEL, VECTOR_DB_PATH, RES_DIR
from tools import image_to_base64, generate_photo_tags


class ArkImageEmbeddings(Embeddings):
    """
    自定义ARK图像嵌入模型类，用于Chroma向量数据库
    """

    def __init__(self):
        self.client = Ark(api_key=ARK_API_KEY)
        self.model_name = EMBED_MODEL

    def _get_image_embedding(self, image_data_url: str) -> list[float]:
        """获取单个图像的嵌入向量"""
        try:
            input_item = {"type": "image_url", "image_url": {"url": image_data_url}}
            resp = self.client.multimodal_embeddings.create(
                model=self.model_name,
                encoding_format="float",
                input=[input_item]
            )
            if hasattr(resp, 'data'):
                embedding = resp.data.embedding
                return embedding
            else:
                raise ValueError("API响应格式不符合预期，无法获取嵌入向量")
        except Exception as e:
            print(f"获取图像嵌入失败: {e}")
            raise

    def _get_text_embedding(self, text: str) -> list[float]:
        """获取单个文本的嵌入向量"""
        try:
            input_item = {"type": "text", "text": text}
            resp = self.client.multimodal_embeddings.create(
                model=self.model_name,
                encoding_format="float",
                input=[input_item]
            )
            if hasattr(resp, 'data'):
                embedding = resp.data.embedding
                return embedding
            else:
                raise ValueError("API响应格式不符合预期，无法获取嵌入向量")
        except Exception as e:
            print(f"获取文本嵌入失败: {e}")
            raise

    def embed_documents(self, texts: list[str], **kwargs) -> list[list[float]]:
        """
        为文档列表创建嵌入向量
        texts列表中的每个元素可以是文本字符串或图像数据URL
        """
        embeddings = []
        for text in texts:
            if text.startswith("data:image/"):
                # 图像数据
                embedding = self._get_image_embedding(text)
            else:
                # 文本数据
                embedding = self._get_text_embedding(text)
            embeddings.append(embedding)
        return embeddings

    def embed_query(self, text: str, **kwargs) -> list[float]:
        """
        为查询创建嵌入向量
        查询可以是文本或图像数据URL
        """
        if text.startswith("data:image/"):
            return self._get_image_embedding(text)
        else:
            return self._get_text_embedding(text)


class VecDB:
    def __init__(self, db_path, res_dir):
        """
        初始化VecDB类
        将embedding和Chroma数据库的初始化移到类的初始化中
        """
        self.db_path = db_path
        self.res_dir = res_dir
        
        # 初始化ARK图像嵌入模型
        print(f"[初始化] 创建ARK图像嵌入模型实例...")
        self.embeddings = ArkImageEmbeddings()
        
        # 初始化或加载Chroma向量数据库
        self.vector_store = None
        if os.path.exists(self.db_path):
            print(f"[初始化] 加载现有向量数据库: {self.db_path}")
            self.vector_store = Chroma(
                persist_directory=self.db_path,
                embedding_function=self.embeddings
            )
        else:
            print(f"[初始化] 向量数据库不存在，将在添加图片/文档时创建: {self.db_path}")

        print("[初始化] 添加资源库中已有文档到向量数据库")
        self.load_text_documents_to_vector_store(f"{self.res_dir}/doc")
        self.load_images_to_vector_store(f"{self.res_dir}/img")

    def load_images_to_vector_store(self, img_dir):
        """
        加载本地图片并构建向量存储，避免重复添加相同文件
        递归检查子目录，添加所有层级子目录中的图片
        """
        # 步骤1: 加载本地图片并创建Document对象
        print(f"\n[1/3] 开始加载 {img_dir} 目录及其子目录下的图片...")

        # 获取目录下的所有图片文件（递归遍历子目录）
        image_files = []
        for root, dirs, files in os.walk(img_dir):
            for file_name in files:
                if file_name.endswith((".jpg", ".jpeg", ".png")):
                    image_files.append(os.path.join(root, file_name))

        if not image_files:
            raise ValueError(f"在 {img_dir} 目录及其子目录下未找到图片文件")

        print(f"[2/3] 找到 {len(image_files)} 张图片，开始检查是否已存在于数据库...")

        # 获取已存在于数据库中的文件路径
        existing_file_paths = set()
        if self.vector_store is not None:
            print(f"  检查数据库中已存在的文件...")
            existing_docs = self.vector_store.get()
            for i, metadata in enumerate(existing_docs.get('metadatas', [])):
                if metadata and 'file_path' in metadata:
                    existing_file_paths.add(metadata['file_path'])
            print(f"  数据库中已存在 {len(existing_file_paths)} 个文件")

        # 转换图片为base64数据URL并创建Document对象（仅处理新文件）
        documents = []
        skipped_count = 0
        for image_path in image_files:
            file_name = os.path.basename(image_path)
            
            # 检查图片是否已存在于数据库
            if image_path in existing_file_paths:
                print(f"  跳过已存在的图片: {file_name} (路径: {image_path})")
                skipped_count += 1
                continue
            
            try:
                # 仅处理新文件
                image_data_url = image_to_base64(image_path)

                # 为图片生成标签
                tags = generate_photo_tags.invoke(image_path)
                # 解析标签
                try:
                    if ';' in tags and not tags.startswith("生成照片标签时出错"):
                        scene_tags, style_tags, film_tags = tags.split(';')
                    else:
                        scene_tags, style_tags, film_tags = "未知", "未知", "未知"
                except:
                    scene_tags, style_tags, film_tags = "未知", "未知", "未知"
                
                # 创建Document对象，page_content存储base64数据URL，metadata存储图片信息和标签
                doc = Document(
                    page_content=image_data_url,
                    metadata={
                        "file_name": file_name,
                        "file_path": image_path,
                        "type": "image",
                        "scene_tags": scene_tags,  # 直接存储字符串，不分割为列表
                        "style_tags": style_tags,  # 直接存储字符串，不分割为列表
                        "film_tags": film_tags,    # 直接存储字符串，不分割为列表
                        "full_tags": tags
                    }
                )
                documents.append(doc)
                print(f"  成功处理图片: {file_name} (路径: {image_path})")
            except Exception as e:
                print(f"  处理图片失败 {os.path.basename(image_path)}: {e}")
                continue

        print(f"[3/3] 完成图片处理，共生成 {len(documents)} 个Document对象，跳过 {skipped_count} 个已存在的图片")

        if not documents:
            print("\n  没有新图片需要添加，向量存储保持不变")
            return self.vector_store

        # 步骤2: 构建或更新向量存储
        print(f"\n[向量存储] 开始构建/更新图片向量存储...")

        # 检查向量数据库是否已存在
        if self.vector_store is not None:
            print(f"  向量数据库已存在，添加新文档...")
            # 将新文档添加到现有向量存储
            self.vector_store.add_documents(documents)
            print(f"  向量存储更新完成，已保存到 {self.db_path}")
            return self.vector_store
        else:
            # 数据库不存在，创建新的向量存储
            print("  向量数据库不存在，创建新的向量存储...")
            self.vector_store = Chroma.from_documents(
                documents=documents,
                embedding=self.embeddings,
                persist_directory=self.db_path
            )
            print(f"  向量存储构建完成，已保存到 {self.db_path}")
            return self.vector_store

    def load_text_documents_to_vector_store(self, doc_dir):
        """
        加载本地markdown文档并构建向量存储，避免重复添加相同文件
        """
        # 步骤1: 加载本地markdown文档并创建Document对象
        print(f"\n[1/3] 开始加载 {doc_dir} 目录下的markdown文档...")

        # 获取目录下的所有markdown文件
        text_files = []
        for file_name in os.listdir(doc_dir):
            if file_name.endswith(".md"):
                text_files.append(os.path.join(doc_dir, file_name))

        if not text_files:
            raise ValueError(f"在 {doc_dir} 目录下未找到markdown文件")

        print(f"[2/3] 找到 {len(text_files)} 个markdown文件，开始检查是否已存在于数据库...")

        # 获取已存在于数据库中的文件路径
        existing_file_paths = set()
        if self.vector_store is not None:
            print(f"  检查数据库中已存在的文件...")
            existing_docs = self.vector_store.get()
            for i, metadata in enumerate(existing_docs.get('metadatas', [])):
                if metadata and 'file_path' in metadata:
                    existing_file_paths.add(metadata['file_path'])
            print(f"  数据库中已存在 {len(existing_file_paths)} 个文件")

        # 读取markdown文件内容并创建Document对象（仅处理新文件）
        all_documents = []
        skipped_count = 0
        for file_path in text_files:
            file_name = os.path.basename(file_path)
            
            # 检查文档是否已存在于数据库
            if file_path in existing_file_paths:
                print(f"  跳过已存在的文档: {file_name} (路径: {file_path})")
                skipped_count += 1
                continue
            
            try:
                # 仅处理新文件
                # 读取文件内容
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # 创建Document对象
                doc = Document(
                    page_content=content,
                    metadata={
                        "file_name": file_name,
                        "file_path": file_path,
                        "type": "text",
                        "format": "markdown"
                    }
                )
                
                # 对文档进行分块处理（参考long_text_RAG.py）
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1000,  # 每个块的大小
                    chunk_overlap=200,  # 块之间的重叠部分
                    length_function=len,
                    separators=["\n\n", "\n", " ", ""]
                )
                chunks = text_splitter.split_documents([doc])
                print(f"  成功处理文档: {file_name}，生成 {len(chunks)} 个块")
                all_documents.extend(chunks)
            except Exception as e:
                print(f"  处理文档失败 {os.path.basename(file_path)}: {e}")
                continue

        print(f"[3/3] 完成文档处理，共生成 {len(all_documents)} 个Document对象，跳过 {skipped_count} 个已存在的文档")

        if not all_documents:
            print("\n  没有新文档需要添加，向量存储保持不变")
            return self.vector_store

        # 步骤2: 构建或更新向量存储
        print(f"\n[向量存储] 开始构建/更新文本向量存储...")

        # 检查向量数据库是否已存在
        if self.vector_store is not None:
            print(f"  向量数据库已存在，添加新文档块...")
            print(f"  新增 {len(all_documents)} 个文档块需要添加到数据库")
            
            # 将新文档块添加到现有向量存储
            self.vector_store.add_documents(all_documents)
            print(f"  向量存储更新完成，已保存到 {self.db_path}")
            return self.vector_store
        else:
            # 数据库不存在，创建新的向量存储
            print("  向量数据库不存在，创建新的向量存储...")
            self.vector_store = Chroma.from_documents(
                documents=all_documents,
                embedding=self.embeddings,
                persist_directory=self.db_path
            )
            print(f"  向量存储构建完成，已保存到 {self.db_path}")
            return self.vector_store

    def search_similar_documents(self, query, k=3, doc_type=None, scene_tags=None, style_tags=None, film_tags=None):
        """
        在向量数据库中搜索相似文档（支持多模态检索）
        query可以是文本字符串或图像数据URL
        doc_type: 可选参数，指定返回文档类型，如"image"、"text"或None（返回所有类型）
        scene_tags: 可选参数，指定要过滤的场景标签列表
        style_tags: 可选参数，指定要过滤的风格标签列表
        film_tags: 可选参数，指定要过滤的胶片特征标签列表
        """
        if self.vector_store is None:
            raise ValueError("向量数据库尚未初始化，请先调用load_images_to_vector_store或load_text_documents_to_vector_store方法")
        
        # 构建过滤条件 - 只保留文档类型过滤，因为Chroma不支持$contains操作符
        filter_clause = {}
        if doc_type:
            filter_clause["type"] = doc_type
        
        # 执行相似度搜索，返回(document, score)元组的列表
        # 这里只使用文档类型过滤，不使用标签过滤
        results_with_scores = self.vector_store.similarity_search_with_score(
            query=query,
            k=k,
            filter=filter_clause if filter_clause else None
        )
    
        # 在Python中进行标签过滤
        filtered_results = []
        for result, score in results_with_scores:
            # 检查标签过滤条件
            match = True
            
            # 检查场景标签
            if scene_tags and isinstance(scene_tags, list):
                result_scene_tags = result.metadata.get('scene_tags', '')
                for tag in scene_tags:
                    if tag not in result_scene_tags:
                        match = False
                        break
            
            # 检查风格标签
            if match and style_tags and isinstance(style_tags, list):
                result_style_tags = result.metadata.get('style_tags', '')
                for tag in style_tags:
                    if tag not in result_style_tags:
                        match = False
                        break
            
            # 检查胶片特征标签
            if match and film_tags and isinstance(film_tags, list):
                result_film_tags = result.metadata.get('film_tags', '')
                for tag in film_tags:
                    if tag not in result_film_tags:
                        match = False
                        break
            
            if match:
                filtered_results.append((result, score))
        
        # 确定查询类型
        query_type = "图像" if query.startswith("data:image/") else "文本"
        
        print(f"\n找到 {len(filtered_results)} 个与{query_type}相似的文档:")
        for i, (result, score) in enumerate(filtered_results):
            doc_type = result.metadata.get('type', '未知')
            print(f"\n{i + 1}. 相似度得分: {score:.4f} (类型: {doc_type})")
            print(f"   文件名: {result.metadata.get('file_name')}")
            print(f"   文件路径: {result.metadata.get('file_path')}")
            
            # 如果是图片类型，显示标签信息
            if doc_type == 'image':
                print(f"   场景标签: {result.metadata.get('scene_tags', '未知')}")
                print(f"   风格标签: {result.metadata.get('style_tags', '未知')}")
                print(f"   胶片特征: {result.metadata.get('film_tags', '未知')}")
    
        # 返回文档列表
        return [result for result, score in filtered_results]


if __name__ == "__main__":
    # 初始化VecDB类
    vec_db = VecDB(VECTOR_DB_PATH, RES_DIR)

    # 文本检索文本示例
    print("\n=== 文本检索文本示例 ===")
    text_query = "摄影指南"
    print(f"查询文本: {text_query}")
    text_search_results = vec_db.search_similar_documents(text_query, k=2, doc_type="text")

    # 文本检索图片示例
    print("\n=== 文本检索图片示例 ===")
    text_query = "灯牌"
    print(f"查询文本: {text_query}")
    image_search_results = vec_db.search_similar_documents(text_query, k=2, doc_type="image")

    # 图像检索文本示例
    print("\n=== 图像检索文本示例 ===")
    # 从向量存储中获取所有文档
    all_docs = vec_db.vector_store.get()
    if all_docs.get('documents') and all_docs.get('metadatas'):
        # 找到第一张图片
        image_doc = None
        image_metadata = None
        for i, metadata in enumerate(all_docs['metadatas']):
            if metadata.get('type') == 'image':
                image_doc = all_docs['documents'][i]
                image_metadata = metadata
                break
        
        if image_doc and image_metadata:
            print(f"使用图片 {image_metadata.get('file_name')} 作为查询")
            text_results = vec_db.search_similar_documents(image_doc, k=2, doc_type="text")

    # 图像检索图片示例
    print("\n=== 图像检索图片示例 ===")
    if image_doc and image_metadata:
        print(f"使用图片 {image_metadata.get('file_name')} 作为查询")
        image_results = vec_db.search_similar_documents(image_doc, k=2, doc_type="image")