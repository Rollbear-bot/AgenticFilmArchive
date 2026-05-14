import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Header from './components/Header';
import HomePage from './pages/HomePage';
import ResourcesPage from './pages/ResourcesPage';
import ResourceDetailPage from './pages/ResourceDetailPage';
import SearchPage from './pages/SearchPage';
import ChatPage from './pages/ChatPage';
import SyncPage from './pages/SyncPage';
import NotFoundPage from './pages/NotFoundPage';

function App() {
  return (
    <BrowserRouter>
      <div className="app-container">
        <Header />
        <main className="app-main">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/resources/" element={<ResourcesPage />} />
            <Route path="/resources/:resourceId/" element={<ResourceDetailPage />} />
            <Route path="/search/" element={<SearchPage />} />
            <Route path="/chat/" element={<ChatPage />} />
            <Route path="/sync/" element={<SyncPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
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
    </BrowserRouter>
  );
}

export default App;
