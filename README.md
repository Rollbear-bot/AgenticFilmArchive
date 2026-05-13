# AI Agent驱动的胶片摄影归档助理

## Features

- **多模态知识库**：支持将照片和文本文档（如摄影技法指南）存储到向量数据库中
- **自动标签生成**：为照片自动生成拍摄场景、拍摄风格和胶片特征标签
- **基于向量和标签的混合检索**：支持按场景标签、风格标签和胶片特征标签过滤检索结果
- **通过自然语言交互**：通过自然语言向Agent描述需求，Agent会根据需要通过Tool Using方式检索知识库

## 系统架构

### 核心组件

1. **资源层**
   - 图片资源：存储在`resources/img/`目录下，支持多级子目录组织
   - 文档资源：存储在`resources/doc/`目录下，支持Markdown格式文档

2. **向量处理层**
   - `ArkImageEmbeddings`：自定义嵌入模型，支持文本和图像的多模态嵌入
   - `vecDb_handler.py`：向量数据库核心功能实现

3. **工具层**
   - `tools.py`：提供图片转base64、照片标签生成等工具函数
   - `configures.py`：系统配置和提示词管理

4. **应用层**
   - `chater.py`：自然语言交互入口，Agent支持多工具调用

## Quick Start

### 环境准备

1. 确保已安装Python 3.12或更高版本和uv
    ```bash
   # 如果没有安装uv
    pip install uv
    ```

1. 使用uv创建虚拟环境：
   ```bash
   uv init
   ```
2. 安装项目依赖：
   ```bash
   uv sync
   ```

### 配置设置

1. 复制环境变量示例文件：
   ```bash
   cp .env.example .env
   ```
2. 编辑`.env`文件，配置Ark API Key：
   ```env
   ARK_API_KEY=your_ark_api_key
   ```
### 设置知识库
在你喜欢的位置放置知识库目录，默认目录为项目目录下的`resources/`，可在配置文件`.env`中修改
1. 创建知识库目录
   ```bash
   mkdir -p resources/img resources/doc
   ```


### 系统入口

初始化向量数据库并使用自然语言交互
```bash
uv run chat.py
```


## 项目结构

```
AgenticFilmArchive/
├── chat.py                  # 自然语言交互入口
├── configures.py            # 系统配置和提示词
├── long_text_RAG.py         # 长文档处理demo
├── reDb_handler.py          # 关系数据库处理
├── tools.py                 # 工具函数
└── vecDb_handler.py         # 向量数据库核心功能
├── resources/               # 知识库
│   ├── doc/                     # 文本文档库
│   └── img/                     # 照片库
├── .env.example             # 环境变量示例
├── README.md                # 项目说明文档
└── requirements.txt         # 项目依赖
```


## 注意事项
1. 系统依赖Volcengine Ark（火山引擎）API，需要有效的API Key（[获取方法](https://www.volcengine.com/docs/82379/1399008?lang=zh)）
2. 您的文件会通过Ark API上传到火山引擎，请阅读火山引擎的隐私政策
3. 首次运行时，系统会扫描`resources`目录并构建向量数据库，首次初始化可能需要较长时间
4. 支持的图片格式：jpg、jpeg、png
5. 支持的文档格式：Markdown

## TODO
- File System Tools实现
- 照片元数据（EXIF）解析
- Web前端界面
- 增强AI图片分析能力，如色彩分析、构图评估等