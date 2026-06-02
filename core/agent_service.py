"""
Agent Service - LangGraph ReAct Agent 服务层

使用 LangGraph 的 create_react_agent 创建支持工具调用的智能 Agent，
让 LLM 自主决定何时检索知识库、何时分析图片、何时按标签搜索。
"""

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from configures import ARK_API_KEY, ARK_ENDPOINT, CHAT_MODEL
from core.services import get_image_client, image_to_base64
from core.vector_db import get_vector_db_service

# 侧通道缓存：retrieve_knowledge 将图片的 file_path 写入此缓存，
# SSE 流处理器读取后用 image_to_base64() 生成缩略图 data URL
_tool_image_cache: dict[str, list[dict]] = {}

AGENT_SYSTEM_PROMPT = """你是一个专业的胶片摄影助手。你可以使用以下工具来帮助用户：

- **retrieve_knowledge**: 从知识库中检索胶片摄影相关的文档和图片信息
- **analyze_image**: 查看和分析具体的图片内容
- **search_by_tags**: 按场景、风格、胶片类型标签筛选和浏览资源

当用户提问时：
1. 如果问题涉及胶片摄影知识、技巧、推荐等，先使用 retrieve_knowledge 检索知识库
2. 如果用户提到具体的图片或需要查看图片内容，使用 analyze_image
3. 如果需要按类别浏览资源，使用 search_by_tags
4. 综合检索结果给出专业、准确的中文回答
5. 如果没有检索到相关内容，可以基于你的知识回答，但要说明这是通用知识而非来自用户的档案

请用简洁、专业的中文回答，并在回答中引用你使用的信息来源。"""


# ---------------------------------------------------------------------------
# Tool 定义
# ---------------------------------------------------------------------------


@tool
def retrieve_knowledge(query: str, k: int = 3, doc_type: str = "any") -> str:
    """从胶片摄影知识库中检索相关文档和图片。

    Args:
        query: 搜索查询字符串，描述你想查找的内容
        k: 返回结果数量，默认3
        doc_type: 文档类型过滤，"image"（图片）、"text"（文档）或 "any"（全部）

    Returns:
        格式化的检索结果，包含文档/图片信息和标签
    """
    vec_db = get_vector_db_service()
    results = vec_db.search(
        query=query,
        k=k,
        doc_type=doc_type if doc_type != "any" else None,
    )

    if not results:
        return "未找到相关文档或图片。"

    formatted = []
    image_paths = []  # 收集图片 file_path 用于侧通道
    for i, item in enumerate(results):
        doc = item["document"]
        meta = doc.metadata
        score = item.get("score", 0)
        rerank_score = item.get("rerank_score")

        if meta.get("type") == "image":
            formatted.append(
                f"[{i + 1}] 📷 图片: {meta.get('file_name', '未知')}\n"
                f"    路径: {meta.get('file_path', '未知')}\n"
                f"    场景: {meta.get('scene_tags', '未知')}\n"
                f"    风格: {meta.get('style_tags', '未知')}\n"
                f"    胶片: {meta.get('film_tags', '未知')}\n"
                f"    相关度: {score:.4f}" + (f" (精排: {rerank_score:.4f})" if rerank_score else "")
            )
            # 收集图片 file_path，稍后由 SSE handler 生成缩略图
            file_path = meta.get("file_path", "")
            # 用规范化路径做去重比较（去掉 ./ ../ 前缀差异）
            normalized = _normalize_fp(file_path)
            if file_path and normalized not in [p["_norm"] for p in image_paths]:
                image_paths.append({
                    "file_name": meta.get("file_name", "未知"),
                    "file_path": file_path,
                    "_norm": normalized,
                })
        else:
            content = doc.page_content[:500]
            formatted.append(
                f"[{i + 1}] 📄 文档: {meta.get('file_name', '未知')}\n"
                f"    内容: {content}...\n"
                f"    相关度: {score:.4f}" + (f" (精排: {rerank_score:.4f})" if rerank_score else "")
            )

    # 将图片路径写入侧通道缓存（LLM 不可见）
    if image_paths:
        _tool_image_cache.setdefault("latest", []).extend(image_paths)

    return "\n\n".join(formatted)


