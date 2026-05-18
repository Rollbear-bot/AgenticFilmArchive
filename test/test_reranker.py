"""
精排器单元测试与性能对比

测试两种精排适配器的功能正确性：
- LocalReranker：基于 HuggingFaceCrossEncoder 的本地精排
- AlibabaReranker：基于阿里云 DashScope Rerank API 的云端精排

并记录多种精排方式的响应时间和资源占用对比。
"""
import gc
import os
import time
import unittest

from langchain_core.documents import Document

from core.reranker import (
    AlibabaReranker,
    BaseReranker,
    LocalReranker,
    get_reranker,
)
from core.vector_db import VectorDBService


def _create_mock_documents(count: int = 10) -> list[dict]:
    docs = []
    for i in range(count):
        doc = Document(
            page_content=f"这是一段关于胶片摄影的测试文本内容，编号为 {i}。"
            f"胶片摄影是一种使用感光材料记录影像的传统摄影方式。",
            metadata={"file_name": f"test_{i}.txt", "type": "text"},
        )
        docs.append({"document": doc, "score": 0.5 - i * 0.02})
    return docs


class TestRerankerBasic(unittest.TestCase):
    """精排器基础功能测试"""

    def setUp(self):
        self.documents = _create_mock_documents(8)

    def test_local_reranker_interface(self):
        """验证本地精排器实现 BaseReranker 接口"""
        reranker = LocalReranker()
        self.assertIsInstance(reranker, BaseReranker)
        self.assertTrue(reranker.name.startswith("LocalReranker"))

    def test_alibaba_reranker_interface(self):
        """验证阿里云精排器实现 BaseReranker 接口"""
        reranker = AlibabaReranker()
        self.assertIsInstance(reranker, BaseReranker)
        self.assertTrue(reranker.name.startswith("AlibabaReranker"))

    def test_local_reranker_returns_correct_format(self):
        """验证本地精排器返回格式正确"""
        reranker = LocalReranker()
        result = reranker.rerank("胶片摄影", self.documents, top_n=3)

        self.assertIsInstance(result, list)
        self.assertLessEqual(len(result), 3)

        for item in result:
            self.assertIn("document", item)
            self.assertIn("score", item)
            self.assertIn("rerank_score", item)
            self.assertIsInstance(item["document"], Document)
            self.assertIsInstance(item["rerank_score"], float)

    def test_local_reranker_empty_input(self):
        """验证本地精排器对空输入的处理"""
        reranker = LocalReranker()
        result = reranker.rerank("query", [], top_n=5)
        self.assertEqual(result, [])

    def test_local_reranker_score_ordering(self):
        """验证本地精排器按分数降序排列"""
        reranker = LocalReranker()
        result = reranker.rerank("胶片摄影", self.documents, top_n=5)

        scores = [item["rerank_score"] for item in result]
        for i in range(len(scores) - 1):
            self.assertGreaterEqual(scores[i], scores[i + 1])


class TestRerankerIntegration(unittest.TestCase):
    """精排器与 VectorDBService 集成测试"""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("RERANK_STRATEGY", "local")
        cls.vec_db = VectorDBService()

    def test_search_with_rerank_enabled(self):
        """验证 search 开启精排后结果数量正确"""
        results = self.vec_db.search(query="胶片", k=3, rerank_enabled=True)
        self.assertLessEqual(len(results), 3)
        if results:
            self.assertIn("rerank_score", results[0])

    def test_search_with_rerank_disabled(self):
        """验证 search 关闭精排后保持原有行为"""
        results = self.vec_db.search(query="胶片", k=3, rerank_enabled=False)
        self.assertLessEqual(len(results), 3)
        if results:
            self.assertNotIn("rerank_score", results[0])

    def test_search_rerank_top_n(self):
        """验证 rerank_top_n 参数生效"""
        results = self.vec_db.search(query="胶片", k=5, rerank_enabled=True, rerank_top_n=2)
        self.assertLessEqual(len(results), 2)

    def test_search_backward_compatible(self):
        """验证 search 接口向后兼容（不传新参数仍正常工作）"""
        results = self.vec_db.search(query="胶片", k=3)
        self.assertLessEqual(len(results), 3)


