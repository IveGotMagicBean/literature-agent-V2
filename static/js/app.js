/**
 * Literature Agent - 前端交互逻辑
 */

class LiteratureAgentApp {
    constructor() {
        this.currentPDF = null;
        this.isProcessing = false;
        this.chatHistory = [];
        this.abortController = null;  // 用于打断流式输出
        
        this.initElements();
        this.initEventListeners();
        this.loadTheme();
        this.initChat();  // 启用闲聊功能
        this.checkStatus();
    }
    
    // 初始化DOM元素
    initElements() {
        // 上传相关
        this.uploadArea = document.getElementById('uploadArea');
        this.fileInput = document.getElementById('fileInput');
        this.uploadProgress = document.getElementById('uploadProgress');
        this.fileInfo = document.getElementById('fileInfo');
        this.fileName = document.getElementById('fileName');
        this.pageCount = document.getElementById('pageCount');
        this.figureCount = document.getElementById('figureCount');
        
        // 聊天相关
        this.welcomeScreen = document.getElementById('welcomeScreen');
        this.chatMessages = document.getElementById('chatMessages');
        this.chatInput = document.getElementById('chatInput');
        this.sendBtn = document.getElementById('sendBtn');
        this.stopBtn = document.getElementById('stopBtn');
        
        // 快捷按钮
        this.generatePPT = document.getElementById('generatePPT');
        this.generateReport = document.getElementById('generateReport');
        this.analyzeFigures = document.getElementById('analyzeFigures');
        
        // 主题切换
        this.themeToggle = document.getElementById('themeToggle');
        
        // 状态指示
        this.statusIndicator = document.getElementById('statusIndicator');
        
        // 加载覆盖
        this.loadingOverlay = document.getElementById('loadingOverlay');
        this.loadingText = document.getElementById('loadingText');
        
        // Toast容器
        this.toastContainer = document.getElementById('toastContainer');
    }
    
