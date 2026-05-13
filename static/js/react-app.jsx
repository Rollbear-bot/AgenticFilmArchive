/**
 * 胶片摄影归档系统 - React前端应用
 */

// API服务
const API_BASE = '/api/v1';

const api = {
  async request(method, endpoint, data = null) {
    const url = `${API_BASE}${endpoint}`;
    const options = {
      method,
      headers: { 'Content-Type': 'application/json' }
    };
    if (data) options.body = JSON.stringify(data);
    
    try {
      const response = await fetch(url, options);
      return await response.json();
    } catch (error) {
      console.error('API请求失败:', error);
      throw error;
    }
  },
  
  healthCheck() {
    return this.request('GET', '/health/');
  },
  
  getConfig() {
    return this.request('GET', '/config/');
  },
  
  getResources(params = {}) {
    const query = new URLSearchParams(params).toString();
    return this.request('GET', `/resources/?${query}`);
  },
  
  getResource(id) {
    return this.request('GET', `/resources/${id}/`);
  },
  
  searchResources(query, options = {}) {
    const params = { query, ...options };
    const queryStr = new URLSearchParams(params).toString();
    return this.request('GET', `/resources/search/?${queryStr}`);
  },
  
  syncResources() {
    return this.request('POST', '/resources/sync/');
  },
  
  sendChatMessage(message) {
    return this.request('POST', '/chat/', { message, include_resources: true });
  },
  
  getChatHistory() {
    return this.request('GET', '/chat/history/');
  }
};

// 消息格式化工具
function formatMessage(content) {
  if (!content) return '';
  return content.replace(/\n/g, '<br>');
}

function formatTime(date) {
  return new Date(date).toLocaleTimeString('zh-CN');
}

// ==================== 组件 ====================

// Header组件
function Header({ currentPage, onNavigate }) {
  const navItems = [
    { id: 'home', label: '首页', path: '/' },
    { id: 'resources', label: '资源', path: '/resources/' },
    { id: 'search', label: '搜索', path: '/search/' },
    { id: 'chat', label: '对话', path: '/chat/' },
    { id: 'sync', label: '同步', path: '/sync/' }
  ];
  
  return (
    <header className="app-header">
      <div className="logo">
        <span>📷</span>
        <span>胶片摄影归档系统</span>
      </div>
      <nav className="nav-links">
        {navItems.map(item => (
          <a 
            key={item.id}
            href={item.path}
            className={`nav-link ${currentPage === item.id ? 'active' : ''}`}
            onClick={(e) => { e.preventDefault(); onNavigate(item.id, item.path); }}
          >
            {item.label}
          </a>
        ))}
      </nav>
    </header>
  );
}

