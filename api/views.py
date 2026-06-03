"""
API Views - API视图层
处理RESTful API请求
"""

import asyncio
import json
import os

from django.http import FileResponse
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from api.serializers import (
    AgentChatMessageSerializer,
    ChatMessageSerializer,
    ChatResponseSerializer,
    ConfigSerializer,
    HealthCheckSerializer,
    ResourceListSerializer,
    ResourceSearchSerializer,
    ResourceSerializer,
    SyncResponseSerializer,
)
from configures import RES_DIR, VECTOR_DB_PATH
from core.chat_service import get_chat_service
from core.vector_db import get_vector_db_service


# 健康检查
@api_view(["GET"])
def health_check(request):
    """健康检查接口"""
    vec_db = get_vector_db_service()
    db_status = "ready" if vec_db.vector_store is not None else "initializing"

    data = {"status": "healthy", "version": "1.0.0", "database": "sqlite", "vector_db": db_status}

    serializer = HealthCheckSerializer(data)
    return Response(serializer.data)


# 配置信息
@api_view(["GET"])
def get_config(request):
    """获取系统配置"""
    data = {
        "app_name": "胶片摄影归档系统",
        "version": "1.0.0",
        "resource_dir": RES_DIR,
        "vector_db_path": VECTOR_DB_PATH,
    }

    serializer = ConfigSerializer(data)
    return Response(serializer.data)


# 资源列表
@api_view(["GET"])
def resource_list_api(request):
    """获取资源列表（按文件聚合，避免重复）"""
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("page_size", 20))

    vec_db = get_vector_db_service()

    # 获取聚合后的资源列表
    all_resources = vec_db.get_all_resources(limit=page_size, offset=(page - 1) * page_size, aggregate=True)

    # 获取唯一文件总数及各类型统计
    total_count = vec_db.get_unique_file_count()
    image_count = vec_db.get_file_count_by_type("image")
    doc_count = vec_db.get_file_count_by_type("text")

    # 序列化结果
    results = []
    for r in all_resources:
        result_item = {
            "id": r["id"],
            "file_name": r["file_name"],
            "file_path": r["file_path"],
            "file_type": r["file_type"],
            "scene_tags": r["scene_tags"],
            "style_tags": r["style_tags"],
            "film_tags": r["film_tags"],
            "full_tags": r["full_tags"],
        }
        # 如果是图片且有content字段，添加到结果中用于缩略图
        if r["file_type"] == "image" and "content" in r and r["content"]:
            result_item["content"] = r["content"]
        results.append(result_item)

    data = {
        "total": total_count,
        "image_count": image_count,
        "doc_count": doc_count,
        "page": page,
        "page_size": page_size,
        "results": results,
    }

    serializer = ResourceListSerializer(data)
    return Response(serializer.data)


# 资源详情
@api_view(["GET"])
def resource_detail_api(request, resource_id):
    """获取资源详情"""
    vec_db = get_vector_db_service()
    resource = vec_db.get_resource_by_id(resource_id)

    if resource is None:
        return Response({"message": "资源不存在"}, status=status.HTTP_404_NOT_FOUND)

    serializer = ResourceSerializer(resource)
    return Response(serializer.data)


# 资源搜索
@api_view(["GET", "POST"])
def resource_search_api(request):
    """搜索资源"""
    if request.method == "GET":
        query = request.GET.get("query", "")
        k = int(request.GET.get("k", 10))
        doc_type = request.GET.get("doc_type", "any")

        scene_tags = request.GET.getlist("scene_tags", [])
        style_tags = request.GET.getlist("style_tags", [])
        film_tags = request.GET.getlist("film_tags", [])
    else:
        serializer = ResourceSearchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        query = data["query"]
        k = data.get("k", 10)
        doc_type = data.get("doc_type", "any")
        scene_tags = data.get("scene_tags", [])
        style_tags = data.get("style_tags", [])
        film_tags = data.get("film_tags", [])

    vec_db = get_vector_db_service()
    results = vec_db.search(
        query=query,
        k=k,
        doc_type=doc_type if doc_type != "any" else None,
        scene_tags=scene_tags if scene_tags else None,
        style_tags=style_tags if style_tags else None,
        film_tags=film_tags if film_tags else None,
    )

    serialized_results = []
    for item in results:
        doc = item["document"]
        meta = doc.metadata

        result = {
            "id": 0,
            "file_name": meta.get("file_name", ""),
            "file_path": meta.get("file_path", ""),
            "file_type": meta.get("type", ""),
            "score": item["score"],
            "scene_tags": meta.get("scene_tags", ""),
            "style_tags": meta.get("style_tags", ""),
            "film_tags": meta.get("film_tags", ""),
            "full_tags": meta.get("full_tags", ""),
        }

        # 如果是图片，尝试获取content字段用于缩略图
        if meta.get("type") == "image":
            # 从主块获取content字段
            primary_resource = vec_db.get_resource_by_file_path(meta.get("file_path", ""))
            if primary_resource and "content" in primary_resource:
                result["content"] = primary_resource["content"]

        serialized_results.append(result)

    # 去重：同一文件只保留得分最高的块
    # 使用规范化后的路径进行比较（去除 ./ 和 ../ 前缀，统一斜杠）
    def normalize_path(path):
        if not path:
            return ""
        # 统一使用正斜杠
        path = path.replace("\\", "/")
        # 去除 ./ 和 ../
        path = path.lstrip("./").lstrip("../")
        # 去除多余斜杠
        while "//" in path:
            path = path.replace("//", "/")
        return path

    seen_files = {}
    unique_results = []
    for r in serialized_results:
        normalized_path = normalize_path(r["file_path"])
        if normalized_path not in seen_files:
            seen_files[normalized_path] = r["score"]
            r["file_path"] = normalized_path  # 使用规范化后的路径
            unique_results.append(r)

    # 按得分排序
    unique_results.sort(key=lambda x: -x["score"])

    return Response({"query": query, "count": len(unique_results), "results": unique_results})


