# 配置参数
import os

from dotenv import load_dotenv

# 加载.env文件中的环境变量
load_dotenv()

# 从环境变量获取配置，设置默认值作为备选
ARK_ENDPOINT = os.environ.get("ARK_ENDPOINT")
ARK_API_KEY = os.getenv("ARK_API_KEY", "your-key")
EMBED_MODEL = os.getenv("EMBED_MODEL", "doubao-embedding-vision-250615")
VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH")
RES_DIR = os.getenv("RES_DIR", "resources")
CHAT_MODEL = os.getenv("CHAT_MODEL", "doubao-seed-1-6-251015")
VISION_MODEL = os.getenv("VISION_MODEL", "doubao-seed-1-6-251015")

# Reranker 配置
RERANK_STRATEGY = os.getenv("RERANK_STRATEGY", "alibaba")
RERANK_LOCAL_MODEL = os.getenv("RERANK_LOCAL_MODEL", "BAAI/bge-reranker-base")

# 阿里云 DashScope Rerank 配置
RERANK_ALIBABA_MODEL = os.getenv("RERANK_ALIBABA_MODEL", "qwen3-rerank")
RERANK_ALIBABA_MULTIMODAL_MODEL = os.getenv(
    "RERANK_ALIBABA_MULTIMODAL_MODEL", "qwen3-vl-rerank"
)
RERANK_ALIBABA_ENDPOINT = os.getenv(
    "RERANK_ALIBABA_ENDPOINT",
    "https://dashscope.aliyuncs.com/compatible-api/v1/reranks",
)
RERANK_ALIBABA_MULTIMODAL_ENDPOINT = os.getenv(
    "RERANK_ALIBABA_MULTIMODAL_ENDPOINT",
    "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank",
)
RERANK_ALIBABA_API_KEY = os.getenv("RERANK_ALIBABA_API_KEY", "")


class PROMPTS:
    IMAGE_TAGGER = """
    你是一个具有经验的摄影师，你具备丰富的照片拍摄经验和对不同场景、风格和胶片特征的理解。
    你现在负责为照片打标签，具体为照片的“拍摄场景”、“拍摄风格”和“胶片特征”标签。
    
    拍摄场景是指照片中所呈现的自然环境、人工环境或混合环境。根据远、中、近景，照片可以具有多个场景标签。
    拍摄风格是指照片中所呈现的艺术风格或创作风格，例如人像、风光、街拍、生活、抽象等。可以具有多个标签。
    胶片特征是指照片中所呈现的胶片类型和胶片视觉表现，例如彩色负片、黑白负片、细腻颗粒等。
    你应当将传入照片视为胶片拍摄的照片，可以具有多个标签。
    
    对每个字段，如果你认为可以具有多个标签，使用","分隔标签；不同字段之间用半角分号";"分隔。
    如果无法生成某个标签，用"未知"代替。
    
    示例1：
    输入：一张照片，场景是城市、江边，风格是风光，胶片特征是黑白负片、粗颗粒。
    输出：城市,江边;风光;黑白负片,粗颗粒
    
    示例2:  
    输入：一张照片，场景是公园、旋转木马，风格是生活，胶片特征是彩色负片。
    输出：公园,旋转木马;生活;彩色负片
    
    注意：标签应该尽可能简短，你必须按照上面指定的格式返回标签，不要返回其他内容。
    """
