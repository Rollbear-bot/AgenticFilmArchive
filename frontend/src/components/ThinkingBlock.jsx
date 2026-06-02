import { useState } from 'react';

function ThinkingBlock({ content, isStreaming = false }) {
  const [collapsed, setCollapsed] = useState(true);

  if (!content && !isStreaming) return null;

  return (
    <div className="thinking-block">
      <button
        className="thinking-toggle"
        onClick={() => setCollapsed(!collapsed)}
      >
        <span className="thinking-icon">
          {isStreaming ? '🔄' : '🤔'}
        </span>
        <span className="thinking-label">
          {isStreaming ? 'Agent 正在思考中...' : 'Agent 思考过程'}
        </span>
        <span className="thinking-collapse-icon">
          {collapsed ? '▶' : '▼'}
        </span>
      </button>
      {!collapsed && content && (
        <div className="thinking-content">
          {content.split('\n').map((line, i) => (
            <p key={i}>{line}</p>
          ))}
        </div>
      )}
      {!collapsed && !content && isStreaming && (
        <div className="thinking-content thinking-loading">
          <span className="streaming-cursor">▊</span>
        </div>
      )}
    </div>
  );
}

export default ThinkingBlock;
