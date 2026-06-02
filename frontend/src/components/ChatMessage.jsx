import { formatMessage } from '../utils/format';
import ThinkingBlock from './ThinkingBlock';
import ToolCallBlock from './ToolCallBlock';
import MarkdownRenderer from './MarkdownRenderer';

function ChatMessage({ message, agentMode = false }) {
  const isUser = message.role === 'user';

  return (
    <div className={`chat-message ${message.role}`}>
      <div className="chat-message-avatar">
        {isUser ? '👤' : '🤖'}
      </div>
      <div className="chat-message-content">
        {/* Thinking blocks */}
        {message.thinking && message.thinking.length > 0 && (
          <div className="chat-thinking-blocks">
            {message.thinking.map((think, index) => (
              <ThinkingBlock
                key={index}
                content={think.content}
                isStreaming={think.isStreaming}
              />
            ))}
          </div>
        )}

        {/* Tool call blocks (new format with status, result, images) */}
        {message.tool_calls && message.tool_calls.length > 0 && (
          <div className="chat-tool-blocks">
            {message.tool_calls.map((toolCall, index) => (
              <ToolCallBlock
                key={toolCall.id || index}
                tool={toolCall.tool}
                args={toolCall.args}
                result={toolCall.result}
                images={toolCall.images}
                status={toolCall.status || 'done'}
              />
            ))}
          </div>
        )}

        {/* Text content bubble */}
        {message.content && (
          <div
            className={`chat-message-bubble ${message.isStreaming ? 'chat-message-streaming' : ''}`}
          >
            {isUser ? (
              <span dangerouslySetInnerHTML={{ __html: formatMessage(message.content) }} />
            ) : (
              <MarkdownRenderer content={message.content} />
            )}
          </div>
        )}

        {/* Legacy tool calls (from old format, kept for backward compat) */}
        {message.tool_calls_legacy && message.tool_calls_legacy.length > 0 && (
          <div className="tool-calls">
            {message.tool_calls_legacy.map((tool, index) => (
              <div key={index} className="tool-call">
                <span className="tool-icon">🔧</span>
                <span className="tool-name">{tool.tool}</span>
                {tool.args && Object.keys(tool.args).length > 0 && (
                  <div className="tool-args">
                    {Object.entries(tool.args).map(([key, value]) => (
                      <span key={key} className="tool-arg">
                        <strong>{key}</strong>: {String(value).substring(0, 80)}
                        {String(value).length > 80 ? '...' : ''}
                      </span>
                    ))}
                  </div>
                )}
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
