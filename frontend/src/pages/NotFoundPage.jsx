import { Link } from 'react-router-dom';

function NotFoundPage() {
  return (
    <div className="page-container">
      <div className="card">
        <div className="empty-state">
          <h2 style={{ fontSize: '3rem', marginBottom: '16px' }}>404</h2>
          <p style={{ color: '#666', marginBottom: '24px' }}>页面不存在</p>
          <Link to="/" className="btn btn-primary">
            返回首页
          </Link>
        </div>
      </div>
    </div>
  );
}

export default NotFoundPage;
