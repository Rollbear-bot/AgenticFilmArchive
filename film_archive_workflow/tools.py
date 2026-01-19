import os
import base64
from io import BytesIO

from PIL import Image
from volcenginesdkarkruntime import Ark
from langchain_core.tools import tool
from configures import ARK_API_KEY, CHAT_MODEL, PROMPTS

# 初始化火山平台的多模态大模型客户端
img_client = Ark(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=ARK_API_KEY,
)


@tool
def generate_photo_tags(image_path: str) -> str:
    """为一张照片生成标签。传入照片的路径，返回照片的拍摄场景、拍摄风格、胶片特征三类标签。
    拍摄场景是指照片中所呈现的自然环境、人工环境或混合环境。根据远、中、近景，照片可以具有多个场景标签。
    拍摄风格是指照片中所呈现的艺术风格或创作风格，例如人像、风光、街拍、生活、抽象等。可以具有多个标签。
    胶片特征是指照片中所呈现的胶片类型和胶片视觉表现，例如彩色负片、黑白负片、细腻颗粒等。可以具有多个标签。

    Args:
        :param image_path: 照片的路径
    Returns: str
        照片的拍摄场景、拍摄风格、胶片特征三类标签，用半角分号";"分隔。
        如果某个字段具有多个标签，用半角逗号","分隔标签。
        如果标签生成出错，则会返回：生成照片标签时出错

        示例1：
        输入：一张照片，场景是城市、江边，风格是风光，胶片特征是黑白负片、粗颗粒。
        输出：城市,江边;风光;黑白负片,粗颗粒
    """
    print(f"\n正在为照片生成标签: {image_path}")

    try:
        # 将图片转换为base64
        image_url = image_to_base64(image_path)

        # 调用火山平台的多模态大模型生成标签
        prompt = PROMPTS.IMAGE_TAGGER

        completion = img_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            reasoning_effort="medium",
        )

        return completion.choices[0].message.content
    except Exception as e:
        return f"生成照片标签时出错: {str(e)}"


def image_to_base64(image_path):
    """将本地图片转换为base64数据URL，大于9MB的图片使用缩略图"""
    # 定义9MB的大小阈值
    SIZE_THRESHOLD = 9 * 1024 * 1024  # 9MB

    # 根据文件扩展名设置MIME类型
    _, ext = os.path.splitext(image_path)
    ext = ext.lower().lstrip('.')
    if ext not in ['jpg', 'jpeg', 'png']:
        raise ValueError(f"不支持的图片格式: {ext}")

    if ext == 'jpg':
        ext = 'jpeg'

    # 检查文件大小
    file_size = os.path.getsize(image_path)

    if file_size > SIZE_THRESHOLD:
        print(f"  图片 {os.path.basename(image_path)} 大小 {file_size / (1024*1024):.2f}MB 超过9MB，生成缩略图...")

        # 打开图片并生成缩略图
        with Image.open(image_path) as img:
            # 保持原始宽高比，将最长边缩放到1024像素
            img.thumbnail((1024, 1024))

            # 将缩略图保存到BytesIO对象
            buffer = BytesIO()
            img.save(buffer, format=ext.upper())
            buffer.seek(0)

            # 转换为base64
            base64_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
    else:
        # 正常处理图片
        with open(image_path, "rb") as f:
            base64_data = base64.b64encode(f.read()).decode('utf-8')

    image_data_url = f"data:image/{ext};base64,{base64_data}"
    return image_data_url
