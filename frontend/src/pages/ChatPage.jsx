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
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [convLoading, setConvLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const quickQuestions = [
    '如何选择胶片？',
    '拍摄夜景的技巧？',
    '什么是胶片颗粒感？',
    '推荐几个胶片型号',
    '如何冲洗胶片？',
  ];

  const welcomeMessage = agentMode
    ? '您好！我是胶片摄影 **Agent 智能助手**。我会自主决定是否需要检索知识库、分析图片或按标签搜索，为您提供更精准的回答。'
    : '您好！我是胶片摄影智能助手。您可以向我咨询关于胶片摄影的任何问题，我会尽力为您解答。';

  useEffect(() => {
    loadConversations();
    // 初始不自动创建对话，让用户点击"新建对话"
    setMessages([
      {
        id: nextMsgId(),
        role: 'assistant',
        content: welcomeMessage,
        time: formatTime(new Date()),
        tool_calls: [],
      },
    ]);
  }, [agentMode]);

  // 禁止对话页的页面级滚动，仅对话区域内部滚动
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = '';
    };
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  function scrollToBottom() {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }

  // ===== 对话列表管理 =====

  async function loadConversations() {
    try {
      const result = await api.getConversations();
      setConversations(result.conversations || []);
    } catch (error) {
      console.error('加载对话列表失败:', error);
    }
  }

  async function handleNewConversation() {
    // 如果正在加载，不允许新建
    if (loading) return;

    try {
      setConvLoading(true);
      const result = await api.createConversation();
      const newId = result.id;

      await loadConversations();

      setCurrentConversationId(newId);
      setMessages([
        {
          id: nextMsgId(),
          role: 'assistant',
          content: '新对话已开始！我是胶片摄影 Agent 智能助手。请告诉我您想了解什么？',
          time: formatTime(new Date()),
          tool_calls: [],
        },
      ]);
    } catch (error) {
      console.error('创建对话失败:', error);
    } finally {
      setConvLoading(false);
    }
  }

  async function handleSwitchConversation(convId) {
    if (convId === currentConversationId) return;
    if (loading) return;

    try {
      setConvLoading(true);
      const conv = await api.getConversation(convId);
      const loadedMessages = (conv.messages || []).map((msg) => ({
        id: nextMsgId(),
        role: msg.role,
        content: msg.content,
        time: msg.time,
        tool_calls: msg.tool_calls || [],
        thinking: [],
      }));
      setMessages(loadedMessages);
      setCurrentConversationId(convId);
    } catch (error) {
      console.error('加载对话失败:', error);
    } finally {
      setConvLoading(false);
    }
  }

  async function handleDeleteConversation(convId) {
    if (!confirm('确定要删除这个对话吗？')) return;
    try {
      await api.deleteConversation(convId);
      await loadConversations();
      if (convId === currentConversationId) {
        setCurrentConversationId(null);
        setMessages([
          {
            id: nextMsgId(),
            role: 'assistant',
            content: welcomeMessage,
            time: formatTime(new Date()),
            tool_calls: [],
          },
        ]);
      }
    } catch (error) {
      console.error('删除对话失败:', error);
    }
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
        // 更新 conversation_id 和列表
        if (data.conversation_id) {
          setCurrentConversationId(data.conversation_id);
          // 如果是新对话，刷新列表
          loadConversations();
        } else if (data.thread_id) {
          setCurrentConversationId(data.thread_id);
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
      await api.sendAgentMessageStream(message, currentConversationId, callbacks);
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

    // 如果没有当前对话，自动创建一个
    if (!currentConversationId) {
      try {
        const result = await api.createConversation();
        setCurrentConversationId(result.id);
        await loadConversations();
      } catch (error) {
        console.error('自动创建对话失败:', error);
      }
    }

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
            {agentMode && (
              <button
                className="new-session-btn"
                onClick={handleNewConversation}
                disabled={loading || convLoading}
              >
                ➕ 新对话
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
          {/* 对话列表 — 最常用，置顶 */}
          {agentMode && (
            <div className="conversation-sidebar">
              <h3>历史对话</h3>
              <div className="conversation-list">
                {convLoading && conversations.length === 0 && (
                  <div className="conv-empty">加载中...</div>
                )}
                {conversations.map((conv) => (
                  <div
                    key={conv.id}
                    className={`conversation-item ${conv.id === currentConversationId ? 'active' : ''}`}
                    onClick={() => handleSwitchConversation(conv.id)}
                  >
                    <div className="conv-title">{conv.title || '未命名'}</div>
                    <div className="conv-meta">
                      <span className="conv-msg-count">{conv.message_count || 0} 条消息</span>
                      <span className="conv-time">{formatDate(conv.updated_at)}</span>
                    </div>
                    <button
                      className="conv-delete-btn"
                      onClick={(e) => { e.stopPropagation(); handleDeleteConversation(conv.id); }}
                      title="删除对话"
                    >
                      ×
                    </button>
                  </div>
                ))}
                {!convLoading && conversations.length === 0 && (
                  <div className="conv-empty">暂无历史对话</div>
                )}
              </div>
            </div>
          )}

          {/* 快捷问题 — 次常用 */}
          <h3 style={{ marginTop: agentMode ? '16px' : '0' }}>快捷问题</h3>
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

          {/* Agent 工具集 — 参考信息，置底 */}
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
                <li>
                  🧠 <strong>read_memory</strong>
                  <br />
                  读取用户长期记忆
                </li>
                <li>
                  💾 <strong>write_memory</strong>
                  <br />
                  保存重要偏好信息
                </li>
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/** 简洁日期格式化 */
function formatDate(isoString) {
  if (!isoString) return '';
  const d = new Date(isoString);
  const now = new Date();
  const diff = now - d;
  const mins = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (mins < 1) return '刚刚';
  if (mins < 60) return `${mins}分钟前`;
  if (hours < 24) return `${hours}小时前`;
  if (days < 7) return `${days}天前`;
  return d.toLocaleDateString('zh-CN');
}

export default ChatPage;
