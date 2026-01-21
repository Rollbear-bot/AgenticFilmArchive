from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from volcenginesdkarkruntime import Ark
import concurrent.futures

from configures import *
from tools import image_to_base64
from vecDb_handler import VecDB

print("初始化聊天模型...")
llm = ChatOpenAI(
    model=CHAT_MODEL,
    openai_api_base=ARK_ENDPOINT,
    openai_api_key=ARK_API_KEY,
    temperature=0.7,  # 控制生成随机性
    max_tokens=2048  # 控制生成长度
)

# 初始化向量数据库
print("初始化向量数据库...")
vec_db = VecDB(VECTOR_DB_PATH, RES_DIR)

# 初始化图片理解agent的客户端
img_client = Ark(
    base_url=ARK_ENDPOINT,
    api_key=ARK_API_KEY,
)


@tool
def retrieve_documents(query: str, k: int = 3, doc_type: str = "any", scene_tags: list = None, style_tags: list = None, film_tags: list = None) -> str:
    """从向量数据库检索相关文档。只在需要事实性答案时使用此工具，特别是关于胶片摄影档案的信息。
    可能会检索到文本文档和图片两种类型的文档。
    对于文本文档，该检索会返回文本内容；对于图片文档，该检索会返回图片的路径和标签信息。

    Args:
        :param doc_type: 要检索的文档类型，可选"any"（任意类型）、"text"（仅文本）、"image"（仅图片），
        除非你很确定需要检索的文档类型，否则建议使用"any"。
        :param query: 要搜索的查询文本
        :param k: 返回的文档数量，默认3个
        :param scene_tags: 可选参数，指定要过滤的场景标签列表
        :param style_tags: 可选参数，指定要过滤的风格标签列表
        :param film_tags: 可选参数，指定要过滤的胶片特征标签列表
    """
    print(f"\n[Tool Using] 正在搜索与查询相关的文档: {query}, type: {doc_type}, scene_tags: {scene_tags}, "
          f"style_tags: {style_tags}, film_tags: {film_tags}")
    docs = vec_db.search_similar_documents(
        query, 
        k=k, 
        doc_type=None if doc_type == "any" else doc_type,
        scene_tags=scene_tags,
        style_tags=style_tags,
        film_tags=film_tags
    )

    formatted_content = []
    for i, doc in enumerate(docs):
        if doc.metadata.get('type') == 'text':
            # 文本文档，直接使用内容
            content = doc.page_content[:800]  # 限制内容长度
            formatted_content.append(f"文档 {i + 1} (文本): {content}...")
        elif doc.metadata.get('type') == 'image':
            # 图像文档，使用元数据信息
            file_name = doc.metadata.get('file_name', '未知图像')
            file_path = doc.metadata.get('file_path', '未知路径')
            # 获取标签信息
            scene_tags = doc.metadata.get('scene_tags', '未知')
            style_tags = doc.metadata.get('style_tags', '未知')
            film_tags = doc.metadata.get('film_tags', '未知')
            
            formatted_content.append(f"文档 {i + 1} (图像): {file_name} - {file_path}")
            formatted_content.append(f"   场景标签: {scene_tags}")
            formatted_content.append(f"   风格标签: {style_tags}")
            formatted_content.append(f"   胶片特征: {film_tags}")

    return "\n".join(formatted_content) if formatted_content else "未找到相关文档"


@tool
def understand_image(image_path: str, prompt: str) -> str:
    """理解图片内容。当需要理解图片中的内容时使用此工具。需要提供图片路径和要询问的问题。
    若要获取图片路径，你应当先使用retrieve_documents工具检索向量数据库。

    Args:
        :param prompt: 要询问的问题
        :param image_path: 图片路径
    """
    print(f"\n正在理解图片: {image_path}")
    print(f"理解图片的问题: {prompt}")

    try:
        # 将图片转换为base64
        image_url = image_to_base64(image_path)

        # 调用图片理解模型
        completion = img_client.chat.completions.create(
            model=VISION_MODEL,
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
        return f"理解图片时出错: {str(e)}"


@tool
def understand_multi_img(image_paths: list, prompt: str) -> str:
    """理解多张图片内容，对于多张图片提问同一个问题。
    当需要理解多张图片中的内容时使用此工具。需要提供图片路径列表和要询问的问题。
    若要获取图片路径，你应当先使用retrieve_documents工具检索向量数据库。
    该工具会并行处理多张图片，因此具有较高效率。
    注意：每张图片的处理是相互独立的，你给出的问题（prompt）会分别独立作用于每张图片

    Args:
        :param prompt: 要询问的问题
        :param image_paths: 图片路径的列表
        :return 每张图片的回答，每个回答之间用换行符隔开；示例：照片{image_paths[i]}的回答：{result}\n
    """
    print(f"[Tool Using] 正在理解多张图片: ")
    for p in image_paths:
        print(p)
    print(f"\tprompt: {prompt}")

    # 多线程并行调用理解图片函数
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # 使用executor.map并行处理所有图片
        results = executor.map(understand_image.invoke, [(p, prompt) for p in image_paths])
        results = [r for r in results if r]
    i = 0
    res_str = ""
    for result in results:
        res_str += f"照片{image_paths[i]}的回答：{result}\n"
        i += 1
    return res_str


# 创建工具列表
# tools = [retrieve_documents, understand_image, generate_photo_tags]
tools = [retrieve_documents, understand_image, understand_multi_img]

# 创建代理
print("创建代理...")
agent_executor = create_agent(llm, tools)


def get_chat_response(question):
    """获取聊天机器人响应"""
    # 直接通过代理与模型交互，模型会在必要时调用检索工具和图片理解工具
    result = agent_executor.invoke({"messages": [HumanMessage(content=question)]})
    return result["messages"][-1].content


if __name__ == '__main__':
    # 交互式聊天
    print("\n胶片摄影档案管理聊天机器人已启动！")
    print("输入'退出'或'quit'结束对话。")

    while True:
        question = input("\n您的问题: ")
        if question.lower() in ['退出', 'quit']:
            print("感谢使用，再见！")
            break

        answer = get_chat_response(question)
        print(f"\n机器人回答: {answer}")