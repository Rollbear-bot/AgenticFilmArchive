"""
Core URL configuration - 前端页面路由
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('resources/', views.resource_list, name='resource_list'),
    path('resources/<int:resource_id>/', views.resource_detail, name='resource_detail'),
    path('search/', views.search_page, name='search_page'),
    path('chat/', views.chat_page, name='chat_page'),
    path('sync/', views.sync_page, name='sync_page'),
]
