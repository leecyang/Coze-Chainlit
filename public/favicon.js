// Set custom favicon and welcome screen logo for 灵犀智学
document.addEventListener('DOMContentLoaded', function () {
    // Remove existing favicon
    const existingFavicons = document.querySelectorAll('link[rel*="icon"]');
    existingFavicons.forEach(favicon => favicon.remove());

    // Create new favicon link - 使用 logo_backup.svg
    const link = document.createElement('link');
    link.rel = 'icon';
    link.type = 'image/svg+xml';
    link.href = '/public/logo_backup.svg';
    document.head.appendChild(link);

    // Also add shortcut icon
    const shortcutLink = document.createElement('link');
    shortcutLink.rel = 'shortcut icon';
    shortcutLink.type = 'image/svg+xml';
    shortcutLink.href = '/public/logo_backup.svg';
    document.head.appendChild(shortcutLink);

    // Set page title
    document.title = '灵犀智学';

    // 修改欢迎屏幕的 logo 为带文字的版本
    const welcomeScreenImg = document.querySelector("#welcome-screen > img");
    if (welcomeScreenImg) {
        welcomeScreenImg.src = '/public/logo_full_text.svg';
        welcomeScreenImg.alt = '灵犀智学';
        // 设置合适的宽度
        welcomeScreenImg.style.width = '280px';
        welcomeScreenImg.style.maxWidth = '75%';
        welcomeScreenImg.style.height = 'auto';
        // 防止图片被拖拽和复制
        welcomeScreenImg.draggable = false;
        welcomeScreenImg.style.userSelect = 'none';
        welcomeScreenImg.style.pointerEvents = 'none';
        welcomeScreenImg.addEventListener('contextmenu', (e) => e.preventDefault());
    }

    // 修改登录页面右侧大图
    const loginHeroImg = document.querySelector("#root > div.grid.min-h-svh.lg\\:grid-cols-2 > div.relative.hidden.bg-muted.lg\\:block.overflow-hidden > img");
    if (loginHeroImg) {
        loginHeroImg.src = '/public/hero.png';
        loginHeroImg.alt = '灵犀智学';
    }

    // 修改登录页面左上角的 logo
    const loginLogoImg = document.querySelector("#root > div.grid.min-h-svh.lg\\:grid-cols-2 > div.flex.flex-col.gap-4.p-6.md\\:p-10 > div.flex.justify-center.gap-2.md\\:justify-start > img");
    if (loginLogoImg) {
        loginLogoImg.src = '/public/logo_full_text.svg';
        loginLogoImg.alt = '灵犀智学';
        // 防止图片被拖拽和复制
        loginLogoImg.draggable = false;
        loginLogoImg.style.userSelect = 'none';
        loginLogoImg.addEventListener('contextmenu', (e) => e.preventDefault());
    }

    // 替换 starter 图标为 Lucide SVG 图标
    replaceStarterIcons();
});

// Lucide SVG 图标定义
const lucideIcons = {
    bookOpen: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#9242eb" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>`,
    lightbulb: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#9242eb" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/></svg>`,
    network: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#9242eb" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="16" y="16" width="6" height="6" rx="1"/><rect x="2" y="16" width="6" height="6" rx="1"/><rect x="9" y="2" width="6" height="6" rx="1"/><path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3"/><path d="M12 12V8"/></svg>`,
    globe: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#9242eb" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg>`
};

