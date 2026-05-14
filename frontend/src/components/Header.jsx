import { Link, useLocation } from 'react-router-dom';

function Header() {
  const location = useLocation();
  const currentPath = location.pathname;

  const navItems = [
    { id: 'home', label: '首页', path: '/' },
    { id: 'resources', label: '资源', path: '/resources/' },
    { id: 'search', label: '搜索', path: '/search/' },
    { id: 'chat', label: '对话', path: '/chat/' },
    { id: 'sync', label: '同步', path: '/sync/' }
  ];

  const getActiveId = () => {
    if (currentPath === '/' || currentPath === '') return 'home';
    if (currentPath.startsWith('/resources/')) return 'resources';
    if (currentPath.startsWith('/search')) return 'search';
    if (currentPath === '/chat/') return 'chat';
    if (currentPath === '/sync/') return 'sync';
    return '';
  };

  const activeId = getActiveId();

  return (
    <header className="app-header">
      <div className="logo">
        <span>📷</span>
        <span>胶片摄影归档系统</span>
      </div>
      <nav className="nav-links">
        {navItems.map(item => (
          <Link
            key={item.id}
            to={item.path}
            className={`nav-link ${activeId === item.id ? 'active' : ''}`}
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}

export default Header;
