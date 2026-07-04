export async function lingxiFetch<T>(
  url: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(url, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {})
    },
    ...options
  });

  const contentType = response.headers.get('content-type') || '';
  const body = contentType.includes('application/json')
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const message =
      typeof body === 'object' && body && 'error' in body
        ? String((body as { error: unknown }).error)
        : `HTTP ${response.status}`;
    throw new Error(message);
  }

  return body as T;
}

export type TargetRole = '新手小白' | '辩论对手' | '计网专家';

export type LeaderboardEntry = {
  rank?: number;
  username: string;
  total_score: number;
  highest_score?: number;
  practice_count?: number;
  updated_at?: string;
};

export type AdminUser = {
  username: string;
  role: 'admin' | 'user';
  created_at?: string;
  last_login?: string;
  conversation_count?: number;
  practice_count?: number;
  total_score?: number;
  highest_score?: number;
};

export type Paginated<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
};

export type AdminActivity = {
  id?: number;
  actor?: string;
  action: string;
  target?: string;
  detail?: string;
  created_at: string;
};

export type AdminOverview = {
  range: string;
  kpis: {
    total_users: number;
    normal_users: number;
    active_today: number;
    total_conversations: number;
    total_messages: number;
    practice_sessions: number;
    mistake_count: number;
    assignment_count: number;
  };
  daily: Array<{
    date: string;
    users: number;
    conversations: number;
    practices: number;
  }>;
  persona_stats: Array<{ name: string; count: number; percentage: number }>;
  today_active_users: Array<{ username: string; count: number }>;
  top_active_users: Array<{ username: string; count: number }>;
  conversation_depth: Record<string, number>;
  active_user_proportion: { active: number; total: number; percent: number };
  recent_activity: AdminActivity[];
  token_health?: {
    service_identity?: { valid?: boolean; available?: boolean };
    recommendation?: string;
  };
};

export type AdminConfig = {
  bot_id?: string;
  base_url?: string;
  jwt_expires_at?: number | null;
  has_service_token?: boolean;
  masked_service_token?: string;
  service_token?: string;
};

export type AdminConversation = {
  id: string;
  name?: string;
  username: string;
  persona: TargetRole | string;
  conversation_id?: string;
  message_count: number;
  created_at?: string;
};

export type AdminConversationMessage = {
  id: string;
  author: string;
  type: string;
  content: string;
  created_at?: string;
  metadata?: string;
};

export type AdminPracticeRecord = {
  id: number;
  username: string;
  score: number;
  correct_count: number;
  wrong_count: number;
  current_streak: number;
  created_at: string;
};

export type AdminMistake = {
  id: number;
  record_id: number;
  username: string;
  question_id: string;
  question_text: string;
  user_answer: string;
  correct_answer: string;
  analysis: string;
  created_at: string;
};

export type AdminAssignment = {
  id: number;
  username: string;
  score: number;
  feedback: string;
  created_at: string;
};

export type AdminUserDetail = {
  profile: AdminUser;
  summary: Record<string, number>;
  learning: {
    total_score: number;
    highest_score: number;
    practice_count: number;
    updated_at?: string;
  };
  activity: AdminActivity[];
  conversations: Array<{ id: string; name: string; created_at?: string }>;
  practices: AdminPracticeRecord[];
};
