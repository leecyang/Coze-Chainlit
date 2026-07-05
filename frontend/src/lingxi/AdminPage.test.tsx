import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import AdminPage from './AdminPage';
import { lingxiFetch } from './api';

vi.mock('./api', () => ({
  lingxiFetch: vi.fn()
}));

const page = { items: [], total: 0, page: 1, page_size: 12, total_pages: 0 };

function mockFetch(
  overrides: {
    agents?: unknown;
    topics?: unknown;
  } = {}
) {
  const handler = (url: string, options?: RequestInit) => {
    if (url === '/api/admin/auth/check') {
      return Promise.resolve({ is_admin: true, username: 'yang' });
    }
    if (url.startsWith('/api/admin/overview')) {
      return Promise.resolve({
        range: '7d',
        kpis: {
          total_users: 1,
          normal_users: 0,
          active_today: 0,
          total_conversations: 0,
          total_messages: 0,
          practice_sessions: 0,
          mistake_count: 0,
          assignment_count: 0
        },
        daily: [],
        persona_stats: [],
        today_active_users: [],
        top_active_users: [],
        conversation_depth: {},
        active_user_proportion: { active: 0, total: 0, percent: 0 },
        recent_activity: [],
        token_health: { service_identity: { available: false, valid: false } }
      });
    }
    if (url.startsWith('/api/admin/users')) return Promise.resolve({ ...page, users: [] });
    if (url.startsWith('/api/admin/conversations')) return Promise.resolve({ ...page, conversations: [] });
    if (url.startsWith('/api/admin/leaderboard')) {
      return Promise.resolve({
        leaderboard: [],
        stats: { total_participants: 0, highest_score: 0, avg_score: 0, today_sessions: 0 }
      });
    }
    if (url.startsWith('/api/admin/learning')) return Promise.resolve(page);
    if (url === '/api/admin/agents') {
      return Promise.resolve(overrides.agents || {
        agents: [],
        topics: []
      });
    }
    if (url === '/api/admin/topics') {
      return Promise.resolve(overrides.topics || {
        topics: [],
        keywords: { topic: {}, practice: {}, global: {} },
        settings: {}
      });
    }
    if (url === '/api/admin/config') {
      if (options?.method === 'PUT') return Promise.resolve({ success: true });
      return Promise.resolve({
        base_url: 'https://api.example.test',
        has_service_token: true,
        masked_service_token: 'abcd********wxyz',
        jwt_expires_at: null
      });
    }
    if (url.startsWith('/api/admin/audit')) return Promise.resolve(page);
    return Promise.resolve({});
  };
  vi.mocked(lingxiFetch).mockImplementation(handler);
  return handler;
}

