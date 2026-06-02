"""
BM25 关键词检索引擎

基于 scikit-learn CountVectorizer + numpy 实现的 Okapi BM25 检索，
面向中英文混合文本，无需额外依赖。
"""

import numpy as np
from scipy import sparse as sp_sparse
from sklearn.feature_extraction.text import CountVectorizer
from langchain_core.documents import Document


class Bm25Index:
    """内存级 BM25 关键词检索引擎。

    使用 sklearn CountVectorizer(char_wb, ngram_range=(1,2)) 做分词，
    对中文（字符级 n-gram）和英文（词内字符 n-gram）均能产生有意义的 token。

    Parameters
    ----------
    k1 : float
        Term frequency saturation parameter (default 1.5).
    b : float
        Document length normalization parameter (default 0.75).
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self._k1 = k1
        self._b = b
        self._documents: list[Document] = []
        self._vectorizer: CountVectorizer | None = None
        self._doc_term_matrix: sp_sparse.csr_matrix | None = None
        self._idf: np.ndarray | None = None
        self._doc_lengths: np.ndarray | None = None
        self._avgdl: float = 0.0

    @property
    def is_built(self) -> bool:
        return self._doc_term_matrix is not None

    @property
    def document_count(self) -> int:
        return len(self._documents)

    def build(self, documents: list[Document]) -> None:
        """从 LangChain Document 列表构建 BM25 索引。

        使用 CountVectorizer(analyzer='char_wb', ngram_range=(1,2))
        对中英文混合文本产生有效的 token，然后计算 IDF 和文档长度统计。
        """
        if not documents:
            return

        self._documents = list(documents)
        texts = [doc.page_content for doc in documents]

        self._vectorizer = CountVectorizer(
            analyzer="char_wb",
            ngram_range=(1, 2),
            max_df=self._compute_max_df(len(documents)),
            min_df=1,
            lowercase=True,
        )

        # 构建词频矩阵 (term frequency, CSR 稀疏格式)
        tf_matrix = self._vectorizer.fit_transform(texts)

        # 计算平滑 IDF: log((N - df + 0.5) / (df + 0.5) + 1.0)
        n_docs = tf_matrix.shape[0]
        df = np.bincount(tf_matrix.indices, minlength=tf_matrix.shape[1])
        self._idf = np.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)

        # 文档长度 (每个文档的总词频)
        self._doc_lengths = tf_matrix.sum(axis=1).A1  # (n_docs,) float array
        self._avgdl = float(np.mean(self._doc_lengths)) if n_docs > 0 else 0.0

        # 存储词频矩阵用于后续搜索
        self._doc_term_matrix = tf_matrix

    def search(self, query: str, k: int = 10) -> list[dict]:
        """检索 top-k 文档。

        Args:
            query: 查询文本。空查询返回空列表。
            k: 返回的最大结果数。

        Returns:
            [{"document": Document, "score": float}, ...]
            score 为原始 BM25 分数（越高越相关），后续在 merge 阶段统一归一化。
        """
        if not self.is_built or not query.strip():
            return []

        # 将查询转换为词频向量
        query_vec = self._vectorizer.transform([query])

        # 计算 BM25 分数
        scores = self._compute_scores(query_vec)

        # 获取 top-k 索引
        if k >= len(scores):
            top_indices = np.argsort(scores)[::-1]
        else:
            # 使用 argpartition 避免全量排序
            top_indices = np.argpartition(scores, -k)[-k:]
            top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:  # 只返回得分 > 0 的结果
                results.append(
                    {
                        "document": self._documents[idx],
                        "score": float(scores[idx]),
                    }
                )

        return results

    @staticmethod
    def _compute_max_df(n_docs: int) -> float:
        """Compute a safe max_df that won't conflict with min_df=1.

        For small document sets (< 20 docs), don't prune any terms.
        """
        if n_docs <= 1:
            return 1.0
        # max_df * n_docs must be >= min_df (=1), so max_doc_count >= 1
        # e.g. for n_docs=2: max_df=1.0 gives 2 >= 1 (ok); 0.95 gives 1 >= 1 (ok)
        # for n_docs=1: 0.95 gives 0 < 1 (fail)
        return 0.95

    def invalidate(self) -> None:
        """清除索引状态，下次 search() 前需要重新 build()。"""
        self._documents = []
        self._vectorizer = None
        self._doc_term_matrix = None
        self._idf = None
        self._doc_lengths = None
        self._avgdl = 0.0

    def _compute_scores(self, query_vec: sp_sparse.csr_matrix) -> np.ndarray:
        """计算查询与所有文档的 BM25 分数。

        BM25 公式:
            score(D, Q) = Σ IDF(qi) * tf(qi,D) * (k1+1) /
                          (tf(qi,D) + k1 * (1 - b + b * len(D) / avgdl))

        Args:
            query_vec: 查询的词频向量 (1, vocab_size) CSR 格式。

        Returns:
            (n_docs,) 每个文档的 BM25 分数。
        """
        n_docs = self._doc_term_matrix.shape[0]

        # 获取查询中每个 token 在哪些文档中出现
        # query_vec.indices: 查询中出现的 token 在词典中的索引
        query_token_indices = query_vec.indices

        if len(query_token_indices) == 0:
            return np.zeros(n_docs)

        # 对每个查询 token，获取所有文档的词频
        # 提取 doc-term matrix 中对应列的切片
        tf_qd = self._doc_term_matrix[:, query_token_indices]  # (n_docs, n_query_terms)
        tf_qd = tf_qd.toarray()  # 转为稠密矩阵，通常 n_query_terms 很小

        # 获取这些 token 对应的 IDF
        idf = self._idf[query_token_indices]  # (n_query_terms,)

        # 文档长度归一化因子
        # (n_docs,) -> (n_docs, 1) 用于广播
        len_norm = 1.0 - self._b + self._b * self._doc_lengths / self._avgdl
        len_norm = len_norm.reshape(-1, 1)  # (n_docs, 1)

        # BM25 核心公式
        # tf * (k1+1) / (tf + k1 * len_norm)
        numerator = tf_qd * (self._k1 + 1)
        denominator = tf_qd + self._k1 * len_norm

        # 防止除零
        denominator = np.where(denominator == 0, 1.0, denominator)

        # 按 token 维度求和: Σ IDF(qi) * BM25_tf(qi, D)
        scores = np.sum(idf * (numerator / denominator), axis=1)  # (n_docs,)

        return scores
