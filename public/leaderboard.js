// ==================== 排行榜组件 ====================
// 在 #readme-button 旁边注入一个带动画的排行榜 SVG 图标按钮，
// 点击后弹出排行榜模态框，支持"今日排行"和"历史排行"tab 切换。

(function () {
    'use strict';

    let leaderboardInjected = false;
    let panelOpen = false;
    let currentTab = 'today'; // 默认展示今日排行

    console.log('[Leaderboard] 排行榜模块已加载');

    // ==================== 加载 CSS 样式表 ====================
    function loadLeaderboardCSS() {
        if (document.getElementById('leaderboard-css')) return;
        const link = document.createElement('link');
        link.id = 'leaderboard-css';
        link.rel = 'stylesheet';
        link.href = '/public/leaderboard.css';
        document.head.appendChild(link);
    }

    // ==================== SVG 图标定义 ====================

    // 排行榜入口图标（奖杯 + 闪烁效果）
    const trophySVG = `<svg class="lb-icon-svg" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <defs>
            <linearGradient id="trophy-grad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#fbbf24"/>
                <stop offset="50%" style="stop-color:#f59e0b"/>
                <stop offset="100%" style="stop-color:#9242eb"/>
            </linearGradient>
        </defs>
        <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6" stroke="url(#trophy-grad)"/>
        <path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18" stroke="url(#trophy-grad)"/>
        <path d="M4 22h16" stroke="#9242eb"/>
        <path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 19.24 7 20h10c0-.76-.85-1.25-2.03-1.79C14.47 17.98 14 17.55 14 17v-2.34" stroke="url(#trophy-grad)"/>
        <path d="M18 2H6v7a6 6 0 0 0 12 0V2Z" stroke="url(#trophy-grad)" fill="rgba(146, 66, 235, 0.08)"/>
    </svg>`;

    // 面板头部图标
    const headerIconSVG = `<svg class="lb-header-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/>
        <path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/>
        <path d="M4 22h16"/>
        <path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 19.24 7 20h10c0-.76-.85-1.25-2.03-1.79C14.47 17.98 14 17.55 14 17v-2.34"/>
        <path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/>
    </svg>`;

    // 刷新图标
    const refreshIconSVG = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="23 4 23 10 17 10"/>
        <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
    </svg>`;

    // 关闭图标
    const closeIconSVG = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="18" y1="6" x2="6" y2="18"/>
        <line x1="6" y1="6" x2="18" y2="18"/>
    </svg>`;

    // 空状态图标
    const emptyIconSVG = `<svg class="lb-empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/>
        <path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/>
        <path d="M4 22h16"/>
        <path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 19.24 7 20h10c0-.76-.85-1.25-2.03-1.79C14.47 17.98 14 17.55 14 17v-2.34"/>
        <path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/>
    </svg>`;

    // Tab 图标
    const tabTodayIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`;
    const tabAllIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20V10"/><path d="M18 20V4"/><path d="M6 20v-4"/></svg>`;

    // ==================== 注入排行榜按钮 ====================
    function injectLeaderboardButton() {
        if (leaderboardInjected) return;

        const readmeBtn = document.getElementById('readme-button');
        if (!readmeBtn) return;

        if (document.getElementById('leaderboard-button')) {
            leaderboardInjected = true;
            return;
        }

        const lbBtn = document.createElement('button');
        lbBtn.id = 'leaderboard-button';
        lbBtn.title = '排行榜';
        lbBtn.setAttribute('aria-label', '打开排行榜');
        lbBtn.innerHTML = trophySVG;

        lbBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            openLeaderboardPanel();
        });

        readmeBtn.parentNode.insertBefore(lbBtn, readmeBtn.nextSibling);

        leaderboardInjected = true;
        console.log('[Leaderboard] 排行榜按钮已注入到 #readme-button 旁边');
    }

    // ==================== 获取当前用户名 ====================
    function getCurrentUsername() {
        const userNavBtn = document.getElementById('user-nav-button');
        if (userNavBtn) {
            const spanText = userNavBtn.querySelector('span');
            if (spanText && spanText.textContent.trim()) {
                return spanText.textContent.trim();
            }
        }
        return null;
    }

    // ==================== 打开排行榜 ====================
    async function openLeaderboardPanel() {
        if (panelOpen) return;

        // 创建遮罩层
        const overlay = document.createElement('div');
        overlay.id = 'lb-overlay';
        overlay.className = 'lb-overlay';
        overlay.addEventListener('click', closeLeaderboardPanel);

        // 创建面板
        const panel = document.createElement('div');
        panel.id = 'lb-panel';
        panel.className = 'lb-panel';

        // 头部
        const header = document.createElement('div');
        header.className = 'lb-header';
        header.innerHTML = `
            <div class="lb-header-left">
                ${headerIconSVG}
                <span class="lb-header-title">排行榜</span>
                <span class="lb-header-subtitle">每日一练</span>
            </div>
            <div class="lb-header-actions">
                <button class="lb-btn-icon lb-btn-refresh" title="刷新排行榜">${refreshIconSVG}</button>
                <button class="lb-btn-icon lb-btn-close" title="关闭 (ESC)">${closeIconSVG}</button>
            </div>
        `;

        // Tab 切换栏
        const tabs = document.createElement('div');
        tabs.className = 'lb-tabs';
        tabs.innerHTML = `
            <button class="lb-tab-btn ${currentTab === 'today' ? 'active' : ''}" data-tab="today">
                <span class="lb-tab-icon">${tabTodayIcon}</span>
                今日排行
            </button>
            <button class="lb-tab-btn ${currentTab === 'all' ? 'active' : ''}" data-tab="all">
                <span class="lb-tab-icon">${tabAllIcon}</span>
                历史排行
            </button>
        `;

        // Tab 点击事件
        tabs.querySelectorAll('.lb-tab-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                const tab = this.getAttribute('data-tab');
                if (tab === currentTab) return;
                currentTab = tab;

                // 更新 tab active 状态
                tabs.querySelectorAll('.lb-tab-btn').forEach(function (b) { b.classList.remove('active'); });
                this.classList.add('active');

                // 重新加载数据
                loadLeaderboardData();
            });
        });

        // 内容区（初始为加载状态）
        const content = document.createElement('div');
        content.id = 'lb-content';
        content.innerHTML = `
            <div class="lb-loading">
                <div class="lb-spinner"></div>
                <span class="lb-loading-text">加载排行榜...</span>
            </div>
        `;

        panel.appendChild(header);
        panel.appendChild(tabs);
        panel.appendChild(content);

        document.body.appendChild(overlay);
        document.body.appendChild(panel);

        // 绑定按钮事件
        header.querySelector('.lb-btn-close').addEventListener('click', closeLeaderboardPanel);
        header.querySelector('.lb-btn-refresh').addEventListener('click', function () {
            loadLeaderboardData();
        });

        // 动画展开
        requestAnimationFrame(function () {
            overlay.classList.add('active');
            panel.classList.add('active');
        });

        panelOpen = true;
        document.addEventListener('keydown', handleLbEscKey);

        // 加载数据
        await loadLeaderboardData();
    }

    // ==================== 关闭排行榜 ====================
    function closeLeaderboardPanel() {
        const overlay = document.getElementById('lb-overlay');
        const panel = document.getElementById('lb-panel');

        if (overlay) overlay.classList.remove('active');
        if (panel) panel.classList.remove('active');

        setTimeout(function () {
            if (overlay) overlay.remove();
            if (panel) panel.remove();
        }, 300);

        panelOpen = false;
        document.removeEventListener('keydown', handleLbEscKey);
    }

    function handleLbEscKey(e) {
        if (e.key === 'Escape') closeLeaderboardPanel();
    }

    // ==================== 加载排行榜数据 ====================
    async function loadLeaderboardData() {
        const content = document.getElementById('lb-content');
        if (!content) return;

        // 显示加载状态
        content.innerHTML = `
            <div class="lb-loading">
                <div class="lb-spinner"></div>
                <span class="lb-loading-text">加载排行榜...</span>
            </div>
        `;

        try {
            const username = getCurrentUsername();
            const period = currentTab === 'today' ? 'today' : 'all';
            let url = `/v1/practice/leaderboard?limit=50&period=${period}`;
            if (username) {
                url += '&username=' + encodeURIComponent(username);
            }

            const response = await fetch(url, {
                credentials: 'same-origin',
                headers: { 'Accept': 'application/json' }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const result = await response.json();

            if (result.code !== 200) {
                throw new Error(result.msg || '查询失败');
            }

            renderLeaderboard(content, result.data, username);

        } catch (e) {
            console.error('[Leaderboard] 加载失败:', e);
            content.innerHTML = `
                <div class="lb-empty">
                    ${emptyIconSVG}
                    <span class="lb-empty-title">加载失败</span>
                    <span class="lb-empty-desc">${e.message || '网络异常，请稍后重试'}</span>
                </div>
            `;
        }
    }

    // ==================== 渲染排行榜 ====================
    function renderLeaderboard(container, data, currentUsername) {
        const { leaderboard, total_users, my_rank } = data;
        const isToday = currentTab === 'today';

        let html = '<div class="lb-tab-content">';

        // 我的排名卡片
        if (my_rank) {
            const scoreLabel = isToday ? '今日' : '累计';
            html += `
                <div class="lb-my-rank">
                    <div class="lb-my-rank-left">
                        <div class="lb-my-rank-badge">${my_rank.rank}</div>
                        <div class="lb-my-rank-info">
                            <span class="lb-my-rank-label">我的排名</span>
                            <span class="lb-my-rank-value">${scoreLabel} ${my_rank.total_score} 分 / ${my_rank.practice_count} 次练习</span>
                        </div>
                    </div>
                    <div class="lb-my-rank-stats">
                        <span class="lb-my-rank-beat">${my_rank.beat_percentage}</span>
                        <span class="lb-my-rank-beat-label">击败用户</span>
                    </div>
                </div>
            `;
        }

        // 空状态
        if (!leaderboard || leaderboard.length === 0) {
            const emptyDesc = isToday
                ? '今日还没有人参与练习，快来争做第一名吧！'
                : '完成每日一练后，你的成绩将出现在这里';
            html += `
                <div class="lb-empty">
                    ${emptyIconSVG}
                    <span class="lb-empty-title">暂无排名数据</span>
                    <span class="lb-empty-desc">${emptyDesc}</span>
                </div>
            `;
        } else {
            // 表头
            const scoreHeader = isToday ? '今日总分' : '累计总分';
            html += `
                <div class="lb-table-header">
                    <span style="text-align:center">#</span>
                    <span>用户</span>
                    <span style="text-align:right">${scoreHeader}</span>
                    <span style="text-align:right">练习次数</span>
                </div>
            `;

            // 列表
            html += '<div class="lb-list">';
            leaderboard.forEach(function (item, idx) {
                const isMe = currentUsername && item.username === currentUsername;
                const initial = item.username.charAt(0).toUpperCase();
                const delay = Math.min(idx * 40, 400); // 行入场延迟

                html += `
                    <div class="lb-row${isMe ? ' lb-row-me' : ''}" data-rank="${item.rank}" style="animation-delay: ${delay}ms">
                        <span class="lb-rank">${item.rank}</span>
                        <div class="lb-user">
                            <div class="lb-avatar">${initial}</div>
                            <span class="lb-username">${escapeHtml(item.username)}${isMe ? ' <span class="lb-me-tag">(我)</span>' : ''}</span>
                        </div>
                        <span class="lb-score">${item.total_score.toLocaleString()}</span>
                        <span class="lb-count">${item.practice_count} 次</span>
                    </div>
                `;
            });
            html += '</div>';
        }

        // 底部信息
        const footerLabel = isToday ? '今日参与' : '共';
        html += `
            <div class="lb-footer">
                <span class="lb-footer-text">${footerLabel} <span class="lb-footer-count">${total_users}</span> 位用户参与排名</span>
            </div>
        `;

        html += '</div>'; // .lb-tab-content
        container.innerHTML = html;
    }

    // ==================== 辅助函数 ====================

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // ==================== DOM 监听：自动注入按钮 ====================
    loadLeaderboardCSS();

    const lbObserver = new MutationObserver(function () {
        if (!leaderboardInjected) {
            const readmeBtn = document.getElementById('readme-button');
            if (readmeBtn) {
                injectLeaderboardButton();
            }
        }
    });

    lbObserver.observe(document.body, {
        childList: true,
        subtree: true
    });

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            setTimeout(injectLeaderboardButton, 500);
        });
    } else {
        setTimeout(injectLeaderboardButton, 500);
    }

    // 兜底：定期检查
    setInterval(function () {
        if (!leaderboardInjected || !document.getElementById('leaderboard-button')) {
            leaderboardInjected = false;
            injectLeaderboardButton();
        }
    }, 3000);

})();
