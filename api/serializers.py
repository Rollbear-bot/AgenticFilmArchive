"""
API Serializers - 数据序列化器
"""

from rest_framework import serializers


class ResourceSerializer(serializers.Serializer):
    """资源序列化器"""

    id = serializers.IntegerField(read_only=True)
    file_name = serializers.CharField()
    file_path = serializers.CharField()
    file_type = serializers.CharField()
    thumbnail_url = serializers.CharField(required=False)
    scene_tags = serializers.CharField(required=False, allow_blank=True)
    style_tags = serializers.CharField(required=False, allow_blank=True)
    film_tags = serializers.CharField(required=False, allow_blank=True)
    full_tags = serializers.CharField(required=False, allow_blank=True)
    score = serializers.FloatField(required=False)
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)
    content = serializers.CharField(required=False, allow_blank=True)  # 用于图片预览


class ResourceListSerializer(serializers.Serializer):
    """资源列表响应序列化器"""

    total = serializers.IntegerField()
    image_count = serializers.IntegerField(required=False, default=0)
    doc_count = serializers.IntegerField(required=False, default=0)
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    results = ResourceSerializer(many=True)


class ResourceSearchSerializer(serializers.Serializer):
    """资源搜索请求序列化器"""

    query = serializers.CharField(required=True)
    k = serializers.IntegerField(required=False, default=10)
    doc_type = serializers.ChoiceField(choices=["any", "image", "text"], required=False, default="any")
    scene_tags = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    style_tags = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    film_tags = serializers.ListField(child=serializers.CharField(), required=False, default=list)


class ChatMessageSerializer(serializers.Serializer):
    """对话消息序列化器"""

    message = serializers.CharField(required=True)
    history_id = serializers.CharField(required=False, allow_null=True)
    include_resources = serializers.BooleanField(required=False, default=True)


class ChatResponseSerializer(serializers.Serializer):
    """对话响应序列化器"""

    answer = serializers.CharField()
    resources_used = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    history_id = serializers.CharField(required=False)
    conversation_id = serializers.CharField(required=False)


class AgentChatMessageSerializer(serializers.Serializer):
    """Agent 对话消息序列化器"""

    message = serializers.CharField(required=True)
    thread_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    conversation_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class ChatHistorySerializer(serializers.Serializer):
    """对话历史序列化器"""

    id = serializers.IntegerField()
    session_id = serializers.CharField()
    user_message = serializers.CharField()
    ai_message = serializers.CharField()
    resources_used = serializers.ListField(child=serializers.CharField(), required=False)
    created_at = serializers.DateTimeField()


class SyncResponseSerializer(serializers.Serializer):
    """同步响应序列化器"""

    status = serializers.CharField()
    files_scanned = serializers.IntegerField()
    files_added = serializers.IntegerField()
    files_failed = serializers.IntegerField()
    message = serializers.CharField()


class HealthCheckSerializer(serializers.Serializer):
    """健康检查响应序列化器"""

    status = serializers.CharField()
    version = serializers.CharField()
    database = serializers.CharField()
    vector_db = serializers.CharField()


class ConfigSerializer(serializers.Serializer):
    """配置信息序列化器"""

    app_name = serializers.CharField()
    version = serializers.CharField()
    resource_dir = serializers.CharField()
    vector_db_path = serializers.CharField()


# ---------------------------------------------------------------------------
# 对话管理序列化器
# ---------------------------------------------------------------------------


class ConversationListSerializer(serializers.Serializer):
    """对话列表项（元数据）"""

    id = serializers.CharField()
    title = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    message_count = serializers.IntegerField()


class ConversationDetailSerializer(serializers.Serializer):
    """完整对话（含消息列表）"""

    id = serializers.CharField()
    title = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    messages = serializers.ListField(child=serializers.DictField())


class ConversationCreateSerializer(serializers.Serializer):
    """创建对话请求"""

    title = serializers.CharField(required=False, allow_blank=True)


# ---------------------------------------------------------------------------
# 长期记忆序列化器
# ---------------------------------------------------------------------------


class MemoryReadSerializer(serializers.Serializer):
    """长期记忆内容"""

    content = serializers.CharField()


class MemoryWriteSerializer(serializers.Serializer):
    """写入长期记忆请求"""

    content = serializers.CharField(required=True)
    mode = serializers.ChoiceField(
        choices=["append", "overwrite"], default="append", required=False
    )
