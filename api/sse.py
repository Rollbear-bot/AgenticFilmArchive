"""
SSE (Server-Sent Events) 工具函数
"""

import json
from typing import Any


def sse_event(event_type: str, data: dict[str, Any]) -> str:
    """将数据格式化为 SSE 事件字符串"""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