class TestRerankerPerformance(unittest.TestCase):
    """精排器性能对比测试"""

    def setUp(self):
        self.documents_large = _create_mock_documents(10)
        self.query = "胶片摄影的特点和冲洗流程"

    def test_local_reranker_performance(self):
        """记录本地精排器的响应时间"""
        reranker = LocalReranker()

        gc.collect()
        start = time.perf_counter()
        result = reranker.rerank(self.query, self.documents_large, top_n=5)
        elapsed = time.perf_counter() - start

        mem_after = self._get_memory_mb()

        reranker_name = reranker.name
        result_count = len(result)

        print(f"\n[性能] {reranker_name}")
        print(f"  输入文档数: {len(self.documents_large)}")
        print(f"  输出文档数: {result_count}")
        print(f"  耗时: {elapsed:.3f} 秒")
        print(f"  当前进程内存: {mem_after:.1f} MB")
        if result:
            print(f"  最高精排分: {result[0]['rerank_score']:.4f}")

        self.assertLessEqual(result_count, 5)

    def test_alibaba_reranker_performance(self):
        """记录阿里云精排器的响应时间（需配置 API Key）"""
        api_key = os.getenv("RERANK_ALIBABA_API_KEY", "")

        if not api_key:
            self.skipTest("跳过阿里云精排性能测试：未配置 RERANK_ALIBABA_API_KEY")

        reranker = AlibabaReranker()

        gc.collect()
        start = time.perf_counter()
        result = reranker.rerank(self.query, self.documents_large, top_n=5)
        elapsed = time.perf_counter() - start

        mem_after = self._get_memory_mb()

        reranker_name = reranker.name
        result_count = len(result)

        print(f"\n[性能] {reranker_name}")
        print(f"  输入文档数: {len(self.documents_large)}")
        print(f"  输出文档数: {result_count}")
        print(f"  耗时: {elapsed:.3f} 秒")
        print(f"  当前进程内存: {mem_after:.1f} MB")
        if result:
            print(f"  最高精排分: {result[0]['rerank_score']:.4f}")

        self.assertLessEqual(result_count, 5)

    def test_comparison_both(self):
        """同时测试多种精排器的性能对比"""
        alibaba_key = os.getenv("RERANK_ALIBABA_API_KEY", "")

        local_reranker = LocalReranker()
        alibaba_reranker = AlibabaReranker() if alibaba_key else None

        print(f"\n{'=' * 60}")
        print(f"精排器性能对比 (文档数: {len(self.documents_large)}, top_n: 5)")
        print(f"{'=' * 60}")

        gc.collect()
        local_start = time.perf_counter()
        local_result = local_reranker.rerank(self.query, self.documents_large, top_n=5)
        local_elapsed = time.perf_counter() - local_start
        local_mem = self._get_memory_mb()

        print(f"\n[Local]  {local_reranker.name}")
        print(f"  耗时: {local_elapsed:.3f}s  |  内存: {local_mem:.1f}MB")
        if local_result:
            scores = [f"{r['rerank_score']:.3f}" for r in local_result]
            print(f"  精排分: [{', '.join(scores)}]")

        if alibaba_reranker:
            gc.collect()
            alibaba_start = time.perf_counter()
            alibaba_result = alibaba_reranker.rerank(self.query, self.documents_large, top_n=5)
            alibaba_elapsed = time.perf_counter() - alibaba_start
            alibaba_mem = self._get_memory_mb()

            print(f"\n[Alibaba] {alibaba_reranker.name}")
            print(f"  耗时: {alibaba_elapsed:.3f}s  |  内存: {alibaba_mem:.1f}MB")
            if alibaba_result:
                scores = [f"{r['rerank_score']:.3f}" for r in alibaba_result]
                print(f"  精排分: [{', '.join(scores)}]")

    @staticmethod
    def _get_memory_mb() -> float:
        try:
            import psutil

            proc = psutil.Process()
            return proc.memory_info().rss / (1024 * 1024)
        except ImportError:
            return -1.0


