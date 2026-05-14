import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../services/api';

function HomePage() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getResources({ page: 1, page_size: 100 })
      .then(data => {
        setStats({
          total: data.total,
          images: data.image_count || data.results?.filter(r => r.file_type === 'image').length || 0,
          docs: data.doc_count || data.results?.filter(r => r.file_type === 'text').length || 0
        });
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page-container">
      <section className="hero-section">
        <h1 className="hero-title">AI 驱动的胶片摄影归档助理</h1>
        <p className="hero-subtitle">智能管理您的胶片摄影作品集，支持多模态检索和自然语言交互</p>
        <div className="hero-actions">
          <Link to="/resources/" className="btn btn-primary hero-btn">
            浏览资源
          </Link>
          <Link to="/search/" className="btn btn-secondary hero-btn">
            开始搜索
          </Link>
        </div>
      </section>

      <section className="features-grid">
        <div className="feature-card">
          <div className="feature-icon">🖼️</div>
          <h3>多模态知识库</h3>
          <p>支持照片和文档的统一管理，基于向量检索快速定位目标资源</p>
        </div>
        <div className="feature-card">
          <div className="feature-icon">🏷️</div>
          <h3>自动标签生成</h3>
          <p>AI 自动为照片生成场景、风格、胶片特征标签</p>
        </div>
        <div className="feature-card">
          <div className="feature-icon">💬</div>
          <h3>智能对话</h3>
          <p>用自然语言与 AI 助手交流，获取摄影建议和知识</p>
        </div>
        <div className="feature-card">
          <div className="feature-icon">🔍</div>
          <h3>混合检索</h3>
          <p>结合向量相似度和结构化标签的精准检索</p>
        </div>
      </section>

      {loading ? (
        <div className="loading">
          <div className="loading-spinner"></div>
          <span>加载中...</span>
        </div>
      ) : stats && (
        <section className="quick-stats">
          <div className="quick-stat-card">
            <span className="quick-stat-number">{stats.total || 0}</span>
            <span className="quick-stat-label">资源总数</span>
          </div>
          <div className="quick-stat-card">
            <span className="quick-stat-number">{stats.images || 0}</span>
            <span className="quick-stat-label">照片数量</span>
          </div>
          <div className="quick-stat-card">
            <span className="quick-stat-number">{stats.docs || 0}</span>
            <span className="quick-stat-label">文档数量</span>
          </div>
        </section>
      )}
    </div>
  );
}

export default HomePage;
