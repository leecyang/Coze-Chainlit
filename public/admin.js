/**
 * LingXi Admin Panel — Enterprise-grade Management Console
 * --------------------------------------------------------
 * 完全基于真实后端 API，不含任何假数据或占位内容。
 */

const AdminPanel = {
    currentPage: 'dashboard',
    activityChart: null,
    pendingConfirmCallback: null,

    /* ========================================================
       INITIALISATION
       ======================================================== */
    init() {
        this.checkAuth();
        this.bindNavigation();
        this.bindSidebar();
        this.bindMobile();
        this.bindKeyboard();
        this.bindThemeToggle();
        this.loadThemePreference();
        this.startClock();
        this.loadDashboard();
    },

    /* ---- Auth ---- */
    async checkAuth() {
        try {
            const res = await fetch('/api/admin/auth/check');
            const data = await res.json();
            if (!data.is_admin) {
                window.location.href = '/';
                return;
            }
            const el = document.getElementById('adminUsername');
            if (el && data.username) el.textContent = data.username;
        } catch {
            // Silently continue — the page itself is already gated by backend
        }
    },

    /* ---- Navigation ---- */
    bindNavigation() {
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', e => {
                e.preventDefault();
                this.navigateTo(item.dataset.page);
            });
        });
    },

    navigateTo(page) {
        if (!page) return;
        this.currentPage = page;

        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.toggle('active', item.dataset.page === page);
        });

        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
        const target = document.getElementById(`${page}-page`);
        if (target) target.classList.add('active');

        const titles = {
            dashboard: '仪表盘',
            users: '用户管理',
            leaderboard: '排行榜管理',
            config: '系统配置',
            conversations: '对话管理'
        };
        document.getElementById('pageTitle').textContent = titles[page] || page;

        // Close mobile sidebar
        document.getElementById('sidebar').classList.remove('mobile-open');
        document.getElementById('mobileOverlay').classList.remove('active');

        switch (page) {
            case 'dashboard': this.loadDashboard(); break;
            case 'users': this.loadUsers(); break;
            case 'leaderboard': this.loadLeaderboard(); break;
            case 'config': this.loadConfig(); break;
            case 'conversations': this.loadConversations(); break;
        }
    },

    /* ---- Sidebar ---- */
    bindSidebar() {
        const toggle = document.getElementById('sidebarToggle');
        if (toggle) {
            toggle.addEventListener('click', () => {
                document.getElementById('sidebar').classList.toggle('collapsed');
            });
        }
    },

    /* ---- Mobile ---- */
    bindMobile() {
        const menuBtn = document.getElementById('mobileMenuBtn');
        const overlay = document.getElementById('mobileOverlay');

        if (menuBtn) {
            menuBtn.addEventListener('click', () => {
                document.getElementById('sidebar').classList.add('mobile-open');
                overlay.classList.add('active');
            });
        }
        if (overlay) {
            overlay.addEventListener('click', () => {
                document.getElementById('sidebar').classList.remove('mobile-open');
                overlay.classList.remove('active');
            });
        }
    },

    /* ---- Keyboard ---- */
    bindKeyboard() {
        document.addEventListener('keydown', e => {
            if (e.key === 'Escape') {
                document.querySelectorAll('.modal.active').forEach(m => {
                    this.closeModal(m.id);
                });
            }
        });
    },

    /* ---- Clock ---- */
    startClock() {
        const tick = () => {
            const now = new Date();
            const el = document.getElementById('currentTime');
            if (el) {
                el.textContent = now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
            }
        };
        tick();
        setInterval(tick, 30000);
    },

    /* ---- Theme Toggle ---- */
    bindThemeToggle() {
        const toggle = document.getElementById('themeToggle');
        if (toggle) {
            toggle.addEventListener('click', () => {
                this.toggleTheme();
            });
        }
    },

    loadThemePreference() {
        const savedTheme = localStorage.getItem('admin-theme');
        if (savedTheme) {
            document.body.className = savedTheme;
        }
    },

    toggleTheme() {
        const body = document.body;
        const currentTheme = body.classList.contains('light-theme') ? 'light-theme' : 'dark-theme';
        const newTheme = currentTheme === 'light-theme' ? 'dark-theme' : 'light-theme';

        body.className = newTheme;
        localStorage.setItem('admin-theme', newTheme);

        // Re-render charts with new theme colors
        if (this.currentPage === 'dashboard') {
            this.renderEngagementCharts(this.cachedEngagementData || {});
        }
    },

    /* ========================================================
       DASHBOARD
       ======================================================== */
    async loadDashboard() {
        try {
            const res = await fetch('/api/admin/stats');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            document.getElementById('totalUsers').textContent = data.total_users ?? 0;
            document.getElementById('activeUsers').textContent = data.active_users ?? 0;
            document.getElementById('totalConversations').textContent = data.total_conversations ?? 0;

            // Token & system status
            if (data.token_health) {
                this.updateSystemStatus(data.token_health);
            }

            // Recent activity
            this.renderRecentActivity(data.recent_activity || []);

            // Persona usage stats
            this.renderPersonaStats(data.persona_stats || [], data.persona_users_data || {});

            // Extra new stats
            this.renderExtraStats(data);

            // Engagement charts (isolated error handling — chart errors should not
            // affect stats display or system status indicator)
            try {
                this.renderEngagementCharts(data);
            } catch (chartErr) {
                console.warn('[Dashboard] Chart rendering failed:', chartErr.message);
            }
        } catch (err) {
            console.error('[Dashboard] API load failed:', err);
            this.updateTopBarStatus('offline', '连接异常');
        }
    },

    updateSystemStatus(health) {
        const jwtEl = document.getElementById('jwtStatus');
        const serviceEl = document.getElementById('serviceTokenStatus');
        const oauthEl = document.getElementById('oauthStatus');
        const botEl = document.getElementById('botStatus');

        // Service Identity Token
        if (health.service_identity && health.service_identity.valid) {
            if (serviceEl) {
                serviceEl.textContent = '有效';
                serviceEl.className = 'status-badge success';
            }
            if (jwtEl) {
                jwtEl.textContent = '正常';
                jwtEl.className = 'status-badge success';
            }
            document.getElementById('tokenStatus').textContent = '正常';
            this.updateTopBarStatus('online', '运行中');
        } else if (health.service_identity && health.service_identity.available) {
            if (serviceEl) {
                serviceEl.textContent = '已过期';
                serviceEl.className = 'status-badge warning';
            }
            if (jwtEl) {
                jwtEl.textContent = '需更新';
                jwtEl.className = 'status-badge warning';
            }
            document.getElementById('tokenStatus').textContent = '过期';
            this.updateTopBarStatus('warning', '需注意');
        } else {
            if (serviceEl) {
                serviceEl.textContent = '未配置';
                serviceEl.className = 'status-badge error';
            }
            if (jwtEl) {
                jwtEl.textContent = '未配置';
                jwtEl.className = 'status-badge error';
            }
            document.getElementById('tokenStatus').textContent = '异常';
            this.updateTopBarStatus('warning', '需配置');
        }

        // OAuth
        if (health.oauth && health.oauth.available) {
            if (oauthEl) {
                oauthEl.textContent = `${health.oauth.count} 个授权`;
                oauthEl.className = 'status-badge success';
            }
        } else {
            if (oauthEl) {
                oauthEl.textContent = '无授权';
                oauthEl.className = 'status-badge';
            }
        }

        // Bot — infer from recommendation
        if (botEl) {
            if (health.recommendation && health.recommendation.includes('✅')) {
                botEl.textContent = '已就绪';
                botEl.className = 'status-badge success';
            } else if (health.recommendation && health.recommendation.includes('⚠️')) {
                botEl.textContent = '降级模式';
                botEl.className = 'status-badge warning';
            } else {
                botEl.textContent = '不可用';
                botEl.className = 'status-badge error';
            }
        }
    },

    updateTopBarStatus(state, text) {
        const indicator = document.getElementById('statusIndicator');
        const statusText = document.getElementById('statusText');
        if (indicator) indicator.className = `status-indicator ${state}`;
        if (statusText) statusText.textContent = text;
    },

    renderRecentActivity(activities) {
        const container = document.getElementById('recentActivity');
        if (!container) return;
        const emptyEl = document.getElementById('activityEmpty');

        if (!activities.length) {
            if (emptyEl) emptyEl.style.display = 'flex';
            return;
        }

        if (emptyEl) emptyEl.style.display = 'none';

        // Remove any existing activity items (but keep empty state element)
        container.querySelectorAll('.activity-item').forEach(el => el.remove());

        activities.forEach(activity => {
            const item = document.createElement('div');
            item.className = 'activity-item';
            item.innerHTML = `
                <div class="activity-icon">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                </div>
                <div class="activity-content">
                    <span class="activity-text">${this.escapeHtml(activity.text)}</span>
                    <span class="activity-time">${this.escapeHtml(activity.time)}</span>
                </div>
            `;
            container.appendChild(item);
        });
    },

    renderExtraStats(data) {
        // Render Active User Proportion
        if (data.active_user_proportion) {
            document.getElementById('activeUserPercent').textContent = data.active_user_proportion.percent + '%';
            document.getElementById('activeUserCountText').textContent = data.active_user_proportion.active;
            document.getElementById('totalUserCountText').textContent = data.active_user_proportion.total;
        }

        // Render Today's Active Users
        const container = document.getElementById('todayActiveUsersContainer');
        if (!container) return;

        const emptyEl = document.getElementById('todayActiveUsersEmpty');

        if (!data.today_active_users || !data.today_active_users.length) {
            if (emptyEl) emptyEl.style.display = 'flex';
            container.querySelectorAll('.active-user-item').forEach(el => el.remove());
            return;
        }

        if (emptyEl) emptyEl.style.display = 'none';
        container.querySelectorAll('.active-user-item').forEach(el => el.remove());

        data.today_active_users.forEach(user => {
            const item = document.createElement('div');
            item.className = 'active-user-item';
            item.style.display = 'flex';
            item.style.justifyContent = 'space-between';
            item.style.padding = '8px 12px';
            item.style.borderBottom = '1px solid var(--border-color)';

            item.innerHTML = `
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div style="width: 24px; height: 24px; border-radius: 50%; background: var(--border-color); display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: bold; color: var(--text-primary);">
                        ${this.escapeHtml(user.username.charAt(0).toUpperCase())}
                    </div>
                    <span style="font-weight: 500; font-size: 14px;">${this.escapeHtml(user.username)}</span>
                </div>
                <div style="color: var(--text-secondary); font-size: 14px;">
                    <strong style="color: var(--text-primary);">${user.count}</strong> 次
                </div>
            `;
            container.appendChild(item);
        });

        // Render Top Active Users All-Time
        const topContainer = document.getElementById('topActiveUsersContainer');
        if (!topContainer) return;

        const topEmptyEl = document.getElementById('topActiveUsersEmpty');

        if (!data.top_active_users || !data.top_active_users.length) {
            if (topEmptyEl) topEmptyEl.style.display = 'flex';
            topContainer.querySelectorAll('.active-user-item').forEach(el => el.remove());
            return;
        }

        if (topEmptyEl) topEmptyEl.style.display = 'none';
        topContainer.querySelectorAll('.active-user-item').forEach(el => el.remove());

        data.top_active_users.forEach((user, index) => {
            const item = document.createElement('div');
            item.className = 'active-user-item';
            item.style.display = 'flex';
            item.style.justifyContent = 'space-between';
            item.style.padding = '8px 12px';
            item.style.borderBottom = '1px solid var(--border-color)';

            // Add medal colors for top 3
            let medalColor = 'var(--text-secondary)';
            if (index === 0) medalColor = '#FBBF24'; // Gold
            else if (index === 1) medalColor = '#9CA3AF'; // Silver
            else if (index === 2) medalColor = '#B45309'; // Bronze

            item.innerHTML = `
                <div style="display: flex; align-items: center; gap: 12px;">
                    <div style="width: 20px; font-weight: bold; font-size: 14px; text-align: center; color: ${medalColor};">
                        #${index + 1}
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-weight: 500; font-size: 14px;">${this.escapeHtml(user.username)}</span>
                    </div>
                </div>
                <div style="color: var(--text-secondary); font-size: 14px;">
                    <strong style="color: var(--text-primary);">${user.count}</strong> 次
                </div>
            `;
            topContainer.appendChild(item);
        });
    },

    renderPersonaStats(stats, personaUsersData = {}) {
        const container = document.getElementById('personaStatsContainer');
        if (!container) return;
        const emptyEl = document.getElementById('personaStatsEmpty');

        if (!stats || !stats.length) {
            if (emptyEl) emptyEl.style.display = 'flex';
            return;
        }

        if (emptyEl) emptyEl.style.display = 'none';

        // Remove any existing persona items
        container.querySelectorAll('.persona-stat-item').forEach(el => el.remove());

        // Color mapping for personas
        const colorMap = {
            '新手小白': { color: '#60A5FA', bg: 'rgba(59, 130, 246, 0.12)' },
            '辩论对手': { color: '#F87171', bg: 'rgba(239, 68, 68, 0.12)' },
            '计网专家': { color: '#34D399', bg: 'rgba(16, 185, 129, 0.12)' }
        };

        const totalCount = stats.reduce((sum, s) => sum + s.count, 0);

        stats.forEach(stat => {
            const colors = colorMap[stat.name] || { color: '#9242eb', bg: 'rgba(146, 66, 235, 0.12)' };
            const item = document.createElement('div');
            item.className = 'persona-stat-item';
            // 添加可点击的样式
            item.style.cursor = 'pointer';

            let usersHtml = '';
            let hasUsers = false;
            if (personaUsersData && personaUsersData[stat.name] && personaUsersData[stat.name].length > 0) {
                hasUsers = true;
                usersHtml = '<div class="persona-users-list" style="display: none; margin-top: 14px; font-size: 13px; color: var(--text-secondary); background: var(--bg-hover); padding: 10px; border-radius: 6px;">';
                usersHtml += '<div style="margin-bottom: 6px; font-weight: 600; font-size: 12px; letter-spacing: 0.5px;">相关成员分布表：</div>';
                personaUsersData[stat.name].forEach(u => {
                    usersHtml += `<div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid rgba(0,0,0,0.05);">
                        <span>${this.escapeHtml(u.username)}</span>
                        <span><strong style="color: var(--text-primary);">${u.count}</strong> 次</span>
                    </div>`;
                });
                usersHtml += '</div>';
            }

            const iconHtml = hasUsers ? `
                <div class="persona-stat-expand-icon" style="transition: transform 0.2s; display: flex; align-items: center; justify-content: center; width: 24px; height: 24px;">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
                </div>
            ` : '';

            item.innerHTML = `
                <div class="persona-stat-header" style="display: flex; align-items: center; justify-content: space-between;">
                    <div class="persona-stat-name" style="flex: 1;">
                        <span class="persona-stat-dot" style="background: ${colors.color}"></span>
                        ${this.escapeHtml(stat.name)}
                    </div>
                    <div class="persona-stat-numbers" style="display: flex; gap: 8px; margin-right: ${hasUsers ? '8px' : '0'};">
                        <span class="persona-stat-count">${stat.count} 次</span>
                        <span class="persona-stat-pct">${stat.percentage}%</span>
                    </div>
                    ${iconHtml}
                </div>
                <div class="persona-stat-bar" style="margin-top: 6px;">
                    <div class="persona-stat-bar-fill" style="width: ${stat.percentage}%; background: ${colors.color}"></div>
                </div>
                ${usersHtml}
            `;

            // 绑定点击展开/折叠功能
            if (hasUsers) {
                item.addEventListener('click', function () {
                    const listEl = this.querySelector('.persona-users-list');
                    const iconEl = this.querySelector('.persona-stat-expand-icon');
                    if (listEl.style.display === 'none') {
                        listEl.style.display = 'block';
                        iconEl.style.transform = 'rotate(180deg)';
                    } else {
                        listEl.style.display = 'none';
                        iconEl.style.transform = 'rotate(0deg)';
                    }
                });
            }

            container.appendChild(item);
        });

        // Add total summary
        const summary = document.createElement('div');
        summary.className = 'persona-stat-item persona-stat-summary';
        summary.innerHTML = `<span class="persona-stat-total">总计使用 <strong>${totalCount}</strong> 次</span>`;
        container.appendChild(summary);
    },

    renderChart(data) {
        if (typeof Chart === 'undefined') return;
        const ctx = document.getElementById('activityChart');
        if (!ctx) return;

        if (this.activityChart) {
            this.activityChart.destroy();
        }

        // Generate real date labels for last 7 days
        const days = parseInt(document.getElementById('chartFilter')?.value || '7');
        const labels = [];
        const now = new Date();
        for (let i = days - 1; i >= 0; i--) {
            const d = new Date(now);
            d.setDate(d.getDate() - i);
            labels.push(d.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' }));
        }

        // Use real data if available, otherwise show zeros (honest representation)
        const userActivityData = data.user_activity || new Array(days).fill(0);

        const gradient = ctx.getContext('2d');
        const fill = gradient.createLinearGradient(0, 0, 0, 240);
        fill.addColorStop(0, 'rgba(146, 66, 235, 0.25)');
        fill.addColorStop(1, 'rgba(146, 66, 235, 0.01)');

        this.activityChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: '活跃用户',
                    data: userActivityData.slice(-days),
                    borderColor: '#9242eb',
                    backgroundColor: fill,
                    borderWidth: 2.5,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    pointHoverBorderWidth: 2,
                    pointHoverBackgroundColor: '#9242eb',
                    pointHoverBorderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(19, 24, 41, 0.95)',
                        borderColor: 'rgba(146, 66, 235, 0.3)',
                        borderWidth: 1,
                        titleColor: '#F1F5F9',
                        bodyColor: '#94A3B8',
                        titleFont: { family: 'Inter', weight: '600', size: 13 },
                        bodyFont: { family: 'Inter', weight: '400', size: 12 },
                        padding: 12,
                        cornerRadius: 10,
                        displayColors: false
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(148, 163, 184, 0.05)' },
                        ticks: { color: '#64748B', font: { family: 'Inter', size: 11 } },
                        border: { display: false }
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(148, 163, 184, 0.05)' },
                        ticks: {
                            color: '#64748B',
                            font: { family: 'Inter', size: 11 },
                            stepSize: 1,
                            precision: 0
                        },
                        border: { display: false }
                    }
                }
            }
        });

        // Bind filter change
        const filter = document.getElementById('chartFilter');
        if (filter && !filter._bound) {
            filter._bound = true;
            filter.addEventListener('change', () => this.loadDashboard());
        }
    },

    renderEngagementCharts(data) {
        // Cache data for theme switching
        this.cachedEngagementData = data;

        const days = parseInt(document.getElementById('engagementFilter')?.value || '7');
        const labels = [];
        const now = new Date();
        for (let i = days - 1; i >= 0; i--) {
            const d = new Date(now);
            d.setDate(d.getDate() - i);
            labels.push(d.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' }));
        }

        // Get theme colors
        const isDark = !document.body.classList.contains('light-theme');
        const primaryColor = '#9242eb';
        const successColor = isDark ? '#34D399' : '#059669';
        const infoColor = isDark ? '#60A5FA' : '#2563EB';
        const gridColor = isDark ? 'rgba(148, 163, 184, 0.05)' : 'rgba(124, 58, 237, 0.08)';
        const tickColor = isDark ? '#64748B' : '#6B21A8';

        // User Activity Charts
        this.renderMiniChart('userCountChart', labels, data.user_count_data || [], primaryColor, gridColor, tickColor);
        this.renderMiniChart('conversationCountChart', labels, data.conversation_count_data || [], infoColor, gridColor, tickColor);
        this.renderMiniChart('avgConversationChart', labels, data.avg_conversation_data || [], successColor, gridColor, tickColor);

        // User Retention Charts
        this.renderMiniChart('retention1dChart', labels, data.retention_1d_data || [], primaryColor, gridColor, tickColor);
        this.renderMiniChart('retention7dChart', labels, data.retention_7d_data || [], infoColor, gridColor, tickColor);
        this.renderMiniChart('retention30dChart', labels, data.retention_30d_data || [], successColor, gridColor, tickColor);

        // Extra Full-Site Depth Charts
        const fontColor = isDark ? '#E2E8F0' : '#475569';
        // Chat Time Distribution
        if (data.chat_time_data) {
            const timeLabels = Object.keys(data.chat_time_data);
            const timeVals = Object.values(data.chat_time_data);
            this.renderDoughnutChart('chatTimeChart', timeLabels, timeVals, ['#3B82F6', '#8B5CF6', '#F59E0B', '#10B981'], fontColor);
        }

        // Conversation Depth
        if (data.conversation_depth_data) {
            const depthLabels = ['1-5轮', '6-15轮', '16-30轮', '30+轮（专家级）'];
            const depthKeys = ['1-5', '6-15', '16-30', '30+'];
            const depthVals = depthKeys.map(k => data.conversation_depth_data[k] || 0);
            this.renderDoughnutChart('conversationDepthChart', depthLabels, depthVals, ['#93C5FD', '#FCD34D', '#F87171', '#C084FC'], fontColor);
        }

        // Update values — 使用 != null 判断避免值为 0 时被误判为空
        const latestIndex = labels.length - 1;
        const uc = data.user_count_data?.[latestIndex];
        document.getElementById('userCountValue').textContent = uc != null ? uc : '-';
        const cc = data.conversation_count_data?.[latestIndex];
        document.getElementById('conversationCountValue').textContent = cc != null ? cc : '-';
        const ac = data.avg_conversation_data?.[latestIndex];
        document.getElementById('avgConversationValue').textContent = ac != null ? ac.toFixed(1) : '-';
        const r1 = data.retention_1d_data?.[latestIndex];
        document.getElementById('retention1dValue').textContent = r1 != null ? `${r1}%` : '-';
        const r7 = data.retention_7d_data?.[latestIndex];
        document.getElementById('retention7dValue').textContent = r7 != null ? `${r7}%` : '-';
        const r30 = data.retention_30d_data?.[latestIndex];
        document.getElementById('retention30dValue').textContent = r30 != null ? `${r30}%` : '-';

        // Bind filter change
        const filter = document.getElementById('engagementFilter');
        if (filter && !filter._engagementBound) {
            filter._engagementBound = true;
            filter.addEventListener('change', () => this.loadDashboard());
        }
    },

    renderDoughnutChart(canvasId, labels, data, colors, fontColor) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        // Destroy existing instance to prevent duplication
        if (canvas._chartInstance) {
            canvas._chartInstance.destroy();
        }

        const ctx = canvas.getContext('2d');
        canvas._chartInstance = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: colors,
                    borderWidth: 0,
                    hoverOffset: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '70%',
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            color: fontColor,
                            font: { size: 12, family: 'Inter, system-ui, sans-serif' },
                            usePointStyle: true,
                            padding: 15
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.9)',
                        titleColor: '#F8FAFC',
                        bodyColor: '#F8FAFC',
                        borderWidth: 1,
                        borderColor: 'rgba(255,255,255,0.1)',
                        padding: 10,
                        cornerRadius: 8,
                        displayColors: true
                    }
                }
            }
        });
    },

    renderMiniChart(canvasId, labels, data, color, gridColor, tickColor) {
        if (typeof Chart === 'undefined') return; // Chart.js 未加载
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;

        // Destroy existing chart
        if (this[canvasId]) {
            this[canvasId].destroy();
        }

        // Ensure data array has same length as labels
        const chartData = data.length === labels.length ? data : new Array(labels.length).fill(0);

        // Get theme-aware colors
        const isDark = !document.body.classList.contains('light-theme');
        const tooltipBg = isDark ? 'rgba(19, 24, 41, 0.95)' : 'rgba(255, 255, 255, 0.95)';
        const tooltipTitleColor = isDark ? '#F1F5F9' : '#1E293B';
        const tooltipBodyColor = isDark ? '#94A3B8' : '#64748B';

        const gradient = ctx.getContext('2d').createLinearGradient(0, 0, 0, 120);
        gradient.addColorStop(0, color + '40');
        gradient.addColorStop(1, color + '05');

        this[canvasId] = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    data: chartData,
                    borderColor: color,
                    backgroundColor: gradient,
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    pointHoverBorderWidth: 2,
                    pointHoverBackgroundColor: color,
                    pointHoverBorderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        enabled: true,
                        backgroundColor: tooltipBg,
                        borderColor: color + '50',
                        borderWidth: 1,
                        titleColor: tooltipTitleColor,
                        bodyColor: tooltipBodyColor,
                        titleFont: { family: 'Inter', weight: '600', size: 11 },
                        bodyFont: { family: 'Inter', weight: '400', size: 11 },
                        padding: 8,
                        cornerRadius: 8,
                        displayColors: false,
                        callbacks: {
                            label: (context) => {
                                return context.parsed.y.toFixed(1);
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        display: false,
                        grid: { display: false }
                    },
                    y: {
                        beginAtZero: true,
                        display: false,
                        grid: { display: false }
                    }
                },
                layout: {
                    padding: 0
                }
            }
        });
    },

    /* ========================================================
       USER MANAGEMENT
       ======================================================== */
    async loadUsers() {
        const tbody = document.getElementById('usersTableBody');
        if (!tbody) return;
        tbody.innerHTML = '<tr><td colspan="4" class="loading-cell">加载中...</td></tr>';

        try {
            const res = await fetch('/api/admin/users');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            const users = data.users || [];

            if (!users.length) {
                tbody.innerHTML = `<tr><td colspan="4"><div class="empty-state"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg><span class="empty-title">暂无用户</span><span class="empty-desc">点击"添加用户"创建第一个用户</span></div></td></tr>`;
                return;
            }

            tbody.innerHTML = users.map(u => `
                <tr>
                    <td style="font-weight: 550;">${this.escapeHtml(u.username)}</td>
                    <td><span class="role-badge ${u.role}">${u.role === 'admin' ? '管理员' : '普通用户'}</span></td>
                    <td><span class="oauth-badge ${u.has_oauth ? 'authorized' : 'unauthorized'}">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">${u.has_oauth
                    ? '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>'
                    : '<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>'
                }</svg>
                        ${u.has_oauth ? '已授权' : '未授权'}
                    </span></td>
                    <td>
                        <div class="action-buttons">
                            <button class="btn btn-secondary btn-sm" onclick="AdminPanel.editUser('${this.escapeHtml(u.username)}')" title="编辑">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                            </button>
                            <button class="btn btn-danger btn-sm" onclick="AdminPanel.confirmDeleteUser('${this.escapeHtml(u.username)}')" title="删除">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                            </button>
                        </div>
                    </td>
                </tr>
            `).join('');

            this.bindUserFilters(users);
        } catch (err) {
            console.error('[Users] Load failed:', err);
            tbody.innerHTML = `<tr><td colspan="4" class="loading-cell" style="color: var(--error);">加载失败，请刷新重试</td></tr>`;
        }

        this.bindUserActions();
    },

    bindUserFilters(allUsers) {
        const search = document.getElementById('userSearch');
        const roleFilter = document.getElementById('roleFilter');
        if (!search || !roleFilter) return;

        const filterFn = () => {
            const currentSearch = document.getElementById('userSearch');
            const currentRoleFilter = document.getElementById('roleFilter');
            const q = currentSearch ? currentSearch.value.toLowerCase().trim() : '';
            const role = currentRoleFilter ? currentRoleFilter.value : '';
            const tbody = document.getElementById('usersTableBody');
            const rows = tbody.querySelectorAll('tr');

            rows.forEach(row => {
                const username = row.cells?.[0]?.textContent?.toLowerCase() || '';
                const rowRole = row.querySelector('.role-badge')?.classList.contains('admin') ? 'admin' : 'user';
                const matchSearch = !q || username.includes(q);
                const matchRole = !role || rowRole === role;
                row.style.display = (matchSearch && matchRole) ? '' : 'none';
            });
        };

        // Remove old listeners by replacing elements
        const newSearch = search.cloneNode(true);
        search.parentNode.replaceChild(newSearch, search);
        newSearch.addEventListener('input', filterFn);

        const newRole = roleFilter.cloneNode(true);
        roleFilter.parentNode.replaceChild(newRole, roleFilter);
        newRole.addEventListener('change', filterFn);
    },

    bindUserActions() {
        const addBtn = document.getElementById('addUserBtn');
        if (addBtn && !addBtn._bound) {
            addBtn._bound = true;
            addBtn.addEventListener('click', () => this.openModal('addUserModal'));
        }

        const confirmAdd = document.getElementById('confirmAddUser');
        if (confirmAdd && !confirmAdd._bound) {
            confirmAdd._bound = true;
            confirmAdd.addEventListener('click', () => this.addUser());
        }

        const confirmEdit = document.getElementById('confirmEditUser');
        if (confirmEdit && !confirmEdit._bound) {
            confirmEdit._bound = true;
            confirmEdit.addEventListener('click', () => this.saveUserEdit());
        }

        // Batch import bindings
        const batchBtn = document.getElementById('batchImportBtn');
        if (batchBtn && !batchBtn._bound) {
            batchBtn._bound = true;
            batchBtn.addEventListener('click', () => {
                // Reset modal state
                const fileInput = document.getElementById('csvFileInput');
                const uploadArea = document.getElementById('csvUploadArea');
                const uploadText = document.getElementById('uploadFileName');
                const confirmBtn = document.getElementById('confirmBatchImport');
                const resultDiv = document.getElementById('batchResult');
                if (fileInput) fileInput.value = '';
                if (uploadArea) uploadArea.classList.remove('has-file');
                if (uploadText) uploadText.textContent = '点击选择或拖拽 CSV 文件到此处';
                if (confirmBtn) confirmBtn.disabled = true;
                if (resultDiv) resultDiv.style.display = 'none';
                this.openModal('batchImportModal');
            });
        }

        // CSV upload area - click to trigger file input
        const uploadArea = document.getElementById('csvUploadArea');
        const fileInput = document.getElementById('csvFileInput');
        if (uploadArea && fileInput && !uploadArea._bound) {
            uploadArea._bound = true;

            uploadArea.addEventListener('click', () => fileInput.click());

            // Drag & drop
            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.classList.add('drag-over');
            });
            uploadArea.addEventListener('dragleave', () => {
                uploadArea.classList.remove('drag-over');
            });
            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('drag-over');
                const file = e.dataTransfer.files[0];
                if (file) this._handleCsvFileSelect(file);
            });

            fileInput.addEventListener('change', (e) => {
                const file = e.target.files[0];
                if (file) this._handleCsvFileSelect(file);
            });
        }

        // Confirm batch import
        const confirmBatch = document.getElementById('confirmBatchImport');
        if (confirmBatch && !confirmBatch._bound) {
            confirmBatch._bound = true;
            confirmBatch.addEventListener('click', () => this.batchImportUsers());
        }
    },

    _selectedCsvFile: null,

    _handleCsvFileSelect(file) {
        this._selectedCsvFile = file;
        const uploadArea = document.getElementById('csvUploadArea');
        const uploadText = document.getElementById('uploadFileName');
        const confirmBtn = document.getElementById('confirmBatchImport');

        if (uploadArea) uploadArea.classList.add('has-file');
        if (uploadText) uploadText.textContent = `已选择: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
        if (confirmBtn) confirmBtn.disabled = false;

        // Hide previous results
        const resultDiv = document.getElementById('batchResult');
        if (resultDiv) resultDiv.style.display = 'none';
    },

    async batchImportUsers() {
        if (!this._selectedCsvFile) {
            this.showToast('error', '请先选择文件', '请上传 CSV 格式的用户列表文件');
            return;
        }

        const btn = document.getElementById('confirmBatchImport');
        btn.classList.add('loading');
        btn.disabled = true;

        try {
            // 用 FileReader 读取原始二进制数据，转 base64 发送给后端做编码检测
            const fileBase64 = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => {
                    const bytes = new Uint8Array(reader.result);
                    let binary = '';
                    for (let i = 0; i < bytes.length; i++) {
                        binary += String.fromCharCode(bytes[i]);
                    }
                    resolve(btoa(binary));
                };
                reader.onerror = () => reject(new Error('文件读取失败'));
                reader.readAsArrayBuffer(this._selectedCsvFile);
            });

            const res = await fetch('/api/admin/users/batch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ file_base64: fileBase64 })
            });
            const data = await res.json();

            const resultDiv = document.getElementById('batchResult');
            const resultContent = document.getElementById('batchResultContent');
            if (resultDiv && resultContent) {
                resultDiv.style.display = 'block';

                if (data.success) {
                    const d = data.data;
                    let html = `<div class="result-summary">${this.escapeHtml(data.message)}</div>`;
                    html += `<div class="result-stats">`;
                    html += `<span class="result-stat created">✓ 创建 ${d.total_created}</span>`;
                    if (d.total_skipped > 0) html += `<span class="result-stat skipped">⊘ 跳过 ${d.total_skipped}</span>`;
                    if (d.total_errors > 0) html += `<span class="result-stat errored">✕ 错误 ${d.total_errors}</span>`;
                    html += `</div>`;

                    if (d.created.length > 0) {
                        html += `<div class="result-detail"><div class="result-detail-title">新建用户</div>`;
                        html += `<div class="result-detail-list">${d.created.map(u => this.escapeHtml(u)).join('、')}</div></div>`;
                    }
                    if (d.skipped.length > 0) {
                        html += `<div class="result-detail"><div class="result-detail-title">跳过（已存在）</div>`;
                        html += `<div class="result-detail-list">${d.skipped.map(u => this.escapeHtml(u)).join('、')}</div></div>`;
                    }
                    if (d.errors.length > 0) {
                        html += `<div class="result-detail"><div class="result-detail-title">错误详情</div>`;
                        html += `<div class="result-detail-list">${d.errors.map(e => this.escapeHtml(e)).join('<br>')}</div></div>`;
                    }

                    resultContent.innerHTML = html;
                    this.showToast('success', '批量导入完成', data.message);
                    this.loadUsers(); // Refresh user table
                } else {
                    resultContent.innerHTML = `<div class="result-summary" style="color:var(--error)">${this.escapeHtml(data.message)}</div>`;
                    this.showToast('error', '导入失败', data.message);
                }
            }
        } catch (err) {
            this.showToast('error', '请求失败', err.message);
        } finally {
            btn.classList.remove('loading');
            btn.disabled = false;
            this._selectedCsvFile = null;
        }
    },

    async addUser() {
        const username = document.getElementById('newUsername')?.value.trim();
        const password = document.getElementById('newPassword')?.value;
        const role = document.getElementById('newUserRole')?.value || 'user';

        if (!username || !password) {
            this.showToast('error', '输入不完整', '请填写用户名和密码');
            return;
        }

        const btn = document.getElementById('confirmAddUser');
        btn.classList.add('loading');

        try {
            const res = await fetch('/api/admin/users', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password, role })
            });
            const data = await res.json();

            if (res.ok && data.success !== false) {
                this.showToast('success', '用户已创建', `用户 ${username} 已成功添加`);
                this.closeModal('addUserModal');
                document.getElementById('newUsername').value = '';
                document.getElementById('newPassword').value = '';
                this.loadUsers();
            } else {
                this.showToast('error', '创建失败', data.error || data.message || '未知错误');
            }
        } catch (err) {
            this.showToast('error', '请求失败', err.message);
        } finally {
            btn.classList.remove('loading');
        }
    },

    editUser(username) {
        document.getElementById('editUsername').value = username;
        document.getElementById('editPassword').value = '';

        // Try to detect current role from table
        const rows = document.getElementById('usersTableBody').querySelectorAll('tr');
        for (const row of rows) {
            if (row.cells?.[0]?.textContent === username) {
                const isAdmin = row.querySelector('.role-badge.admin');
                document.getElementById('editUserRole').value = isAdmin ? 'admin' : 'user';
                break;
            }
        }

        this.openModal('editUserModal');
    },

    async saveUserEdit() {
        const username = document.getElementById('editUsername')?.value;
        const password = document.getElementById('editPassword')?.value;
        const role = document.getElementById('editUserRole')?.value;

        if (!username) return;

        const btn = document.getElementById('confirmEditUser');
        btn.classList.add('loading');

        try {
            // Update role
            const roleRes = await fetch(`/api/admin/users/${username}/role`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ role })
            });

            // Update password if provided
            if (password) {
                await fetch(`/api/admin/users/${username}/password`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ password })
                });
            }

            if (roleRes.ok) {
                this.showToast('success', '修改已保存', `用户 ${username} 的信息已更新`);
                this.closeModal('editUserModal');
                this.loadUsers();
            } else {
                const d = await roleRes.json();
                this.showToast('error', '保存失败', d.error || '未知错误');
            }
        } catch (err) {
            this.showToast('error', '请求失败', err.message);
        } finally {
            btn.classList.remove('loading');
        }
    },

    confirmDeleteUser(username) {
        document.getElementById('confirmTitle').textContent = '删除用户';
        document.getElementById('confirmMessage').textContent = `确定要删除用户「${username}」吗？此操作不可撤销，该用户的所有数据将被永久移除。`;

        const icon = document.getElementById('confirmIcon');
        icon.className = 'confirm-icon danger';
        icon.innerHTML = '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';

        const actionBtn = document.getElementById('confirmAction');
        actionBtn.textContent = '确认删除';
        actionBtn.className = 'btn btn-danger';

        // Replace listener
        const newBtn = actionBtn.cloneNode(true);
        actionBtn.parentNode.replaceChild(newBtn, actionBtn);
        newBtn.id = 'confirmAction';
        newBtn.addEventListener('click', () => this.deleteUser(username));

        this.openModal('confirmModal');
    },

    async deleteUser(username) {
        const btn = document.getElementById('confirmAction');
        btn.classList.add('loading');

        try {
            const res = await fetch(`/api/admin/users/${username}`, { method: 'DELETE' });
            const data = await res.json();

            if (res.ok) {
                this.showToast('success', '用户已删除', `用户 ${username} 已被移除`);
                this.closeModal('confirmModal');
                this.loadUsers();
            } else {
                this.showToast('error', '删除失败', data.error || '未知错误');
            }
        } catch (err) {
            this.showToast('error', '请求失败', err.message);
        } finally {
            btn.classList.remove('loading');
        }
    },

    /* ========================================================
       SYSTEM CONFIGURATION
       ======================================================== */
    async loadConfig() {
        try {
            const res = await fetch('/api/admin/config');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            if (data.bot_id) document.getElementById('configBotId').value = data.bot_id;
            if (data.service_token) document.getElementById('configServiceToken').value = data.service_token;
            if (data.base_url) document.getElementById('configBaseUrl').value = data.base_url;
            if (data.client_id) document.getElementById('configClientId').value = data.client_id;
            if (data.client_secret) document.getElementById('configClientSecret').value = data.client_secret;
            if (data.redirect_url) document.getElementById('configRedirectUrl').value = data.redirect_url;
        } catch (err) {
            console.error('[Config] Load failed:', err);
        }

        this.bindConfigActions();
    },

    bindConfigActions() {
        const saveApi = document.getElementById('saveApiConfig');
        if (saveApi && !saveApi._bound) {
            saveApi._bound = true;
            saveApi.addEventListener('click', () => this.saveConfig('api'));
        }

        const saveOauth = document.getElementById('saveOauthConfig');
        if (saveOauth && !saveOauth._bound) {
            saveOauth._bound = true;
            saveOauth.addEventListener('click', () => this.saveConfig('oauth'));
        }
    },

    async saveConfig(type) {
        const btn = type === 'api' ? document.getElementById('saveApiConfig') : document.getElementById('saveOauthConfig');
        btn.classList.add('loading');

        const payload = {};
        if (type === 'api') {
            payload.bot_id = document.getElementById('configBotId').value.trim();
            payload.service_token = document.getElementById('configServiceToken').value.trim();
            payload.base_url = document.getElementById('configBaseUrl').value.trim();
        } else {
            payload.client_id = document.getElementById('configClientId').value.trim();
            payload.client_secret = document.getElementById('configClientSecret').value.trim();
            payload.redirect_url = document.getElementById('configRedirectUrl').value.trim();
        }

        try {
            const res = await fetch('/api/admin/config', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                this.showToast('success', '配置已保存', `${type === 'api' ? 'API' : 'OAuth'} 配置已成功更新`);
            } else {
                const data = await res.json();
                this.showToast('error', '保存失败', data.error || '未知错误');
            }
        } catch (err) {
            this.showToast('error', '请求失败', err.message);
        } finally {
            btn.classList.remove('loading');
        }
    },

    /* ========================================================
       CONVERSATIONS
       ======================================================== */
    async loadConversations() {
        const tbody = document.getElementById('conversationsTableBody');
        if (!tbody) return;

        tbody.innerHTML = '<tr><td colspan="6" class="loading-cell">加载中...</td></tr>';

        // Color mapping for persona badges
        const personaColors = {
            '新手小白': 'beginner',
            '辩论对手': 'debater',
            '计网专家': 'expert'
        };

        try {
            const res = await fetch('/api/admin/conversations');
            if (!res.ok) {
                tbody.innerHTML = `<tr><td colspan="6"><div class="empty-state"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg><span class="empty-title">暂无对话数据</span><span class="empty-desc">用户发起对话后，记录将在此显示</span></div></td></tr>`;
                return;
            }
            const data = await res.json();
            const conversations = data.conversations || [];

            if (!conversations.length) {
                tbody.innerHTML = `<tr><td colspan="6"><div class="empty-state"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg><span class="empty-title">暂无对话数据</span><span class="empty-desc">用户发起对话后，记录将在此显示</span></div></td></tr>`;
                return;
            }

            tbody.innerHTML = conversations.map(c => {
                const personaClass = personaColors[c.persona] || '';
                // 如果没有人设记录，使用默认人设"计网专家"
                const displayPersona = c.persona || '计网专家';
                const displayClass = personaColors[displayPersona] || '';
                const personaHtml = `<span class="persona-badge ${displayClass}">${this.escapeHtml(displayPersona)}</span>`;

                return `
                <tr>
                    <td style="font-family: monospace; font-size: 0.8rem; color: var(--text-secondary);">${this.escapeHtml(c.id || '-')}</td>
                    <td style="font-weight: 550;">${this.escapeHtml(c.username || '-')}</td>
                    <td>${personaHtml}</td>
                    <td>${c.message_count ?? '-'}</td>
                    <td style="color: var(--text-secondary);">${c.created_at ? new Date(c.created_at).toLocaleString('zh-CN') : '-'}</td>
                    <td>
                        <button class="btn btn-secondary btn-sm" onclick="AdminPanel.viewConversation('${this.escapeHtml(c.id)}')" title="查看">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                        </button>
                    </td>
                </tr>
            `;
            }).join('');
        } catch {
            tbody.innerHTML = `<tr><td colspan="6"><div class="empty-state"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg><span class="empty-title">暂无对话数据</span><span class="empty-desc">对话管理 API 尚未就绪</span></div></td></tr>`;
        }
    },

    async viewConversation(id) {
        // Open modal and load conversation details
        this.openModal('conversationDetailModal');

        const modalBody = document.getElementById('conversationDetailBody');
        if (!modalBody) return;

        // Show loading state
        modalBody.innerHTML = '<div class="loading-cell">加载对话记录中...</div>';

        try {
            const res = await fetch(`/api/admin/conversations/${encodeURIComponent(id)}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            if (!data.messages || data.messages.length === 0) {
                modalBody.innerHTML = `
                    <div class="empty-state">
                        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                        </svg>
                        <span class="empty-title">暂无消息</span>
                        <span class="empty-desc">此对话尚未包含任何消息</span>
                    </div>
                `;
                return;
            }

            // Render messages
            modalBody.innerHTML = data.messages.map(msg => `
                <div class="message-item ${msg.type}">
                    <div class="message-header">
                        <span class="message-author">${this.escapeHtml(msg.author || msg.type)}</span>
                        <span class="message-time">${msg.created_at ? new Date(msg.created_at).toLocaleString('zh-CN') : '-'}</span>
                    </div>
                    <div class="message-content">${this.escapeHtml(msg.content || '')}</div>
                </div>
            `).join('');

        } catch (err) {
            console.error('[Conversation Detail] Load failed:', err);
            modalBody.innerHTML = `
                <div class="empty-state">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                        <line x1="12" y1="9" x2="12" y2="13"/>
                        <line x1="12" y1="17" x2="12.01" y2="17"/>
                    </svg>
                    <span class="empty-title">加载失败</span>
                    <span class="empty-desc">${err.message}</span>
                </div>
            `;
        }
    },

    /* ========================================================
       MODAL SYSTEM
       ======================================================== */
    openModal(id) {
        const modal = document.getElementById(id);
        if (modal) {
            modal.classList.add('active');
            // Focus first input
            const input = modal.querySelector('input:not([readonly])');
            if (input) setTimeout(() => input.focus(), 100);
        }
    },

    closeModal(id) {
        const modal = document.getElementById(id);
        if (modal) modal.classList.remove('active');
    },

    /* ========================================================
       TOAST SYSTEM
       ======================================================== */
    showToast(type, title, message) {
        const container = document.getElementById('toastContainer');
        if (!container) return;

        const icons = {
            success: '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
            error: '<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>',
            warning: '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
            info: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>'
        };

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${icons[type] || icons.info}</svg>
            <div class="toast-content">
                <div class="toast-title">${this.escapeHtml(title)}</div>
                ${message ? `<div class="toast-message">${this.escapeHtml(message)}</div>` : ''}
            </div>
            <button class="toast-close" onclick="this.parentElement.remove()" aria-label="关闭提示">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
        `;

        container.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(40px)';
            toast.style.transition = 'all 300ms ease-out';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    },

    /* ========================================================
       LEADERBOARD MANAGEMENT
       ======================================================== */
    async loadLeaderboard() {
        const tbody = document.getElementById('leaderboardTableBody');
        if (!tbody) return;
        tbody.innerHTML = '<tr><td colspan="7" class="loading-cell">加载中...</td></tr>';

        const period = document.getElementById('leaderboardPeriod')?.value || 'all';

        try {
            const res = await fetch(`/api/admin/leaderboard?period=${period}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            const list = data.leaderboard || [];
            const stats = data.stats || {};

            // Update stats cards
            document.getElementById('lbTotalParticipants').textContent = stats.total_participants ?? 0;
            document.getElementById('lbHighestScore').textContent = stats.highest_score ?? 0;
            document.getElementById('lbAvgScore').textContent = stats.avg_score ?? 0;
            document.getElementById('lbTodaySessions').textContent = stats.today_sessions ?? 0;

            if (!list.length) {
                tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5C7 4 6 9 6 9Z"/>
                        <path d="M18 9h1.5a2.5 2.5 0 0 0 0-5C17 4 18 9 18 9Z"/>
                        <path d="M4 22h16"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/>
                    </svg>
                    <span class="empty-title">暂无排行数据</span>
                    <span class="empty-desc">用户完成每日一练后，成绩将在此显示</span>
                </div></td></tr>`;
                return;
            }

            tbody.innerHTML = list.map(item => {
                const rankIcon = item.rank === 1 ? '🥇' : item.rank === 2 ? '🥈' : item.rank === 3 ? '🥉' : item.rank;
                const updatedAt = item.updated_at ? new Date(item.updated_at).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '-';
                return `
                <tr>
                    <td style="text-align: center; font-size: ${item.rank <= 3 ? '1.2em' : '0.95em'}; font-weight: ${item.rank <= 3 ? '700' : '500'};">${rankIcon}</td>
                    <td style="font-weight: 550;">${this.escapeHtml(item.username)}</td>
                    <td><span style="font-weight: 600; color: var(--primary);">${item.total_score}</span></td>
                    <td>${item.highest_score}</td>
                    <td>${item.practice_count}</td>
                    <td style="color: var(--text-secondary); font-size: 0.88em;">${updatedAt}</td>
                    <td>
                        <div class="action-buttons">
                            <button class="btn btn-secondary btn-sm" onclick="AdminPanel.editLeaderboardScore('${this.escapeHtml(item.username)}', ${item.total_score}, ${item.highest_score}, '${period}')" title="编辑分数">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                            </button>
                            <button class="btn btn-sm" onclick="AdminPanel.resetLeaderboardToday('${this.escapeHtml(item.username)}')" title="重置今日做题次数" style="background-color: rgba(217, 119, 6, 0.1); color: #d97706; ${period !== 'today' ? 'display:none;' : ''}">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>
                            </button>
                            <button class="btn btn-danger btn-sm" onclick="AdminPanel.confirmDeleteLeaderboard('${this.escapeHtml(item.username)}')" title="删除记录">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                            </button>
                        </div>
                    </td>
                </tr>`;
            }).join('');

            this.bindLeaderboardFilters(list);
        } catch (err) {
            console.error('[Leaderboard] Load failed:', err);
            tbody.innerHTML = `<tr><td colspan="7" class="loading-cell" style="color: var(--error);">加载失败，请刷新重试</td></tr>`;
        }

        this.bindLeaderboardActions();
    },

    bindLeaderboardFilters(allData) {
        const search = document.getElementById('leaderboardSearch');
        const periodFilter = document.getElementById('leaderboardPeriod');
        if (!search) return;

        const filterFn = () => {
            const q = search.value.toLowerCase().trim();
            const tbody = document.getElementById('leaderboardTableBody');
            const rows = tbody.querySelectorAll('tr');
            rows.forEach(row => {
                const username = row.cells?.[1]?.textContent?.toLowerCase() || '';
                row.style.display = (!q || username.includes(q)) ? '' : 'none';
            });
        };

        // Replace old listeners
        const newSearch = search.cloneNode(true);
        search.parentNode.replaceChild(newSearch, search);
        newSearch.addEventListener('input', filterFn);

        if (periodFilter && !periodFilter._lbBound) {
            periodFilter._lbBound = true;
            periodFilter.addEventListener('change', () => this.loadLeaderboard());
        }
    },

    bindLeaderboardActions() {
        const refreshBtn = document.getElementById('refreshLeaderboardBtn');
        if (refreshBtn && !refreshBtn._bound) {
            refreshBtn._bound = true;
            refreshBtn.addEventListener('click', () => this.loadLeaderboard());
        }
    },

    editLeaderboardScore(username, currentTotal, currentHighest, period) {
        // Reuse confirm modal for editing
        document.getElementById('confirmTitle').textContent = `编辑分数 - ${username}`;

        const icon = document.getElementById('confirmIcon');
        icon.className = 'confirm-icon';
        icon.style.background = 'rgba(146, 66, 235, 0.1)';
        icon.style.color = '#9242eb';
        icon.innerHTML = '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>';

        document.getElementById('confirmMessage').innerHTML = `
            <div style="text-align: left; margin-top: 12px;">
                <div style="margin-bottom: 12px;">
                    <label style="display: block; margin-bottom: 4px; font-weight: 500; font-size: 0.9em; color: var(--text-secondary);">累计得分</label>
                    <input type="number" id="editTotalScore" value="${currentTotal}" min="0" style="width: 100%; padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--bg-secondary); color: var(--text-primary); font-size: 0.95em;">
                </div>
                <div>
                    <label style="display: block; margin-bottom: 4px; font-weight: 500; font-size: 0.9em; color: var(--text-secondary);">最高分</label>
                    <input type="number" id="editHighestScore" value="${currentHighest}" min="0" style="width: 100%; padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--bg-secondary); color: var(--text-primary); font-size: 0.95em;">
                </div>
            </div>
        `;

        const actionBtn = document.getElementById('confirmAction');
        const newBtn = actionBtn.cloneNode(true);
        actionBtn.parentNode.replaceChild(newBtn, actionBtn);
        newBtn.id = 'confirmAction';
        newBtn.textContent = '保存修改';
        newBtn.className = 'btn btn-primary';

        newBtn.addEventListener('click', async () => {
            newBtn.classList.add('loading');
            const totalScore = parseInt(document.getElementById('editTotalScore')?.value || '0');
            const highestScore = parseInt(document.getElementById('editHighestScore')?.value || '0');

            try {
                const res = await fetch(`/api/admin/leaderboard/${encodeURIComponent(username)}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ total_score: totalScore, highest_score: highestScore, period: period })
                });
                const data = await res.json();
                if (res.ok) {
                    this.showToast('success', '分数已更新', `${username} 的分数已成功修改`);
                    this.closeModal('confirmModal');
                    this.loadLeaderboard();
                } else {
                    this.showToast('error', '修改失败', data.error || '未知错误');
                }
            } catch (err) {
                this.showToast('error', '请求失败', err.message);
            } finally {
                newBtn.classList.remove('loading');
            }
        });

        this.openModal('confirmModal');
    },

    resetLeaderboardToday(username) {
        document.getElementById('confirmTitle').textContent = '重置今日练习';
        document.getElementById('confirmMessage').textContent = `确定要重置用户「${username}」的今日练习机会吗？这将清除该用户今天的答题记录，允许其重新练习一次。`;

        const icon = document.getElementById('confirmIcon');
        icon.className = 'confirm-icon warning';
        icon.style.background = 'rgba(217, 119, 6, 0.1)';
        icon.style.color = '#d97706';
        icon.innerHTML = '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>';

        const actionBtn = document.getElementById('confirmAction');
        const newBtn = actionBtn.cloneNode(true);
        actionBtn.parentNode.replaceChild(newBtn, actionBtn);
        newBtn.id = 'confirmAction';
        newBtn.textContent = '确认重置';
        newBtn.className = 'btn';
        newBtn.style.backgroundColor = '#d97706';
        newBtn.style.color = 'white';
        newBtn.style.border = 'none';

        newBtn.addEventListener('click', async () => {
            newBtn.classList.add('loading');
            try {
                const res = await fetch(`/api/admin/leaderboard/${encodeURIComponent(username)}?period=today`, { method: 'DELETE' });
                const data = await res.json();
                if (res.ok) {
                    this.showToast('success', '重置成功', data.message || '今日练习已重置');
                    this.closeModal('confirmModal');
                    this.loadLeaderboard();
                } else {
                    this.showToast('error', '重置失败', data.error || '未知错误');
                }
            } catch (err) {
                this.showToast('error', '请求失败', err.message);
            } finally {
                newBtn.classList.remove('loading');
            }
        });

        this.openModal('confirmModal');
    },

    confirmDeleteLeaderboard(username) {
        document.getElementById('confirmTitle').textContent = '删除练习记录';
        document.getElementById('confirmMessage').textContent = `确定要删除用户「${username}」的所有练习记录吗？此操作将清除该用户的排行榜数据、练习记录和错题记录，且不可撤销。`;

        const icon = document.getElementById('confirmIcon');
        icon.className = 'confirm-icon danger';
        icon.style.background = '';
        icon.style.color = '';
        icon.innerHTML = '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';

        const actionBtn = document.getElementById('confirmAction');
        const newBtn = actionBtn.cloneNode(true);
        actionBtn.parentNode.replaceChild(newBtn, actionBtn);
        newBtn.id = 'confirmAction';
        newBtn.textContent = '确认删除';
        newBtn.className = 'btn btn-danger';

        newBtn.addEventListener('click', async () => {
            newBtn.classList.add('loading');
            try {
                const res = await fetch(`/api/admin/leaderboard/${encodeURIComponent(username)}`, { method: 'DELETE' });
                const data = await res.json();
                if (res.ok) {
                    this.showToast('success', '记录已删除', `${username} 的所有练习记录已被清除`);
                    this.closeModal('confirmModal');
                    this.loadLeaderboard();
                } else {
                    this.showToast('error', '删除失败', data.error || '未知错误');
                }
            } catch (err) {
                this.showToast('error', '请求失败', err.message);
            } finally {
                newBtn.classList.remove('loading');
            }
        });

        this.openModal('confirmModal');
    },

    /* ========================================================
       UTILITIES
       ======================================================== */
    togglePasswordVisibility(inputId, btn) {
        const input = document.getElementById(inputId);
        if (!input) return;

        const isPassword = input.type === 'password';
        input.type = isPassword ? 'text' : 'password';

        const svg = btn.querySelector('svg');
        if (svg) {
            svg.innerHTML = isPassword
                ? '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>'
                : '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>';
        }
    },

    escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
};

// ---- Boot ----
document.addEventListener('DOMContentLoaded', () => AdminPanel.init());