// 替换 starter 图标
function replaceStarterIcons() {
    // 通过文本内容匹配 starter 按钮
    const starterMappings = [
        { text: '考试大纲', icon: lucideIcons.bookOpen },
        { text: '备考建议', icon: lucideIcons.lightbulb },
        { text: '网络基础', icon: lucideIcons.network },
        { text: 'IP地址', icon: lucideIcons.globe }
    ];

    // 查找所有可能的 starter 按钮
    const allButtons = document.querySelectorAll('button');

    allButtons.forEach(button => {
        const buttonText = button.textContent.trim();

        starterMappings.forEach(mapping => {
            if (buttonText === mapping.text || buttonText.includes(mapping.text)) {
                // 查找按钮内的 img 元素
                const imgElement = button.querySelector('img');
                if (imgElement && !button.dataset.iconReplaced) {
                    // 创建一个新的 div 来放置 SVG
                    const svgContainer = document.createElement('div');
                    svgContainer.innerHTML = mapping.icon;
                    svgContainer.style.width = '24px';
                    svgContainer.style.height = '24px';
                    svgContainer.style.display = 'flex';
                    svgContainer.style.alignItems = 'center';
                    svgContainer.style.justifyContent = 'center';
                    svgContainer.style.flexShrink = '0';

                    // 替换 img 元素
                    imgElement.parentNode.replaceChild(svgContainer, imgElement);

                    // 设置按钮样式使文字垂直居中
                    button.style.display = 'flex';
                    button.style.alignItems = 'center';
                    button.style.justifyContent = 'center';
                    button.style.gap = '8px';

                    // 查找内部 flex 容器并设置居中
                    const innerFlex = button.querySelector('.flex');
                    if (innerFlex) {
                        innerFlex.style.display = 'flex';
                        innerFlex.style.alignItems = 'center';
                        innerFlex.style.justifyContent = 'center';
                    }

                    // 查找文字元素并调整样式
                    const textElement = button.querySelector('p');
                    if (textElement) {
                        textElement.style.margin = '0';
                        textElement.style.lineHeight = '1';
                        textElement.style.display = 'flex';
                        textElement.style.alignItems = 'center';
                    }

                    // 标记已替换，避免重复处理
                    button.dataset.iconReplaced = 'true';
                }
            }
        });
    });
}

// 监听 DOM 变化，以防欢迎屏幕是动态加载的
const observer = new MutationObserver(function (mutations) {
    const welcomeScreenImg = document.querySelector("#welcome-screen > img");
    if (welcomeScreenImg && !welcomeScreenImg.src.includes('logo_full_text.svg')) {
        welcomeScreenImg.src = '/public/logo_full_text.svg';
        welcomeScreenImg.alt = '灵犀智学';
        welcomeScreenImg.style.width = '280px';
        welcomeScreenImg.style.maxWidth = '75%';
        welcomeScreenImg.style.height = 'auto';
        // 防止图片被拖拽和复制
        welcomeScreenImg.draggable = false;
        welcomeScreenImg.style.userSelect = 'none';
        welcomeScreenImg.style.pointerEvents = 'none';
        welcomeScreenImg.addEventListener('contextmenu', (e) => e.preventDefault());
    }

    // 监听登录页面右侧大图
    const loginHeroImg = document.querySelector("#root > div.grid.min-h-svh.lg\\:grid-cols-2 > div.relative.hidden.bg-muted.lg\\:block.overflow-hidden > img");
    if (loginHeroImg && !loginHeroImg.src.includes('hero.png')) {
        loginHeroImg.src = '/public/hero.png';
        loginHeroImg.alt = '灵犀智学';
    }

    // 监听登录页面左上角的 logo
    const loginLogoImg = document.querySelector("#root > div.grid.min-h-svh.lg\\:grid-cols-2 > div.flex.flex-col.gap-4.p-6.md\\:p-10 > div.flex.justify-center.gap-2.md\\:justify-start > img");
    if (loginLogoImg && !loginLogoImg.src.includes('logo_full_text.svg')) {
        loginLogoImg.src = '/public/logo_full_text.svg';
        loginLogoImg.alt = '灵犀智学';
        // 防止图片被拖拽和复制
        loginLogoImg.draggable = false;
        loginLogoImg.style.userSelect = 'none';
        loginLogoImg.addEventListener('contextmenu', (e) => e.preventDefault());
    }

    // 监听并替换 starter 图标
    replaceStarterIcons();

    // 添加打字指示器监听
    observeTypingIndicator();
});

