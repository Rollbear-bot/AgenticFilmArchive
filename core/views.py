"""
Core Views - 页面视图层
重定向到React SPA应用
"""
from django.http import HttpResponse
from django.conf import settings


def react_app_view(request):
    """渲染React应用入口页面"""
    try:
        with open(settings.BASE_DIR / 'templates' / 'react-index.html', 'r', encoding='utf-8') as f:
            content = f.read()
        return HttpResponse(content, content_type='text/html')
    except Exception as e:
        return HttpResponse(f'Error loading React app: {e}', status=500)


def index(request):
    """首页"""
    return react_app_view(request)


def resource_list(request):
    """资源列表页面"""
    return react_app_view(request)


def resource_detail(request, resource_id):
    """资源详情页面"""
    return react_app_view(request)


def search_page(request):
    """搜索页面"""
    return react_app_view(request)


def chat_page(request):
    """对话页面"""
    return react_app_view(request)


def sync_page(request):
    """同步页面"""
    return react_app_view(request)
