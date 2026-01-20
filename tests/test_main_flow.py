from film_archive_workflow.vecDb_handler import VecDB
from film_archive_workflow.configures import VECTOR_DB_PATH, RES_DIR
import unittest


class TestMainFlow(unittest.TestCase):
    def setUp(self):
        # 测试前的准备工作
        self.vec_db = VecDB("../film_archive_workflow/chroma_multimodal", RES_DIR)

    def test_main_flow(self):
        # 文本查询示例
        print("\n=== 文本查询示例 ===")
        text_query = "灯牌"
        print(f"查询文本: {text_query}")
        text_search_results = self.vec_db.search_similar_documents(text_query, k=2)

        # 图像查询示例
        print("\n=== 图像查询示例 ===")
        # 使用第一张图片作为查询
        # 从向量存储中获取所有文档
        all_docs = self.vec_db.vector_store.get(include=['documents', 'embeddings'])
        if all_docs['documents']:
            first_image_doc = all_docs['documents'][0]
            print(f"查询图像")
            image_search_results = self.vec_db.search_similar_documents(first_image_doc, k=2)
        else:
            print("向量存储中没有文档可用于查询")

    def tearDown(self):
        # 测试后的清理工作
        pass


if __name__ == '__main__':
    unittest.main()
