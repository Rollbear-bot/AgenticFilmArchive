# AI Agent驱动的胶片摄影归档系统

## 🚀Features

- **多模态知识库**：支持照片、Markdown 文本文档、PDF 文档（文本/图片/表格混合提取）存储到向量数据库
- **自动标签生成**：为照片自动生成拍摄场景、拍摄风格和胶片特征标签
- **Agent 多层记忆机制**：长期记忆（跨对话用户偏好持久化）+ 对话持久化（JSON 文件存储，服务器重启后可恢复）
- **基于向量和标签的混合检索**：支持按场景标签、风格标签和胶片特征标签过滤检索结果
- **通过自然语言交互**：通过自然语言向 Agent 描述需求，Agent 根据需要通过 Tool Using 方式检索知识库、读取记忆


## 🔧系统架构

### 核心组件

1. **资源层**
   - 图片资源：存储在`resources/img/`目录下，支持多级子目录组织
   - 文档资源：存储在`resources/doc/`目录下，支持 Markdown 和 PDF 格式

2. **文档处理层**
   - `core/vector_db.py`：向量数据库核心功能，封装Chroma与Ark多模态嵌入
   - `core/bm25_index.py`：BM25关键词检索索引，支持稀疏向量多路召回
   - `core/reranker.py`：多策略结果精排（alibaba/local/none）
   - `core/pdf_processor.py`：PDF文档解析，提取文本/图片（多模态模型生成描述）/表格（转Markdown）
   - `core/text_splitter.py`：语义切分（SemanticMarkdownSplitter），按标题层级切分，过长章节回退固定长度切分

3. **检索与生成层**
   - `core/agent_service.py`：LangGraph ReAct Agent，通过Tool Using检索知识库并流式输出，支持 `read_memory`/`write_memory` 长期记忆工具
   - `core/chat_service.py`：RAG对话服务（非Agent路径）
   - `core/memory_manager.py`：长期记忆管理，Markdown 文件存储，跨对话存取用户偏好
   - `core/conversation_store.py`：对话持久化，JSON 文件 CRUD，服务器重启后回放恢复 LangGraph checkpoint

4. **工具层**
   - `core/services.py`：提供图片转base64、照片标签生成等工具函数
   - `configures.py`：系统配置和提示词管理

5. **应用层**
   - `api/views.py` / `api/sse.py`：Django RESTful API与SSE流式响应
   - Web前端：React（Vite构建）

### 数据流示意
#### Offline 数据准备

```mermaid
flowchart TD
    IMG_IN([图像输入<br/>jpg png])
    TXT_IN([文本输入<br/>md 文件])
    PDF_IN([PDF 输入<br/>pdf 文件])

    IMG_IN --> SCAN[图像扫描<br/>os.walk]
    SCAN --> TAG[生成标签<br/>Ark Vision API]
    TAG --> B64[Base64 编码<br/>image_to_base64]

    TXT_IN --> MD_LOAD[Markdown 加载器]
    MD_LOAD --> SPLIT[语义切分<br/>SemanticMarkdownSplitter]

    PDF_IN --> PDF_PROCESS[PDF 解析<br/>core/pdf_processor.py]
    PDF_PROCESS --> PDF_BLOCKS{提取内容类型}
    PDF_BLOCKS -->|文本| PDF_TXT[pdf_text]
    PDF_BLOCKS -->|图片| PDF_IMG[pdf_image<br/>多模态模型生成描述]
    PDF_BLOCKS -->|表格| PDF_TBL[pdf_table<br/>表格转 Markdown]
    PDF_TXT --> SPLIT
    PDF_IMG --> EMBED
    PDF_TBL --> SPLIT

    B64 --> EMBED[ArkImageEmbeddings]
    SPLIT --> EMBED

    EMBED --> VEC["稠密向量 2048d"]
    VEC --> CHROMA[(ChromaDB<br/>chroma_multimodal)]

    SPLIT -.-> BM25_BUILD[构建 BM25 索引<br/>core/bm25_index.py]
    BM25_BUILD -.-> BM25_IDX[(BM25 稀疏索引)]
```

#### Online 检索生成