@tool
def analyze_image(file_path: str, question: str = "请详细描述这张照片的内容、构图和特点") -> str:
    """使用视觉模型分析具体的图片内容。

    Args:
        file_path: 图片文件的完整路径
        question: 你想了解的关于这张图片的具体问题

    Returns:
        视觉模型对图片的分析结果
    """
    import os

    # 使用 _resolve_path 处理 Chroma DB 中不一致的 ./ 和 ../ 前缀
    resolved_path = _resolve_path(file_path)
    if not resolved_path:
        return f"错误: 文件不存在 - {file_path}"

    try:
        image_url = image_to_base64(resolved_path)
        client = get_image_client()

        completion = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {"type": "text", "text": question},
                    ],
                }
            ],
            reasoning_effort="medium",
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"分析图片时出错: {str(e)}"


@tool
def search_by_tags(
    scene_tags: str = "",
    style_tags: str = "",
    film_tags: str = "",
) -> str:
    """按标签类别浏览和筛选胶片摄影资源。

    Args:
        scene_tags: 场景标签，用逗号分隔，如 "城市,夜景"
        style_tags: 风格标签，用逗号分隔，如 "街拍,纪实"
        film_tags: 胶片特征标签，用逗号分隔，如 "彩色负片,粗颗粒"

    Returns:
        匹配的资源列表
    """
    vec_db = get_vector_db_service()

    scene_list = [t.strip() for t in scene_tags.split(",") if t.strip()] if scene_tags else None
    style_list = [t.strip() for t in style_tags.split(",") if t.strip()] if style_tags else None
    film_list = [t.strip() for t in film_tags.split(",") if t.strip()] if film_tags else None

    if not any([scene_list, style_list, film_list]):
        return "请至少指定一种标签类型（场景、风格或胶片特征）。"

    # 使用一个通用查询来检索，然后用标签过滤
    query_parts = []
    if scene_list:
        query_parts.append(" ".join(scene_list))
    if style_list:
        query_parts.append(" ".join(style_list))
    if film_list:
        query_parts.append(" ".join(film_list))

    query = " ".join(query_parts) if query_parts else "照片"

    results = vec_db.search(
        query=query,
        k=10,
        scene_tags=scene_list,
        style_tags=style_list,
        film_tags=film_list,
    )

    if not results:
        return "未找到匹配标签的资源。"

    formatted = [f"找到 {len(results)} 个匹配资源:\n"]
    for i, item in enumerate(results):
        doc = item["document"]
        meta = doc.metadata
        formatted.append(
            f"[{i + 1}] {meta.get('file_name', '未知')} "
            f"({meta.get('type', '未知')}) | "
            f"场景: {meta.get('scene_tags', '未知')} | "
            f"风格: {meta.get('style_tags', '未知')} | "
            f"胶片: {meta.get('film_tags', '未知')}"
        )

    return "\n".join(formatted)


# ---------------------------------------------------------------------------
# Agent 工具列表
# ---------------------------------------------------------------------------

AGENT_TOOLS = [retrieve_knowledge, analyze_image, search_by_tags]


# ---------------------------------------------------------------------------
# AgentService
# ---------------------------------------------------------------------------


