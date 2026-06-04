"""
API URL configuration - RESTful API路由
"""

from django.urls import path

from . import views

urlpatterns = [
    # 健康检查和配置
    path("health/", views.health_check, name="health_check"),
    path("config/", views.get_config, name="get_config"),
    # 资源管理接口
    path("resources/", views.resource_list_api, name="resource_list_api"),
    path("resources/<int:resource_id>/", views.resource_detail_api, name="resource_detail_api"),
    path("resources/search/", views.resource_search_api, name="resource_search_api"),
    path("resources/sync/", views.resource_sync_api, name="resource_sync_api"),
    path("resources/<int:resource_id>/tags/", views.resource_tags_api, name="resource_tags_api"),
    path("resources/<int:resource_id>/download/", views.resource_download_api, name="resource_download_api"),
    # 对话接口
    path("chat/", views.chat_api, name="chat_api"),
    path("chat/history/", views.chat_history_api, name="chat_history_api"),
    # Agent 对话接口（LangGraph ReAct Agent）
    path("agent/chat/", views.agent_chat_api, name="agent_chat_api"),
    # Agent 流式对话接口（SSE）
    path("agent/chat/stream/", views.agent_chat_stream_api, name="agent_chat_stream_api"),
    # 对话管理接口
    path("conversations/", views.conversation_list_api, name="conversation_list"),
    path("conversations/create/", views.conversation_create_api, name="conversation_create"),
    path("conversations/<str:conversation_id>/", views.conversation_detail_api, name="conversation_detail"),
    path("conversations/<str:conversation_id>/delete/", views.conversation_delete_api, name="conversation_delete"),
    # 长期记忆接口
    path("memory/", views.memory_read_api, name="memory_read"),
    path("memory/write/", views.memory_write_api, name="memory_write"),
]
