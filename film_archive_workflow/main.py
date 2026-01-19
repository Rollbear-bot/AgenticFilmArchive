from vecDb_handler import VecDB
from configures import VECTOR_DB_PATH, RES_DIR


if __name__ == '__main__':
    # 初始化VecDB类
    vec_db = VecDB(VECTOR_DB_PATH, RES_DIR)

    # 文本查询示例
    print("\n=== 文本查询示例 ===")
    text_query = "灯牌"
    print(f"查询文本: {text_query}")
    text_search_results = vec_db.search_similar_documents(text_query, k=2)

    # 图像查询示例
    print("\n=== 图像查询示例 ===")
    # 使用第一张图片作为查询
    # 从向量存储中获取所有文档
    all_docs = vec_db.vector_store.get(include=['documents', 'embeddings'])
    if all_docs['documents']:
        first_image_doc = all_docs['documents'][0]
        print(f"查询图像")
        image_search_results = vec_db.search_similar_documents(first_image_doc, k=2)
    else:
        print("向量存储中没有文档可用于查询")
