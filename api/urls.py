"""
API URL configuration - RESTful API路由
"""
from django.urls import path
from . import views

urlpatterns = [
    # 健康检查和配置
    path('health/', views.health_check, name='health_check'),
    path('config/', views.get_config, name='get_config'),
    
    # 资源管理接口
    path('resources/', views.resource_list_api, name='resource_list_api'),
    path('resources/<int:resource_id>/', views.resource_detail_api, name='resource_detail_api'),
    path('resources/search/', views.resource_search_api, name='resource_search_api'),
    path('resources/sync/', views.resource_sync_api, name='resource_sync_api'),
    path('resources/<int:resource_id>/tags/', views.resource_tags_api, name='resource_tags_api'),
    path('resources/<int:resource_id>/download/', views.resource_download_api, name='resource_download_api'),
    
    # 对话接口
    path('chat/', views.chat_api, name='chat_api'),
    path('chat/history/', views.chat_history_api, name='chat_history_api'),
]