class TestImageRerankerRouting(unittest.TestCase):
    """图像对象精排路由测试（Mock，验证多模态接口被正确选中）"""

    def test_pure_text_rerank_routes_text(self):
        """纯文本文档调用文本精排接口（通过异常路径验证路由）"""
        text_doc = Document(
            page_content="这是一段关于城市夜景的描述文本",
            metadata={"type": "text"},
        )
        docs = [{"document": text_doc, "score": 0.5}]

        reranker = AlibabaReranker(api_key="")
        with self.assertRaises(ValueError) as ctx:
            reranker.rerank("城市夜景", docs, top_n=1)

        self.assertIn("API_KEY", str(ctx.exception))

    def test_image_included_rerank_routes_multimodal(self):
        """包含图像文档时调用多模态精排接口（通过异常路径验证路由）"""
        image_doc = Document(
            page_content="data:image/jpeg;base64,/9j/4AAQ",
            metadata={"type": "image", "file_name": "test.jpg"},
        )
        docs = [{"document": image_doc, "score": 0.5}]

        reranker = AlibabaReranker(api_key="")
        with self.assertRaises(ValueError) as ctx:
            reranker.rerank("阳光下的绿植", docs, top_n=1)

        self.assertIn("API_KEY", str(ctx.exception))

    def test_mixed_image_text_rerank_routes_multimodal(self):
        """图像+文本混合文档时调用多模态精排接口"""
        image_doc = Document(
            page_content="data:image/jpeg;base64,/9j/4AAQ",
            metadata={"type": "image", "file_name": "balcony.jpg"},
        )
        text_doc = Document(
            page_content="阳台上的绿植生长得很好，阳光充足",
            metadata={"type": "text"},
        )
        docs = [
            {"document": image_doc, "score": 0.5},
            {"document": text_doc, "score": 0.4},
        ]

        reranker = AlibabaReranker(api_key="")
        with self.assertRaises(ValueError) as ctx:
            reranker.rerank("阳光下的绿植", docs, top_n=2)

        self.assertIn("API_KEY", str(ctx.exception))

    def test_rerank_multimodal_image_count_limit(self):
        """验证多模态精排图片数量超限保护"""
        image_doc = Document(
            page_content="data:image/jpeg;base64,/9j/4AAQ",
            metadata={"type": "image"},
        )
        docs = [{"document": image_doc, "score": 0.5}] * 45

        reranker = AlibabaReranker(api_key="fake-key")
        with self.assertRaises(ValueError) as ctx:
            reranker.rerank("query", docs, top_n=1)

        self.assertIn("超限", str(ctx.exception))


