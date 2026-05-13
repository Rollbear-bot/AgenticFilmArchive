# AI Agent驱动的胶片摄影归档系统

## 🚀Features

- **多模态知识库**：支持将照片和文本文档（如摄影技法指南）存储到向量数据库中
- **自动标签生成**：为照片自动生成拍摄场景、拍摄风格和胶片特征标签
- **基于向量和标签的混合检索**：支持按场景标签、风格标签和胶片特征标签过滤检索结果
- **通过自然语言交互**：通过自然语言向Agent描述需求，Agent会根据需要通过Tool Using方式检索知识库


## 🔧系统架构

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
   - Web App: Django + React

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
│   └── urls.py           
├── core/                 # 核心业务逻辑
│   ├── vector_db.py      # 向量数据库服务
│   ├── chat_service.py   # AI对话服务
│   ├── models.py         # 数据模型
│   └── views.py          # 页面视图
├── frontend/             # React前端应用
│   ├── src/              
│   │   ├── App.jsx       
│   │   └── main.jsx      
│   ├── package.json      # 前端依赖
│   └── vite.config.js    # 前端构建配置
├── static/               # 前端静态资源
│   ├── js/react-app.jsx  
│   └── css/              
├── templates/            # HTML模板
│   └── react-index.html  
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
# 编辑.env文件，配置Ark API密钥
# ARK_API_KEY=your_ark_api_key_here
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

#### 5. 初始化向量数据库
```bash
# 稍后通过Web界面操作同步资源
# 或使用命令行工具初始化
python -c "from core.vector_db import get_vector_db_service; db = get_vector_db_service(); db.sync_resources()"
```

#### 6. 启动服务器
```bash
# 启动Django后端（端口8000）
python manage.py runserver

# 在另一个终端启动React前端（端口5173）
cd frontend
npm install
npm run dev
```

#### 7. 访问应用
- http://localhost:8000/


## ⚠️注意事项

1. 系统依赖Volcengine Ark（火山引擎）API，需要有效的API Key（[获取方法](https://www.volcengine.com/docs/82379/1399008?lang=zh)）
2. 您的文件会通过Ark API上传到火山引擎，请阅读火山引擎的隐私政策
3. 首次运行时，系统会扫描`resources`目录并构建向量数据库，首次初始化可能需要较长时间
4. 支持的图片格式：jpg、jpeg、png
5. 支持的文档格式：Markdown

## 📝TODO

- [ ] 批量导入/导出工具
- [ ] 高级搜索过滤器（EXIF元数据）
- [ ] 智能相册自动分类
- [ ] 用户认证和权限管理

