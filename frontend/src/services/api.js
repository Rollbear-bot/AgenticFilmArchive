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
  }
};

export default api;