// Home页面
function HomePage({ onNavigate }) {
  const [stats, setStats] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  
  React.useEffect(() => {
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
          <button className="btn btn-primary hero-btn" onClick={() => onNavigate('resources', '/resources/')}>
            浏览资源
          </button>
          <button className="btn btn-secondary hero-btn" onClick={() => onNavigate('search', '/search/')}>
            开始搜索
          </button>
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

// 资源卡片组件
function ResourceCard({ resource, onClick }) {
  // 生成缩略图URL（使用content字段作为base64图片）
  const thumbnailUrl = resource.content || '';
  const hasImage = resource.file_type === 'image' && thumbnailUrl.startsWith('data:image/');
  
  return (
    <div className="resource-card" onClick={onClick}>
      <div className="resource-thumbnail">
        {hasImage ? (
          <img 
            src={thumbnailUrl} 
            alt={resource.file_name}
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
        ) : resource.file_type === 'image' ? (
          <span className="doc-icon">📷</span>
        ) : (
          <span className="doc-icon">📄</span>
        )}
      </div>
      <div className="resource-info">
        <div className="resource-name">{resource.file_name}</div>
        {resource.scene_tags && (
          <div className="resource-tags">
            <span className="tag">{resource.scene_tags}</span>
          </div>
        )}
      </div>
    </div>
  );
}

// 资源列表页面
function ResourcesPage({ onNavigate }) {
  const [resources, setResources] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [page, setPage] = React.useState(1);
  const [total, setTotal] = React.useState(0);
  const [filter, setFilter] = React.useState('all');
  
  const pageSize = 20;
  
  React.useEffect(() => {
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
    // 找到资源的索引ID
    const resourceIndex = resources.findIndex(r => r.file_path === resource.file_path);
    if (resourceIndex !== -1) {
      onNavigate('detail', `/resources/${resource.id}/`);
    }
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
            <button className="btn btn-primary" style={{ marginTop: '16px' }} onClick={() => onNavigate('sync', '/sync/')}>
              去同步
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// 资源详情页面
function ResourceDetailPage({ resourceId, onNavigate }) {
  const [resource, setResource] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [imageLoaded, setImageLoaded] = React.useState(false);
  
  React.useEffect(() => {
    loadResource();
  }, [resourceId]);
  
  function loadResource() {
    setLoading(true);
    api.getResource(resourceId)
      .then(data => {
        setResource(data);
        if (data.file_type === 'image') {
          preloadImage(data.content);
        }
      })
      .catch(error => {
        console.error('加载资源失败:', error);
      })
      .finally(() => setLoading(false));
  }
  
  function preloadImage(content) {
    if (content && content.startsWith('data:image/')) {
      const img = new Image();
      img.onload = () => setImageLoaded(true);
      img.onerror = () => setImageLoaded(true);
      img.src = content;
    } else {
      setImageLoaded(true);
    }
  }
  
  function getImageSrc() {
    if (resource && resource.content) {
      return resource.content;
    }
    return '';
  }
  
  if (loading) {
    return (
      <div className="page-container">
        <div className="loading">
          <div className="loading-spinner"></div>
          <span>加载中...</span>
        </div>
      </div>
    );
  }
  
  if (!resource) {
    return (
      <div className="page-container">
        <div className="card">
          <div className="empty-state">
            <p>资源不存在</p>
            <button className="btn btn-primary" style={{ marginTop: '16px' }} onClick={() => onNavigate('resources', '/resources/')}>
              返回资源列表
            </button>
          </div>
        </div>
      </div>
    );
  }
  
  return (
    <div className="page-container">
      <div className="card">
        <div className="card-header">
          <button className="btn btn-secondary" onClick={() => onNavigate('resources', '/resources/')}>
            ← 返回
          </button>
          <h2 className="card-title">资源详情</h2>
        </div>
        
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: '24px' }}>
          <div>
            {resource.file_type === 'image' ? (
              <div style={{ 
                background: '#f0f0f0', 
                borderRadius: '12px', 
                minHeight: '400px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                overflow: 'hidden'
              }}>
                {getImageSrc() ? (
                  <img 
                    src={getImageSrc()} 
                    alt={resource.file_name}
                    style={{ maxWidth: '100%', maxHeight: '500px', display: imageLoaded ? 'block' : 'none' }}
                    onLoad={() => setImageLoaded(true)}
                  />
                ) : null}
                {!imageLoaded && (
                  <div style={{ textAlign: 'center', color: '#999' }}>
                    <div className="loading-spinner" style={{ margin: '0 auto 16px' }}></div>
                    <span>加载图片中...</span>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ 
                background: '#f8f9fa', 
                borderRadius: '12px', 
                padding: '24px',
                whiteSpace: 'pre-wrap',
                fontSize: '0.95rem',
                lineHeight: '1.8'
              }}>
                {resource.content || '无内容'}
              </div>
            )}
          </div>
          
          <div>
            <div className="card" style={{ marginBottom: '16px' }}>
              <h3 style={{ marginBottom: '16px', paddingBottom: '12px', borderBottom: '1px solid #eee' }}>基本信息</h3>
              <div style={{ marginBottom: '12px' }}>
                <label style={{ color: '#666', display: 'block', marginBottom: '4px' }}>文件名</label>
                <span>{resource.file_name}</span>
              </div>
              <div style={{ marginBottom: '12px' }}>
                <label style={{ color: '#666', display: 'block', marginBottom: '4px' }}>类型</label>
                <span>{resource.file_type === 'image' ? '图片' : '文档'}</span>
              </div>
            </div>
            
            {resource.file_type === 'image' && (
              <div className="card" style={{ marginBottom: '16px' }}>
                <h3 style={{ marginBottom: '16px', paddingBottom: '12px', borderBottom: '1px solid #eee' }}>标签信息</h3>
                <div style={{ marginBottom: '12px' }}>
                  <label style={{ color: '#666', display: 'block', marginBottom: '4px' }}>场景标签</label>
                  <span>{resource.scene_tags || '-'}</span>
                </div>
                <div style={{ marginBottom: '12px' }}>
                  <label style={{ color: '#666', display: 'block', marginBottom: '4px' }}>风格标签</label>
                  <span>{resource.style_tags || '-'}</span>
                </div>
                <div>
                  <label style={{ color: '#666', display: 'block', marginBottom: '4px' }}>胶片特征</label>
                  <span>{resource.film_tags || '-'}</span>
                </div>
              </div>
            )}
            
            <a 
              href={`/api/v1/resources/${resourceId}/download/`} 
              className="btn btn-primary" 
              style={{ width: '100%' }}
              download
            >
              下载文件
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

// 搜索页面
function SearchPage({ onNavigate }) {
  const [query, setQuery] = React.useState('');
  const [loading, setLoading] = React.useState(false);
  const [results, setResults] = React.useState([]);
  const [count, setCount] = React.useState(0);
  const [searched, setSearched] = React.useState(false);
  const [filters, setFilters] = React.useState({
    docType: 'any',
    sceneTags: '',
    styleTags: '',
    filmTags: ''
  });
  
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
    // 查找匹配的资源ID
    const data = await api.getResources({ page: 1, page_size: 1000 });
    const matched = data.results?.find(r => {
      const rPath = r.file_path.replace(/^\.?\/?resources\//, 'resources/');
      const sPath = result.file_path.replace(/^\.?\/?resources\//, 'resources/');
      return rPath === sPath || r.file_name === result.file_name;
    });
    
    if (matched) {
      onNavigate('detail', `/resources/${matched.id}/`);
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

// ChatMessage组件 - 使用spark-ai/chat设计理念
function ChatMessage({ message }) {
  const isUser = message.role === 'user';
  
  return (
    <div className={`chat-message ${message.role}`}>
      <div className="chat-message-avatar">
        {isUser ? '👤' : '🤖'}
      </div>
      <div className="chat-message-content">
        <div 
          className="chat-message-bubble"
          dangerouslySetInnerHTML={{ __html: formatMessage(message.content) }}
        />
        
        {/* 工具调用信息 */}
        {message.tool_calls && message.tool_calls.length > 0 && (
          <div className="tool-calls">
            {message.tool_calls.map((tool, index) => (
              <div key={index} className="tool-call">
                <span className="tool-icon">🔧</span>
                <span className="tool-name">{tool.tool}</span>
                {tool.query && (
                  <span style={{ color: '#999', marginLeft: '8px' }}>
                    查询: "{tool.query}"
                  </span>
                )}
                {tool.result_count !== undefined && (
                  <span className="tool-result">
                    找到 {tool.result_count} 个结果
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
        
        <div className="chat-message-time">{message.time}</div>
      </div>
    </div>
  );
}

// 对话页面 - Spark AI Chat设计
function ChatPage() {
  const [messages, setMessages] = React.useState([]);
  const [inputMessage, setInputMessage] = React.useState('');
  const [loading, setLoading] = React.useState(false);
  const messagesEndRef = React.useRef(null);
  
  const quickQuestions = [
    '如何选择胶片？',
    '拍摄夜景的技巧？',
    '什么是胶片颗粒感？',
    '推荐几个胶片型号',
    '如何冲洗胶片？'
  ];
  
  React.useEffect(() => {
    // 添加欢迎消息
    setMessages([
      {
        role: 'assistant',
        content: '您好！我是胶片摄影智能助手。您可以向我咨询关于胶片摄影的任何问题，我会尽力为您解答。',
        time: formatTime(new Date()),
        tool_calls: []
      }
    ]);
  }, []);
  
  React.useEffect(() => {
    scrollToBottom();
  }, [messages]);
  
  function scrollToBottom() {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }
  
  async function sendMessage() {
    const message = inputMessage.trim();
    if (!message || loading) return;
    
    // 添加用户消息
    const userMsg = {
      role: 'user',
      content: message,
      time: formatTime(new Date()),
      tool_calls: []
    };
    setMessages(prev => [...prev, userMsg]);
    
    setInputMessage('');
    setLoading(true);
    
    try {
      const data = await api.sendChatMessage(message);
      
      // 添加AI回复
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: data.answer || '抱歉，我暂时无法回答您的问题。',
          time: formatTime(new Date()),
          tool_calls: data.resources_used || []
        }
      ]);
    } catch (error) {
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: '抱歉，连接服务器时出现错误，请稍后重试。',
          time: formatTime(new Date()),
          tool_calls: []
        }
      ]);
    } finally {
      setLoading(false);
    }
  }
  
  function handleQuickQuestion(question) {
    setInputMessage(question);
  }
  
  return (
    <div className="page-container">
      <div className="chat-container">
        <div className="chat-messages">
          <div className="chat-messages-list">
            {messages.map((msg, index) => (
              <ChatMessage key={index} message={msg} />
            ))}
            
            {loading && (
              <div className="chat-message assistant">
                <div className="chat-message-avatar">🤖</div>
                <div className="chat-message-content">
                  <div className="chat-message-bubble">
                    <div className="typing-indicator">
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                  </div>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>
          
          <div className="chat-input-area">
            <div className="chat-input-container">
              <div className="chat-input-wrapper">
                <textarea
                  className="chat-input"
                  placeholder="输入消息... (Ctrl+Enter 发送)"
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && e.ctrlKey) {
                      sendMessage();
                    }
                  }}
                  rows="3"
                />
              </div>
              <button 
                className="btn btn-primary"
                onClick={sendMessage}
                disabled={loading || !inputMessage.trim()}
              >
                发送
              </button>
            </div>
            <div style={{ marginTop: '8px', fontSize: '0.85rem', color: '#999' }}>
              Ctrl+Enter 发送快捷键
            </div>
          </div>
        </div>
        
        <div className="chat-sidebar">
          <h3>快捷问题</h3>
          <div className="quick-questions">
            {quickQuestions.map((q, index) => (
              <button 
                key={index}
                className="quick-question-btn"
                onClick={() => handleQuickQuestion(q)}
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// 同步页面
function SyncPage() {
  const [config, setConfig] = React.useState(null);
  const [syncing, setSyncing] = React.useState(false);
  const [result, setResult] = React.useState(null);
  
  React.useEffect(() => {
    api.getConfig()
      .then(data => setConfig(data))
      .catch(console.error);
  }, []);
  
  async function handleSync() {
    setSyncing(true);
    setResult(null);
    
    try {
      const data = await api.syncResources();
      setResult(data);
    } catch (error) {
      setResult({
        files_scanned: 0,
        files_added: 0,
        files_failed: 0,
        message: '同步失败: ' + error.message
      });
    } finally {
      setSyncing(false);
    }
  }
  
  return (
    <div className="page-container">
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">资源同步</h2>
        </div>
        
        <div className="sync-info-grid">
          <div className="card">
            <h4 style={{ color: '#666', fontSize: '0.9rem', marginBottom: '8px' }}>资源目录</h4>
            <p style={{ fontFamily: 'monospace', wordBreak: 'break-all' }}>
              {config?.resource_dir || '加载中...'}
            </p>
          </div>
          <div className="card">
            <h4 style={{ color: '#666', fontSize: '0.9rem', marginBottom: '8px' }}>向量数据库</h4>
            <p style={{ fontFamily: 'monospace', wordBreak: 'break-all' }}>
              {config?.vector_db_path || '加载中...'}
            </p>
          </div>
        </div>
        
        <div className="sync-action">
          <button 
            className="btn btn-primary btn-large"
            onClick={handleSync}
            disabled={syncing}
          >
            {syncing ? '同步中...' : '开始同步'}
          </button>
        </div>
        
        {(syncing || result) && (
          <div className="sync-progress">
            {syncing && (
              <div className="sync-progress-bar">
                <div className="sync-progress-fill"></div>
              </div>
            )}
            
            {result && (
              <>
                <div className="sync-stats">
                  <div className="sync-stat">
                    <span className="sync-stat-value">{result.files_scanned || 0}</span>
                    <span className="sync-stat-label">扫描文件</span>
                  </div>
                  <div className="sync-stat">
                    <span className="sync-stat-value">{result.files_added || 0}</span>
                    <span className="sync-stat-label">新增资源</span>
                  </div>
                  <div className="sync-stat">
                    <span className="sync-stat-value">{result.files_failed || 0}</span>
                    <span className="sync-stat-label">失败</span>
                  </div>
                </div>
                <p style={{ marginTop: '16px', color: '#666', textAlign: 'center' }}>
                  {result.message}
                </p>
              </>
            )}
          </div>
        )}
        
        <div className="card">
          <h4 style={{ marginBottom: '16px' }}>同步说明</h4>
          <ul style={{ marginLeft: '20px', color: '#666' }}>
            <li style={{ marginBottom: '8px' }}>同步会扫描资源目录下的所有图片和文档</li>
            <li style={{ marginBottom: '8px' }}>新添加的文件会自动生成标签并建立向量索引</li>
            <li style={{ marginBottom: '8px' }}>已存在的文件会被跳过，不会重复处理</li>
            <li>首次同步可能需要较长时间，请耐心等待</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

// 404页面
function NotFoundPage({ onNavigate }) {
  return (
    <div className="page-container">
      <div className="card">
        <div className="empty-state">
          <h2 style={{ fontSize: '3rem', marginBottom: '16px' }}>404</h2>
          <p style={{ color: '#666', marginBottom: '24px' }}>页面不存在</p>
          <button className="btn btn-primary" onClick={() => onNavigate('home', '/')}>
            返回首页
          </button>
        </div>
      </div>
    </div>
  );
}

// 主应用组件
function App() {
  const [currentPage, setCurrentPage] = React.useState('home');
  const [currentPath, setCurrentPath] = React.useState('/');
  
  // 解析URL路径
  React.useEffect(() => {
    const path = window.location.pathname;
    setCurrentPath(path);
    
    if (path === '/' || path === '') {
      setCurrentPage('home');
    } else if (path.startsWith('/resources/')) {
      const id = path.split('/resources/')[1]?.replace(/\/$/, '');
      if (id && !isNaN(id)) {
        setCurrentPage('detail');
      } else {
        setCurrentPage('resources');
      }
    } else if (path === '/search/' || path.startsWith('/search')) {
      setCurrentPage('search');
    } else if (path === '/chat/') {
      setCurrentPage('chat');
    } else if (path === '/sync/') {
      setCurrentPage('sync');
    } else {
      setCurrentPage('notFound');
    }
  }, []);
  
  function navigate(pageId, path) {
    setCurrentPage(pageId);
    setCurrentPath(path);
    window.history.pushState({}, '', path);
    window.scrollTo(0, 0);
  }
  
  function getResourceId() {
    if (currentPage === 'detail') {
      const match = currentPath.match(/\/resources\/(\d+)/);
      return match ? parseInt(match[1]) : null;
    }
    return null;
  }
  
  return (
    <div className="app-container">
      <Header currentPage={currentPage} onNavigate={navigate} />
      
      <main className="app-main">
        {currentPage === 'home' && <HomePage onNavigate={navigate} />}
        {currentPage === 'resources' && <ResourcesPage onNavigate={navigate} />}
        {currentPage === 'detail' && (
          <ResourceDetailPage 
            resourceId={getResourceId()} 
            onNavigate={navigate} 
          />
        )}
        {currentPage === 'search' && <SearchPage onNavigate={navigate} />}
        {currentPage === 'chat' && <ChatPage />}
        {currentPage === 'sync' && <SyncPage />}
        {currentPage === 'notFound' && <NotFoundPage onNavigate={navigate} />}
      </main>
      
      <footer style={{ 
        background: '#1a1a2e', 
        color: 'rgba(255,255,255,0.7)', 
        textAlign: 'center', 
        padding: '16px',
        fontSize: '0.9rem'
      }}>
        胶片摄影归档系统 v1.0 | Powered by AI Agent
      </footer>
    </div>
  );
}

// 渲染应用
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
