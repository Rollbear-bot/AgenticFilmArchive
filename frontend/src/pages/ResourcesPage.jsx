import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import ResourceCard from '../components/ResourceCard';

function ResourcesPage() {
  const [resources, setResources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [filter, setFilter] = useState('all');
  const navigate = useNavigate();

  const pageSize = 20;

  useEffect(() => {
    loadResources();
  }, [page, filter]);

  function loadResources() {
    setLoading(true);
    const params = { page, page_size: pageSize };
    if (filter !== 'all') {
      params.doc_type = filter;
    }

    api.getResources(params)
      .then(data => {
        setResources(data.results || []);
        setTotal(data.total);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }

  function handleResourceClick(resource) {
    navigate(`/resources/${resource.id}/`);
  }

  function totalPages() {
    return Math.ceil(total / pageSize);
  }

  return (
    <div className="page-container">
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">资源浏览</h2>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <select
              className="form-select"
              style={{ width: 'auto' }}
              value={filter}
              onChange={(e) => { setFilter(e.target.value); setPage(1); }}
            >
              <option value="all">全部类型</option>
              <option value="image">仅图片</option>
              <option value="text">仅文档</option>
            </select>
            <button className="btn btn-primary" onClick={loadResources}>
              刷新
            </button>
          </div>
        </div>

        {loading ? (
          <div className="loading">
            <div className="loading-spinner"></div>
            <span>加载中...</span>
          </div>
        ) : resources.length > 0 ? (
          <>
            <div className="resource-grid">
              {resources.map(resource => (
                <ResourceCard
                  key={resource.id || resource.file_path}
                  resource={resource}
                  onClick={() => handleResourceClick(resource)}
                />
              ))}
            </div>

            <div style={{ display: 'flex', justifyContent: 'center', gap: '16px', marginTop: '24px', alignItems: 'center' }}>
              <button
                className="btn btn-secondary"
                disabled={page === 1}
                onClick={() => setPage(p => p - 1)}
              >
                上一页
              </button>
              <span>第 {page} 页 / 共 {totalPages()} 页</span>
              <button
                className="btn btn-secondary"
                disabled={page >= totalPages()}
                onClick={() => setPage(p => p + 1)}
              >
                下一页
              </button>
            </div>
          </>
        ) : (
          <div className="empty-state">
            <p>暂无资源，请先同步资源目录</p>
            <button className="btn btn-primary" style={{ marginTop: '16px' }} onClick={() => navigate('/sync/')}>
              去同步
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default ResourcesPage;
