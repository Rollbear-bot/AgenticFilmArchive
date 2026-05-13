/**
 * 应用主模块
 * 全局工具函数和初始化逻辑
 */

// 工具函数
const utils = {
    /**
     * 格式化文件大小
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },
    
    /**
     * 格式化时间
     */
    formatTime(date) {
        if (typeof date === 'string') {
            date = new Date(date);
        }
        return date.toLocaleString('zh-CN');
    },
    
    /**
     * 截取字符串
     */
    truncate(str, length = 50) {
        if (!str) return '';
        if (str.length <= length) return str;
        return str.substring(0, length) + '...';
    },
    
    /**
     * 获取URL参数
     */
    getUrlParam(name) {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get(name);
    },
    
    /**
     * 延迟函数
     */
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    },
    
    /**
     * 显示提示消息
     */
    showToast(message, type = 'info') {
        // 创建toast元素
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            top: 80px;
            right: 20px;
            padding: 12px 24px;
            background: ${type === 'success' ? '#27ae60' : type === 'error' ? '#e74c3c' : '#3498db'};
            color: white;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 10000;
            animation: slideIn 0.3s ease;
        `;
        
        document.body.appendChild(toast);
        
        // 3秒后移除
        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    },
    
    /**
     * 显示加载状态
     */
    showLoading(text = '加载中...') {
        if (window.loadingOverlay) return;
        
        const overlay = document.createElement('div');
        overlay.className = 'loading-overlay';
        overlay.id = 'loadingOverlay';
        overlay.innerHTML = `
            <div class="loading-content">
                <div class="loading-spinner"></div>
                <p>${text}</p>
            </div>
        `;
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 9999;
        `;
        
        const spinner = overlay.querySelector('.loading-spinner');
        spinner.style.cssText = `
            width: 40px;
            height: 40px;
            border: 3px solid rgba(255,255,255,0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 16px;
        `;
        
        const content = overlay.querySelector('.loading-content');
        content.style.cssText = `
            background: white;
            padding: 32px;
            border-radius: 12px;
            text-align: center;
        `;
        
        document.body.appendChild(overlay);
        window.loadingOverlay = overlay;
    },
    
    /**
     * 隐藏加载状态
     */
    hideLoading() {
        if (window.loadingOverlay) {
            window.loadingOverlay.remove();
            window.loadingOverlay = null;
        }
    },
    
    /**
     * 确认对话框
     */
    confirm(message) {
        return window.confirm(message);
    }
};

// 添加动画样式
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
    @keyframes spin {
        to { transform: rotate(360deg); }
    }
`;
document.head.appendChild(style);

// 导出到全局
window.utils = utils;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    console.log('胶片摄影归档系统已加载');
    
    // 检查后端连接
    checkBackendConnection();
});

async function checkBackendConnection() {
    try {
        const response = await fetch('/api/v1/health/');
        if (response.ok) {
            const data = await response.json();
            console.log('后端服务状态:', data.status);
        }
    } catch (error) {
        console.warn('无法连接到后端服务:', error.message);
        utils.showToast('无法连接到后端服务，请检查服务器是否运行', 'error');
    }
}