# 资源同步
@api_view(["POST"])
def resource_sync_api(request):
    """同步资源目录"""
    vec_db = get_vector_db_service()

    img_result = vec_db.load_images(f"{RES_DIR}/img")
    doc_result = vec_db.load_text_documents(f"{RES_DIR}/doc")
    pdf_result = vec_db.load_pdf_documents(f"{RES_DIR}/pdf")

    total_scanned = (
        img_result.get("count", 0)
        + img_result.get("skipped", 0)
        + doc_result.get("count", 0)
        + doc_result.get("skipped", 0)
        + pdf_result.get("count", 0)
        + pdf_result.get("skipped", 0)
    )
    total_added = (
        img_result.get("count", 0)
        + doc_result.get("count", 0)
        + pdf_result.get("count", 0)
    )
    total_failed = 0

    data = {
        "status": "completed",
        "files_scanned": total_scanned,
        "files_added": total_added,
        "files_failed": total_failed,
        "message": f"同步完成，新增 {total_added} 个资源",
    }

    serializer = SyncResponseSerializer(data)
    return Response(serializer.data)


# 资源标签
@api_view(["GET"])
def resource_tags_api(request, resource_id):
    """获取资源标签"""
    vec_db = get_vector_db_service()
    resource = vec_db.get_resource_by_id(resource_id)

    if resource is None:
        return Response({"message": "资源不存在"}, status=status.HTTP_404_NOT_FOUND)

    return Response(
        {
            "scene_tags": resource["scene_tags"],
            "style_tags": resource["style_tags"],
            "film_tags": resource["film_tags"],
            "full_tags": resource["full_tags"],
        }
    )


# 资源下载
@api_view(["GET"])
def resource_download_api(request, resource_id):
    """下载资源文件"""
    vec_db = get_vector_db_service()
    resource = vec_db.get_resource_by_id(resource_id)

    if resource is None:
        return Response({"message": "资源不存在"}, status=status.HTTP_404_NOT_FOUND)

    file_path = resource["file_path"]
    if not os.path.exists(file_path):
        return Response({"message": "文件不存在"}, status=status.HTTP_404_NOT_FOUND)

    file_name = resource["file_name"]
    response = FileResponse(open(file_path, "rb"))
    response["Content-Disposition"] = f'attachment; filename="{file_name}"'
    return response


# 对话接口
@api_view(["POST"])
def chat_api(request):
    """处理对话消息"""
    serializer = ChatMessageSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    message = data["message"]
    include_resources = data.get("include_resources", True)

    chat_service = get_chat_service()
    result = chat_service.chat(message, include_resources=include_resources)

    response_serializer = ChatResponseSerializer(result)
    return Response(response_serializer.data)


# Agent 对话接口
@api_view(["POST"])
def agent_chat_api(request):
    """Agent 对话接口 - 使用 LangGraph ReAct Agent

    Agent 会自主决定是否需要检索知识库、分析图片或按标签搜索。
    支持多轮对话（通过 thread_id）。
    """
    serializer = AgentChatMessageSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    message = data["message"]
    thread_id = data.get("thread_id") or None

    chat_service = get_chat_service()
    result = chat_service.chat_with_agent(message, thread_id=thread_id)

    response_serializer = ChatResponseSerializer(result)
    return Response(response_serializer.data)


# Agent 流式对话接口（SSE）
@api_view(["POST"])
def agent_chat_stream_api(request):
    """Agent 流式对话接口 - SSE (Server-Sent Events)

    实时推送 Agent 的思考过程、工具调用和回答内容。
    事件类型：thinking | text | tool_start | tool_end | tool_images | done | error

    使用 queue + threading 将异步 astream_events 桥接到同步 WSGI 流，
    确保每个事件即时推送到客户端。
    """
    import queue
    import threading

    from django.http import StreamingHttpResponse

    serializer = AgentChatMessageSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    message = data["message"]
    thread_id = data.get("thread_id") or None

    chat_service = get_chat_service()

    # 用 Queue 桥接异步 Agent → 同步 WSGI 流
    q: queue.Queue = queue.Queue()

    def _run_async_agent():
        """在独立线程中运行异步 Agent，将 SSE 事件推入队列"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async def _collect():
                async for sse_chunk in chat_service.chat_with_agent_stream(message, thread_id=thread_id):
                    q.put(sse_chunk.encode("utf-8"))
                q.put(None)  # 结束哨兵
            loop.run_until_complete(_collect())
        except Exception as e:
            q.put(_sse_event_bytes("error", {"message": str(e)}))
            q.put(None)
        finally:
            loop.close()

    t = threading.Thread(target=_run_async_agent, daemon=True)
    t.start()

    def _sync_generator():
        while True:
            item = q.get()
            if item is None:
                break
            yield item

    response = StreamingHttpResponse(
        _sync_generator(),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    response["Access-Control-Allow-Origin"] = "*"
    return response


def _sse_event_bytes(event_type: str, data: dict) -> bytes:
    """内联 SSE 格式化（bytes 版本，避免在异步线程中导入 api.sse）"""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode()


# 对话历史
@api_view(["GET", "DELETE"])
def chat_history_api(request):
    """获取或清除对话历史"""
    if request.method == "DELETE":
        return Response({"message": "对话历史已清除"})

    return Response({"history": [], "message": "对话历史记录功能开发中"})
