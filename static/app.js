class VideoTranscriber {
    constructor() {
        this.currentTaskId = null;
        this.eventSource = null;
        this.apiBase = 'http://localhost:8000/api';
        this.currentLanguage = 'en'; // 默认英文
        this.currentResultInfo = null; // 当前展示的结果详情
        this.historyVisible = false;
        this.historyState = {
            page: 1,
            limit: 20,
            total: 0,
            items: []
        };
        
        // 智能进度模拟相关
        this.smartProgress = {
            enabled: false,
            current: 0,           // 当前显示的进度
            target: 0,            // 目标进度
            lastServerUpdate: 0,  // 最后一次服务器更新的进度
            interval: null,       // 定时器
            estimatedDuration: 0, // 预估总时长（秒）
            startTime: null,      // 任务开始时间
            stage: 'preparing'    // 当前阶段
        };
        
        this.translations = {
            en: {
                title: "AI Video Transcriber",
                subtitle: "Supports automatic transcription and AI summary for YouTube, Tiktok, Bilibili and other platforms",
                video_url: "Video URL",
                video_url_placeholder: "Enter YouTube, Tiktok, Bilibili or other platform video URLs...",
                summary_language: "Summary Language",
                start_transcription: "Start",
                processing_progress: "Processing Progress",
                preparing: "Preparing...",
                transcription_results: "Results",
                download_transcript: "Download Transcript",
                download_translation: "Download Translation",
                download_summary: "Download Summary",
                transcript_text: "Transcript Text",
                translation: "Translation",
                intelligent_summary: "AI Summary",
                footer_text: "Powered by AI, supports multi-platform video transcription",
                processing: "Processing...",
                downloading_video: "Downloading video...",
                parsing_video: "Parsing video info...",
                transcribing_audio: "Transcribing audio...",
                optimizing_transcript: "Optimizing transcript...",
                generating_summary: "Generating summary...",
                completed: "Processing completed!",
                error_invalid_url: "Please enter a valid video URL",
                error_processing_failed: "Processing failed: ",
                error_task_not_found: "Task not found",
                error_task_not_completed: "Task not completed yet",
                error_invalid_file_type: "Invalid file type",
                error_file_not_found: "File not found",
                error_download_failed: "Download failed: ",
                error_no_file_to_download: "No file available for download",
                history_toggle_show: "View History",
                history_toggle_hide: "Hide History",
                history_title: "History",
                history_refresh: "Refresh",
                history_empty: "No history records yet",
                history_loading: "Loading history...",
                history_view_detail: "View Details",
                history_delete: "Delete",
                history_delete_failed: "Failed to delete history: ",
                history_detail_failed: "Failed to load history detail: ",
                history_load_error: "Failed to load history: ",
                history_load_more: "Load More",
                history_finished_at: "Finished At",
                history_language_label: "Language",
                history_has_translation: "With Translation",
                history_no_title: "Untitled Video"
            },
            zh: {
                title: "AI视频转录器",
                subtitle: "支持YouTube、Tiktok、Bilibili等平台的视频自动转录和智能摘要",
                video_url: "视频链接",
                video_url_placeholder: "请输入YouTube、Tiktok、Bilibili等平台的视频链接...",
                summary_language: "摘要语言",
                start_transcription: "开始转录",
                processing_progress: "处理进度",
                preparing: "准备中...",
                transcription_results: "转录结果",
                download_transcript: "下载转录",
                download_translation: "下载翻译",
                download_summary: "下载摘要",
                transcript_text: "转录文本",
                translation: "翻译",
                intelligent_summary: "智能摘要",
                footer_text: "由AI驱动，支持多平台视频转录",
                processing: "处理中...",
                downloading_video: "正在下载视频...",
                parsing_video: "正在解析视频信息...",
                transcribing_audio: "正在转录音频...",
                optimizing_transcript: "正在优化转录文本...",
                generating_summary: "正在生成摘要...",
                completed: "处理完成！",
                error_invalid_url: "请输入有效的视频链接",
                error_processing_failed: "处理失败: ",
                error_task_not_found: "任务不存在",
                error_task_not_completed: "任务尚未完成",
                error_invalid_file_type: "无效的文件类型",
                error_file_not_found: "文件不存在",
                error_download_failed: "下载文件失败: ",
                error_no_file_to_download: "没有可下载的文件",
                history_toggle_show: "查看历史记录",
                history_toggle_hide: "收起历史记录",
                history_title: "历史记录",
                history_refresh: "刷新",
                history_empty: "暂无历史记录",
                history_loading: "正在加载历史记录...",
                history_view_detail: "查看详情",
                history_delete: "删除",
                history_delete_failed: "删除历史记录失败: ",
                history_detail_failed: "获取历史详情失败: ",
                history_load_error: "加载历史记录失败: ",
                history_load_more: "加载更多",
                history_finished_at: "完成时间",
                history_language_label: "语言",
                history_has_translation: "含翻译内容",
                history_no_title: "未命名视频"
            }
        };
        
        this.initializeElements();
        this.bindEvents();
        this.initializeLanguage();
    }
    
    initializeElements() {
        // 表单元素
        this.form = document.getElementById('videoForm');
        this.videoUrlInput = document.getElementById('videoUrl');
        this.summaryLanguageSelect = document.getElementById('summaryLanguage');
        this.submitBtn = document.getElementById('submitBtn');
        
        // 进度元素
        this.progressSection = document.getElementById('progressSection');
        this.progressStatus = document.getElementById('progressStatus');
        this.progressFill = document.getElementById('progressFill');
        this.progressMessage = document.getElementById('progressMessage');
        
        // 错误提示
        this.errorAlert = document.getElementById('errorAlert');
        this.errorMessage = document.getElementById('errorMessage');
        
        // 结果元素
        this.resultsSection = document.getElementById('resultsSection');
        this.scriptContent = document.getElementById('scriptContent');
        this.translationContent = document.getElementById('translationContent');
        this.summaryContent = document.getElementById('summaryContent');
        this.downloadScriptBtn = document.getElementById('downloadScript');
        this.downloadTranslationBtn = document.getElementById('downloadTranslation');
        this.downloadSummaryBtn = document.getElementById('downloadSummary');
        this.translationTabBtn = document.getElementById('translationTabBtn');
        this.resultsVideoTitle = document.getElementById('resultsVideoTitle');

        // 历史记录相关元素
        this.historyToggleBtn = document.getElementById('historyToggleBtn');
        this.historySection = document.getElementById('historySection');
        this.historyList = document.getElementById('historyList');
        this.historyEmpty = document.getElementById('historyEmpty');
        this.historyLoading = document.getElementById('historyLoading');
        this.historyRefreshBtn = document.getElementById('historyRefresh');
        this.historyLoadMoreBtn = document.getElementById('historyLoadMore');
        this.historyError = document.getElementById('historyError');
        
        // 调试：检查元素是否正确初始化
        console.log('[DEBUG] 🔧 初始化检查:', {
            translationTabBtn: !!this.translationTabBtn,
            elementId: this.translationTabBtn ? this.translationTabBtn.id : 'N/A'
        });
        
        // 标签页
        this.tabButtons = document.querySelectorAll('.tab-button');
        this.tabContents = document.querySelectorAll('.tab-content');
        
        // 语言切换按钮
        this.langToggle = document.getElementById('langToggle');
        this.langText = document.getElementById('langText');
    }
    
    bindEvents() {
        // 表单提交
        this.form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.startTranscription();
        });
        
        // 标签页切换
        this.tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                this.switchTab(button.dataset.tab);
            });
        });
        
        // 下载按钮
        if (this.downloadScriptBtn) {
            this.downloadScriptBtn.addEventListener('click', () => {
                this.downloadFile('script');
            });
        }
        
        if (this.downloadTranslationBtn) {
            this.downloadTranslationBtn.addEventListener('click', () => {
                this.downloadFile('translation');
            });
        }
        
        if (this.downloadSummaryBtn) {
            this.downloadSummaryBtn.addEventListener('click', () => {
                this.downloadFile('summary');
            });
        }
        
        // 语言切换按钮
        this.langToggle.addEventListener('click', () => {
            this.toggleLanguage();
        });

        // 历史功能事件
        if (this.historyToggleBtn) {
            this.historyToggleBtn.addEventListener('click', () => {
                this.toggleHistorySection();
            });
        }

        if (this.historyRefreshBtn) {
            this.historyRefreshBtn.addEventListener('click', () => {
                this.loadHistory(1, false);
            });
        }

        if (this.historyLoadMoreBtn) {
            this.historyLoadMoreBtn.addEventListener('click', () => {
                const nextPage = Number(this.historyLoadMoreBtn.dataset.nextPage || (this.historyState.page + 1));
                this.loadHistory(nextPage, true);
            });
        }

        if (this.historyList) {
            this.historyList.addEventListener('click', (event) => {
                this.handleHistoryListClick(event);
            });
        }
    }
    
    initializeLanguage() {
        // 设置默认语言为英文
        this.switchLanguage('en');
    }
    
    toggleLanguage() {
        // 切换语言
        this.currentLanguage = this.currentLanguage === 'en' ? 'zh' : 'en';
        this.switchLanguage(this.currentLanguage);
    }
    
    switchLanguage(lang) {
        this.currentLanguage = lang;
        
        // 更新语言按钮文本 - 显示当前语言
        this.langText.textContent = lang === 'en' ? 'English' : '中文';
        
        // 更新页面文本
        this.updatePageText();
        this.refreshHistoryTexts();
        this.updateHistoryToggleLabel();
        
        // 更新HTML lang属性
        document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
        
        // 更新页面标题
        document.title = this.t('title');
    }
    
    t(key) {
        return this.translations[this.currentLanguage][key] || key;
    }
    
    updatePageText() {
        // 更新所有带有data-i18n属性的元素
        document.querySelectorAll('[data-i18n]').forEach(element => {
            const key = element.getAttribute('data-i18n');
            element.textContent = this.t(key);
        });
        
        // 更新placeholder
        document.querySelectorAll('[data-i18n-placeholder]').forEach(element => {
            const key = element.getAttribute('data-i18n-placeholder');
            element.placeholder = this.t(key);
        });
    }

    updateHistoryToggleLabel() {
        if (!this.historyToggleBtn) {
            return;
        }
        const labelKey = this.historyVisible ? 'history_toggle_hide' : 'history_toggle_show';
        const labelSpan = this.historyToggleBtn.querySelector('span[data-i18n]');
        if (labelSpan) {
            labelSpan.setAttribute('data-i18n', labelKey);
            labelSpan.textContent = this.t(labelKey);
        }
    }
    
    toggleHistorySection() {
        this.historyVisible = !this.historyVisible;
        if (this.historySection) {
            this.historySection.style.display = this.historyVisible ? 'block' : 'none';
        }
        this.updateHistoryToggleLabel();
        if (this.historyVisible && (!this.historyState.items || this.historyState.items.length === 0)) {
            this.loadHistory(1, false);
        }
    }
    
    setHistoryLoading(loading) {
        if (this.historyLoading) {
            this.historyLoading.style.display = loading ? 'block' : 'none';
        }
        if (this.historyRefreshBtn) {
            this.historyRefreshBtn.disabled = loading;
        }
        if (this.historyLoadMoreBtn) {
            this.historyLoadMoreBtn.disabled = loading;
        }
    }
    
    clearHistoryError() {
        if (this.historyError) {
            this.historyError.style.display = 'none';
            this.historyError.textContent = '';
        }
    }
    
    showHistoryError(message) {
        if (this.historyError) {
            this.historyError.textContent = message;
            this.historyError.style.display = 'block';
        } else {
            this.showError(message);
        }
    }
    
    async loadHistory(page = 1, append = false) {
        if (!this.historySection) {
            return;
        }
        
        try {
            this.clearHistoryError();
            this.setHistoryLoading(true);
            
            const response = await fetch(`${this.apiBase}/history?page=${page}&limit=${this.historyState.limit}`);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || response.statusText || 'Request failed');
            }
            
            const data = await response.json();
            const items = Array.isArray(data.items) ? data.items : [];
            const currentPage = data.page || page;
            const limit = data.limit || this.historyState.limit;
            const total = data.total || 0;
            
            this.historyState.page = currentPage;
            this.historyState.limit = limit;
            this.historyState.total = total;
            
            if (append) {
                this.historyState.items = (this.historyState.items || []).concat(items);
                this.renderHistoryList(items, true);
            } else {
                this.historyState.items = items;
                this.renderHistoryList(this.historyState.items, false);
            }
            
            const hasMore = currentPage * limit < total;
            this.updateHistoryLoadMoreButton(hasMore, currentPage + 1);
        } catch (error) {
            console.error('加载历史失败:', error);
            this.showHistoryError(this.t('history_load_error') + (error.message || ''));
        } finally {
            this.setHistoryLoading(false);
            if (this.historyEmpty) {
                const length = (this.historyState.items || []).length;
                this.historyEmpty.style.display = length === 0 ? 'block' : 'none';
            }
        }
    }
    
    renderHistoryList(items, append = false) {
        if (!this.historyList) {
            return;
        }
        
        const listItems = append ? items : (items || []);
        if (!append) {
            this.historyList.innerHTML = '';
        }
        
        listItems.forEach(item => {
            if (!item || !item.task_id) {
                return;
            }
            const card = this.createHistoryItemElement(item);
            this.historyList.appendChild(card);
        });
    }
    
    createHistoryItemElement(item) {
        const card = document.createElement('div');
        card.className = 'history-item';
        const safeTitle = this.escapeHtml(item.video_title || this.t('history_no_title'));
        const finishedTime = this.formatDate(item.finished_at || item.created_at);
        const languageLabel = this.t('history_language_label');
        const languageDisplay = item.summary_language
            ? `${item.detected_language || '-'} -> ${item.summary_language}`
            : (item.detected_language || '-');
        
        card.innerHTML = `
            <div class="history-item-header">
                <div class="history-title" title="${safeTitle}">${safeTitle}</div>
                ${item.has_translation ? `<span class="history-badge">${this.t('history_has_translation')}</span>` : ''}
            </div>
            <div class="history-meta">
                <span><i class="fas fa-calendar-check"></i> ${this.t('history_finished_at')}: ${finishedTime}</span>
                <span><i class="fas fa-language"></i> ${languageLabel}: ${languageDisplay}</span>
            </div>
            <div class="history-actions">
                <button class="btn btn-secondary" data-action="view" data-task="${item.task_id}">
                    <i class="fas fa-eye"></i> ${this.t('history_view_detail')}
                </button>
                <button class="btn btn-secondary" data-action="delete" data-task="${item.task_id}">
                    <i class="fas fa-trash"></i> ${this.t('history_delete')}
                </button>
            </div>
        `;
        
        return card;
    }
    
    formatDate(value) {
        if (!value) {
            return '-';
        }
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
            return value;
        }
        const locale = this.currentLanguage === 'zh' ? 'zh-CN' : 'en-US';
        return date.toLocaleString(locale);
    }
    
    escapeHtml(text) {
        if (text === undefined || text === null) {
            return '';
        }
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }
    
    handleHistoryListClick(event) {
        const viewButton = event.target.closest('[data-action="view"]');
        const deleteButton = event.target.closest('[data-action="delete"]');
        
        if (viewButton) {
            const taskId = viewButton.getAttribute('data-task');
            this.loadHistoryDetail(taskId);
            return;
        }
        
        if (deleteButton) {
            const taskId = deleteButton.getAttribute('data-task');
            this.deleteHistoryItem(taskId);
        }
    }
    
    async loadHistoryDetail(taskId) {
        if (!taskId) {
            return;
        }
        
        try {
            const response = await fetch(`${this.apiBase}/history/${taskId}`);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || response.statusText || 'Request failed');
            }
            
            const data = await response.json();
            this.currentTaskId = taskId;
            this.currentResultInfo = data;
            this.hideError();
            this.showResults(
                data.script,
                data.summary,
                data.video_title,
                data.translation,
                data.detected_language,
                data.summary_language,
                data
            );
            this.switchTab('script');
        } catch (error) {
            console.error('获取历史详情失败:', error);
            this.showHistoryError(this.t('history_detail_failed') + (error.message || ''));
        }
    }
    
    async deleteHistoryItem(taskId) {
        if (!taskId) {
            return;
        }
        
        try {
            const response = await fetch(`${this.apiBase}/history/${taskId}`, {
                method: 'DELETE'
            });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || response.statusText || 'Request failed');
            }
            
            if (this.currentResultInfo && this.currentResultInfo.task_id === taskId) {
                this.currentResultInfo = null;
                this.currentTaskId = null;
                this.hideResults();
            }
            
            await this.loadHistory(1, false);
        } catch (error) {
            console.error('删除历史失败:', error);
            this.showHistoryError(this.t('history_delete_failed') + (error.message || ''));
        }
    }
    
    updateHistoryLoadMoreButton(hasMore, nextPage) {
        if (!this.historyLoadMoreBtn) {
            return;
        }
        if (hasMore) {
            this.historyLoadMoreBtn.style.display = 'inline-flex';
            this.historyLoadMoreBtn.dataset.nextPage = nextPage;
            this.historyLoadMoreBtn.disabled = false;
        } else {
            this.historyLoadMoreBtn.style.display = 'none';
            this.historyLoadMoreBtn.dataset.nextPage = '';
        }
    }
    
    refreshHistoryTexts() {
        if (!this.historyList) {
            return;
        }
        const items = this.historyState.items || [];
        if (items.length === 0) {
            if (this.historyEmpty) {
                this.historyEmpty.textContent = this.t('history_empty');
            }
            return;
        }
        this.renderHistoryList(items, false);
    }
    
    async startTranscription() {
        // 立即禁用按钮，防止重复点击
        if (this.submitBtn.disabled) {
            return; // 如果按钮已禁用，直接返回
        }
        
        const videoUrl = this.videoUrlInput.value.trim();
        const summaryLanguage = this.summaryLanguageSelect.value;
        
        if (!videoUrl) {
            this.showError(this.t('error_invalid_url'));
            return;
        }
        
        this.currentResultInfo = null;
        
        try {
            // 立即禁用按钮和隐藏错误
            this.setLoading(true);
            this.hideError();
            this.hideResults();
            this.showProgress();
            
            // 发送转录请求
            const formData = new FormData();
            formData.append('url', videoUrl);
            formData.append('summary_language', summaryLanguage);
            
            const response = await fetch(`${this.apiBase}/process-video`, {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || '请求失败');
            }
            
            const data = await response.json();
            this.currentTaskId = data.task_id;
            
            console.log('[DEBUG] ✅ 任务已创建，Task ID:', this.currentTaskId);
            
            // 启动智能进度模拟
            this.initializeSmartProgress();
            this.updateProgress(5, this.t('preparing'), true);
            
            // 使用SSE实时接收状态更新
            this.startSSE();
            
        } catch (error) {
            console.error('启动转录失败:', error);
            this.showError(this.t('error_processing_failed') + error.message);
            this.setLoading(false);
            this.hideProgress();
        }
    }
    
    startSSE() {
        if (!this.currentTaskId) return;
        
        console.log('[DEBUG] 🔄 启动SSE连接，Task ID:', this.currentTaskId);
        
        // 创建EventSource连接
        this.eventSource = new EventSource(`${this.apiBase}/task-stream/${this.currentTaskId}`);
        
        this.eventSource.onmessage = (event) => {
            try {
                const task = JSON.parse(event.data);
                
                // 忽略心跳消息
                if (task.type === 'heartbeat') {
                    console.log('[DEBUG] 💓 收到心跳');
                    return;
                }
                
                console.log('[DEBUG] 📊 收到SSE任务状态:', {
                    status: task.status,
                    progress: task.progress,
                    message: task.message
                });
                
                // 更新进度 (标记为服务器推送)
                console.log('[DEBUG] 📈 更新进度条:', `${task.progress}% - ${task.message}`);
                this.updateProgress(task.progress, task.message, true);
                
                if (task.status === 'completed') {
                    console.log('[DEBUG] ✅ 任务完成，显示结果');
                    this.stopSmartProgress(); // 停止智能进度模拟
                    this.stopSSE();
                    this.setLoading(false);
                    this.hideProgress();
                    const resultInfo = Object.assign({ task_id: this.currentTaskId }, task);
                    this.showResults(
                        task.script,
                        task.summary,
                        task.video_title,
                        task.translation,
                        task.detected_language,
                        task.summary_language,
                        resultInfo
                    );
                } else if (task.status === 'error') {
                    console.log('[DEBUG] ❌ 任务失败:', task.error);
                    this.stopSmartProgress(); // 停止智能进度模拟
                    this.stopSSE();
                    this.setLoading(false);
                    this.hideProgress();
                    this.showError(task.error || '处理过程中发生错误');
                }
            } catch (error) {
                console.error('[DEBUG] 解析SSE数据失败:', error);
            }
        };
        
        this.eventSource.onerror = async (error) => {
            console.error('[DEBUG] SSE连接错误:', error);
            this.stopSSE();

            // 兜底：查询任务最终状态，若已完成则直接渲染结果
            try {
                if (this.currentTaskId) {
                    const resp = await fetch(`${this.apiBase}/task-status/${this.currentTaskId}`);
                    if (resp.ok) {
                        const task = await resp.json();
                        if (task && task.status === 'completed') {
                            console.log('[DEBUG] 🔁 SSE断开，但任务已完成，直接渲染结果');
                            this.stopSmartProgress();
                            this.setLoading(false);
                            this.hideProgress();
                            const resultInfo = Object.assign({ task_id: this.currentTaskId }, task);
                            this.showResults(
                                task.script,
                                task.summary,
                                task.video_title,
                                task.translation,
                                task.detected_language,
                                task.summary_language,
                                resultInfo
                            );
                            return;
                        }
                    }
                }
            } catch (e) {
                console.error('[DEBUG] 兜底查询任务状态失败:', e);
            }

            // 未完成则提示并保持页面状态（可由用户重试或自动重连）
            this.showError(this.t('error_processing_failed') + 'SSE连接断开');
            this.setLoading(false);
        };
        
        this.eventSource.onopen = () => {
            console.log('[DEBUG] 🔗 SSE连接已建立');
        };
    }
    
    stopSSE() {
        if (this.eventSource) {
            console.log('[DEBUG] 🔌 关闭SSE连接');
            this.eventSource.close();
            this.eventSource = null;
        }
    }
    

    
    updateProgress(progress, message, fromServer = false) {
        console.log('[DEBUG] 🎯 updateProgress调用:', { progress, message, fromServer });
        
        if (fromServer) {
            // 服务器推送的真实进度
            this.handleServerProgress(progress, message);
        } else {
            // 本地模拟进度
            this.updateProgressDisplay(progress, message);
        }
    }
    
    handleServerProgress(serverProgress, message) {
        console.log('[DEBUG] 📡 处理服务器进度:', serverProgress);
        
        // 停止当前的模拟进度
        this.stopSmartProgress();
        
        // 更新服务器进度记录
        this.smartProgress.lastServerUpdate = serverProgress;
        this.smartProgress.current = serverProgress;
        
        // 立即显示服务器进度
        this.updateProgressDisplay(serverProgress, message);
        
        // 确定当前处理阶段和预估目标
        this.updateProgressStage(serverProgress, message);
        
        // 重新启动智能进度模拟
        this.startSmartProgress();
    }
    
    updateProgressStage(progress, message) {
        // 根据进度和消息确定处理阶段
        // 解析信息通常发生在长时间下载之前或期间，
        // 若此时仅将目标设为25%，进度会在长下载阶段停在25%。
        // 为了持续“假装增长”，将解析阶段的目标直接提升到60%，
        // 覆盖整个下载阶段，直到服务器推送新的更高阶段。
        if (message.includes('解析') || message.includes('parsing')) {
            this.smartProgress.stage = 'parsing';
            this.smartProgress.target = 60;
        } else if (message.includes('下载') || message.includes('downloading')) {
            this.smartProgress.stage = 'downloading';
            this.smartProgress.target = 60;
        } else if (message.includes('转录') || message.includes('transcrib')) {
            this.smartProgress.stage = 'transcribing';
            this.smartProgress.target = 80;
        } else if (message.includes('优化') || message.includes('optimiz')) {
            this.smartProgress.stage = 'optimizing';
            this.smartProgress.target = 90;
        } else if (message.includes('摘要') || message.includes('summary')) {
            this.smartProgress.stage = 'summarizing';
            this.smartProgress.target = 95;
        } else if (message.includes('完成') || message.includes('completed')) {
            this.smartProgress.stage = 'completed';
            this.smartProgress.target = 100;
        }
        
        // 如果当前进度超过预设目标，调整目标
        if (progress >= this.smartProgress.target) {
            this.smartProgress.target = Math.min(progress + 10, 100);
        }
        
        console.log('[DEBUG] 🎯 阶段更新:', {
            stage: this.smartProgress.stage,
            target: this.smartProgress.target,
            current: progress
        });
    }
    
    initializeSmartProgress() {
        // 初始化智能进度状态
        this.smartProgress.enabled = false;
        this.smartProgress.current = 0;
        this.smartProgress.target = 15;
        this.smartProgress.lastServerUpdate = 0;
        this.smartProgress.startTime = Date.now();
        this.smartProgress.stage = 'preparing';
        
        console.log('[DEBUG] 🔧 智能进度模拟已初始化');
    }
    
    startSmartProgress() {
        // 启动智能进度模拟
        if (this.smartProgress.interval) {
            clearInterval(this.smartProgress.interval);
        }
        
        this.smartProgress.enabled = true;
        this.smartProgress.startTime = this.smartProgress.startTime || Date.now();
        
        // 每500ms更新一次模拟进度
        this.smartProgress.interval = setInterval(() => {
            this.simulateProgress();
        }, 500);
        
        console.log('[DEBUG] 🚀 智能进度模拟已启动');
    }
    
    stopSmartProgress() {
        if (this.smartProgress.interval) {
            clearInterval(this.smartProgress.interval);
            this.smartProgress.interval = null;
        }
        this.smartProgress.enabled = false;
        console.log('[DEBUG] ⏹️ 智能进度模拟已停止');
    }
    
    simulateProgress() {
        if (!this.smartProgress.enabled) return;
        
        const current = this.smartProgress.current;
        const target = this.smartProgress.target;
        
        // 如果已经达到目标，暂停模拟
        if (current >= target) return;
        
        // 计算进度增量（基于阶段的不同速度）
        let increment = this.calculateProgressIncrement();
        
        // 确保不超过目标进度
        const newProgress = Math.min(current + increment, target);
        
        if (newProgress > current) {
            this.smartProgress.current = newProgress;
            this.updateProgressDisplay(newProgress, this.getCurrentStageMessage());
        }
    }
    
    calculateProgressIncrement() {
        const elapsedTime = (Date.now() - this.smartProgress.startTime) / 1000; // 秒
        
        // 基于不同阶段的预估速度
        const stageConfig = {
            'parsing': { speed: 0.3, maxTime: 30 },      // 解析阶段：30秒内到25%
            'downloading': { speed: 0.2, maxTime: 120 }, // 下载阶段：2分钟内到60%
            'transcribing': { speed: 0.15, maxTime: 180 }, // 转录阶段：3分钟内到80%
            'optimizing': { speed: 0.25, maxTime: 60 },  // 优化阶段：1分钟内到90%
            'summarizing': { speed: 0.3, maxTime: 30 }   // 摘要阶段：30秒内到95%
        };
        
        const config = stageConfig[this.smartProgress.stage] || { speed: 0.2, maxTime: 60 };
        
        // 基础增量：每500ms增加的百分比
        let baseIncrement = config.speed;
        
        // 时间因子：如果时间过长，加快进度
        if (elapsedTime > config.maxTime) {
            baseIncrement *= 1.5;
        }
        
        // 距离因子：距离目标越近，速度越慢
        const remaining = this.smartProgress.target - this.smartProgress.current;
        if (remaining < 5) {
            baseIncrement *= 0.3; // 接近目标时放慢
        }
        
        return baseIncrement;
    }
    
    getCurrentStageMessage() {
        const stageMessages = {
            'parsing': this.t('parsing_video'),
            'downloading': this.t('downloading_video'),
            'transcribing': this.t('transcribing_audio'),
            'optimizing': this.t('optimizing_transcript'),
            'summarizing': this.t('generating_summary'),
            'completed': this.t('completed')
        };
        
        return stageMessages[this.smartProgress.stage] || this.t('processing');
    }
    
    updateProgressDisplay(progress, message) {
        // 实际更新UI显示
        const roundedProgress = Math.round(progress * 10) / 10; // 保留1位小数
        this.progressStatus.textContent = `${roundedProgress}%`;
        this.progressFill.style.width = `${roundedProgress}%`;
        console.log('[DEBUG] 📏 进度条已更新:', this.progressFill.style.width);
        
        // 翻译常见的进度消息
        let translatedMessage = message;
        if (message.includes('下载视频') || message.includes('downloading') || message.includes('Downloading')) {
            translatedMessage = this.t('downloading_video');
        } else if (message.includes('解析视频') || message.includes('parsing') || message.includes('Parsing')) {
            translatedMessage = this.t('parsing_video');
        } else if (message.includes('转录') || message.includes('transcrib') || message.includes('Transcrib')) {
            translatedMessage = this.t('transcribing_audio');
        } else if (message.includes('优化转录') || message.includes('optimizing') || message.includes('Optimizing')) {
            translatedMessage = this.t('optimizing_transcript');
        } else if (message.includes('摘要') || message.includes('summary') || message.includes('Summary')) {
            translatedMessage = this.t('generating_summary');
        } else if (message.includes('完成') || message.includes('complet') || message.includes('Complet')) {
            translatedMessage = this.t('completed');
        } else if (message.includes('准备') || message.includes('prepar') || message.includes('Prepar')) {
            translatedMessage = this.t('preparing');
        }
        
        this.progressMessage.textContent = translatedMessage;
    }
    
    showProgress() {
        this.progressSection.style.display = 'block';
    }
    
    hideProgress() {
        this.progressSection.style.display = 'none';
    }
    
    showResults(script, summary, videoTitle = null, translation = null, detectedLanguage = null, summaryLanguage = null, resultInfo = null) {

        if (resultInfo) {
            this.currentResultInfo = resultInfo;
            if (resultInfo.task_id) {
                this.currentTaskId = resultInfo.task_id;
            }
        }

        if (this.resultsVideoTitle) {
            if (videoTitle) {
                this.resultsVideoTitle.textContent = videoTitle;
                this.resultsVideoTitle.style.display = 'block';
            } else {
                this.resultsVideoTitle.textContent = this.t('history_no_title');
                this.resultsVideoTitle.style.display = 'block';
            }
        }

        // 调试日志：检查翻译相关参数
        console.log('[DEBUG] 🔍 showResults参数:', {
            hasTranslation: !!translation,
            translationLength: translation ? translation.length : 0,
            detectedLanguage,
            summaryLanguage,
            languagesDifferent: detectedLanguage !== summaryLanguage
        });

        // 渲染markdown内容，确保参数不为null
        const safeScript = script || '';
        const safeSummary = summary || '';
        const safeTranslation = translation || '';
        
        this.scriptContent.innerHTML = safeScript ? marked.parse(safeScript) : '';
        this.summaryContent.innerHTML = safeSummary ? marked.parse(safeSummary) : '';
        
        // 处理翻译
        const shouldShowTranslation = Boolean(safeTranslation);
        
        console.log('[DEBUG] 🌐 翻译显示判断:', {
            safeTranslation: !!safeTranslation,
            detectedLanguage: detectedLanguage,
            summaryLanguage: summaryLanguage,
            languagesDifferent: detectedLanguage !== summaryLanguage,
            shouldShowTranslation: shouldShowTranslation,
            translationTabBtn: !!this.translationTabBtn,
            downloadTranslationBtn: !!this.downloadTranslationBtn
        });
        
        // 调试：检查DOM元素（多种方式）
        const debugBtn1 = document.getElementById('translationTabBtn');
        const debugBtn2 = document.querySelector('#translationTabBtn');
        const debugBtn3 = document.querySelector('[data-tab="translation"]');
        
        console.log('[DEBUG] 🔍 DOM检查:', {
            getElementById: !!debugBtn1,
            querySelector_id: !!debugBtn2,
            querySelector_attr: !!debugBtn3,
            currentDisplay: debugBtn1 ? debugBtn1.style.display : 'N/A',
            computedStyle: debugBtn1 ? window.getComputedStyle(debugBtn1).display : 'N/A'
        });
        
        // 使用备用方法获取元素
        const actualBtn = debugBtn1 || debugBtn2 || debugBtn3;
        if (actualBtn && !this.translationTabBtn) {
            this.translationTabBtn = actualBtn;
            console.log('[DEBUG] 🔄 使用备用方法找到翻译按钮');
        }
        
        if (shouldShowTranslation) {
            console.log('[DEBUG] ✅ 显示翻译标签页');
            // 显示翻译标签页和按钮
            if (this.translationTabBtn) {
                this.translationTabBtn.style.display = 'inline-block';
                this.translationTabBtn.style.visibility = 'visible';
                console.log('[DEBUG] 🎯 翻译按钮样式已设置:', this.translationTabBtn.style.display);
            }
            if (this.downloadTranslationBtn) {
                this.downloadTranslationBtn.style.display = 'inline-flex';
            }
            if (this.translationContent) {
                this.translationContent.innerHTML = marked.parse(safeTranslation);
            }
        } else {
            console.log('[DEBUG] ❌ 隐藏翻译标签页');
            // 隐藏翻译标签页和按钮
            if (this.translationTabBtn) {
                this.translationTabBtn.style.display = 'none';
            }
            if (this.downloadTranslationBtn) {
                this.downloadTranslationBtn.style.display = 'none';
            }
            if (this.translationContent) {
                this.translationContent.innerHTML = '';
            }
        }
        
        // 显示结果区域
        this.resultsSection.style.display = 'block';
        
        // 滚动到结果区域
        this.resultsSection.scrollIntoView({ behavior: 'smooth' });
        
        // 高亮代码
        if (window.Prism) {
            Prism.highlightAll();
        }
    }
    
    hideResults() {
        this.resultsSection.style.display = 'none';
        if (this.resultsVideoTitle) {
            this.resultsVideoTitle.textContent = '';
            this.resultsVideoTitle.style.display = 'none';
        }
    }
    
    switchTab(tabName) {
        // 移除所有活动状态
        this.tabButtons.forEach(btn => btn.classList.remove('active'));
        this.tabContents.forEach(content => content.classList.remove('active'));
        
        // 激活选中的标签页
        const activeButton = document.querySelector(`[data-tab="${tabName}"]`);
        const activeContent = document.getElementById(`${tabName}Tab`);
        
        if (activeButton && activeContent) {
            activeButton.classList.add('active');
            activeContent.classList.add('active');
        }
    }
    
    extractFilename(pathValue) {
        if (!pathValue) {
            return null;
        }
        const normalized = String(pathValue);
        if (normalized.includes('/')) {
            return normalized.split('/').pop();
        }
        if (normalized.includes('\\')) {
            return normalized.split('\\').pop();
        }
        return normalized;
    }

    triggerDownload(filename) {
        const encodedFilename = encodeURIComponent(filename);
        const link = document.createElement('a');
        link.href = `${this.apiBase}/download/${encodedFilename}`;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    async ensureCurrentResultInfo() {
        if (this.currentResultInfo) {
            return this.currentResultInfo;
        }
        if (!this.currentTaskId) {
            return null;
        }
        try {
            const taskResp = await fetch(`${this.apiBase}/task-status/${this.currentTaskId}`);
            if (taskResp.ok) {
                const taskData = await taskResp.json();
                taskData.task_id = this.currentTaskId;
                this.currentResultInfo = taskData;
                return taskData;
            }
        } catch (error) {
            console.error('获取任务状态失败:', error);
        }
        try {
            const historyResp = await fetch(`${this.apiBase}/history/${this.currentTaskId}`);
            if (historyResp.ok) {
                const historyData = await historyResp.json();
                this.currentResultInfo = historyData;
                return historyData;
            }
        } catch (error) {
            console.error('获取历史详情失败:', error);
        }
        return null;
    }

    async downloadFile(fileType) {
        const resultInfo = await this.ensureCurrentResultInfo();
        if (!resultInfo) {
            this.showError(this.t('error_no_file_to_download'));
            return;
        }

        this.currentResultInfo = resultInfo;
        let filename = null;

        try {
            switch (fileType) {
                case 'script':
                    filename = resultInfo.script_filename || this.extractFilename(resultInfo.script_path);
                    break;
                case 'summary':
                    filename = resultInfo.summary_filename || this.extractFilename(resultInfo.summary_path);
                    break;
                case 'translation':
                    filename = resultInfo.translation_filename || this.extractFilename(resultInfo.translation_path);
                    break;
                default:
                    throw new Error('未知的文件类型');
            }

            if (!filename) {
                this.showError(this.t('error_no_file_to_download'));
                return;
            }

            this.triggerDownload(filename);
        } catch (error) {
            console.error('下载文件失败:', error);
            this.showError(this.t('error_download_failed') + error.message);
        }
    }
    
    setLoading(loading) {
        this.submitBtn.disabled = loading;
        
        if (loading) {
            this.submitBtn.innerHTML = `<div class="loading-spinner"></div> ${this.t('processing')}`;
        } else {
            this.submitBtn.innerHTML = `<i class="fas fa-play"></i> ${this.t('start_transcription')}`;
        }
    }
    
    showError(message) {
        this.errorMessage.textContent = message;
        this.errorAlert.style.display = 'block';
        
        // 滚动到错误提示
        this.errorAlert.scrollIntoView({ behavior: 'smooth' });
        
        // 5秒后自动隐藏错误提示
        setTimeout(() => {
            this.hideError();
        }, 5000);
    }
    
    hideError() {
        this.errorAlert.style.display = 'none';
    }
}

// 页面加载完成后初始化应用
document.addEventListener('DOMContentLoaded', () => {
    window.transcriber = new VideoTranscriber();
    
    // 添加一些示例链接提示
    const urlInput = document.getElementById('videoUrl');
    urlInput.addEventListener('focus', () => {
        if (!urlInput.value) {
            urlInput.placeholder = '例如: https://www.youtube.com/watch?v=... 或 https://www.bilibili.com/video/...';
        }
    });
    
    urlInput.addEventListener('blur', () => {
        if (!urlInput.value) {
            urlInput.placeholder = '请输入YouTube、Bilibili等平台的视频链接...';
        }
    });
});

// 处理页面刷新时的清理工作
window.addEventListener('beforeunload', () => {
    if (window.transcriber && window.transcriber.eventSource) {
        window.transcriber.stopSSE();
    }
});