// 打字指示器功能
function observeTypingIndicator() {
    let typingIndicator = null;
    let processedSteps = new Set();

    // 监听消息列表的变化
    const messageObserver = new MutationObserver(function (mutations) {
        // 查找所有 step 元素 - Chainlit 使用 id="step-xxx" 格式
        const allSteps = document.querySelectorAll('[id^="step-"]');

        if (allSteps.length === 0) return;

        // 获取最后一条 step
        const lastStep = allSteps[allSteps.length - 1];
        const stepId = lastStep.id;

        // 检查是否是助手消息 - 通过查找消息作者
        const authorElement = lastStep.querySelector('[data-testid="author-name"], .author-name, [class*="author"]');
        const authorName = authorElement ? authorElement.textContent.trim() : '';

        // 检查头像或作者名称
        const isAssistant = authorName === '计算机三级网络小助手' ||
            lastStep.textContent.includes('计算机三级网络小助手') ||
            lastStep.querySelector('img[src*="logo_backup"]') !== null;

        if (isAssistant) {
            // 查找消息内容区域 - 排除头像区域，找到文本内容区域
            // 通常消息结构是：头像 + 内容区域
            const messageContainer = lastStep.querySelector('[class*="message"], [class*="Message"], .step-body, [class*="body"]') || lastStep;

            // 查找文本内容区域（头像右侧的区域）
            const content = messageContainer.querySelector('[class*="content"]:not([class*="avatar"]), [class*="text"], [class*="body"] > div:last-child, .message-content') ||
                messageContainer.querySelector('div:nth-child(2)') ||
                messageContainer;

            if (content) {
                // 获取文本内容（排除打字指示器）
                let text = content.innerText || content.textContent || '';
                text = text.replace(/\s/g, '');

                // 检查是否已经有打字指示器
                const hasIndicator = content.querySelector('.typing-indicator') !== null;

                // 如果内容为空且没有指示器，添加指示器
                if (text.length === 0 && !hasIndicator && !processedSteps.has(stepId)) {
                    // 移除之前可能存在的指示器
                    if (typingIndicator && typingIndicator.parentNode) {
                        typingIndicator.remove();
                    }

                    typingIndicator = createTypingIndicator();

                    // 将指示器添加到内容区域
                    content.appendChild(typingIndicator);

                    // 设置内容区域样式
                    content.style.position = 'relative';

                    processedSteps.add(stepId);

                    // 确保消息可见
                    lastStep.style.display = 'block';
                    lastStep.style.visibility = 'visible';
                    lastStep.style.opacity = '1';
                }

                // 如果内容不为空且有指示器，移除指示器
                if (text.length > 0 && hasIndicator) {
                    const existingIndicator = content.querySelector('.typing-indicator');
                    if (existingIndicator) {
                        existingIndicator.remove();
                    }
                    typingIndicator = null;
                }
            }
        }
    });

    // 监听整个文档的变化
    messageObserver.observe(document.body, {
        childList: true,
        subtree: true,
        characterData: true
    });
}

// 创建打字指示器元素
function createTypingIndicator() {
    const indicator = document.createElement('div');
    indicator.className = 'typing-indicator';
    indicator.innerHTML = `
        <span class="dot"></span>
        <span class="dot"></span>
        <span class="dot"></span>
    `;
    return indicator;
}

// 开始监听 DOM 变化
observer.observe(document.body, {
    childList: true,
    subtree: true
});

// ==================== 管理员后台按钮与面板 ====================

