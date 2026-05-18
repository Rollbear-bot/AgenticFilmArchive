"""
Reranker 精排器模块

基于适配器模式设计，提供统一的精排接口，支持：
- 本地精排：HuggingFaceCrossEncoder
- 云端精排：阿里云 DashScope Rerank API（纯文本 + 多模态）
"""
import base64
import io
from abc import ABC, abstractmethod

import requests

from configures import (
    RERANK_ALIBABA_API_KEY,
    RERANK_ALIBABA_ENDPOINT,
    RERANK_ALIBABA_MODEL,
    RERANK_ALIBABA_MULTIMODAL_ENDPOINT,
    RERANK_ALIBABA_MULTIMODAL_MODEL,
    RERANK_LOCAL_MODEL,
    RERANK_STRATEGY,
)


class BaseReranker(ABC):
    """精排器抽象基类"""

    @abstractmethod
    def rerank(self, query: str, documents: list[dict], top_n: int) -> list[dict]:
        """对文档列表进行精排

        Args:
            query: 用户查询字符串
            documents: 粗排结果列表，每项为 {'document': Document, 'score': float}
            top_n: 返回的精排文档数量

        Returns:
            精排后的文档列表，格式同输入
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """精排器名称"""


class LocalReranker(BaseReranker):
    """本地精排器，使用 HuggingFaceCrossEncoder 模型"""

    def __init__(self, model_name: str | None = None):
        self._model_name = model_name or RERANK_LOCAL_MODEL
        self._cross_encoder = None

    @property
    def name(self) -> str:
        return f"LocalReranker({self._model_name})"

    def _ensure_model_loaded(self):
        if self._cross_encoder is not None:
            return
        from sentence_transformers import CrossEncoder

        self._cross_encoder = CrossEncoder(self._model_name)

    def rerank(self, query: str, documents: list[dict], top_n: int) -> list[dict]:
        if not documents:
            return documents

        self._ensure_model_loaded()

        contents = [item["document"].page_content for item in documents]
        pairs = [[query, content] for content in contents]
        scores = self._cross_encoder.predict(pairs)

        scored = []
        for i, item in enumerate(documents):
            scored.append({**item, "rerank_score": float(scores[i])})

        scored.sort(key=lambda x: x["rerank_score"], reverse=True)
        return scored[:top_n]


class AlibabaReranker(BaseReranker):
    """阿里云 DashScope Rerank API 精排器

    支持纯文本 rerank（qwen3-rerank，OpenAI 兼容接口）
    和多模态 rerank（qwen3-vl-rerank，DashScope 原生接口，支持图像 + 文本混合）。
    根据输入文档类型自动选择模型和接口。

    图像处理策略：
    - 当图片 base64 data URL 超过阈值时，使用 PIL 动态压缩而非截断。
    - 压缩失败时降级为使用图片标签文本替代。
    """

    MAX_IMAGE_DOCS = 40
    MAX_TEXT_DOCS = 100
    MAX_TEXT_CONTENT_LEN = 8_000
    IMAGE_MAX_EDGE = 1024
    IMAGE_MAX_SIZE_BYTES = 200_000
    IMAGE_JPEG_QUALITY = 80

    def __init__(
        self,
        model_name: str | None = None,
        multimodal_model_name: str | None = None,
        endpoint: str | None = None,
        multimodal_endpoint: str | None = None,
        api_key: str | None = None,
    ):
        self._model_name = model_name or RERANK_ALIBABA_MODEL
        self._multimodal_model_name = multimodal_model_name or RERANK_ALIBABA_MULTIMODAL_MODEL
        self._endpoint = endpoint or RERANK_ALIBABA_ENDPOINT
        self._multimodal_endpoint = multimodal_endpoint or RERANK_ALIBABA_MULTIMODAL_ENDPOINT
        self._api_key = api_key if api_key is not None else RERANK_ALIBABA_API_KEY

    @property
    def name(self) -> str:
        return f"AlibabaReranker({self._model_name}/{self._multimodal_model_name})"

    def rerank(self, query: str, documents: list[dict], top_n: int) -> list[dict]:
        if not documents:
            return documents

        if not self._api_key:
            raise ValueError("阿里云精排需要配置 RERANK_ALIBABA_API_KEY 环境变量")

        has_image = any(
            item["document"].metadata.get("type") == "image" for item in documents
        )

        if has_image:
            return self._rerank_multimodal(query, documents, top_n)
        return self._rerank_text(query, documents, top_n)

    def _rerank_text(self, query: str, documents: list[dict], top_n: int) -> list[dict]:
        """纯文本精排，使用 OpenAI 兼容接口。"""
        contents = [item["document"].page_content for item in documents]

        body = {
            "model": self._model_name,
            "query": query,
            "documents": contents,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

        resp = requests.post(self._endpoint, json=body, headers=headers, timeout=30)

        if resp.status_code != 200:
            raise RuntimeError(
                f"阿里云精排请求失败: HTTP {resp.status_code}, {resp.text[:500]}"
            )

        result = resp.json()
        raw_results = result.get("results", [])
        return self._apply_scores(documents, raw_results, top_n)

    def _rerank_multimodal(
        self, query: str, documents: list[dict], top_n: int
    ) -> list[dict]:
        """多模态精排，支持图像 + 文本混合，使用 DashScope 原生接口。"""
        image_count = sum(
            1 for item in documents if item["document"].metadata.get("type") == "image"
        )
        if image_count > self.MAX_IMAGE_DOCS:
            raise ValueError(
                f"多模态精排图片数量超限: {image_count} > {self.MAX_IMAGE_DOCS}"
            )
        if len(documents) > self.MAX_TEXT_DOCS:
            raise ValueError(
                f"多模态精排文档数量超限: {len(documents)} > {self.MAX_TEXT_DOCS}"
            )

        api_docs: list[dict] = []
        for item in documents:
            doc = item["document"]
            content = doc.page_content
            if doc.metadata.get("type") == "image":
                compressed = self._prepare_image(content)
                api_docs.append(compressed)
            else:
                if len(content) > self.MAX_TEXT_CONTENT_LEN:
                    content = content[: self.MAX_TEXT_CONTENT_LEN]
                api_docs.append({"text": content})

        body = {
            "model": self._multimodal_model_name,
            "input": {
                "query": {"text": query},
                "documents": api_docs,
            },
            "parameters": {
                "top_n": top_n,
                "return_documents": True,
            },
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

        resp = requests.post(
            self._multimodal_endpoint, json=body, headers=headers, timeout=60
        )

        if resp.status_code != 200:
            raise RuntimeError(
                f"阿里云多模态精排请求失败: HTTP {resp.status_code}, "
                f"{resp.text[:500]}"
            )

        result = resp.json()
        output = result.get("output", {})
        raw_results = output.get("results", []) if isinstance(output, dict) else []
        return self._apply_scores(documents, raw_results, top_n)

    def _prepare_image(self, data_url: str) -> dict:
        """准备图像数据供 API 使用。

        策略：
        1. 若 data URL 长度在限制内，直接传递。
        2. 若超限，尝试 PIL 动态压缩（resize + 重新编码 JPEG）。
        3. 若压缩失败，降级为使用图片标签文本替代。

        Returns:
            {"image": data_url} 或 {"text": description}
        """
        if len(data_url) <= self.IMAGE_MAX_SIZE_BYTES:
            return {"image": data_url}

        try:
            compressed = self._compress_image_data_url(data_url)
            if len(compressed) <= self.IMAGE_MAX_SIZE_BYTES:
                return {"image": compressed}
        except Exception:
            pass

        return self._image_fallback(data_url)

    @classmethod
    def _compress_image_data_url(cls, data_url: str) -> str:
        """使用 PIL 压缩图片至目标大小以下。

        流程：
        1. 解析 data URL，提取 MIME 类型和 base64 数据。
        2. 解码为 PIL Image。
        3. 等比例缩放，最长边不超过 IMAGE_MAX_EDGE。
        4. 编码为 JPEG，质量 IMAGE_JPEG_QUALITY。
        5. 若仍超限，递归降低质量（每次降 10%）。
        6. 若质量低于 30%，递归降低分辨率（每次减半）。

        Returns:
            新的 base64 data URL 字符串。

        Raises:
            ValueError: 无法解析 data URL。
            Exception: PIL 处理失败。
        """
        from PIL import Image

        if "," in data_url:
            prefix, b64data = data_url.split(",", 1)
        else:
            raise ValueError("无效的 data URL 格式")

        img_bytes = base64.b64decode(b64data)
        img = Image.open(io.BytesIO(img_bytes))

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        max_edge = cls.IMAGE_MAX_EDGE
        quality = cls.IMAGE_JPEG_QUALITY

        while True:
            width, height = img.size
            if max(width, height) > max_edge:
                ratio = max_edge / max(width, height)
                new_size = (int(width * ratio), int(height * ratio))
                img = img.resize(new_size, Image.LANCZOS)

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            compressed_bytes = buf.getvalue()

            if len(compressed_bytes) <= cls.IMAGE_MAX_SIZE_BYTES:
                compressed_b64 = base64.b64encode(compressed_bytes).decode("ascii")
                return f"data:image/jpeg;base64,{compressed_b64}"

            if quality > 40:
                quality -= 10
                continue

            if max_edge > 256:
                max_edge //= 2
                quality = cls.IMAGE_JPEG_QUALITY
                continue

            compressed_b64 = base64.b64encode(compressed_bytes).decode("ascii")
            return f"data:image/jpeg;base64,{compressed_b64}"

    @staticmethod
    def _image_fallback(data_url: str) -> dict:
        """图像压缩失败时的降级方案。

        从 data URL 中提取文件名前缀（若存在），返回文本描述占位。
        实际调用方应在外层通过 metadata 中的 scene_tags/style_tags
        构造更丰富的文本替代，此处仅提供兜底。

        Returns:
            {"text": "[图片]"} 占位符字典。
        """
        if "," in data_url:
            prefix = data_url.split(",", 1)[0]
            if "jpeg" in prefix.lower() or "jpg" in prefix.lower():
                return {"text": "[JPEG 图片]"}
            if "png" in prefix.lower():
                return {"text": "[PNG 图片]"}
        return {"text": "[图片]"}

    @staticmethod
    def _apply_scores(
        documents: list[dict], raw_results: list, top_n: int
    ) -> list[dict]:
        """将 API 返回的分数映射回原始文档列表。"""
        if not isinstance(raw_results, list):
            raw_results = []

        index_to_score: dict[int, float] = {}
        for entry in raw_results:
            idx = entry.get("index")
            score = entry.get("relevance_score", 0.0)
            if isinstance(idx, int):
                index_to_score[idx] = float(score)

        scored = []
        for i, item in enumerate(documents):
            rerank_score = index_to_score.get(i, 0.0)
            scored.append({**item, "rerank_score": rerank_score})

        scored.sort(key=lambda x: x["rerank_score"], reverse=True)
        return scored[:top_n]


def get_reranker(strategy: str | None = None) -> BaseReranker:
    """获取精排器实例

    Args:
        strategy: 精排策略，"local" 或 "alibaba"，默认从环境变量 RERANK_STRATEGY 读取

    Returns:
        精排器实例
    """
    strategy = strategy or RERANK_STRATEGY
    if strategy == "alibaba":
        return AlibabaReranker()
    return LocalReranker()
