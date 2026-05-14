import { useState, useEffect } from 'react';
import api from '../services/api';

function SyncPage() {
  const [config, setConfig] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [result, setResult] = useState(null);

  useEffect(() => {
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

export default SyncPage;