describe('AdminPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders the operational dashboard with empty data', async () => {
    render(
      <MemoryRouter>
        <AdminPage />
      </MemoryRouter>
    );

    expect(await screen.findByText('灵犀管理后台')).toBeTruthy();
    expect(screen.getByText('总用户')).toBeTruthy();
    expect(screen.getByText('暂无趋势数据')).toBeTruthy();
  });

  it('surfaces overview load failures during initialization', async () => {
    const handler = mockFetch();
    vi.mocked(lingxiFetch).mockImplementation((url: string, options?: RequestInit) => {
      if (url.startsWith('/api/admin/overview')) {
        return Promise.reject(new Error('总览加载失败'));
      }
      return handler(url, options);
    });

    render(
      <MemoryRouter>
        <AdminPage />
      </MemoryRouter>
    );

    expect(await screen.findByText('总览加载失败')).toBeTruthy();
  });

  it('renders when agent and topic payloads omit array fields', async () => {
    vi.clearAllMocks();
    mockFetch({ agents: {}, topics: {} });

    render(
      <MemoryRouter>
        <AdminPage />
      </MemoryRouter>
    );

    expect(await screen.findByText('灵犀管理后台')).toBeTruthy();
    const agentsTab = screen.getAllByRole('tab', { name: '智能体' })[0];
    fireEvent.mouseDown(agentsTab);
    fireEvent.mouseUp(agentsTab);
    fireEvent.click(agentsTab);

    expect(await screen.findByText('暂无智能体，请先注册')).toBeTruthy();
    expect(screen.getByText('暂无 topic，请先维护路由词表')).toBeTruthy();
  });

  it('renders agent cards and opens the step-by-step registration wizard', async () => {
    vi.clearAllMocks();
    mockFetch({
      agents: {
        agents: [
          {
            agent_id: 'Network_Expert',
            display_name: '计网专家',
            description: '系统讲解、考试映射和规范推导。',
            agent_type: 'coze_chat',
            bot_id: '',
            enabled: true,
            system_builtin: true,
            locked: false,
            exclusive: false,
            priority: 10,
            context_policy: 'on_switch_recent_2',
            subscription_count: 1,
            subscriptions: [
              { topic: 'concept.explain', base_bid: 0.7, basic_bonus: 0, advanced_bonus: 0.1 }
            ]
          }
        ],
        topics: [
          {
            topic: 'concept.explain',
            display_name: '概念讲解',
            description: '',
            is_teaching: true,
            is_exclusive: false,
            route_priority: 40,
            enabled: true
          }
        ]
      }
    });

    render(
      <MemoryRouter>
        <AdminPage />
      </MemoryRouter>
    );

    expect(await screen.findByText('灵犀管理后台')).toBeTruthy();
    const agentsTab = screen.getAllByRole('tab', { name: '智能体' })[0];
    fireEvent.mouseDown(agentsTab);
    fireEvent.mouseUp(agentsTab);
    fireEvent.click(agentsTab);

    // 卡片墙：名称、运行状态、Bot 绑定与订阅置信度可视化
    expect(await screen.findByText('计网专家')).toBeTruthy();
    expect(screen.getByText('运行中')).toBeTruthy();
    expect(screen.getByText('未绑定专属 Bot')).toBeTruthy();
    expect(screen.getByText('概念讲解')).toBeTruthy();
    expect(screen.getByText('订阅与置信度')).toBeTruthy();

    // 注册入口打开分步向导
    fireEvent.click(screen.getByRole('button', { name: /注册智能体/ }));
    expect(await screen.findByText('注册新智能体')).toBeTruthy();
    expect(screen.getByText('基本信息')).toBeTruthy();
    expect(screen.getByText('Bot 绑定')).toBeTruthy();
    expect(screen.getByText('订阅与竞价')).toBeTruthy();
    expect(screen.getByText('确认提交')).toBeTruthy();

    // 第一步校验：Agent ID 为空时不能进入下一步
    fireEvent.click(screen.getByRole('button', { name: /下一步/ }));
    expect(
      await screen.findByText('Agent ID 需以英文字母开头，仅含字母、数字、下划线，长度 2-64')
    ).toBeTruthy();
  });

  it('does not overwrite the service token when config token input is empty', async () => {
    render(
      <MemoryRouter>
        <AdminPage />
      </MemoryRouter>
    );

    await screen.findByText('灵犀管理后台');
    const configTab = screen.getAllByRole('tab', { name: '配置' })[0];
    fireEvent.mouseDown(configTab);
    fireEvent.mouseUp(configTab);
    fireEvent.click(configTab);
    await screen.findByText('Coze 连接');
    expect(screen.queryByText('全局主 Bot ID')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '保存配置' }));

    await waitFor(() => {
      const configCall = vi
        .mocked(lingxiFetch)
        .mock.calls.find(([url, options]) => url === '/api/admin/config' && options?.method === 'PUT');
      expect(configCall).toBeTruthy();
      const payload = JSON.parse(String(configCall?.[1]?.body));
      expect(payload).not.toHaveProperty('service_token');
      expect(payload).not.toHaveProperty('bot_id');
      expect(payload).not.toHaveProperty('jwt_expires_at');
    });
  });
});
