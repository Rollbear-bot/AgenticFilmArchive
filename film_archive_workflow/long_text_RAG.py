import os
import numpy as np
from langchain_openai import ChatOpenAI
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter  # 修复导入语句
from langchain_chroma import Chroma  # 添加Chroma导入
from volcenginesdkarkruntime import Ark
from film_archive_workflow.configures import RES_DIR, ARK_API_KEY, CHAT_MODEL
from film_archive_workflow.vecDb_handler import ArkImageEmbeddings  # 添加ArkImageEmbeddings导入

# 设置环境变量
os.environ["ARK_API_KEY"] = ARK_API_KEY

# 配置参数
EMBED_MODEL = "doubao-embedding-vision-250615"
CHAT_MODEL = CHAT_MODEL
CHROMA_PATH = "./long_text_chroma_db"  # 长文本专用的Chroma数据库路径

# 初始化语言模型（参考chater.py）
print("初始化聊天模型...")
llm = ChatOpenAI(
    model=CHAT_MODEL,
    openai_api_base="https://ark.cn-beijing.volces.com/api/v3",
    openai_api_key=ARK_API_KEY,
    temperature=0.7,
    max_tokens=2048
)

# 火山引擎嵌入模型相关函数（参考ark_embed_match_demo.py）
def get_embedding(input_data, input_type="text"):
    """调用火山引擎API获取单个文本或图片的向量表示"""
    client = Ark(api_key=os.environ.get("ARK_API_KEY"))
    if input_type == "text":
        input_item = {"type": "text", "text": input_data}
    elif input_type == "image_url":
        input_item = {"type": "image_url", "image_url": {"url": input_data}}
    else:
        raise ValueError("输入类型仅支持'text'或'image_url'")

    try:
        resp = client.multimodal_embeddings.create(
            model=EMBED_MODEL,
            encoding_format="float",
            input=[input_item]
        )
        if hasattr(resp, 'data') and hasattr(resp.data, 'embedding'):
            embedding = resp.data.embedding
            # 确保向量是numpy数组并展平为一维
            embedding = np.array(embedding).flatten()
            return embedding
        else:
            raise ValueError("API响应格式不符合预期，无法获取嵌入向量")
    except Exception as e:
        print(f" 获取向量失败，输入类型: {input_type}, 错误: {str(e)}")
        raise

# 文档加载与处理
class LongTextRAG:
    def __init__(self, document_path):
        self.document_path = document_path
        self.documents = []
        self.chunks = []
        self.vector_store = None
        
        # 初始化ARK图像嵌入模型（用于Chroma）
        self.embeddings = ArkImageEmbeddings()
        
        # 加载文档
        self.load_document()
        # 文档分块
        self.split_document()
        # 将文档块存入Chroma向量数据库
        self.store_chunks_to_chroma()
    
    def load_document(self):
        """加载长文本文档"""
        print(f"加载文档: {self.document_path}")
        try:
            with open(self.document_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.documents.append(Document(page_content=content, metadata={"source": self.document_path}))
            print(f"文档加载成功，总字数: {len(content)}")
        except Exception as e:
            print(f"文档加载失败: {str(e)}")
            raise
    
    def split_document(self):
        """将长文档分块"""
        print("开始文档分块...")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,  # 每个块的大小
            chunk_overlap=200,  # 块之间的重叠部分
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        
        self.chunks = text_splitter.split_documents(self.documents)
        print(f"文档分块完成，共生成 {len(self.chunks)} 个块")
    
    def store_chunks_to_chroma(self):
        """将文档块存入Chroma向量数据库"""
        print("开始将文档块存入Chroma向量数据库...")
        
        # 检查Chroma数据库是否已存在
        if os.path.exists(CHROMA_PATH):
            print(f"  Chroma数据库已存在，正在加载: {CHROMA_PATH}")
            self.vector_store = Chroma(
                persist_directory=CHROMA_PATH,
                embedding_function=self.embeddings
            )
            
            # 检查当前文档是否已经存在于数据库中
            existing_docs = self.vector_store.get()
            existing_sources = set()
            for metadata in existing_docs.get('metadatas', []):
                if metadata and 'source' in metadata:
                    existing_sources.add(metadata['source'])
            
            if self.document_path in existing_sources:
                print(f"  文档 {os.path.basename(self.document_path)} 已存在于数据库中，跳过添加")
                return
            else:
                print(f"  将文档 {os.path.basename(self.document_path)} 的块添加到现有数据库中")
                self.vector_store.add_documents(self.chunks)
        else:
            print(f"  Chroma数据库不存在，创建新数据库: {CHROMA_PATH}")
            self.vector_store = Chroma.from_documents(
                documents=self.chunks,
                embedding=self.embeddings,
                persist_directory=CHROMA_PATH
            )
        
        print(f"  成功将 {len(self.chunks)} 个文档块存入Chroma向量数据库")
    
    def retrieve_relevant_chunks(self, query, top_k=3):
        """从Chroma向量数据库检索与查询相关的文档块"""
        print(f"\n从Chroma检索与查询相关的文档块: {query}")
        
        if self.vector_store is None:
            raise ValueError("向量数据库尚未初始化，请先调用store_chunks_to_chroma方法")
        
        # 使用Chroma进行相似度搜索，返回(document, score)元组的列表
        results_with_scores = self.vector_store.similarity_search_with_score(
            query=query,
            k=top_k
        )
        
        print("检索结果：")
        relevant_chunks = []
        for i, (doc, score) in enumerate(results_with_scores):
            print(f" [{i+1}] 相似度: {score:.4f}, 内容预览: {doc.page_content[:100]}...")
            # 转换为与原有方法兼容的格式
            relevant_chunks.append((score, {
                "chunk_id": i,
                "content": doc.page_content,
                "metadata": doc.metadata
            }))
        
        return relevant_chunks
    
    def generate_response(self, query, top_k=3):
        """生成基于检索结果的响应"""
        # 检索相关文档块
        relevant_chunks = self.retrieve_relevant_chunks(query, top_k)
        
        # 构建上下文
        context = ""
        for similarity, chunk in relevant_chunks:
            context += f"[文档块 {chunk['chunk_id']}]\n{chunk['content']}\n\n"
        
        # 构建提示
        prompt = f"你是一个智能助手，请根据提供的上下文回答用户问题。\n\n上下文：\n{context}\n\n用户问题：{query}\n\n回答："
        
        # 生成回答
        print("\n生成回答...")
        response = llm.invoke(prompt)
        
        return response.content

# 主程序
if __name__ == "__main__":
    # 选择长文档
    document_path = os.path.join(RES_DIR, "doc", "研究生工作记录.md")
    
    # 创建RAG实例
    rag = LongTextRAG(document_path)
    
    # 交互式查询
    print("\n长文本RAG检索系统已启动！")
    print("输入'退出'或'quit'结束对话。")
    
    while True:
        question = input("\n您的问题: ")
        if question.lower() in ['退出', 'quit']:
            print("感谢使用，再见！")
            break
        
        try:
            answer = rag.generate_response(question)
            print(f"\n回答: {answer}")
        except Exception as e:
            print(f"\n生成回答失败: {str(e)}")