(function () {
    let adminBtnInjected = false;
    let adminPanelOpen = false;
    let lastAuthCheck = 0;

    console.log('[Admin] Admin panel module loaded');

    // 检查用户是否为管理员并注入按钮
    async function checkAndInjectAdminButton() {
        // 如果已经验证过是管理员，直接注入按钮
        if (adminBtnInjected === 'verified') {
            injectAdminButton();
            return;
        }

        // 防止频繁请求（至少间隔 2 秒）
        const now = Date.now();
        if (now - lastAuthCheck < 2000) {
            return;
        }
        lastAuthCheck = now;

        try {
            const response = await fetch('/api/admin/auth/check', {
                credentials: 'same-origin',
                headers: { 'Accept': 'application/json' }
            });
            if (!response.ok) {
                console.log('[Admin] Auth check returned status:', response.status);
                return;
            }
            const data = await response.json();
            console.log('[Admin] Auth check result:', data);
            if (data.is_admin) {
                adminBtnInjected = 'verified'; // 标记为已验证的管理员
                injectAdminButton();
                console.log('[Admin] Admin button injected successfully');
            }
        } catch (e) {
            console.log('[Admin] Auth check failed:', e.message);
        }
    }

    // 注入管理后台按钮 - 放在用户下拉菜单中
    function injectAdminButton() {
        // 查找用户下拉菜单
        const userMenu = document.querySelector('[role="menu"][data-radix-menu-content]');
        if (!userMenu) {
            console.log('[Admin] User menu not found, will retry...');
            return;
        }

        // 检查是否已经注入
        if (userMenu.querySelector('#admin-menu-item')) {
            return;
        }

        // 查找"退出登录"按钮
        const logoutBtn = Array.from(userMenu.querySelectorAll('[role="menuitem"]')).find(item =>
            item.textContent.includes('退出登录') || item.textContent.includes('Logout')
        );

        if (!logoutBtn) {
            console.log('[Admin] Logout button not found in menu');
            return;
        }

        // 创建管理后台菜单项
        const adminMenuItem = document.createElement('div');
        adminMenuItem.id = 'admin-menu-item';
        adminMenuItem.setAttribute('role', 'menuitem');
        adminMenuItem.setAttribute('tabindex', '-1');
        adminMenuItem.setAttribute('data-orientation', 'vertical');
        adminMenuItem.setAttribute('data-radix-collection-item', '');
        adminMenuItem.className = logoutBtn.className; // 复用退出登录按钮的样式类

        adminMenuItem.innerHTML = `
            <span>管理后台</span>
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-settings ml-auto" aria-hidden="true">
                <circle cx="12" cy="12" r="3"/>
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
            </svg>
        `;

        // 添加点击事件 - 直接跳转到 /admin 页面
        adminMenuItem.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            window.location.href = '/admin';
        });

        // 在退出登录按钮之前插入
        logoutBtn.parentNode.insertBefore(adminMenuItem, logoutBtn);

        console.log('[Admin] Admin menu item injected successfully');
    }

    // 切换管理后台面板
    function toggleAdminPanel() {
        if (adminPanelOpen) {
            closeAdminPanel();
        } else {
            openAdminPanel();
        }
    }

    // 打开管理后台面板
    function openAdminPanel() {
        if (document.getElementById('admin-panel-overlay')) return;

        const overlay = document.createElement('div');
        overlay.id = 'admin-panel-overlay';
        overlay.className = 'admin-panel-overlay';
        overlay.addEventListener('click', closeAdminPanel);

        const panel = document.createElement('div');
        panel.id = 'admin-panel-container';
        panel.className = 'admin-panel-container';

        const panelHeader = document.createElement('div');
        panelHeader.className = 'admin-panel-header';
        panelHeader.innerHTML = `
            <div class="admin-panel-title">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#9242eb" stroke-width="2">
                    <circle cx="12" cy="12" r="3"/>
                    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
                </svg>
                <span>管理后台</span>
            </div>
            <div class="admin-panel-actions">
                <button class="admin-panel-refresh-btn" title="刷新">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="23 4 23 10 17 10"/>
                        <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
                    </svg>
                </button>
                <button class="admin-panel-close-btn" title="关闭 (ESC)">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"/>
                        <line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                </button>
            </div>
        `;

        panelHeader.querySelector('.admin-panel-close-btn').addEventListener('click', closeAdminPanel);
        panelHeader.querySelector('.admin-panel-refresh-btn').addEventListener('click', function () {
            const iframe = document.getElementById('admin-panel-iframe');
            if (iframe) iframe.contentWindow.location.reload();
        });

        const iframe = document.createElement('iframe');
        iframe.id = 'admin-panel-iframe';
        iframe.className = 'admin-panel-iframe';
        iframe.src = '/admin';
        iframe.setAttribute('frameborder', '0');

        panel.appendChild(panelHeader);
        panel.appendChild(iframe);
        document.body.appendChild(overlay);
        document.body.appendChild(panel);

        requestAnimationFrame(() => {
            overlay.classList.add('active');
            panel.classList.add('active');
        });

        adminPanelOpen = true;
        document.addEventListener('keydown', handleEscKey);
    }

    // 关闭管理后台面板
    function closeAdminPanel() {
        const overlay = document.getElementById('admin-panel-overlay');
        const panel = document.getElementById('admin-panel-container');

        if (overlay) overlay.classList.remove('active');
        if (panel) panel.classList.remove('active');

        setTimeout(() => {
            if (overlay) overlay.remove();
            if (panel) panel.remove();
        }, 300);

        adminPanelOpen = false;
        document.removeEventListener('keydown', handleEscKey);
    }

    function handleEscKey(e) {
        if (e.key === 'Escape') closeAdminPanel();
    }

    // 监听 DOM 变化，检测用户菜单打开
    const adminObserver = new MutationObserver(function (mutations) {
        // 检测用户是否已登录
        const userNavBtn = document.getElementById('user-nav-button');
        if (!userNavBtn) {
            // 如果用户按钮消失了，重置状态（可能是页面切换）
            if (adminBtnInjected === 'verified') {
                console.log('[Admin] User nav button disappeared, will re-inject on next menu open');
            }
            return;
        }

        // 检测用户菜单是否打开
        const userMenu = document.querySelector('[role="menu"][data-radix-menu-content][data-state="open"]');
        if (userMenu) {
            console.log('[Admin] User menu opened, checking admin status...');
            checkAndInjectAdminButton();
        }
    });

    adminObserver.observe(document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['data-state']
    });

    // 监听用户按钮点击，在菜单打开时注入
    document.addEventListener('click', function (e) {
        const userNavBtn = document.getElementById('user-nav-button');
        if (userNavBtn && (e.target === userNavBtn || userNavBtn.contains(e.target))) {
            setTimeout(() => {
                const userMenu = document.querySelector('[role="menu"][data-radix-menu-content][data-state="open"]');
                if (userMenu) {
                    console.log('[Admin] User menu clicked, checking admin status...');
                    checkAndInjectAdminButton();
                }
            }, 100);
        }
    });

    // 监听浏览器历史记录变化（前进/后退）
    window.addEventListener('popstate', function () {
        console.log('[Admin] Browser navigation detected (popstate)');
        // 页面导航后，菜单会重新渲染，需要重新注入
        // 不重置 adminBtnInjected，保持 'verified' 状态
    });

    // 监听 Chainlit 的路由变化（如果有的话）
    const originalPushState = history.pushState;
    const originalReplaceState = history.replaceState;

    history.pushState = function () {
        originalPushState.apply(this, arguments);
        console.log('[Admin] History pushState detected');
        // 路由变化后，菜单会重新渲染
    };

    history.replaceState = function () {
        originalReplaceState.apply(this, arguments);
        console.log('[Admin] History replaceState detected');
    };

    // 首次检查（如果页面已有 user-nav-button）
    setTimeout(() => {
        if (document.getElementById('user-nav-button')) {
            console.log('[Admin] #user-nav-button found on init');
        }
    }, 1000);
})();