class AgentService:
    """LangGraph ReAct Agent 服务

    管理 Agent 的生命周期，提供同步对话接口。
    使用 MemorySaver 实现多轮对话状态管理。
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not AgentService._initialized:
            self._agent = None
            self._memory = None
            self._llm = None
            AgentService._initialized = True

    def _ensure_agent(self):
        """延迟初始化 Agent（避免 Django 启动时加载模型）"""
        if self._agent is not None:
            return

        print("[Agent] 初始化 LangGraph ReAct Agent...")

        self._llm = ChatOpenAI(
            model=CHAT_MODEL,
            openai_api_base=ARK_ENDPOINT,
            openai_api_key=ARK_API_KEY,
            temperature=0.7,
            max_tokens=2048,
        )

        self._memory = MemorySaver()

        self._agent = create_react_agent(
            model=self._llm,
            tools=AGENT_TOOLS,
            prompt=AGENT_SYSTEM_PROMPT,
            checkpointer=self._memory,
            version="v2",
        )

        print("[Agent] Agent 初始化完成")

    def chat(self, message: str, thread_id: str | None = None) -> dict[str, Any]:
        """同步对话接口

        Args:
            message: 用户消息
            thread_id: 会话线程 ID，用于多轮对话。不传则自动生成。

        Returns:
            {
                "answer": str,          # Agent 最终回答
                "tool_calls": list,     # 工具调用记录
                "thread_id": str,       # 会话线程 ID
            }
        """
        self._ensure_agent()

        if thread_id is None:
            thread_id = str(uuid.uuid4())

        config = {"configurable": {"thread_id": thread_id}}

        print(f"\n[Agent] 收到消息 (thread={thread_id[:8]}...): {message[:100]}")

        try:
            result = self._agent.invoke(
                {"messages": [HumanMessage(content=message)]},
                config=config,
            )
        except Exception as e:
            print(f"[Agent] 调用失败: {e}")
            return {
                "answer": f"抱歉，处理您的消息时出错：{str(e)}",
                "tool_calls": [],
                "thread_id": thread_id,
            }

        # 解析结果：提取最终回答和工具调用记录
        messages = result.get("messages", [])
        tool_calls = []
        final_answer = ""

        for msg in messages:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_calls.append(
                        {
                            "tool": tc.get("name", "unknown"),
                            "args": tc.get("args", {}),
                            "id": tc.get("id", ""),
                        }
                    )

            if hasattr(msg, "content") and msg.content:
                # 跳过 ToolMessage 的内容（那是工具返回值，不是最终回答）
                from langchain_core.messages import AIMessage

                if isinstance(msg, AIMessage) and not (hasattr(msg, "tool_calls") and msg.tool_calls):
                    final_answer = msg.content

        # 如果没找到纯文本 AIMessage，取最后一个有内容的 AIMessage
        if not final_answer:
            from langchain_core.messages import AIMessage

            for msg in reversed(messages):
                if isinstance(msg, AIMessage) and msg.content:
                    final_answer = msg.content
                    break

        if not final_answer:
            final_answer = "抱歉，我无法生成有效的回答。"

        # 打印工具调用摘要
        if tool_calls:
            print(f"[Agent] 调用了 {len(tool_calls)} 个工具: {[tc['tool'] for tc in tool_calls]}")

        return {
            "answer": final_answer,
            "tool_calls": tool_calls,
            "thread_id": thread_id,
        }

    async def chat_stream(self, message: str, thread_id: str | None = None) -> AsyncGenerator[str, None]:
        """流式对话接口 — 通过 astream_events 实时推送 Agent 执行过程。

        生成 SSE 格式的事件字符串，供 Django StreamingHttpResponse 消费。
        事件类型：thinking | text | tool_start | tool_end | tool_images | done | error

        Args:
            message: 用户消息
            thread_id: 会话线程 ID，用于多轮对话。不传则自动生成。

        Yields:
            SSE 格式字符串，如 "event: text\\ndata: {...}\\n\\n"
        """
        self._ensure_agent()

        if thread_id is None:
            thread_id = str(uuid.uuid4())

        config = {"configurable": {"thread_id": thread_id}}

        # 清空上一次的图片缓存
        _tool_image_cache.pop("latest", None)

        print(f"\n[Agent Stream] 收到消息 (thread={thread_id[:8]}...): {message[:100]}")

        input_data = {"messages": [HumanMessage(content=message)]}

        try:
            async for event in self._agent.astream_events(input_data, config=config, version="v2"):
                event_type = event.get("event", "")
                event_name = event.get("name", "")
                event_data = event.get("data", {})

                # --- 模型流式输出 ---
                if event_type == "on_chat_model_stream":
                    chunk = event_data.get("chunk", None)
                    if chunk is None:
                        continue

                    chunk_content = getattr(chunk, "content", "") or ""

                    # 如果模型决定调用工具，chunk 可能包含 tool_call_chunks
                    has_tool_calls = (
                        hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks
                    )

                    if has_tool_calls:
                        # 模型正在构造 tool_call，视为 thinking
                        for tc_chunk in chunk.tool_call_chunks:
                            name = getattr(tc_chunk, "name", None)
                            args = getattr(tc_chunk, "args", None)
                            if name or args:
                                thinking_parts = []
                                if name:
                                    thinking_parts.append(f"调用工具: {name}")
                                if args:
                                    thinking_parts.append(str(args))
                                yield _sse_event("thinking", {"content": " | ".join(thinking_parts)})
                    elif chunk_content:
                        yield _sse_event("text", {"content": chunk_content})

                # --- 工具开始执行 ---
                elif event_type == "on_tool_start":
                    tool_input = event_data.get("input", {})
                    # 如果 input 是 dict 且有 args，提取 args
                    args = tool_input if isinstance(tool_input, dict) else {"input": str(tool_input)}
                    yield _sse_event("tool_start", {
                        "tool": event_name,
                        "args": args if isinstance(args, dict) else {},
                    })

                # --- 工具执行完成 ---
                elif event_type == "on_tool_end":
                    output = event_data.get("output", "")
                    # ToolMessage 对象：提取 .content 属性获得纯文本结果
                    if hasattr(output, "content"):
                        output_str = str(output.content)
                    elif isinstance(output, str):
                        output_str = output
                    else:
                        output_str = str(output)
                    # 结果摘要（前 500 字符）
                    result_preview = output_str[:500] + ("..." if len(output_str) > 500 else "")

                    yield _sse_event("tool_end", {
                        "tool": event_name,
                        "result": result_preview,
                    })

                    # retrieve_knowledge 工具完成后，从缓存读取图片路径生成缩略图
                    if event_name == "retrieve_knowledge":
                        await asyncio.sleep(0)  # 让出事件循环
                        image_entries = _tool_image_cache.pop("latest", [])
                        if image_entries:
                            # 按 file_path 去重
                            seen = set()
                            unique_entries = []
                            for entry in image_entries:
                                fp = entry.get("file_path", "")
                                if fp and fp not in seen:
                                    seen.add(fp)
                                    unique_entries.append(entry)
                            thumbs = []
                            for entry in unique_entries:
                                file_path = entry.get("file_path", "")
                                file_name = entry.get("file_name", "")
                                if file_path:
                                    import os as _os
                                    # 路径规范化：处理 ./ 和 ../ 前缀不一致的问题
                                    # Chroma DB 中可能存储了带不同相对前缀的路径
                                    resolved = _resolve_path(file_path)
                                    if resolved and _os.path.exists(resolved):
                                        try:
                                            thumb_url = image_to_base64(resolved)
                                            thumbs.append({
                                                "file_name": file_name,
                                                "thumb_url": thumb_url,
                                            })
                                        except Exception as e:
                                            print(f"[WARN] 缩略图生成失败 {file_name}: {e}")
                                    else:
                                        print(f"[WARN] 图片文件不存在 (原始路径: {file_path}, 解析后: {resolved})")
                            if thumbs:
                                yield _sse_event("tool_images", {"images": thumbs})

            # --- 完成 ---
            yield _sse_event("done", {"thread_id": thread_id})

        except Exception as e:
            print(f"[Agent Stream] 错误: {e}")
            yield _sse_event("error", {"message": str(e)})


def _normalize_fp(file_path: str) -> str:
    """规范化文件路径用于去重比较，去掉 ./ 和 ../ 前缀"""
    cleaned = file_path
    while cleaned.startswith("./") or cleaned.startswith("../"):
        if cleaned.startswith("./"):
            cleaned = cleaned[2:]
        else:
            cleaned = cleaned[3:]
    return cleaned


def _resolve_path(file_path: str) -> str | None:
    """解析文件路径，处理 ./ 和 ../ 前缀不一致的问题。

    Chroma DB 在不同次同步时可能存储了带不同前缀的路径：
    - ./resources/img/photo.jpg
    - ../resources/img/photo.jpg
    - resources/img/photo.jpg

    本函数尝试多种解析方式，返回第一个存在的路径。
    """
    import os as _os

    candidates = [
        file_path,                                          # 原始路径
        file_path.lstrip("./"),                             # 去掉 ./
        file_path.lstrip("../"),                            # 去掉 ../
    ]
    # 也尝试不断去掉 ../ 前缀
    cleaned = file_path
    while cleaned.startswith("../"):
        cleaned = cleaned[3:]
        if cleaned not in candidates:
            candidates.append(cleaned)

    for path in candidates:
        if path and _os.path.exists(path):
            return path
    return None


def _sse_event(event_type: str, data: dict[str, Any]) -> str:
    """将数据格式化为 SSE 事件字符串"""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def get_agent_service() -> AgentService:
    """获取 Agent 服务单例"""
    return AgentService()
