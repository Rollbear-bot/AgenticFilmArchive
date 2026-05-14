import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';

function SearchPage() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]);
  const [count, setCount] = useState(0);
  const [searched, setSearched] = useState(false);
  const [filters, setFilters] = useState({
    docType: 'any',
    sceneTags: '',
    styleTags: '',
    filmTags: ''
  });
  const navigate = useNavigate();

  async function handleSearch() {
    if (!query.trim()) return;

    setLoading(true);
    setSearched(true);

    try {
      const params = {
        query,
        k: 20,
        doc_type: filters.docType
      };

      if (filters.sceneTags) params.scene_tags = [filters.sceneTags];
      if (filters.styleTags) params.style_tags = [filters.styleTags];
      if (filters.filmTags) params.film_tags = [filters.filmTags];

      const data = await api.searchResources(query, params);
      setResults(data.results || []);
      setCount(data.count || 0);
    } catch (error) {
      console.error('搜索失败:', error);
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  async function handleResultClick(result) {
    const data = await api.getResources({ page: 1, page_size: 1000 });
    const matched = data.results?.find(r => {
      const rPath = r.file_path.replace(/^\.?\/?resources\//, 'resources/');
      const sPath = result.file_path.replace(/^\.?\/?resources\//, 'resources/');
      return rPath === sPath || r.file_name === result.file_name;
    });

    if (matched) {
      navigate(`/resources/${matched.id}/`);
    }
  }

  return (
    <div className="page-container">
      <div className="search-container">
        <div className="search-form-card">
          <div className="search-input-group">
            <input
              type="text"
              className="search-input"
              placeholder="输入关键词或描述来搜索..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            />
            <button
              className="btn btn-primary"
              onClick={handleSearch}
              disabled={loading}
            >
              {loading ? '搜索中...' : '搜索'}
            </button>
          </div>

          <div className="search-filters">
            <div className="filter-group">
              <label>类型筛选：</label>
              <select
                value={filters.docType}
                onChange={(e) => setFilters(f => ({ ...f, docType: e.target.value }))}
              >
                <option value="any">全部</option>
                <option value="image">仅图片</option>
                <option value="text">仅文档</option>
              </select>
            </div>
            <div className="filter-group">
              <label>场景标签：</label>
              <input
                type="text"
                placeholder="可选"
                value={filters.sceneTags}
                onChange={(e) => setFilters(f => ({ ...f, sceneTags: e.target.value }))}
              />
            </div>
            <div className="filter-group">
              <label>风格标签：</label>
              <input
                type="text"
                placeholder="可选"
                value={filters.styleTags}
                onChange={(e) => setFilters(f => ({ ...f, styleTags: e.target.value }))}
              />
            </div>
            <div className="filter-group">
              <label>胶片特征：</label>
              <input
                type="text"
                placeholder="可选"
                value={filters.filmTags}
                onChange={(e) => setFilters(f => ({ ...f, filmTags: e.target.value }))}
              />
            </div>
          </div>
        </div>

        {loading ? (
          <div className="loading">
            <div className="loading-spinner"></div>
            <span>搜索中...</span>
          </div>
        ) : results.length > 0 ? (
          <div>
            <div className="results-header">
              找到 <span className="results-count">{count}</span> 个结果
            </div>
            <div className="resource-grid">
              {results.map((result, index) => (
                <div
                  key={index}
                  className="resource-card"
                  onClick={() => handleResultClick(result)}
                >
                  <div className="resource-thumbnail">
                    {result.file_type === 'image' ? (
                      result.content && result.content.startsWith('data:image/') ? (
                        <img
                          src={result.content}
                          alt={result.file_name}
                          style={{
                            width: '100%',
                            height: '100%',
                            objectFit: 'cover',
                            borderRadius: '8px'
                          }}
                          onError={(e) => {
                            e.target.style.display = 'none';
                            e.target.parentElement.innerHTML = '<span style="font-size: 2rem;">📷</span>';
                          }}
                        />
                      ) : (
                        <span className="doc-icon">📷</span>
                      )
                    ) : (
                      <span className="doc-icon">📄</span>
                    )}
                  </div>
                  <div className="resource-info">
                    <div className="resource-name">{result.file_name}</div>
                    <div style={{ fontSize: '0.85rem', color: '#3498db', marginTop: '4px' }}>
                      相似度: {(result.score * 100).toFixed(1)}%
                    </div>
                    {result.scene_tags && (
                      <div className="resource-tags" style={{ marginTop: '4px' }}>
                        <span className="tag">{result.scene_tags}</span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : searched ? (
          <div className="empty-state">
            <p>未找到相关结果，请尝试其他关键词</p>
          </div>
        ) : (
          <div className="card">
            <h3 style={{ marginBottom: '16px' }}>搜索技巧</h3>
            <ul style={{ marginLeft: '20px', color: '#666' }}>
              <li style={{ marginBottom: '8px' }}>使用自然语言描述，如"街拍风格的黑白照片"</li>
              <li style={{ marginBottom: '8px' }}>可以指定场景标签进行筛选</li>
              <li>可以指定胶片类型，如"Kodak Portra 400"</li>
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

export default SearchPage;
