import { useState, useEffect, useRef } from 'react';
import { formatTime } from '../utils/format';
import api from '../services/api';
import ChatMessage from '../components/ChatMessage';

function ChatPage() {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const quickQuestions = [
    '如何选择胶片？',
    '拍摄夜景的技巧？',
    '什么是胶片颗粒感？',
    '推荐几个胶片型号',
    '如何冲洗胶片？'
  ];

  useEffect(() => {
    setMessages([
      {
        role: 'assistant',
        content: '您好！我是胶片摄影智能助手。您可以向我咨询关于胶片摄影的任何问题，我会尽力为您解答。',
        time: formatTime(new Date()),
        tool_calls: []
      }
    ]);
  }, []);

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
      const data = await api.sendChatMessage(message);

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

  return (
    <div className="page-container">
      <div className="chat-container">
        <div className="chat-messages">
          <div className="chat-messages-list">
            {messages.map((msg, index) => (
              <ChatMessage key={index} message={msg} />
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
                  placeholder="输入消息... (Ctrl+Enter 发送)"
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
        </div>
      </div>
    </div>
  );
}

export default ChatPage;