```mermaid
flowchart TD
    USER_QUERY([用户查询<br/>文本或图像])

    subgraph AGENT_PATH["Agent 路径 (ReAct + SSE)"]
        direction TB
        AGENT[LangGraph ReAct Agent<br/>core/agent_service.py] --> TOOL_CALL{工具调用}
        TOOL_CALL -->|retrieve_knowledge| RECALL_Q[查询嵌入]
        TOOL_CALL -->|analyze_image| VISION[Vision API<br/>图片内容分析]
        TOOL_CALL -->|search_by_tags| TAG_DIRECT[标签直接筛选]
        TOOL_CALL -->|read_memory| MEM_READ[读取长期记忆<br/>data/memory.md]
        TOOL_CALL -->|write_memory| MEM_WRITE[写入长期记忆<br/>data/memory.md]
        RANKED --> OBS[Observation]
        VISION --> OBS
        TAG_DIRECT --> OBS
        MEM_READ --> OBS
        MEM_WRITE --> OBS
        OBS --> AGENT
        AGENT --> SSE[SSE 流式推送<br/>thinking / text / tool / tool_images / done]
        AGENT -.->|对话持久化| CONV_STORE[(JSON 对话存储<br/>data/conversations/)]
    end

    subgraph RAG_PATH["RAG 路径 (直接检索)"]
        direction TB
        RAG_Q[查询嵌入]
        RANKED --> CTX[格式化上下文]
        CTX --> LLM[LLM API]
        LLM --> ANSWER([生成回答])
    end

    subgraph RETRIEVAL["多路召回与精排"]
        direction TB
        RECALL_Q --> VEC_SEARCH[向量检索<br/>ChromaDB]
        RAG_Q --> VEC_SEARCH
        BM25_IDX[(BM25 稀疏索引)] -.-> BM25_SEARCH[BM25 关键词检索<br/>仅文本文档]
        VEC_SEARCH --> MERGE[合并去重]
        BM25_SEARCH --> MERGE
        MERGE --> TAG_FILTER[Tag 过滤<br/>scene/style/film]
        TAG_FILTER --> RERANK[精排（重排）<br/>Reranker接口]
        RERANK --> RANKED[精排结果<br/>top_k]
    end

    USER_QUERY --> AGENT
    USER_QUERY --> RAG_Q
    CHROMA[(ChromaDB)] -.->|向量检索| VEC_SEARCH
    SSE --> FE[前端实时渲染<br/>工具调用 + 缩略图 + Markdown]
    ANSWER --> FE
```


### 代码结构

```
AgenticFilmArchive/
├── film_archive/         # Django项目配置
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── api/                  # RESTful API层
│   ├── views.py
│   ├── serializers.py
│   ├── sse.py            # SSE流式传输
│   └── urls.py
├── core/                 # 核心业务逻辑
│   ├── agent_service.py  # ReAct Agent服务（含长期记忆工具）
│   ├── vector_db.py      # 向量数据库服务
│   ├── chat_service.py   # AI对话服务
│   ├── bm25_index.py     # BM25关键词检索
│   ├── reranker.py       # 多策略精排
│   ├── pdf_processor.py  # PDF文档解析（文本/图片/表格）
│   ├── text_splitter.py  # Markdown语义切分
│   ├── memory_manager.py # 长期记忆管理（Markdown文件）
│   ├── conversation_store.py  # 对话持久化（JSON文件）
│   ├── services.py       # 图片处理与标签生成
│   └── views.py          # 前端入口视图
├── frontend/             # React前端应用（Vite构建）
│   ├── src/
│   │   ├── components/   # 可复用组件
│   │   ├── pages/        # 页面组件
│   │   ├── services/     # API客户端
│   │   └── utils/        # 工具函数
│   ├── package.json
│   └── vite.config.js
├── static/               # 构建产物静态资源（Django serve）
├── templates/            # HTML模板
├── test/                 # 测试用例
│   ├── test_bm25.py
│   └── test_reranker.py
├── resources/            # 知识库资源
│   ├── img/              # 图片资源
│   └── doc/              # 文档资源
├── pyproject.toml        # uv项目配置
├── uv.lock               # uv依赖锁定文件
├── manage.py             # Django管理脚本
└── .env                  # 环境配置变量
```

## 📦 安装

### 前置需求
- Python 3.12+（使用uv环境）
- Node.js 18+
- 火山引擎API

### 快速开始

#### 1. 克隆项目代码
```bash
git clone https://github.com/Rollbear-bot/AgenticFilmArchive.git
cd AgenticFilmArchive
```

#### 2. 配置环境变量
```bash
cp .env.example .env
# 编辑.env文件，配置Ark API密钥及相关参数
# ARK_API_KEY=your_ark_api_key_here
# BM25_ENABLED="true"          # 是否启用BM25关键词多路召回
# RERANK_STRATEGY="alibaba"    # 精排策略：alibaba / local / none
```

#### 3. 安装依赖
```bash
# 使用uv安装Python依赖
uv sync
```

#### 4. 准备知识库资源
```bash
# 创建资源目录结构
mkdir -p resources/img resources/doc

# 将照片放入resources/img/
# 将相关文本文档放入resources/doc/
```

#### 5. 构建前端
```bash
cd frontend
npm install
npm run build
cd ..
```

#### 6. 启动服务器
```bash
# Django后端（端口8000，同时serve前端静态文件）
python manage.py runserver
```

#### 7. 初始化向量数据库
访问 http://localhost:8000/sync/ ，点击"开始同步"将资源导入向量数据库。


## ⚠️注意事项

1. 系统依赖Volcengine Ark（火山引擎）API，需要有效的API Key（[获取方法](https://www.volcengine.com/docs/82379/1399008?lang=zh)）
2. 您的文件会通过Ark API上传到火山引擎，请阅读火山引擎的隐私政策
3. 首次运行时，系统会扫描`resources`目录并构建向量数据库，首次初始化可能需要较长时间
4. 支持的图片格式：jpg、jpeg、png
5. 支持的文档格式：Markdown、PDF

## 📝TODO

- [x] 召回后精排rerank
- [x] BM25关键词匹配 + 多路召回
- [x] 多查询召回
- [x] 语义切分chunking
- [x] 多层Agent Memory
- [ ] 智能相册自动分类
