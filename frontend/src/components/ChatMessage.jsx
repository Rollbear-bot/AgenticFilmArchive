import { formatMessage, formatTime } from '../utils/format';

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

export default ChatMessage;
