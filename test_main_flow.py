from vecDb_handler import VecDB
import unittest
from configures import *
from chat import get_chat_response


class TestMainFlow(unittest.TestCase):
    def setUp(self):
        # 测试前的准备工作
        self.vec_db = VecDB(VECTOR_DB_PATH, RES_DIR)

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

    def test_chat(self):
        # 测试聊天机器人响应
        question = "基于库中的照片，总结黑白照片的共同点"
        response = get_chat_response(question)
        self.assertIsNotNone(response)
        self.assertNotEqual(response.strip(), "")

    def tearDown(self):
        # 测试后的清理工作
        pass


if __name__ == '__main__':
    unittest.main()
