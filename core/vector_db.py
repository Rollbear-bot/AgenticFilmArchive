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
from langchain_text_splitters import RecursiveCharacterTextSplitter

from configures import ARK_API_KEY, EMBED_MODEL, VECTOR_DB_PATH, RES_DIR
from core.services import image_to_base64, generate_photo_tags


class ArkImageEmbeddings(Embeddings):
    def __init__(self):
        self.client = Ark(api_key=ARK_API_KEY)
        self.model_name = EMBED_MODEL
    
    def _get_image_embedding(self, image_data_url):
        try:
            input_item = {"type": "image_url", "image_url": {"url": image_data_url}}
            resp = self.client.multimodal_embeddings.create(
                model=self.model_name,
                encoding_format="float",
                input=[input_item]
            )
            return resp.data.embedding if hasattr(resp, 'data') else []
        except Exception as e:
            print(f"获取图像嵌入失败: {e}")
            return []
    
    def _get_text_embedding(self, text):
        try:
            input_item = {"type": "text", "text": text}
            resp = self.client.multimodal_embeddings.create(
                model=self.model_name,
                encoding_format="float",
                input=[input_item]
            )
            return resp.data.embedding if hasattr(resp, 'data') else []
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
            self._init_db()
            VectorDBService._initialized = True
    
    def _init_db(self):
        print(f"[初始化] 向量数据库服务...")
        if os.path.exists(self.db_path):
            print(f"[初始化] 加载现有向量数据库: {self.db_path}")
            self.vector_store = Chroma(
                persist_directory=self.db_path,
                embedding_function=self.embeddings
            )
        else:
            print(f"[初始化] 向量数据库不存在")
    
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
            for metadata in existing_docs.get('metadatas', []):
                if metadata and 'file_path' in metadata:
                    existing_file_paths.add(metadata['file_path'])
        
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
                        if ';' in tags and not tags.startswith("生成照片标签时出错"):
                            parts = tags.split(';', 2)
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
                            "is_primary": True  # 图片的primary标记
                        }
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
                documents=documents,
                embedding=self.embeddings,
                persist_directory=self.db_path
            )
        
        return {"status": "success", "message": f"成功添加 {len(documents)} 张图片", "count": len(documents), "skipped": skipped_count}
    
    def load_text_documents(self, doc_dir):
        print(f"\n开始加载文档: {doc_dir}")
        
        text_files = [os.path.join(doc_dir, f) for f in os.listdir(doc_dir) if f.endswith(".md")]
        
        if not text_files:
            return {"status": "warning", "message": "未找到markdown文件", "count": 0}
        
        existing_file_paths = set()
        if self.vector_store is not None:
            existing_docs = self.vector_store.get()
            for metadata in existing_docs.get('metadatas', []):
                if metadata and 'file_path' in metadata:
                    existing_file_paths.add(metadata['file_path'])
        
        all_documents = []
        skipped_count = 0
        
        for file_path in text_files:
            file_name = os.path.basename(file_path)
            if file_path in existing_file_paths:
                skipped_count += 1
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                doc = Document(
                    page_content=content,
                    metadata={
                        "file_name": file_name,
                        "file_path": file_path,
                        "type": "text",
                        "format": "markdown",
                        "is_primary": True  # 第一个块标记为primary
                    }
                )
                
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1000,
                    chunk_overlap=200
                )
                chunks = text_splitter.split_documents([doc])
                # 标记第一个块为primary
                if chunks:
                    chunks[0].metadata["is_primary"] = True
                all_documents.extend(chunks)
            except Exception as e:
                print(f"处理文档失败 {file_name}: {e}")
        
        if not all_documents:
            return {"status": "success", "message": "没有新文档", "count": 0, "skipped": skipped_count}
        
        if self.vector_store is not None:
            self.vector_store.add_documents(all_documents)
        else:
            self.vector_store = Chroma.from_documents(
                documents=all_documents,
                embedding=self.embeddings,
                persist_directory=self.db_path
            )
        
        return {"status": "success", "message": f"成功添加 {len(all_documents)} 个文档块", "count": len(all_documents), "skipped": skipped_count}
    
    def search(self, query, k=10, doc_type=None, scene_tags=None, style_tags=None, film_tags=None):
        if self.vector_store is None:
            return []
        
        filter_clause = {}
        if doc_type:
            filter_clause["type"] = doc_type
        
        results_with_scores = self.vector_store.similarity_search_with_score(
            query=query,
            k=k * 2,
            filter=filter_clause if filter_clause else None
        )
        
        filtered_results = []
        for result, score in results_with_scores:
            match = True
            
            if scene_tags:
                result_scene = result.metadata.get('scene_tags', '')
                for tag in scene_tags:
                    if tag not in result_scene:
                        match = False
                        break
            
            if match and style_tags:
                result_style = result.metadata.get('style_tags', '')
                for tag in style_tags:
                    if tag not in result_style:
                        match = False
                        break
            
            if match and film_tags:
                result_film = result.metadata.get('film_tags', '')
                for tag in film_tags:
                    if tag not in result_film:
                        match = False
                        break
            
            if match:
                filtered_results.append({'document': result, 'score': float(score)})
            
            if len(filtered_results) >= k:
                break
        
        return filtered_results
    
    def normalize_path(self, path):
        """规范化文件路径"""
        if not path:
            return ''
        # 统一使用正斜杠
        path = path.replace('\\', '/')
        # 去除 ./ 和 ../
        path = path.lstrip('./').lstrip('../')
        # 去除多余斜杠
        while '//' in path:
            path = path.replace('//', '/')
        return path
    
    def get_all_resources(self, limit=100, offset=0, aggregate=True):
        """获取资源列表
        
        Args:
            limit: 返回数量限制
            offset: 偏移量
            aggregate: 是否按文件路径聚合（避免重复显示分块文档）
        """
        if self.vector_store is None:
            return []
        
        all_docs = self.vector_store.get()
        documents = all_docs.get('documents', [])
        metadatas = all_docs.get('metadatas', [])
        
        # 如果需要聚合，按file_path分组，每个文件只返回第一个块
        if aggregate:
            seen_files = {}
            resources = []
            
            for i, (doc, meta) in enumerate(zip(documents, metadatas)):
                raw_path = meta.get('file_path', '')
                file_path = self.normalize_path(raw_path)
                
                # 如果这个文件还没见过
                if file_path not in seen_files:
                    seen_files[file_path] = {
                        'index': i,
                        'meta': meta,
                        'doc': doc,
                        'normalized_path': file_path
                    }
            
            # 构建结果列表（按文件路径去重）
            unique_resources = []
            for file_path, info in seen_files.items():
                meta = info['meta']
                doc = info['doc']
                
                file_type = meta.get('type', '')
                
                unique_resources.append({
                    'id': info['index'],  # 使用实际的索引
                    'file_name': meta.get('file_name', ''),
                    'file_path': file_path,
                    'file_type': file_type,
                    'scene_tags': meta.get('scene_tags', ''),
                    'style_tags': meta.get('style_tags', ''),
                    'film_tags': meta.get('film_tags', ''),
                    'full_tags': meta.get('full_tags', ''),
                    # 图片存储完整的base64内容，文档截断
                    'content': doc if file_type == 'image' else (doc[:200] if len(doc) > 200 else doc),
                    'is_primary': meta.get('is_primary', False)
                })
            
            # 按文件类型和文件名排序
            unique_resources.sort(key=lambda x: (x['file_type'], x['file_name']))
            
            # 应用分页
            resources = unique_resources[offset:offset + limit] if offset < len(unique_resources) else []
            return resources
        else:
            # 不聚合，返回所有块
            resources = []
            for i, (doc, meta) in enumerate(zip(documents, metadatas)):
                if i < offset:
                    continue
                if len(resources) >= limit:
                    break
                
                resources.append({
                    'id': i,
                    'file_name': meta.get('file_name', ''),
                    'file_path': meta.get('file_path', ''),
                    'file_type': meta.get('type', ''),
                    'scene_tags': meta.get('scene_tags', ''),
                    'style_tags': meta.get('style_tags', ''),
                    'film_tags': meta.get('film_tags', ''),
                    'full_tags': meta.get('full_tags', ''),
                    'content': doc[:200] if len(doc) > 200 else doc
                })
            
            return resources
    
    def get_unique_file_count(self):
        """获取唯一文件数量"""
        if self.vector_store is None:
            return 0
        
        all_docs = self.vector_store.get()
        metadatas = all_docs.get('metadatas', [])
        
        unique_paths = set()
        for meta in metadatas:
            file_path = meta.get('file_path', '')
            if file_path:
                unique_paths.add(file_path)
        
        return len(unique_paths)
    
    def get_file_count_by_type(self, file_type):
        """获取指定类型的唯一文件数量"""
        if self.vector_store is None:
            return 0
        
        all_docs = self.vector_store.get()
        metadatas = all_docs.get('metadatas', [])
        
        unique_paths = set()
        for meta in metadatas:
            if meta.get('type') == file_type:
                file_path = meta.get('file_path', '')
                if file_path:
                    unique_paths.add(file_path)
        
        return len(unique_paths)
    
    def get_resource_by_id(self, resource_id):
        """根据ID获取资源详情"""
        if self.vector_store is None:
            return None
        
        all_docs = self.vector_store.get()
        documents = all_docs.get('documents', [])
        metadatas = all_docs.get('metadatas', [])
        
        if resource_id < len(documents):
            doc = documents[resource_id]
            meta = metadatas[resource_id]
            
            return {
                'id': resource_id,
                'file_name': meta.get('file_name', ''),
                'file_path': meta.get('file_path', ''),
                'file_type': meta.get('type', ''),
                'scene_tags': meta.get('scene_tags', ''),
                'style_tags': meta.get('style_tags', ''),
                'film_tags': meta.get('film_tags', ''),
                'full_tags': meta.get('full_tags', ''),
                'content': doc,
                'is_primary': meta.get('is_primary', False)
            }
        return None
    
    def get_resource_by_file_path(self, file_path):
        """根据文件路径获取主资源（返回primary块）"""
        if self.vector_store is None:
            return None
        
        all_docs = self.vector_store.get()
        documents = all_docs.get('documents', [])
        metadatas = all_docs.get('metadatas', [])
        
        # 先找primary块
        for i, (doc, meta) in enumerate(zip(documents, metadatas)):
            if meta.get('file_path') == file_path and meta.get('is_primary', False):
                return {
                    'id': i,
                    'file_name': meta.get('file_name', ''),
                    'file_path': file_path,
                    'file_type': meta.get('type', ''),
                    'scene_tags': meta.get('scene_tags', ''),
                    'style_tags': meta.get('style_tags', ''),
                    'film_tags': meta.get('film_tags', ''),
                    'full_tags': meta.get('full_tags', ''),
                    'content': doc,
                    'is_primary': True
                }
        
        # 如果没有primary块，返回第一个块
        for i, (doc, meta) in enumerate(zip(documents, metadatas)):
            if meta.get('file_path') == file_path:
                return {
                    'id': i,
                    'file_name': meta.get('file_name', ''),
                    'file_path': file_path,
                    'file_type': meta.get('type', ''),
                    'scene_tags': meta.get('scene_tags', ''),
                    'style_tags': meta.get('style_tags', ''),
                    'film_tags': meta.get('film_tags', ''),
                    'full_tags': meta.get('full_tags', ''),
                    'content': doc,
                    'is_primary': meta.get('is_primary', False)
                }
        
        return None


def get_vector_db_service():
    return VectorDBService()
