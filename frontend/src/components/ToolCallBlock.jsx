import { useState } from 'react';
import ImageThumbnails from './ImageThumbnails';

const TOOL_ICONS = {
  retrieve_knowledge: '🔍',
  analyze_image: '🖼️',
  search_by_tags: '🏷️',
};

function ToolCallBlock({ tool, args, result, images, status = 'done' }) {
  const [showResult, setShowResult] = useState(false);
  const isRunning = status === 'running';

  const toolIcon = TOOL_ICONS[tool] || '🔧';
  const argsSummary = args
    ? Object.entries(args)
        .map(([k, v]) => `${k}=${String(v).substring(0, 40)}`)
        .join(', ')
    : '';

  return (
    <div className={`tool-call-block ${isRunning ? 'tool-call-running' : ''}`}>
      <div className="tool-call-header">
        <span className="tool-call-icon">{toolIcon}</span>
        <span className="tool-call-name">{tool}</span>
        {isRunning && <span className="tool-call-spinner" />}
        {argsSummary && (
          <span className="tool-call-args">({argsSummary})</span>
        )}
      </div>

      {result && !isRunning && (
        <div className="tool-call-result">
          <button
            className="tool-result-toggle"
            onClick={() => setShowResult(!showResult)}
          >
            {showResult ? '▼' : '▶'} 查看结果
          </button>
          {showResult && (
            <pre className="tool-result-content">{result}</pre>
          )}
        </div>
      )}

      {isRunning && (
        <div className="tool-call-pending">执行中...</div>
      )}

      {images && images.length > 0 && (
        <ImageThumbnails images={images} />
      )}
    </div>
  );
}

export default ToolCallBlock;
