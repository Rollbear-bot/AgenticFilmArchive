"""
URL configuration for film_archive project.
"""
from django.urls import path, re_path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse


# React应用入口视图
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


# Favicon处理
def favicon_view(request):
    """返回空的favicon响应"""
    return HttpResponse(status=204)


urlpatterns = [
    # API路由
    path('api/v1/', include('api.urls')),
    
    # 页面路由 - 使用core应用
    path('', include('core.urls')),
    
    # Favicon
    path('favicon.ico', favicon_view),
    
    # React SPA 路由 - 捕获所有其他非静态文件请求
    re_path(r'^(?!api/|static/|favicon\.)(.*)$', react_app_view, name='react_app'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