// ==================== 人设选择器模块（Persona Selector） ====================
(function () {
    'use strict';

    let selectorInjected = false;
    let dropdownOpen = false;
    let currentRole = '';

    // 人设配置列表（仅三个可选人设，无默认选项）
    const PERSONAS = [
        {
            value: '计网专家',
            name: '计网专家',
            desc: '权威导师细致精讲，<br>带你吃透知识点',
            iconClass: 'expert',
            // Lucide: Network
            iconSvg: '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="16" y="16" width="6" height="6" rx="1"/><rect x="2" y="16" width="6" height="6" rx="1"/><rect x="9" y="2" width="6" height="6" rx="1"/><path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3"/><path d="M12 12V8"/></svg>'
        },
        {
            value: '辩论对手',
            name: '辩论对手',
            desc: '犀利反驳寻找漏洞，<br>激发批判性深思',
            iconClass: 'debater',
            // Lucide: Swords
            iconSvg: '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="14.5 17.5 3 6 3 3 6 3 17.5 14.5"/><line x1="13" x2="19" y1="19" y2="13"/><line x1="16" x2="20" y1="16" y2="20"/><line x1="19" x2="21" y1="21" y2="19"/><polyline points="14.5 6.5 18 3 21 3 21 6 17.5 9.5"/><line x1="5" x2="9" y1="14" y2="18"/><line x1="7" x2="4" y1="17" y2="20"/><line x1="3" x2="5" y1="19" y2="21"/></svg>'
        },
        {
            value: '新手小白',
            name: '新手小白',
            desc: '化身萌新向你提问，<br>以教代学强输出',
            iconClass: 'beginner',
            // Lucide: GraduationCap
            iconSvg: '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z"/><path d="M22 10v6"/><path d="M6 12.5V16a6 3 0 0 0 12 0v-3.5"/></svg>'
        }
    ];

    // Lucide SVG 图标
    const ICONS = {
        // User 图标（触发按钮）
        user: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
        // ChevronDown 箭头
        chevron: '<svg class="persona-chevron" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>',
        // Check 勾号
        check: '<svg class="persona-check" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>'
    };

    // 从 localStorage 恢复上一次的选择，如果没有保存过，默认使用"计网专家"
    function loadSavedRole() {
        try {
            const saved = localStorage.getItem('lingxi_target_role');
            if (saved !== null && saved !== '') {
                currentRole = saved;
            } else {
                // 用户未主动选择过人设，使用默认人设"计网专家"
                currentRole = '计网专家';
                saveRole(currentRole);
            }
        } catch (e) {
            console.warn('[Persona] Failed to load saved role:', e);
            currentRole = '计网专家';
        }
    }

    // 保存选择到 localStorage
    function saveRole(role) {
        try {
            localStorage.setItem('lingxi_target_role', role);
        } catch (e) {
            console.warn('[Persona] Failed to save role:', e);
        }
    }

    // 同步选择到后端 API
    async function syncRoleToBackend(role) {
        try {
            const response = await fetch('/api/target-role', {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify({ target_role: role })
            });
            if (!response.ok) {
                console.warn('[Persona] Backend sync failed:', response.status);
            } else {
                const data = await response.json();
                console.log('[Persona] 人设已同步:', data.target_role || '默认');
            }
        } catch (e) {
            console.warn('[Persona] Backend sync error:', e);
        }
    }

    // 从后端读取当前状态（页面加载时同步）
    async function syncRoleFromBackend() {
        try {
            const response = await fetch('/api/target-role', {
                credentials: 'same-origin',
                headers: { 'Accept': 'application/json' }
            });
            if (response.ok) {
                const data = await response.json();
                if (data.target_role !== undefined && data.target_role !== currentRole) {
                    currentRole = data.target_role;
                    saveRole(currentRole);
                    updateButtonState();
                }
            }
        } catch (e) {
            // 静默失败，使用 localStorage 的值
        }
    }

    // 创建选择器 DOM
    function createSelector() {
        const wrapper = document.createElement('div');
        wrapper.className = 'persona-selector-wrapper';
        wrapper.id = 'persona-selector';

        // 触发按钮
        const btn = document.createElement('button');
        btn.className = 'persona-trigger-btn';
        btn.type = 'button';
        btn.setAttribute('aria-label', '选择对话人设');
        btn.setAttribute('aria-haspopup', 'true');
        btn.setAttribute('aria-expanded', 'false');
        btn.title = '选择对话人设';
        btn.innerHTML = `
            ${ICONS.user}
            <span class="persona-label"></span>
            ${ICONS.chevron}
            <span class="persona-dot"></span>
        `;

        // 点击切换下拉菜单
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            toggleDropdown();
        });

        // 下拉菜单
        const dropdown = document.createElement('div');
        dropdown.className = 'persona-dropdown';
        dropdown.id = 'persona-dropdown';
        dropdown.setAttribute('role', 'listbox');
        dropdown.setAttribute('aria-label', '对话人设列表');

        // 菜单标题
        const title = document.createElement('div');
        title.className = 'persona-dropdown-title';
        title.textContent = '选择对话人设';
        dropdown.appendChild(title);

        // 添加选项
        PERSONAS.forEach((persona, index) => {
            const option = document.createElement('div');
            option.className = 'persona-option' + (persona.value === currentRole ? ' selected' : '');
            option.setAttribute('role', 'option');
            option.setAttribute('aria-selected', persona.value === currentRole ? 'true' : 'false');
            option.setAttribute('data-value', persona.value);
            option.setAttribute('tabindex', '0');
            option.innerHTML = `
                <div class="persona-option-icon ${persona.iconClass}">
                    ${persona.iconSvg}
                </div>
                <div class="persona-option-text">
                    <div class="persona-option-name">${persona.name}</div>
                    <div class="persona-option-desc">${persona.desc}</div>
                </div>
                ${ICONS.check}
            `;

            option.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                selectRole(persona.value);
            });

            // 键盘支持
            option.addEventListener('keydown', function (e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    selectRole(persona.value);
                }
            });

            dropdown.appendChild(option);
        });

        wrapper.appendChild(btn);
        wrapper.appendChild(dropdown);

        return wrapper;
    }

    // 切换下拉菜单
    function toggleDropdown() {
        if (dropdownOpen) {
            closeDropdown();
        } else {
            openDropdown();
        }
    }

    function openDropdown() {
        const btn = document.querySelector('.persona-trigger-btn');
        const dropdown = document.getElementById('persona-dropdown');
        if (!btn || !dropdown) return;

        btn.classList.add('active');
        btn.setAttribute('aria-expanded', 'true');
        dropdown.classList.add('open');
        dropdownOpen = true;

        // 延迟添加全局关闭监听
        setTimeout(() => {
            document.addEventListener('click', handleOutsideClick);
            document.addEventListener('keydown', handleEscapeKey);
        }, 10);
    }

    function closeDropdown() {
        const btn = document.querySelector('.persona-trigger-btn');
        const dropdown = document.getElementById('persona-dropdown');
        if (!btn || !dropdown) return;

        btn.classList.remove('active');
        btn.setAttribute('aria-expanded', 'false');
        dropdown.classList.remove('open');
        dropdownOpen = false;

        document.removeEventListener('click', handleOutsideClick);
        document.removeEventListener('keydown', handleEscapeKey);
    }

    function handleOutsideClick(e) {
        const wrapper = document.getElementById('persona-selector');
        if (wrapper && !wrapper.contains(e.target)) {
            closeDropdown();
        }
    }

    function handleEscapeKey(e) {
        if (e.key === 'Escape') {
            closeDropdown();
        }
    }

    // 选择人设
    function selectRole(roleValue) {
        currentRole = roleValue;
        saveRole(roleValue);
        syncRoleToBackend(roleValue);
        updateButtonState();
        updateOptionStates();
        closeDropdown();
    }

    // 更新触发按钮的显示状态
    function updateButtonState() {
        const label = document.querySelector('.persona-label');
        const dot = document.querySelector('.persona-dot');
        if (!label || !dot) return;

        if (currentRole) {
            label.textContent = currentRole;
            dot.classList.add('visible');
        } else {
            label.textContent = '';
            dot.classList.remove('visible');
        }
    }

    // 更新选项选中状态
    function updateOptionStates() {
        const options = document.querySelectorAll('.persona-option');
        options.forEach(option => {
            const value = option.getAttribute('data-value');
            if (value === currentRole) {
                option.classList.add('selected');
                option.setAttribute('aria-selected', 'true');
            } else {
                option.classList.remove('selected');
                option.setAttribute('aria-selected', 'false');
            }
        });
    }

    // 注入选择器到 DOM
    function injectSelector() {
        const uploadBtn = document.getElementById('upload-button');
        if (!uploadBtn) return;

        // 找到附件按钮的父容器
        const parentContainer = uploadBtn.parentElement;
        if (!parentContainer) return;

        // 如果附件按钮旁已经有选择器了，退出
        if (uploadBtn.nextElementSibling && uploadBtn.nextElementSibling.id === 'persona-selector') {
            return;
        }

        // 清理页面上因为 React DOM 重绘残留的旧选择器节点
        const oldSelector = document.getElementById('persona-selector');
        if (oldSelector) {
            oldSelector.remove();
        }

        const selector = createSelector();
        // 在附件按钮之后插入
        uploadBtn.insertAdjacentElement('afterend', selector);

        updateButtonState();

        if (!selectorInjected) {
            selectorInjected = true;
            console.log('[Persona] 人设选择器已初始注入');
            // 页面首次加载且注入后，同步后端状态
            syncRoleFromBackend();
        } else {
            console.log('[Persona] 人设选择器因页面切换已重新注入');
            updateOptionStates();
        }
    }

    // 初始化
    loadSavedRole();

    // 使用 MutationObserver 监听 upload-button 出现 (处理 SPA 页面切换)
    const personaObserver = new MutationObserver(function () {
        const uploadBtn = document.getElementById('upload-button');
        if (uploadBtn) {
            // 检查当前新的 uploadBtn 旁边是否有选择器
            if (!uploadBtn.nextElementSibling || uploadBtn.nextElementSibling.id !== 'persona-selector') {
                injectSelector();
            }
        }
    });

    personaObserver.observe(document.body, {
        childList: true,
        subtree: true
    });

    // 如果按钮已经存在，直接注入
    if (document.getElementById('upload-button')) {
        injectSelector();
    }

    console.log('[Persona] 人设选择器模块已加载');
})();

