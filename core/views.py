"""
Core Views - 页面视图层
重定向到React SPA应用
"""
from django.http import HttpResponse
from django.conf import settings


def react_app_view(request):
    """渲染React应用入口页面"""
    dist_index = settings.BASE_DIR / 'frontend' / 'dist' / 'index.html'

    if not dist_index.exists():
        return HttpResponse(
            '<h1>前端未构建</h1>'
            '<p>请运行以下命令构建前端：</p>'
            '<pre>cd frontend && npm install && npm run build</pre>',
            status=503,
            content_type='text/html'
        )

    try:
        with open(dist_index, 'r', encoding='utf-8') as f:
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
