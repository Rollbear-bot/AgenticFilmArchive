import { useState, useEffect, useRef } from 'react';
import { formatTime } from '../utils/format';
import api from '../services/api';
import ChatMessage from '../components/ChatMessage';

function ChatPage() {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [agentMode, setAgentMode] = useState(true);
  const [threadId, setThreadId] = useState(null);
  const messagesEndRef = useRef(null);

  const quickQuestions = [
    '如何选择胶片？',
    '拍摄夜景的技巧？',
    '什么是胶片颗粒感？',
    '推荐几个胶片型号',
    '如何冲洗胶片？'
  ];

  useEffect(() => {
    const welcomeMsg = agentMode
      ? '您好！我是胶片摄影 **Agent 智能助手**。我会自主决定是否需要检索知识库、分析图片或按标签搜索，为您提供更精准的回答。'
      : '您好！我是胶片摄影智能助手。您可以向我咨询关于胶片摄影的任何问题，我会尽力为您解答。';
    setMessages([
      {
        role: 'assistant',
        content: welcomeMsg,
        time: formatTime(new Date()),
        tool_calls: []
      }
    ]);
    setThreadId(null);
  }, [agentMode]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  function scrollToBottom() {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }

  async function sendMessage() {
    const message = inputMessage.trim();
    if (!message || loading) return;

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
      let data;
      if (agentMode) {
        data = await api.sendAgentMessage(message, threadId);
        // 保存 thread_id 用于后续多轮对话
        if (data.history_id) {
          setThreadId(data.history_id);
        }
      } else {
        data = await api.sendChatMessage(message);
      }

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

  function handleToggleMode() {
    setAgentMode(prev => !prev);
  }

  function handleNewSession() {
    setThreadId(null);
    setMessages([
      {
        role: 'assistant',
        content: '已开始新的对话会话。Agent 将重新理解您的上下文。',
        time: formatTime(new Date()),
        tool_calls: []
      }
    ]);
  }

  return (
    <div className="page-container">
      <div className="chat-container">
        <div className="chat-messages">
          {/* 模式切换栏 */}
          <div className="chat-mode-bar">
            <div className="mode-toggle">
              <button
                className={`mode-btn ${agentMode ? 'mode-btn-active' : ''}`}
                onClick={() => !agentMode && handleToggleMode()}
              >
                🤖 Agent 模式
              </button>
              <button
                className={`mode-btn ${!agentMode ? 'mode-btn-active' : ''}`}
                onClick={() => agentMode && handleToggleMode()}
              >
                📋 普通模式
              </button>
            </div>
            {agentMode && threadId && (
              <button className="new-session-btn" onClick={handleNewSession}>
                🔄 新会话
              </button>
            )}
            {agentMode && (
              <span className="mode-hint">
                Agent 自主决策工具调用 | 支持多轮对话
              </span>
            )}
          </div>

          <div className="chat-messages-list">
            {messages.map((msg, index) => (
              <ChatMessage key={index} message={msg} agentMode={agentMode} />
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
                    {agentMode && (
                      <div style={{ fontSize: '0.8rem', color: '#888', marginTop: '6px' }}>
                        Agent 正在思考并决定是否调用工具...
                      </div>
                    )}
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
                  placeholder={agentMode
                    ? "Agent 模式下输入消息... (Ctrl+Enter 发送)"
                    : "输入消息... (Ctrl+Enter 发送)"
                  }
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

          {agentMode && (
            <div className="agent-info" style={{ marginTop: '20px' }}>
              <h3>Agent 工具集</h3>
              <ul style={{ fontSize: '0.85rem', color: '#666', paddingLeft: '16px', lineHeight: '1.8' }}>
                <li>🔍 <strong>retrieve_knowledge</strong><br/>检索胶片摄影知识库</li>
                <li>🖼️ <strong>analyze_image</strong><br/>分析具体图片内容</li>
                <li>🏷️ <strong>search_by_tags</strong><br/>按标签筛选浏览资源</li>
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default ChatPage;
