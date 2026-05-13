/**
 * API 客户端模块
 * 封装所有与后端API的交互
 */

const API_BASE = '/api/v1';

const api = {
    /**
     * 通用请求方法
     */
    async request(method, endpoint, data = null, params = null) {
        let url = `${API_BASE}${endpoint}`;
        
        // 添加查询参数
        if (params) {
            const queryString = new URLSearchParams(params).toString();
            url += `?${queryString}`;
        }
        
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json'
            }
        };
        
        if (data && (method === 'POST' || method === 'PUT' || method === 'PATCH')) {
            options.body = JSON.stringify(data);
        }
        
        try {
            const response = await fetch(url, options);
            
            if (!response.ok) {
                const error = await response.json().catch(() => ({ message: '请求失败' }));
                throw new Error(error.message || `HTTP ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error(`API请求失败: ${method} ${endpoint}`, error);
            throw error;
        }
    },
    
    /**
     * 健康检查
     */
    async healthCheck() {
        return this.request('GET', '/health/');
    },
    
    /**
     * 获取配置
     */
    async getConfig() {
        return this.request('GET', '/config/');
    },
    
    // ========== 资源管理 ==========
    
    /**
     * 获取资源列表
     */
    async getResources(params = {}) {
        const defaultParams = {
            page: 1,
            page_size: 20,
            ...params
        };
        return this.request('GET', '/resources/', null, defaultParams);
    },
    
    /**
     * 获取资源详情
     */
    async getResource(id) {
        return this.request('GET', `/resources/${id}/`);
    },
    
    /**
     * 搜索资源
     */
    async searchResources(query, options = {}) {
        const params = {
            query,
            k: 20,
            doc_type: 'any',
            ...options
        };
        return this.request('GET', '/resources/search/', null, params);
    },
    
    /**
     * 同步资源
     */
    async syncResources() {
        return this.request('POST', '/resources/sync/');
    },
    
    /**
     * 获取资源标签
     */
    async getResourceTags(id) {
        return this.request('GET', `/resources/${id}/tags/`);
    },
    
    /**
     * 下载资源
     */
    async downloadResource(id) {
        const url = `${API_BASE}/resources/${id}/download/`;
        window.open(url, '_blank');
    },
    
    // ========== 对话管理 ==========
    
    /**
     * 发送对话消息
     */
    async sendChatMessage(message, options = {}) {
        return this.request('POST', '/chat/', {
            message,
            include_resources: true,
            ...options
        });
    },
    
    /**
     * 获取对话历史
     */
    async getChatHistory() {
        return this.request('GET', '/chat/history/');
    },
    
    /**
     * 清除对话历史
     */
    async clearChatHistory() {
        return this.request('DELETE', '/chat/history/');
    }
};

// 导出到全局
window.API = api;
