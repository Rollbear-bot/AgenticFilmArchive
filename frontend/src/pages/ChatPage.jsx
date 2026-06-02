import { useState, useEffect, useRef, useCallback } from 'react';
import { flushSync } from 'react-dom';
import { formatTime } from '../utils/format';
import api from '../services/api';
import ChatMessage from '../components/ChatMessage';

let _msgIdCounter = 0;
function nextMsgId() {
  return ++_msgIdCounter;
}

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
    '如何冲洗胶片？',
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
        tool_calls: [],
      },
    ]);
    setThreadId(null);
  }, [agentMode]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  function scrollToBottom() {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }

  // ===== 流式对话 =====
  async function sendMessageStreaming(message) {
    const userMsg = {
      id: nextMsgId(),
      role: 'user',
      content: message,
      time: formatTime(new Date()),
      tool_calls: [],
    };
    setMessages((prev) => [...prev, userMsg]);

    setInputMessage('');
    setLoading(true);

    // 创建一个空的 assistant 消息用于流式更新
    const assistantMsgId = nextMsgId();
    const assistantMsg = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      time: formatTime(new Date()),
      tool_calls: [],
      thinking: [],
      isStreaming: true,
    };
    setMessages((prev) => [...prev, assistantMsg]);

    // 流式回调
    const callbacks = {
      onThinking(data) {
        flushSync(() => {
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== assistantMsgId) return m;
              const lastThink = m.thinking?.[m.thinking.length - 1];
              if (lastThink && lastThink.isStreaming) {
                const updatedThinking = [...m.thinking];
                updatedThinking[updatedThinking.length - 1] = {
                  ...lastThink,
                  content: (lastThink.content || '') + data.content,
                };
                return { ...m, thinking: updatedThinking };
              }
              return {
                ...m,
                thinking: [
                  ...(m.thinking || []),
                  { content: data.content, isStreaming: true },
                ],
              };
            })
          );
        });
      },

      onText(data) {
        flushSync(() => {
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== assistantMsgId) return m;
              const updatedThinking = (m.thinking || []).map((t) =>
                t.isStreaming ? { ...t, isStreaming: false } : t
              );
              return {
                ...m,
                content: (m.content || '') + data.content,
                thinking: updatedThinking,
              };
            })
          );
        });
      },

      onToolStart(data) {
        flushSync(() => {
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== assistantMsgId) return m;
              return {
                ...m,
                tool_calls: [
                  ...(m.tool_calls || []),
                  {
                    id: `tc-${nextMsgId()}`,
                    tool: data.tool,
                    args: data.args,
                    result: null,
                    images: null,
                    status: 'running',
                  },
                ],
              };
            })
          );
        });
      },

      onToolEnd(data) {
        flushSync(() => {
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== assistantMsgId) return m;
              return {
                ...m,
                tool_calls: (m.tool_calls || []).map((tc) =>
                  tc.tool === data.tool && tc.status === 'running'
                    ? { ...tc, result: data.result, status: 'done' }
                    : tc
                ),
              };
            })
          );
        });
      },

      onToolImages(data) {
        flushSync(() => {
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== assistantMsgId) return m;
              const updatedToolCalls = [...(m.tool_calls || [])];
              for (let i = updatedToolCalls.length - 1; i >= 0; i--) {
                if (updatedToolCalls[i].tool === 'retrieve_knowledge' && updatedToolCalls[i].status === 'done') {
                  updatedToolCalls[i] = {
                    ...updatedToolCalls[i],
                    images: data.images,
                  };
                  break;
                }
              }
              return { ...m, tool_calls: updatedToolCalls };
            })
          );
        });
      },

      onDone(data) {
        if (data.thread_id) {
          setThreadId(data.thread_id);
        }
        setMessages((prev) =>
          prev.map((m) => {
            if (m.id !== assistantMsgId) return m;
            return { ...m, isStreaming: false, time: formatTime(new Date()) };
          })
        );
        setLoading(false);
      },

      onError(data) {
        setMessages((prev) =>
          prev.map((m) => {
            if (m.id !== assistantMsgId) return m;
            return {
              ...m,
              content: m.content || `抱歉，处理消息时出错：${data.message || '未知错误'}`,
              isStreaming: false,
              time: formatTime(new Date()),
            };
          })
        );
        setLoading(false);
      },
    };

    try {
      await api.sendAgentMessageStream(message, threadId, callbacks);
    } catch (error) {
      console.error('Stream error:', error);
      setLoading(false);
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id !== assistantMsgId) return m;
          return {
            ...m,
            content: m.content || `抱歉，连接服务器时出现错误：${error.message}`,
            isStreaming: false,
            time: formatTime(new Date()),
          };
        })
      );
    }
  }

  // ===== 普通对话（非流式）=====
  async function sendMessageNormal() {
    const message = inputMessage.trim();
    if (!message || loading) return;

    const userMsg = {
      id: nextMsgId(),
      role: 'user',
      content: message,
      time: formatTime(new Date()),
      tool_calls: [],
    };
    setMessages((prev) => [...prev, userMsg]);

    setInputMessage('');
    setLoading(true);

    try {
      const data = await api.sendChatMessage(message);

      setMessages((prev) => [
        ...prev,
        {
          id: nextMsgId(),
          role: 'assistant',
          content: data.answer || '抱歉，我暂时无法回答您的问题。',
          time: formatTime(new Date()),
          tool_calls: data.resources_used || [],
        },
      ]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          id: nextMsgId(),
          role: 'assistant',
          content: '抱歉，连接服务器时出现错误，请稍后重试。',
          time: formatTime(new Date()),
          tool_calls: [],
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  // ===== 发送入口 =====
  async function sendMessage() {
    const message = inputMessage.trim();
    if (!message || loading) return;

    if (agentMode) {
      await sendMessageStreaming(message);
    } else {
      await sendMessageNormal();
    }
  }

  function handleQuickQuestion(question) {
    setInputMessage(question);
  }

  function handleToggleMode() {
    setAgentMode((prev) => !prev);
  }

  function handleNewSession() {
    setThreadId(null);
    setMessages([
      {
        id: nextMsgId(),
        role: 'assistant',
        content: '已开始新的对话会话。Agent 将重新理解您的上下文。',
        time: formatTime(new Date()),
        tool_calls: [],
      },
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
                流式实时输出 | 多轮对话 | 工具调用可视化
              </span>
            )}
          </div>

          <div className="chat-messages-list">
            {messages.map((msg) => (
              <ChatMessage key={msg.id} message={msg} agentMode={agentMode} />
            ))}

            {loading && !agentMode && (
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
                  placeholder={
                    agentMode
                      ? 'Agent 模式下输入消息... (Ctrl+Enter 发送)'
                      : '输入消息... (Ctrl+Enter 发送)'
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
              {agentMode && ' | Agent 模式下自动流式输出'}
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
              <ul
                style={{
                  fontSize: '0.85rem',
                  color: '#666',
                  paddingLeft: '16px',
                  lineHeight: '1.8',
                }}
              >
                <li>
                  🔍 <strong>retrieve_knowledge</strong>
                  <br />
                  检索胶片摄影知识库
                </li>
                <li>
                  🖼️ <strong>analyze_image</strong>
                  <br />
                  分析具体图片内容
                </li>
                <li>
                  🏷️ <strong>search_by_tags</strong>
                  <br />
                  按标签筛选浏览资源
                </li>
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default ChatPage;