    // 初始化事件监听器
    initEventListeners() {
        // 文件上传
        this.uploadArea.addEventListener('click', () => this.fileInput.click());
        this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
        
        // 拖拽上传
        this.uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.uploadArea.classList.add('dragover');
        });
        
        this.uploadArea.addEventListener('dragleave', () => {
            this.uploadArea.classList.remove('dragover');
        });
        
        this.uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            this.uploadArea.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.handleFile(files[0]);
            }
        });
        
        // 发送消息
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        this.stopBtn.addEventListener('click', () => this.stopGeneration());
        this.chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // 自动调整输入框高度
        this.chatInput.addEventListener('input', () => {
            this.chatInput.style.height = 'auto';
            this.chatInput.style.height = this.chatInput.scrollHeight + 'px';
        });
        
        // 快捷操作
        this.generatePPT.addEventListener('click', () => {
            this.generateDocument('ppt');
        });
        
        this.generateReport.addEventListener('click', () => {
            this.generateDocument('report');
        });
        
        this.analyzeFigures.addEventListener('click', () => {
            this.chatInput.value = '请分析所有图表';
            this.sendMessage();
        });
        
        // 模板按钮
        document.querySelectorAll('.template-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const prompt = btn.dataset.prompt;
                this.chatInput.value = prompt;
                this.chatInput.focus();
            });
        });
        
        // 主题切换
        this.themeToggle.addEventListener('click', () => this.toggleTheme());
        
        // 全部下载按钮
        const downloadAllBtn = document.getElementById('downloadAllBtn');
        if (downloadAllBtn) {
            downloadAllBtn.addEventListener('click', () => this.downloadAll());
        }
        
        // 示例文档按钮
        const loadExampleBtn = document.getElementById('loadExampleBtn');
        if (loadExampleBtn) {
            loadExampleBtn.addEventListener('click', () => this.loadExampleDocument());
        }
        
        // 演示视频按钮
        const helpBtn = document.getElementById('helpBtn');
        if (helpBtn) {
            helpBtn.addEventListener('click', () => this.showDemoVideo());
        }
        
        // 项目说明按钮
        const docsBtn = document.getElementById('docsBtn');
        if (docsBtn) {
            docsBtn.addEventListener('click', () => this.showProjectDocs());
        }
        
        // 标签页切换
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const tab = btn.dataset.tab;
                this.switchTab(tab);
            });
        });
    }
    
    // 处理文件选择
    handleFileSelect(event) {
        const file = event.target.files[0];
        if (file) {
            this.handleFile(file);
        }
    }
    
    // 处理文件上传
    async handleFile(file) {
        if (!file.name.endsWith('.pdf')) {
            this.showToast('请上传PDF文件', 'error');
            return;
        }
        
        // 检查文件大小（50MB）
        if (file.size > 50 * 1024 * 1024) {
            this.showToast('文件过大，请上传小于50MB的文件', 'error');
            return;
        }
        
        // 显示上传进度
        this.uploadProgress.style.display = 'block';
        this.fileInfo.style.display = 'none';
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.currentPDF = data.filename;
                this.showFileInfo(data);
                this.enableChat();
                this.showToast('PDF上传成功！', 'success');
                
                // 显示所有主图到侧边栏
                if (data.figures && data.figures.length > 0) {
                    console.log(`发现 ${data.figures.length} 个主图，添加到图表栏`);
                    data.figures.forEach(figure => {
                        this.addToFiguresTab(figure);
                    });
                    this.showToast(`已加载 ${data.figures.length} 个图表`, 'info');
                }
                
                // 隐藏欢迎界面，显示聊天区
                this.welcomeScreen.style.display = 'none';
                this.chatMessages.style.display = 'flex';
            } else {
                this.showToast('上传失败', 'error');
            }
        } catch (error) {
            console.error('Upload error:', error);
            this.showToast('上传失败: ' + error.message, 'error');
        } finally {
            this.uploadProgress.style.display = 'none';
        }
    }
    
    // 显示文件信息
    showFileInfo(data) {
        this.fileName.textContent = data.filename;
        this.pageCount.textContent = data.stats.pages || 0;
        this.figureCount.textContent = data.stats.figures || 0;
        this.fileInfo.style.display = 'block';
    }
    
    // 启用聊天功能
    enableChat() {
        console.log('启用聊天功能...');
        
        // 移除disabled属性
        this.chatInput.disabled = false;
        this.sendBtn.disabled = false;
        this.generatePPT.disabled = false;
        this.generateReport.disabled = false;
        this.analyzeFigures.disabled = false;
        
        // 强制更新DOM
        this.chatInput.removeAttribute('disabled');
        this.sendBtn.removeAttribute('disabled');
        
        // 聚焦到输入框
        this.chatInput.focus();
        
        console.log('聊天功能已启用');
        console.log('输入框状态:', this.chatInput.disabled);
    }
    
    // 启动时默认启用闲聊
    initChat() {
        this.chatInput.disabled = false;
        this.sendBtn.disabled = false;
        this.chatInput.placeholder = "输入您的问题...（上传PDF后可分析文献）";
    }
    
    // 停止生成
    stopGeneration() {
        if (this.abortController) {
            this.abortController.abort();
            this.abortController = null;
        }
    }

    // 切换发送/停止按钮显示
    _showStopBtn() {
        this.sendBtn.style.display = 'none';
        this.stopBtn.style.display = 'flex';
    }

    _showSendBtn() {
        this.stopBtn.style.display = 'none';
        this.sendBtn.style.display = 'flex';
    }

    // 发送消息
    async sendMessage() {
        const message = this.chatInput.value.trim();
        if (!message || this.isProcessing) return;
        
        // 添加用户消息
        this.addMessage('user', message);
        this.chatInput.value = '';
        this.chatInput.style.height = 'auto';
        
        // 显示加载状态
        this.isProcessing = true;
        this._showStopBtn();
        const loadingMsg = this.addMessage('assistant', '正在思考...', true);
        
        // 创建可打断的控制器
        this.abortController = new AbortController();

        try {
            const response = await fetch('/api/query/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: message }),
                signal: this.abortController.signal
            });
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            
            let assistantMessage = '';
            let figures = [];
            let downloads = [];
            
            // 移除加载消息
            loadingMsg.remove();
            const msgElement = this.addMessage('assistant', '', false);
            const contentElement = msgElement.querySelector('.message-bubble');
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const event = JSON.parse(line.slice(6));
                            
                            if (event.type === 'status' || event.type === 'thinking') {
                                const statusText = event.content || '';
                                if (statusText) {
                                    // status只在还没有正文时显示，有正文后不覆盖
                                    if (!assistantMessage) {
                                        const statusLine = `<div style="color: #94a3b8; font-size: 0.9em; margin: 4px 0;">${statusText}</div>`;
                                        contentElement.innerHTML = statusLine;
                                    }
                                }
                            } else if (event.type === 'answer' || event.type === 'answer_chunk' || event.type === 'answer_done') {
                                assistantMessage += event.content || '';
                                contentElement.innerHTML = this.formatMarkdown(assistantMessage);
                            } else if (event.type === 'figure') {
                                figures.push(event.data);
                                // 同时添加到图表标签
                                this.addToFiguresTab(event.data);
                            } else if (event.type === 'download' || event.type === 'complete') {
                                // complete事件包含下载链接
                                const downloadData = event.type === 'complete' ? {
                                    name: event.file_path ? event.file_path.split('/').pop() : '生成的文件',
                                    url: event.download_url
                                } : event.data;
                                downloads.push(downloadData);
                                // 同时添加到下载标签
                                this.addToDownloadsTab(downloadData);
                            }
                        } catch (e) {
                            // 忽略JSON解析错误
                        }
                    }
                }
                
                // 滚动到底部
                this.scrollToBottom();
            }
            
            // 显示图片
            if (figures.length > 0) {
                this.addFiguresToMessage(msgElement, figures);
            }
            
            // 显示下载链接
            if (downloads.length > 0) {
                this.addDownloads(downloads);
            }
            
        } catch (error) {
            if (error.name === 'AbortError') {
                // 用户主动打断，在消息末尾加提示
                const bubble = document.querySelector('.message.assistant:last-child .message-bubble');
                if (bubble && bubble.innerHTML) {
                    bubble.innerHTML += '<br><span style="color:#94a3b8;font-size:0.85em;">⏹ 已停止生成</span>';
                } else if (loadingMsg) {
                    loadingMsg.remove();
                }
            } else {
                console.error('Query error:', error);
                if (loadingMsg && loadingMsg.parentNode) {
                    loadingMsg.querySelector('.message-bubble').textContent = '抱歉，处理您的请求时出错了。';
                }
                this.showToast('查询失败: ' + error.message, 'error');
            }
        } finally {
            this.isProcessing = false;
            this.abortController = null;
            this._showSendBtn();
            this.scrollToBottom();
        }
    }
    
    // 添加消息到聊天区
    addMessage(role, content, isLoading = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.innerHTML = role === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        bubble.innerHTML = isLoading ? '<i class="fas fa-spinner fa-spin"></i> ' + content : this.formatMarkdown(content);
        
        const time = document.createElement('div');
        time.className = 'message-time';
        time.textContent = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
        
        contentDiv.appendChild(bubble);
        contentDiv.appendChild(time);
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(contentDiv);
        
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
        
        return messageDiv;
    }
    
    // 添加图片到消息
    addFiguresToMessage(messageElement, figures) {
        const contentDiv = messageElement.querySelector('.message-content');
        const figuresDiv = document.createElement('div');
        figuresDiv.className = 'message-figures';
        
        figures.forEach(fig => {
            const figItem = document.createElement('div');
            figItem.className = 'figure-item';
            // 处理路径：如果已包含data/，不再添加
            const imgPath = fig.path.startsWith('data/') ? `/${fig.path}` : `/data/${fig.path}`;
            figItem.innerHTML = `<img src="${imgPath}" alt="${fig.caption || 'Figure'}" />`;
            figItem.addEventListener('click', () => this.showImageModal(fig));
            figuresDiv.appendChild(figItem);
        });
        
        contentDiv.insertBefore(figuresDiv, contentDiv.querySelector('.message-time'));
    }
    
    // 添加下载链接
    addDownloads(downloads) {
        downloads.forEach(download => {
            this.addToDownloadsTab(download);
        });
        
        // 切换到下载标签页
        this.switchTab('downloads');
        this.showToast('文件已生成，可在右侧下载', 'success');
    }
    
    // 添加到图表标签
    addToFiguresTab(figure) {
        const figuresTab = document.getElementById('figuresTab');
        
        const item = document.createElement('div');
        item.className = 'figure-item';
        item.style.cssText = 'margin: 8px; padding: 8px; border: 1px solid var(--border); border-radius: 8px; cursor: pointer; transition: all 0.3s;';
        
        // 处理路径：如果已包含data/，不再添加
        const imgPath = figure.path.startsWith('data/') ? `/${figure.path}` : `/data/${figure.path}`;
        
        item.innerHTML = `
            <img src="${imgPath}" alt="${figure.label || 'Figure'}" 
                 style="width: 100%; border-radius: 4px; display: block;">
            <div style="margin-top: 6px; font-size: 0.85em; color: var(--text-secondary); text-align: center;">
                ${figure.label || 'Figure'}
            </div>
        `;
        item.addEventListener('click', () => this.showImageModal(figure));
        item.addEventListener('mouseenter', () => {
            item.style.transform = 'scale(1.02)';
            item.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
        });
        item.addEventListener('mouseleave', () => {
            item.style.transform = 'scale(1)';
            item.style.boxShadow = 'none';
        });
        figuresTab.appendChild(item);
    }
    
    // 添加到下载标签
    addToDownloadsTab(download) {
        const downloadsTab = document.getElementById('downloadsTab');
        const downloadAllContainer = document.getElementById('downloadAllContainer');
        
        // 提取文件名（从URL或path）
        let fileName = download.name;
        if (!fileName || fileName === 'undefined') {
            // 从URL或file_path提取
            const path = download.url || download.file_path || '';
            fileName = path.split('/').pop() || '下载文件';
        }
        
        const item = document.createElement('div');
        item.className = 'download-item';
        item.dataset.url = download.url;  // 保存URL用于全部下载
        item.innerHTML = `
            <div class="download-info">
                <i class="fas fa-file"></i>
                <span title="${fileName}">${fileName}</span>
            </div>
            <a href="${download.url}" class="download-btn" download>
                <i class="fas fa-download"></i>
            </a>
        `;
        downloadsTab.appendChild(item);
        
        // 显示全部下载按钮
        if (downloadAllContainer) {
            downloadAllContainer.style.display = 'block';
        }
    }
    
    // 格式化Markdown
    formatMarkdown(text) {
        // 完整的Markdown渲染
        return text
            // 标题
            .replace(/^### (.*?)$/gm, '<h3 style="font-size: 1.1em; font-weight: 600; margin: 12px 0 8px 0;">$1</h3>')
            .replace(/^## (.*?)$/gm, '<h2 style="font-size: 1.2em; font-weight: 700; margin: 14px 0 10px 0;">$1</h2>')
            .replace(/^# (.*?)$/gm, '<h1 style="font-size: 1.3em; font-weight: 700; margin: 16px 0 12px 0;">$1</h1>')
            // 粗体和斜体
            .replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            // 代码
            .replace(/`([^`]+)`/g, '<code style="background: var(--bg-tertiary); padding: 2px 6px; border-radius: 4px; font-family: monospace;">$1</code>')
            // 列表
            .replace(/^- (.*?)$/gm, '<li style="margin-left: 20px;">$1</li>')
            .replace(/^(\d+)\. (.*?)$/gm, '<li style="margin-left: 20px; list-style-type: decimal;">$2</li>')
            // 换行
            .replace(/\n\n/g, '<br><br>')
            .replace(/\n/g, '<br>');
    }
    
    // 滚动到底部
    scrollToBottom() {
        setTimeout(() => {
            this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
        }, 100);
    }
    
    // 生成文档（PPT或报告）
    async generateDocument(type) {
        if (this.isProcessing) return;
        
        this.isProcessing = true;
        const docName = type === 'ppt' ? 'PPT' : '报告';
        
        // 添加进度消息
        const progressMsg = this.addMessage('assistant', `正在生成${docName}...`, false);
        const contentElement = progressMsg.querySelector('.message-bubble');
        
        try {
            const response = await fetch('/api/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    type: type,
                    style: '学术风格',
                    language: '中文',
                    include_figures: true,
                    max_figures: 10,
                    output_format: 'Word'
                })
            });
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            
            let progressText = '';
            let downloadUrl = '';
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const event = JSON.parse(line.slice(6));
                            
                            if (event.type === 'progress') {
                                // 更新进度
                                progressText += event.content + '<br>';
                                contentElement.innerHTML = progressText;
                                this.scrollToBottom();
                            } else if (event.type === 'complete') {
                                // 生成完成
                                downloadUrl = event.download_url;
                                contentElement.innerHTML = progressText + `
                                    <div style="margin-top: 12px; padding: 12px; background: var(--accent-primary); border-radius: 8px;">
                                        <a href="${downloadUrl}" style="color: white; text-decoration: none; display: flex; align-items: center; gap: 8px;" download>
                                            <i class="fas fa-download"></i>
                                            <span>点击下载${docName}</span>
                                        </a>
                                    </div>
                                `;
                                
                                this.showToast(`${docName}生成成功！`, 'success');
                            } else if (event.type === 'error') {
                                contentElement.innerHTML = `❌ ${event.content}`;
                                this.showToast('生成失败', 'error');
                            }
                        } catch (e) {
                            console.error('解析事件失败:', e);
                        }
                    }
                }
            }
        } catch (error) {
            console.error('生成失败:', error);
            contentElement.innerHTML = `❌ 生成失败: ${error.message}`;
            this.showToast('生成失败', 'error');
        } finally {
            this.isProcessing = false;
        }
    }
    
    // 切换标签页
    switchTab(tabName) {
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tabName);
        });
        
        document.querySelectorAll('.tab-pane').forEach(pane => {
            pane.classList.toggle('active', pane.id === `${tabName}Tab`);
        });
    }
    
    // 全部下载
    downloadAll() {
        const downloadItems = document.querySelectorAll('#downloadsTab .download-item');
        
        if (downloadItems.length === 0) {
            this.showToast('没有可下载的文件', 'warning');
            return;
        }
        
        this.showToast(`开始下载 ${downloadItems.length} 个文件...`, 'info');
        
        // 依次触发下载（浏览器会处理）
        downloadItems.forEach((item, index) => {
            setTimeout(() => {
                const url = item.dataset.url;
                if (url) {
                    const link = document.createElement('a');
                    link.href = url;
                    link.download = '';
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                }
            }, index * 500); // 每个文件间隔500ms，避免浏览器阻止
        });
    }
    
    // 主题切换
    toggleTheme() {
        const body = document.body;
        const isDark = body.classList.contains('theme-dark');
        
        if (isDark) {
            body.classList.remove('theme-dark');
            body.classList.add('theme-light');
            this.themeToggle.innerHTML = '<i class="fas fa-sun"></i>';
            localStorage.setItem('theme', 'light');
        } else {
            body.classList.remove('theme-light');
            body.classList.add('theme-dark');
            this.themeToggle.innerHTML = '<i class="fas fa-moon"></i>';
            localStorage.setItem('theme', 'dark');
        }
    }
    
    // 加载主题
    loadTheme() {
        const savedTheme = localStorage.getItem('theme') || 'dark';
        const body = document.body;
        
        body.classList.remove('theme-dark', 'theme-light');
        body.classList.add(`theme-${savedTheme}`);
        
        this.themeToggle.innerHTML = savedTheme === 'dark' 
            ? '<i class="fas fa-moon"></i>' 
            : '<i class="fas fa-sun"></i>';
    }
    
    // 显示Toast通知
    showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const icon = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle'
        }[type] || 'fa-info-circle';
        
        toast.innerHTML = `
            <i class="fas ${icon}"></i>
            <span>${message}</span>
        `;
        
        this.toastContainer.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
    
    // 显示加载覆盖
    showLoading(text = '处理中...') {
        this.loadingText.textContent = text;
        this.loadingOverlay.style.display = 'flex';
    }
    
    // 隐藏加载覆盖
    hideLoading() {
        this.loadingOverlay.style.display = 'none';
    }
    
    // 检查状态
    async checkStatus() {
        try {
            const response = await fetch('/api/status');
            const data = await response.json();
            
            if (data.loaded) {
                this.enableChat();
                this.welcomeScreen.style.display = 'none';
                this.chatMessages.style.display = 'flex';
            }
        } catch (error) {
            console.error('Status check failed:', error);
        }
    }
    
    // 显示图片模态框
    showImageModal(figure) {
        // TODO: 实现图片查看器
        const imgPath = figure.path.startsWith('data/') ? `/${figure.path}` : `/data/${figure.path}`;
        window.open(imgPath, '_blank');
    }
    
    // 加载示例文档
    async loadExampleDocument() {
        this.showToast('正在加载示例文档...', 'info');
        
        try {
            const response = await fetch('/api/load_example');
            const data = await response.json();
            
            if (data.success) {
                this.currentPDF = data.filename;
                this.showFileInfo(data);
                this.enableChat();
                this.showToast('示例文档加载成功！', 'success');
                
                // 显示所有主图到侧边栏
                if (data.figures && data.figures.length > 0) {
                    data.figures.forEach(figure => {
                        this.addToFiguresTab(figure);
                    });
                }
                
                // 隐藏欢迎界面
                this.welcomeScreen.style.display = 'none';
                this.chatMessages.style.display = 'flex';
            } else {
                this.showToast('示例文档加载失败', 'error');
            }
        } catch (error) {
            console.error('Load example error:', error);
            this.showToast('示例文档加载失败: ' + error.message, 'error');
        }
    }
    
    // 显示演示视频
    showDemoVideo() {
        // 创建视频模态框
        const modal = document.createElement('div');
        modal.className = 'video-modal';
        modal.innerHTML = `
            <div class="video-modal-overlay"></div>
            <div class="video-modal-content">
                <button class="video-modal-close">
                    <i class="fas fa-times"></i>
                </button>
                <div class="video-modal-header">
                    <h2>📺 演示视频</h2>
                    <p>快速了解 Literature Agent 的强大功能</p>
                </div>
                <div class="video-modal-body">
                    <div class="video-container">
                        <video controls autoplay style="width: 100%; border-radius: 8px;">
                            <source src="/static/demo.mp4" type="video/mp4">
                            您的浏览器不支持视频播放。
                        </video>
                    </div>
                    <div class="video-info">
                        <h3>🎯 功能亮点</h3>
                        <ul>
                            <li>📄 <strong>智能PDF解析</strong> - 自动提取文本和图表</li>
                            <li>🖼️ <strong>图表分析</strong> - 支持主图和子图精细分析</li>
                            <li>💬 <strong>智能问答</strong> - 基于LLM的深度理解</li>
                            <li>📊 <strong>一键生成</strong> - PPT和研究报告自动生成</li>
                            <li>🔍 <strong>本地部署</strong> - 支持Ollama，保护隐私</li>
                        </ul>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // 添加动画
        setTimeout(() => {
            modal.classList.add('active');
        }, 10);
        
        // 关闭按钮
        const closeBtn = modal.querySelector('.video-modal-close');
        const overlay = modal.querySelector('.video-modal-overlay');
        
        const closeModal = () => {
            modal.classList.remove('active');
            setTimeout(() => {
                document.body.removeChild(modal);
            }, 300);
        };
        
        closeBtn.addEventListener('click', closeModal);
        overlay.addEventListener('click', closeModal);
        
        // ESC键关闭
        const handleEsc = (e) => {
            if (e.key === 'Escape') {
                closeModal();
                document.removeEventListener('keydown', handleEsc);
            }
        };
        document.addEventListener('keydown', handleEsc);
    }
    
    // 显示项目说明文档
    showProjectDocs() {
        // 创建文档模态框
        const modal = document.createElement('div');
        modal.className = 'video-modal';
        modal.innerHTML = `
            <div class="video-modal-overlay"></div>
            <div class="video-modal-content">
                <button class="video-modal-close">
                    <i class="fas fa-times"></i>
                </button>
                <div class="video-modal-header">
                    <h2>📄 项目说明文档</h2>
                    <p>详细了解 Literature Agent 的功能和使用方法</p>
                </div>
                <div class="video-modal-body" style="padding: 0;">
                    <iframe 
                        src="/static/README.pdf" 
                        style="width: 100%; height: 70vh; border: none; border-radius: 8px;"
                        type="application/pdf">
                        <p>您的浏览器不支持PDF预览。<a href="/static/README.pdf" download>点击下载</a></p>
                    </iframe>
                    <div style="padding: 20px; text-align: center;">
                        <a href="/static/README.pdf" download class="btn-download">
                            <i class="fas fa-download"></i> 下载完整文档
                        </a>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // 添加动画
        setTimeout(() => {
            modal.classList.add('active');
        }, 10);
        
        // 关闭按钮
        const closeBtn = modal.querySelector('.video-modal-close');
        const overlay = modal.querySelector('.video-modal-overlay');
        
        const closeModal = () => {
            modal.classList.remove('active');
            setTimeout(() => {
                document.body.removeChild(modal);
            }, 300);
        };
        
        closeBtn.addEventListener('click', closeModal);
        overlay.addEventListener('click', closeModal);
        
        // ESC键关闭
        const handleEsc = (e) => {
            if (e.key === 'Escape') {
                closeModal();
                document.removeEventListener('keydown', handleEsc);
            }
        };
        document.addEventListener('keydown', handleEsc);
    }
}

// 添加slideOut动画
const style = document.createElement('style');
style.textContent = `
    @keyframes slideOut {
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
    
    .download-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px;
        background: var(--bg-tertiary);
        border-radius: var(--radius-md);
        margin-bottom: 10px;
    }
    
    .download-info {
        display: flex;
        align-items: center;
        gap: 10px;
        flex: 1;
    }
    
    .download-info i {
        color: var(--accent-primary);
        font-size: 18px;
    }
    
    .download-btn {
        width: 36px;
        height: 36px;
        border-radius: var(--radius-sm);
        background: var(--accent-primary);
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        text-decoration: none;
        transition: var(--transition);
    }
    
    .download-btn:hover {
        background: var(--accent-secondary);
        transform: scale(1.1);
    }
`;
document.head.appendChild(style);

// 初始化应用
document.addEventListener('DOMContentLoaded', () => {
    window.app = new LiteratureAgentApp();
});