// ==================== 动态加载排行榜模块 ====================
(function () {
    const lbScript = document.createElement('script');
    lbScript.src = '/public/leaderboard.js';
    lbScript.async = true;
    document.head.appendChild(lbScript);
    console.log('[Loader] 排行榜模块已动态加载');
})();

// ==================== 题目卡片模块（已禁用，展示原始文字） ====================
// (function () {
//     const qcScript = document.createElement('script');
//     qcScript.src = '/public/quiz-card.js';
//     qcScript.async = true;
//     document.head.appendChild(qcScript);
//     console.log('[Loader] 题目卡片模块已动态加载');
// })();

// ==================== ICP备案信息注入 ====================
(function () {
    function injectICP() {
        if (document.getElementById('icp-footer')) return;
        
        const footer = document.createElement('div');
        footer.id = 'icp-footer';
        footer.style.position = 'fixed';
        footer.style.bottom = '0';
        footer.style.left = '0';
        footer.style.width = '100%';
        footer.style.height = '28px';
        footer.style.display = 'flex';
        footer.style.alignItems = 'center';
        footer.style.justifyContent = 'center';
        footer.style.fontSize = '12px';
        footer.style.color = '#888';
        footer.style.zIndex = '999999';
        footer.style.pointerEvents = 'none';
        footer.style.backgroundColor = 'var(--background, var(--bg-paper, rgba(255,255,255,0.8)))';
        footer.style.backdropFilter = 'blur(4px)';
        footer.style.borderTop = '1px solid rgba(146, 66, 235, 0.1)';
        
        // 关键样式：避免在移动端因为屏幕过窄导致换行
        footer.style.whiteSpace = 'nowrap';
        footer.style.flexWrap = 'nowrap';
        // 为了能在极小屏幕完整显示，使用一个较小的字号限制以及容差
        if (window.innerWidth < 400) {
            footer.style.fontSize = '10px';
            footer.style.gap = '4px';
        } else {
            footer.style.gap = '12px';
        }

        // ICP 备案链接
        const link = document.createElement('a');
        link.href = 'https://beian.miit.gov.cn/';
        link.target = '_blank';
        link.textContent = '蒙ICP备2025033227号-3';
        link.style.color = '#888';
        link.style.textDecoration = 'none';
        link.style.pointerEvents = 'auto'; // 允许点击
        
        // 公安备案 wrapper
        const mpsWrapper = document.createElement('div');
        mpsWrapper.style.display = 'flex';
        mpsWrapper.style.alignItems = 'center';
        mpsWrapper.style.gap = '4px';

        const mpsIcon = document.createElement('img');
        mpsIcon.src = '/public/备案图标.png';
        // 原生固定一个小巧好看的体积
        mpsIcon.style.width = '14px';
        mpsIcon.style.height = '14px';
        mpsIcon.style.display = 'block';

        const mpsLink = document.createElement('a');
        mpsLink.href = 'https://beian.mps.gov.cn/#/query/webSearch?code=15020302000647';
        mpsLink.rel = 'noreferrer';
        mpsLink.target = '_blank';
        mpsLink.textContent = '蒙公网安备15020302000647号';
        mpsLink.style.color = '#888';
        mpsLink.style.textDecoration = 'none';
        mpsLink.style.pointerEvents = 'auto';

        mpsWrapper.appendChild(mpsIcon);
        mpsWrapper.appendChild(mpsLink);
        
        // 添加悬停效果
        link.addEventListener('mouseenter', () => link.style.color = '#9242eb');
        link.addEventListener('mouseleave', () => link.style.color = '#888');
        mpsLink.addEventListener('mouseenter', () => mpsLink.style.color = '#9242eb');
        mpsLink.addEventListener('mouseleave', () => mpsLink.style.color = '#888');
        
        // 当窗口变化时自适应
        window.addEventListener('resize', () => {
             if (window.innerWidth < 400) {
                 footer.style.fontSize = '10px';
                 footer.style.gap = '4px';
             } else {
                 footer.style.fontSize = '12px';
                 footer.style.gap = '12px';
             }
        });

        footer.appendChild(link);
        footer.appendChild(mpsWrapper);
        document.body.appendChild(footer);
        
        // 给 body 添加标识类，便于 theme.css 进行总体高度缩减，防止 ICP 遮挡页面内容
        document.body.classList.add('has-icp');
    }
    
    // DOMContentLoaded时注入
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', injectICP);
    } else {
        injectICP();
    }
    
    // 使用 MutationObserver 确保如果在页面跳转或重新渲染时丢失的话自动重新添加
    const observer = new MutationObserver(function() {
        if (!document.getElementById('icp-footer')) {
            injectICP();
        }
    });
    
    // 只在 document.body 准备好的时候开始观察
    if (document.body) {
        observer.observe(document.body, { childList: true, subtree: true });
    } else {
        document.addEventListener('DOMContentLoaded', () => {
            observer.observe(document.body, { childList: true, subtree: true });
        });
    }
})();
