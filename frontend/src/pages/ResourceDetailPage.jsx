import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../services/api';

function ResourceDetailPage() {
  const { resourceId } = useParams();
  const navigate = useNavigate();
  const [resource, setResource] = useState(null);
  const [loading, setLoading] = useState(true);
  const [imageLoaded, setImageLoaded] = useState(false);

  useEffect(() => {
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
            <button className="btn btn-primary" style={{ marginTop: '16px' }} onClick={() => navigate('/resources/')}>
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
          <button className="btn btn-secondary" onClick={() => navigate('/resources/')}>
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

export default ResourceDetailPage;
