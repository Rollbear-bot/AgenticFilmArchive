const API_BASE = '/api/v1';

const api = {
  async request(method, endpoint, data = null) {
    const url = `${API_BASE}${endpoint}`;
    const options = {
      method,
      headers: { 'Content-Type': 'application/json' }
    };
    if (data) options.body = JSON.stringify(data);

    try {
      const response = await fetch(url, options);
      return await response.json();
    } catch (error) {
      console.error('API请求失败:', error);
      throw error;
    }
  },

  healthCheck() {
    return this.request('GET', '/health/');
  },

  getConfig() {
    return this.request('GET', '/config/');
  },

  getResources(params = {}) {
    const query = new URLSearchParams(params).toString();
    return this.request('GET', `/resources/?${query}`);
  },

  getResource(id) {
    return this.request('GET', `/resources/${id}/`);
  },

  searchResources(query, options = {}) {
    const params = { query, ...options };
    const queryStr = new URLSearchParams(params).toString();
    return this.request('GET', `/resources/search/?${queryStr}`);
  },

  syncResources() {
    return this.request('POST', '/resources/sync/');
  },

  sendChatMessage(message) {
    return this.request('POST', '/chat/', { message, include_resources: true });
  },

  sendAgentMessage(message, threadId = null) {
    const body = { message };
    if (threadId) body.thread_id = threadId;
    return this.request('POST', '/agent/chat/', body);
  },

  getChatHistory() {
    return this.request('GET', '/chat/history/');
  },

  async sendAgentMessageStream(message, threadId, callbacks) {
    const url = `${API_BASE}/agent/chat/stream/`;
    const body = { message };
    if (threadId) body.thread_id = threadId;

    let reader;
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const errText = await response.text();
        callbacks.onError?.({ message: `HTTP ${response.status}: ${errText}` });
        return;
      }

      reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE 事件以 \n\n 分隔
        const parts = buffer.split('\n\n');
        buffer = parts.pop(); // 保留不完整的事件在 buffer 中

        for (const part of parts) {
          if (!part.trim()) continue;

          const lines = part.split('\n');
          let eventType = '';
          let dataStr = '';

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith('data: ')) {
              dataStr = line.slice(6).trim();
            }
          }

          if (eventType && dataStr) {
            try {
              const data = JSON.parse(dataStr);
              switch (eventType) {
                case 'thinking':
                  callbacks.onThinking?.(data);
                  break;
                case 'text':
                  callbacks.onText?.(data);
                  break;
                case 'tool_start':
                  callbacks.onToolStart?.(data);
                  break;
                case 'tool_end':
                  callbacks.onToolEnd?.(data);
                  break;
                case 'tool_images':
                  callbacks.onToolImages?.(data);
                  break;
                case 'done':
                  callbacks.onDone?.(data);
                  break;
                case 'error':
                  callbacks.onError?.(data);
                  break;
              }
            } catch (e) {
              console.warn('SSE parse error:', e, part);
            }
          }
        }
      }
    } catch (error) {
      console.error('SSE stream error:', error);
      callbacks.onError?.({ message: error.message || '连接失败' });
    }
  },
};

export default api;