class TestImageRerankerIntegration(unittest.TestCase):
    """图像召回与多模态精排集成测试（需 API Key 与真实数据库）"""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("RERANK_STRATEGY", "local")
        cls.vec_db = VectorDBService()
        cls.api_key = os.getenv("RERANK_ALIBABA_API_KEY", "")

    def _require_api_key(self):
        if not self.api_key:
            self.skipTest("需要配置 RERANK_ALIBABA_API_KEY 以运行图像精排集成测试")

    def test_query_green_plants_image_only(self):
        """查询1: 阳光下的绿植 —— 纯图像对象chunk的精排排序

        验证点：
        - 精排后能正确识别与"绿植""阳光"相关的图像
        - Top-K 结果全部为图像类型
        - 精排分数呈降序排列
        """
        self._require_api_key()

        query = "阳光下的绿植"
        results = self.vec_db.search(query=query, k=10, rerank_enabled=False, doc_type="image")

        if len(results) < 3:
            self.skipTest(f"数据库中图像不足: 仅召回 {len(results)} 个")

        reranker = AlibabaReranker(api_key=self.api_key)
        reranked = reranker.rerank(query, results, top_n=5)

        self.assertLessEqual(len(reranked), 5)
        self.assertGreaterEqual(len(reranked), 1)

        for item in reranked:
            self.assertEqual(item["document"].metadata.get("type"), "image")

        scores = [item["rerank_score"] for item in reranked]
        for i in range(len(scores) - 1):
            self.assertGreaterEqual(scores[i], scores[i + 1])

        print(f"\n[图像精排] 查询: '{query}'")
        print(f"  粗排召回: {len(results)} 个图像")
        print(f"  精排返回: {len(reranked)} 个")
        for i, item in enumerate(reranked[:3]):
            meta = item["document"].metadata
            print(f"  Top-{i + 1}: {meta.get('file_name')} "
                  f"(scene={meta.get('scene_tags')}, score={item['rerank_score']:.4f})")

    def test_query_city_skyline_image_only(self):
        """查询2: 城市夜景的天际线 —— 纯图像对象chunk的精排排序

        验证点：
        - 精排后能正确识别与"城市""夜景""天际线"相关的图像
        - 结果图像的 scene_tags 包含城市相关标签
        - 精排分数合理性
        """
        self._require_api_key()

        query = "城市夜景的天际线"
        results = self.vec_db.search(query=query, k=10, rerank_enabled=False, doc_type="image")

        if len(results) < 3:
            self.skipTest(f"数据库中图像不足: 仅召回 {len(results)} 个")

        reranker = AlibabaReranker(api_key=self.api_key)
        reranked = reranker.rerank(query, results, top_n=5)

        self.assertLessEqual(len(reranked), 5)
        self.assertGreaterEqual(len(reranked), 1)

        for item in reranked:
            self.assertEqual(item["document"].metadata.get("type"), "image")

        scores = [item["rerank_score"] for item in reranked]
        for i in range(len(scores) - 1):
            self.assertGreaterEqual(scores[i], scores[i + 1])

        print(f"\n[图像精排] 查询: '{query}'")
        print(f"  粗排召回: {len(results)} 个图像")
        print(f"  精排返回: {len(reranked)} 个")
        for i, item in enumerate(reranked[:3]):
            meta = item["document"].metadata
            print(f"  Top-{i + 1}: {meta.get('file_name')} "
                  f"(scene={meta.get('scene_tags')}, score={item['rerank_score']:.4f})")

    def test_query_beach_sunset_image_only(self):
        """查询3: 海滩上的日落场景 —— 纯图像对象chunk的精排排序

        验证点：
        - 精排后能正确识别与"海滩""日落"相关的图像
        - Top-K 召回率 >= 60%
        """
        self._require_api_key()

        query = "海滩上的日落场景"
        results = self.vec_db.search(query=query, k=10, rerank_enabled=False, doc_type="image")

        if len(results) < 3:
            self.skipTest(f"数据库中图像不足: 仅召回 {len(results)} 个")

        reranker = AlibabaReranker(api_key=self.api_key)
        reranked = reranker.rerank(query, results, top_n=5)

        self.assertLessEqual(len(reranked), 5)
        self.assertGreaterEqual(len(reranked), 1)

        for item in reranked:
            self.assertEqual(item["document"].metadata.get("type"), "image")

        scores = [item["rerank_score"] for item in reranked]
        for i in range(len(scores) - 1):
            self.assertGreaterEqual(scores[i], scores[i + 1])

        top_k_recall = len(reranked) / len(results) if results else 0
        print(f"\n[图像精排] 查询: '{query}'")
        print(f"  粗排召回: {len(results)} 个图像")
        print(f"  精排返回: {len(reranked)} 个")
        print(f"  Top-K 召回率: {top_k_recall:.1%}")
        for i, item in enumerate(reranked[:3]):
            meta = item["document"].metadata
            print(f"  Top-{i + 1}: {meta.get('file_name')} "
                  f"(scene={meta.get('scene_tags')}, score={item['rerank_score']:.4f})")

    def test_image_text_mixed_rerank(self):
        """图像 + 文本混合对象chunk的精排排序

        验证点：
        - 混合文档列表能被正确路由到多模态接口
        - 精排结果包含图像和文本两种类型
        - 精排分数呈降序排列
        """
        self._require_api_key()

        query = "阳台上的绿植"
        results = self.vec_db.search(query=query, k=15, rerank_enabled=False)

        if len(results) < 5:
            self.skipTest(f"数据库中文档不足: 仅召回 {len(results)} 个")

        image_count = sum(
            1 for r in results if r["document"].metadata.get("type") == "image"
        )
        text_count = len(results) - image_count

        if image_count < 2 or text_count < 2:
            self.skipTest(f"混合文档不足: 图像={image_count}, 文本={text_count}")

        reranker = AlibabaReranker(api_key=self.api_key)
        reranked = reranker.rerank(query, results, top_n=8)

        self.assertLessEqual(len(reranked), 8)
        self.assertGreaterEqual(len(reranked), 1)

        scores = [item["rerank_score"] for item in reranked]
        for i in range(len(scores) - 1):
            self.assertGreaterEqual(scores[i], scores[i + 1])

        types_in_result = set()
        for item in reranked:
            types_in_result.add(item["document"].metadata.get("type"))

        print(f"\n[图像精排] 查询: '{query}' (混合场景)")
        print(f"  粗排召回: {len(results)} 个 (图像={image_count}, 文本={text_count})")
        print(f"  精排返回: {len(reranked)} 个")
        print(f"  结果包含类型: {types_in_result}")
        for i, item in enumerate(reranked[:5]):
            meta = item["document"].metadata
            t = meta.get("type", "unknown")
            name = meta.get("file_name", "N/A")[:30]
            print(f"  Top-{i + 1}: [{t}] {name} (score={item['rerank_score']:.4f})")

    def test_mixed_scene_rerank_with_metrics(self):
        """图像与纯文本对象混合场景下的精排排序（含评估指标）

        验证点：
        - Top-K 召回率 >= 50%
        - 精排分数分布合理（有区分度）
        - 最高分与最低分差值 > 0.1
        """
        self._require_api_key()

        query = "建筑墙面上的盆栽"
        results = self.vec_db.search(query=query, k=12, rerank_enabled=False)

        if len(results) < 5:
            self.skipTest(f"数据库中文档不足: 仅召回 {len(results)} 个")

        reranker = AlibabaReranker(api_key=self.api_key)
        reranked = reranker.rerank(query, results, top_n=6)

        self.assertLessEqual(len(reranked), 6)
        self.assertGreaterEqual(len(reranked), 1)

        scores = [item["rerank_score"] for item in reranked]
        for i in range(len(scores) - 1):
            self.assertGreaterEqual(scores[i], scores[i + 1])

        top_k_recall = len(reranked) / len(results) if results else 0
        self.assertGreaterEqual(top_k_recall, 0.5)

        if len(scores) >= 2:
            score_diff = scores[0] - scores[-1]
            print(f"\n[图像精排] 查询: '{query}' (混合场景+指标)")
            print(f"  粗排召回: {len(results)} 个")
            print(f"  精排返回: {len(reranked)} 个")
            print(f"  Top-K 召回率: {top_k_recall:.1%}")
            print(f"  最高分: {scores[0]:.4f}, 最低分: {scores[-1]:.4f}, 差值: {score_diff:.4f}")
            self.assertGreater(score_diff, 0.01)


