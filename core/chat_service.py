"""
Chat Service - 对话服务层
提供AI对话和图片理解功能
"""

from langchain_openai import ChatOpenAI
from volcenginesdkarkruntime import Ark

from configures import ARK_API_KEY, ARK_ENDPOINT, CHAT_MODEL, VISION_MODEL
from core.services import image_to_base64
from core.vector_db import get_vector_db_service


class ChatService:
    """对话服务类"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.llm = ChatOpenAI(
                model=CHAT_MODEL,
                openai_api_base=ARK_ENDPOINT,
                openai_api_key=ARK_API_KEY,
                temperature=0.7,
                max_tokens=2048,
            )

            self.img_client = Ark(
                base_url=ARK_ENDPOINT,
                api_key=ARK_API_KEY,
            )

            self.vec_db = get_vector_db_service()
            self._agent_service = None  # 延迟初始化 AgentService
            self._initialized = True

    def _get_agent_service(self):
        """延迟初始化 Agent 服务（避免 Django 启动时加载模型）"""
        if self._agent_service is None:
            from core.agent_service import get_agent_service

            self._agent_service = get_agent_service()
        return self._agent_service

    def chat_with_agent(self, message: str, thread_id: str | None = None) -> dict:
        """使用 LangGraph Agent 处理用户消息

        Agent 会自主决定是否需要检索知识库、分析图片或按标签搜索。

        Args:
            message: 用户消息
            thread_id: 会话线程 ID，用于多轮对话。不传则自动生成。

        Returns:
            {
                "answer": str,          # Agent 最终回答
                "resources_used": list, # 工具调用记录
                "history_id": str,      # thread_id（用于后续对话）
            }
        """
        agent = self._get_agent_service()
        result = agent.chat(message, thread_id=thread_id)

        return {
            "answer": result["answer"],
            "resources_used": result["tool_calls"],
            "history_id": result["thread_id"],
        }

    def retrieve_documents(
        self,
        query: str,
        k: int = 3,
        doc_type: str = "any",
        scene_tags: list = None,
        style_tags: list = None,
        film_tags: list = None,
    ) -> str:
        """检索相关文档"""
        print(f"\n[检索] 搜索与查询相关的文档: {query}")

        docs = self.vec_db.search(
            query=query,
            k=k,
            doc_type=doc_type if doc_type != "any" else None,
            scene_tags=scene_tags,
            style_tags=style_tags,
            film_tags=film_tags,
        )

        formatted_content = []
        for i, item in enumerate(docs):
            doc = item["document"]
            meta = doc.metadata

            if meta.get("type") == "text":
                content = doc.page_content[:800]
                formatted_content.append(f"文档 {i + 1} (文本): {content}...")
            elif meta.get("type") == "image":
                file_name = meta.get("file_name", "未知图像")
                scene = meta.get("scene_tags", "未知")
                style = meta.get("style_tags", "未知")
                film = meta.get("film_tags", "未知")

                formatted_content.append(f"文档 {i + 1} (图像): {file_name}")
                formatted_content.append(f"   场景标签: {scene}")
                formatted_content.append(f"   风格标签: {style}")
                formatted_content.append(f"   胶片特征: {film}")

        return "\n".join(formatted_content) if formatted_content else "未找到相关文档"

    def understand_image(self, image_path: str, prompt: str) -> str:
        """理解图片内容"""
        print(f"\n[理解] 正在理解图片: {image_path}")

        try:
            image_url = image_to_base64(image_path)

            completion = self.img_client.chat.completions.create(
                model=VISION_MODEL,
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
            return f"理解图片时出错: {str(e)}"

    def understand_multiple_images(self, image_paths: list, prompt: str) -> str:
        """理解多张图片"""
        print(f"\n[理解] 正在理解 {len(image_paths)} 张图片")

        results = []
        for path in image_paths:
            result = self.understand_image(path, prompt)
            results.append(f"照片{path}的回答：{result}")

        return "\n".join(results)

    def chat(self, message: str, include_resources: bool = True) -> dict:
        """处理用户消息并返回回答"""
        tool_calls = []  # 记录工具调用
        context = ""

        if include_resources:
            # 调用检索工具
            search_result = self.vec_db.search(
                query=message, k=3, doc_type=None, scene_tags=None, style_tags=None, film_tags=None
            )

            tool_calls.append({"tool": "retrieve_documents", "query": message, "result_count": len(search_result)})

            # 格式化检索结果
            formatted_content = []
            for i, item in enumerate(search_result):
                doc = item["document"]
                meta = doc.metadata

                if meta.get("type") == "text":
                    content = doc.page_content[:800]
                    formatted_content.append(f"文档 {i + 1} (文本): {content}...")
                elif meta.get("type") == "image":
                    file_name = meta.get("file_name", "未知图像")
                    scene = meta.get("scene_tags", "未知")
                    style = meta.get("style_tags", "未知")
                    film = meta.get("film_tags", "未知")

                    formatted_content.append(f"文档 {i + 1} (图像): {file_name}")
                    formatted_content.append(f"   场景标签: {scene}")
                    formatted_content.append(f"   风格标签: {style}")
                    formatted_content.append(f"   胶片特征: {film}")

            context = "\n".join(formatted_content) if formatted_content else "未找到相关文档"

        # 构建提示词
        system_prompt = """你是一个专业的胶片摄影助手。你可以基于知识库中的文档和图片回答用户关于胶片摄影的问题。
当检索到相关内容时，优先基于这些内容回答问题。如果没有检索到相关内容，可以基于你的知识回答。
请用简洁、专业的中文回答。"""

        if context:
            system_prompt += f"\n\n参考信息：\n{context}"

        try:
            # 直接使用Ark SDK调用
            completion = self.img_client.chat.completions.create(
                model=CHAT_MODEL,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": message}],
                temperature=0.7,
                max_tokens=2048,
            )

            answer = completion.choices[0].message.content

            return {"answer": answer, "resources_used": tool_calls, "history_id": None}
        except Exception as e:
            return {"answer": f"抱歉，处理您的消息时出错：{str(e)}", "resources_used": tool_calls, "history_id": None}


# 获取单例实例的函数
def get_chat_service() -> ChatService:
    """获取对话服务单例"""
    return ChatService()
