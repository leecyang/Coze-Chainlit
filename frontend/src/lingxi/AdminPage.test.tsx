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
  vi.mocked(lingxiFetch).mockImplementation((url: string, options?: RequestInit) => {
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
        bot_id: 'bot',
        base_url: 'https://api.example.test',
        has_service_token: true,
        masked_service_token: 'abcd********wxyz',
        jwt_expires_at: null
      });
    }
    if (url.startsWith('/api/admin/audit')) return Promise.resolve(page);
    return Promise.resolve({});
  });
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
    await screen.findByText('Coze 配置');
    fireEvent.click(screen.getByRole('button', { name: '保存配置' }));

    await waitFor(() => {
      const configCall = vi
        .mocked(lingxiFetch)
        .mock.calls.find(([url, options]) => url === '/api/admin/config' && options?.method === 'PUT');
      expect(configCall).toBeTruthy();
      expect(JSON.parse(String(configCall?.[1]?.body))).not.toHaveProperty('service_token');
    });
  });
});