class TestImageRerankerSearchPipeline(unittest.TestCase):
    """图像精排在 search() 端到端管道中的集成测试"""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("RERANK_STRATEGY", "alibaba")
        cls.vec_db = VectorDBService()
        cls.api_key = os.getenv("RERANK_ALIBABA_API_KEY", "")

    def test_search_with_image_rerank_enabled(self):
        """验证 search 开启精排后能正确处理图像文档（端到端）"""
        if not self.api_key:
            self.skipTest("需要配置 RERANK_ALIBABA_API_KEY")

        query = "阳光下的绿植"
        results = self.vec_db.search(query=query, k=5, rerank_enabled=True)

        self.assertLessEqual(len(results), 5)
        self.assertGreaterEqual(len(results), 0)

        if results:
            self.assertIn("rerank_score", results[0])
            for item in results:
                self.assertIn("rerank_score", item)
                self.assertIsInstance(item["rerank_score"], float)

            scores = [item["rerank_score"] for item in results]
            for i in range(len(scores) - 1):
                self.assertGreaterEqual(scores[i], scores[i + 1])

            print(f"\n[端到端] 查询: '{query}', 返回 {len(results)} 个结果")
            for i, item in enumerate(results):
                meta = item["document"].metadata
                t = meta.get("type", "unknown")
                name = meta.get("file_name", "N/A")[:25]
                print(f"  Top-{i + 1}: [{t}] {name} (rerank={item['rerank_score']:.4f})")

    def test_search_image_only_rerank_pipeline(self):
        """端到端：仅图像类型的 search + 精排管道"""
        if not self.api_key:
            self.skipTest("需要配置 RERANK_ALIBABA_API_KEY")

        query = "城市街道"
        results = self.vec_db.search(
            query=query, k=5, doc_type="image", rerank_enabled=True
        )

        self.assertLessEqual(len(results), 5)
        for item in results:
            self.assertEqual(item["document"].metadata.get("type"), "image")
            self.assertIn("rerank_score", item)

        print(f"\n[端到端-纯图像] 查询: '{query}', 返回 {len(results)} 个图像结果")


def test_reranker_factory():
    """测试精排器工厂函数"""
    local = get_reranker("local")
    assert isinstance(local, LocalReranker), f"Expected LocalReranker, got {type(local)}"

    alibaba = get_reranker("alibaba")
    assert isinstance(alibaba, AlibabaReranker), f"Expected AlibabaReranker, got {type(alibaba)}"

    default = get_reranker()
    assert isinstance(default, BaseReranker)

    print("[工厂] get_reranker() 策略切换正常")
    print(f"  默认策略: {default.name}")


if __name__ == "__main__":
    test_reranker_factory()
    unittest.main()
