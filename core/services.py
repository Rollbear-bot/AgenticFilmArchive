"""
Core Services - 核心服务层
重构自tools.py，提供图片处理和标签生成服务
"""
import base64
import os
from io import BytesIO
from PIL import Image
from volcenginesdkarkruntime import Ark
from configures import *


# 初始化火山平台的多模态大模型客户端
_img_client = Ark(
    base_url=ARK_ENDPOINT,
    api_key=ARK_API_KEY,
)


def image_to_base64(image_path: str) -> str:
    """将本地图片转换为base64数据URL，大于3MB的图片使用缩略图"""
    SIZE_THRESHOLD = 3 * 1024 * 1024  # 3MB
    
    _, ext = os.path.splitext(image_path)
    ext = ext.lower().lstrip('.')
    if ext not in ['jpg', 'jpeg', 'png']:
        raise ValueError(f"不支持的图片格式: {ext}")
    
    if ext == 'jpg':
        ext = 'jpeg'
    
    file_size = os.path.getsize(image_path)
    
    if file_size > SIZE_THRESHOLD:
        with Image.open(image_path) as img:
            img.thumbnail((1024, 1024))
            buffer = BytesIO()
            img.save(buffer, format=ext.upper())
            buffer.seek(0)
            base64_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
    else:
        with open(image_path, "rb") as f:
            base64_data = base64.b64encode(f.read()).decode('utf-8')
    
    image_data_url = f"data:image/{ext};base64,{base64_data}"
    return image_data_url


def generate_photo_tags(image_path: str) -> str:
    """为一张照片生成标签"""
    print(f"正在为照片生成标签: {image_path}")
    
    try:
        image_url = image_to_base64(image_path)
        prompt = PROMPTS.IMAGE_TAGGER
        
        completion = _img_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            reasoning_effort="medium",
        )
        
        return completion.choices[0].message.content
    except Exception as e:
        return f"生成照片标签时出错: {str(e)}"


def parse_tags(tags_string: str) -> dict:
    """解析标签字符串，返回各类型标签列表"""
    result = {
        'scene_tags': [],
        'style_tags': [],
        'film_tags': []
    }
    
    if not tags_string or tags_string.startswith("生成照片标签时出错"):
        return result
    
    try:
        if ';' in tags_string:
            parts = tags_string.split(';')
            if len(parts) >= 3:
                result['scene_tags'] = [t.strip() for t in parts[0].split(',') if t.strip()]
                result['style_tags'] = [t.strip() for t in parts[1].split(',') if t.strip()]
                result['film_tags'] = [t.strip() for t in parts[2].split(',') if t.strip()]
    except Exception:
        pass
    
    return result


def get_image_client():
    """获取图片处理客户端"""
    return _img_client
