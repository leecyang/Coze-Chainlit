import {
  Activity,
  BarChart3,
  BookOpen,
  CheckCircle2,
  Eye,
  FileText,
  KeyRound,
  Loader2,
  MessageSquareText,
  RefreshCw,
  Save,
  Search,
  Shield,
  Trash2,
  Upload,
  UserPlus,
  Users
} from 'lucide-react';
import { startTransition, useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle
} from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

import {
  AdminActivity,
  AdminAssignment,
  AdminConfig,
  AdminConversation,
  AdminConversationMessage,
  AdminMistake,
  AdminOverview,
  AdminPracticeRecord,
  AdminUser,
  AdminUserDetail,
  LeaderboardEntry,
  Paginated,
  lingxiFetch
} from './api';

type ConfirmState = {
  title: string;
  description: string;
  actionLabel?: string;
  onConfirm: () => Promise<void>;
} | null;

type ConversationDetail = {
  thread: AdminConversation & { metadata?: Record<string, unknown> };
  messages: AdminConversationMessage[];
};

type LeaderboardPayload = {
  leaderboard: LeaderboardEntry[];
  stats: {
    total_participants: number;
    highest_score: number;
    avg_score: number;
    today_sessions: number;
  };
};

type CsvPreviewRow = {
  username: string;
  password: string;
  role: string;
  line: number;
  error?: string;
};

const pageSize = 12;
const emptyLeaderboardStats = {
  total_participants: 0,
  highest_score: 0,
  avg_score: 0,
  today_sessions: 0
};

function query(params: Record<string, string | number | undefined>) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') search.set(key, String(value));
  });
  const value = search.toString();
  return value ? `?${value}` : '';
}

function formatTime(value?: string | number | null) {
  if (!value) return '-';
  if (typeof value === 'number') {
    return new Date(value * 1000).toLocaleString();
  }
  return value.replace('T', ' ').replace('Z', '');
}

function StatCard({
  title,
  value,
  icon: Icon,
  note
}: {
  title: string;
  value: string | number;
  icon: typeof Activity;
  note?: string;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-semibold">{value}</div>
        {note ? <p className="mt-1 text-xs text-muted-foreground">{note}</p> : null}
      </CardContent>
    </Card>
  );
}

function EmptyRow({ colSpan, text }: { colSpan: number; text: string }) {
  return (
    <TableRow>
      <TableCell colSpan={colSpan} className="h-24 text-center text-muted-foreground">
        {text}
      </TableCell>
    </TableRow>
  );
}

function Pager({
  page,
  totalPages,
  onPage
}: {
  page: number;
  totalPages: number;
  onPage: (page: number) => void;
}) {
  return (
    <div className="flex items-center justify-end gap-2 pt-3 text-sm">
      <span className="text-muted-foreground">
        第 {page} / {Math.max(totalPages, 1)} 页
      </span>
      <Button
        variant="outline"
        size="sm"
        disabled={page <= 1}
        onClick={() => onPage(page - 1)}
      >
        上一页
      </Button>
      <Button
        variant="outline"
        size="sm"
        disabled={!totalPages || page >= totalPages}
        onClick={() => onPage(page + 1)}
      >
        下一页
      </Button>
    </div>
  );
}

function ConversationDepthChart({ data }: { data?: Record<string, number> }) {
  const entries = Object.entries(data || {}).filter(([, count]) => count > 0);
  const total = entries.reduce((sum, [, count]) => sum + count, 0);
  const colors = ['#2563eb', '#10b981', '#f59e0b', '#ef4444'];
  let cursor = 0;
  const gradient = entries.length
    ? entries
        .map(([label, count], index) => {
          const start = cursor;
          cursor += (count / total) * 100;
          return `${colors[index % colors.length]} ${start}% ${cursor}%`;
        })
        .join(', ')
    : '#e5e7eb 0% 100%';

  return (
    <div className="grid gap-4 sm:grid-cols-[150px_1fr] sm:items-center">
      <div
        className="relative mx-auto grid aspect-square w-36 place-items-center rounded-full"
        style={{ background: `conic-gradient(${gradient})` }}
        aria-label="对话深度环形图"
      >
        <div className="grid h-20 w-20 place-items-center rounded-full bg-background text-center">
          <div>
            <div className="text-xl font-semibold">{total}</div>
            <div className="text-xs text-muted-foreground">对话</div>
          </div>
        </div>
      </div>
      <div className="space-y-2">
        {entries.length ? entries.map(([label, count], index) => (
          <div key={label} className="flex items-center justify-between gap-3 text-sm">
            <span className="flex items-center gap-2">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: colors[index % colors.length] }}
              />
              {label} 轮
            </span>
            <span className="text-muted-foreground">{count}</span>
          </div>
        )) : (
          <div className="py-8 text-center text-sm text-muted-foreground">
            暂无对话深度数据
          </div>
        )}
      </div>
    </div>
  );
}

export default function AdminPage() {
  const [authorized, setAuthorized] = useState<boolean | null>(null);
  const [adminName, setAdminName] = useState('');
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [confirm, setConfirm] = useState<ConfirmState>(null);

  const [overviewRange, setOverviewRange] = useState('7d');
  const [overview, setOverview] = useState<AdminOverview | null>(null);

  const [users, setUsers] = useState<Paginated<AdminUser>>({
    items: [],
    total: 0,
    page: 1,
    page_size: pageSize,
    total_pages: 0
  });
  const [userQ, setUserQ] = useState('');
  const [userRole, setUserRole] = useState('all');
  const [newUser, setNewUser] = useState({ username: '', password: '', role: 'user' });
  const [passwordEdit, setPasswordEdit] = useState<{ username: string; password: string } | null>(null);
  const [userDetail, setUserDetail] = useState<AdminUserDetail | null>(null);
  const [csvOpen, setCsvOpen] = useState(false);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvFileBase64, setCsvFileBase64] = useState('');
  const [csvRows, setCsvRows] = useState<CsvPreviewRow[]>([]);
  const [csvProgress, setCsvProgress] = useState(0);
  const [csvImporting, setCsvImporting] = useState(false);
  const [csvResult, setCsvResult] = useState('');

  const [conversations, setConversations] = useState<Paginated<AdminConversation>>({
    items: [],
    total: 0,
    page: 1,
    page_size: pageSize,
    total_pages: 0
  });
  const [conversationQ, setConversationQ] = useState('');
  const [conversationPersona, setConversationPersona] = useState('all');
  const [conversationDetail, setConversationDetail] = useState<ConversationDetail | null>(null);

  const [leaderboardPeriod, setLeaderboardPeriod] = useState('all');
  const [leaderboard, setLeaderboard] = useState<LeaderboardPayload>({
    leaderboard: [],
    stats: emptyLeaderboardStats
  });
  const [scoreEdit, setScoreEdit] = useState<{
    username: string;
    total_score: number;
    highest_score: number;
  } | null>(null);
  const [records, setRecords] = useState<Paginated<AdminPracticeRecord>>({
    items: [],
    total: 0,
    page: 1,
    page_size: pageSize,
    total_pages: 0
  });
  const [mistakes, setMistakes] = useState<Paginated<AdminMistake>>({
    items: [],
    total: 0,
    page: 1,
    page_size: pageSize,
    total_pages: 0
  });
  const [assignments, setAssignments] = useState<Paginated<AdminAssignment>>({
    items: [],
    total: 0,
    page: 1,
    page_size: pageSize,
    total_pages: 0
  });
  const [learningUser, setLearningUser] = useState('');

  const [config, setConfig] = useState<AdminConfig>({});
  const [configDraft, setConfigDraft] = useState<AdminConfig>({});
  const [audit, setAudit] = useState<Paginated<AdminActivity>>({
    items: [],
    total: 0,
    page: 1,
    page_size: pageSize,
    total_pages: 0
  });
  const [auditTarget, setAuditTarget] = useState('');

  const run = async (task: () => Promise<void>, success?: string) => {
    setLoading(true);
    setMessage('');
    try {
      await task();
      if (success) setMessage(success);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '操作失败');
    } finally {
      setLoading(false);
    }
  };

  const loadOverview = async () => {
    const data = await lingxiFetch<AdminOverview>(
      `/api/admin/overview${query({ range: overviewRange })}`
    );
    setOverview(data);
  };

  const loadUsers = async (page = users.page) => {
    const data = await lingxiFetch<Paginated<AdminUser> & { users: AdminUser[] }>(
      `/api/admin/users${query({
        q: userQ,
        role: userRole === 'all' ? undefined : userRole,
        page,
        page_size: pageSize
      })}`
    );
    setUsers({ ...data, items: data.items || data.users || [], total_pages: data.total_pages || 0 });
  };

  const loadConversations = async (page = conversations.page) => {
    const data = await lingxiFetch<Paginated<AdminConversation> & { conversations: AdminConversation[] }>(
      `/api/admin/conversations${query({
        q: conversationQ,
        persona: conversationPersona === 'all' ? undefined : conversationPersona,
        page,
        page_size: pageSize
      })}`
    );
    setConversations({ ...data, items: data.items || data.conversations || [], total_pages: data.total_pages || 0 });
  };

  const loadLearning = async () => {
    const username = learningUser || undefined;
    const [lb, practiceData, mistakeData, assignmentData] = await Promise.allSettled([
      lingxiFetch<LeaderboardPayload>(
        `/api/admin/leaderboard${query({ period: leaderboardPeriod })}`
      ),
      lingxiFetch<Paginated<AdminPracticeRecord>>(
        `/api/admin/learning/records${query({ username, page: records.page, page_size: pageSize })}`
      ),
      lingxiFetch<Paginated<AdminMistake>>(
        `/api/admin/learning/mistakes${query({ username, page: mistakes.page, page_size: pageSize })}`
      ),
      lingxiFetch<Paginated<AdminAssignment>>(
        `/api/admin/learning/assignments${query({ username, page: assignments.page, page_size: pageSize })}`
      )
    ]);
    if (lb.status === 'fulfilled') {
      setLeaderboard({
        leaderboard: lb.value.leaderboard || [],
        stats: { ...emptyLeaderboardStats, ...(lb.value.stats || {}) }
      });
    }
    if (practiceData.status === 'fulfilled') {
      setRecords({ ...practiceData.value, items: practiceData.value.items || [], total_pages: practiceData.value.total_pages || 0 });
    }
    if (mistakeData.status === 'fulfilled') {
      setMistakes({ ...mistakeData.value, items: mistakeData.value.items || [], total_pages: mistakeData.value.total_pages || 0 });
    }
    if (assignmentData.status === 'fulfilled') {
      setAssignments({ ...assignmentData.value, items: assignmentData.value.items || [], total_pages: assignmentData.value.total_pages || 0 });
    }
  };

  const loadConfig = async () => {
    const data = await lingxiFetch<AdminConfig>('/api/admin/config');
    setConfig(data);
    setConfigDraft({
      bot_id: data.bot_id,
      base_url: data.base_url,
      service_token: ''
    });
  };

  const loadAudit = async (page = audit.page) => {
    const data = await lingxiFetch<Paginated<AdminActivity>>(
      `/api/admin/audit${query({ target: auditTarget, page, page_size: pageSize })}`
    );
    setAudit({ ...data, items: data.items || [], total_pages: data.total_pages || 0 });
  };

  const loadInitial = async () => {
    const auth = await lingxiFetch<{ is_admin: boolean; username: string }>(
      '/api/admin/auth/check'
    );
    setAuthorized(auth.is_admin);
    setAdminName(auth.username || '');
    if (!auth.is_admin) return;
    await Promise.allSettled([
      loadOverview(),
      loadUsers(1),
      loadConversations(1),
      loadLearning(),
      loadConfig(),
      loadAudit(1)
    ]);
  };

  useEffect(() => {
    run(loadInitial).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (authorized) run(loadOverview).catch(() => undefined);
  }, [overviewRange]);

  const createUser = async () => {
    await run(async () => {
      await lingxiFetch('/api/admin/users', {
        method: 'POST',
        body: JSON.stringify(newUser)
      });
      setNewUser({ username: '', password: '', role: 'user' });
      await Promise.all([loadUsers(1), loadAudit(1), loadOverview()]);
    }, '用户已创建');
  };

  const parseCsvLine = (line: string) => {
    const cells: string[] = [];
    let current = '';
    let quoted = false;
    for (let index = 0; index < line.length; index += 1) {
      const char = line[index];
      const next = line[index + 1];
      if (char === '"' && quoted && next === '"') {
        current += '"';
        index += 1;
      } else if (char === '"') {
        quoted = !quoted;
      } else if (char === ',' && !quoted) {
        cells.push(current.trim());
        current = '';
      } else {
        current += char;
      }
    }
    cells.push(current.trim());
    return cells;
  };

  const parseCsvFile = async (file?: File) => {
    if (!file) return;
    setCsvFile(file);
    setCsvRows([]);
    setCsvProgress(10);
    setCsvResult('');

    const dataUrl = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => reject(new Error('读取 CSV 失败'));
      reader.readAsDataURL(file);
    });
    const fileBase64 = dataUrl.split(',')[1] || '';
    setCsvFileBase64(fileBase64);
    setCsvProgress(35);

    const raw = atob(fileBase64);
    const bytes = Uint8Array.from(raw, (char) => char.charCodeAt(0));
    let text = new TextDecoder('utf-8', { fatal: false }).decode(bytes);
    if (text.includes('\uFFFD')) {
      text = new TextDecoder('gbk', { fatal: false }).decode(bytes);
    }
    setCsvProgress(65);

    const lines = text
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    const rows: CsvPreviewRow[] = [];
    const seen = new Set<string>();
    lines.forEach((line, index) => {
      const cells = parseCsvLine(line);
      const first = (cells[0] || '').toLowerCase();
      if (index === 0 && ['username', '用户名', 'user', 'name', '姓名', '账号'].includes(first)) {
        return;
      }
      const username = cells[0] || '';
      const password = cells[1] || '';
      const role = cells[2] || 'user';
      let error = '';
      if (!username) error = '用户名为空';
      else if (!password) error = '密码为空';
      else if (!['user', 'admin'].includes(role)) error = '角色必须是 user 或 admin';
      else if (seen.has(username)) error = 'CSV 内用户名重复';
      seen.add(username);
      rows.push({ username, password, role, line: index + 1, error });
    });
    setCsvRows(rows);
    setCsvProgress(100);
  };

  const confirmCsvImport = async () => {
    if (!csvFileBase64 || csvRows.some((row) => row.error)) return;
    setCsvImporting(true);
    await run(async () => {
      await lingxiFetch('/api/admin/users/batch', {
        method: 'POST',
        body: JSON.stringify({ file_base64: csvFileBase64 })
      });
      await Promise.all([loadUsers(1), loadAudit(1), loadOverview()]);
      setCsvResult(`导入完成：提交 ${csvRows.length} 行用户数据`);
    }, '批量导入完成');
    setCsvImporting(false);
  };

  const resetCsvDialog = () => {
    setCsvFile(null);
    setCsvFileBase64('');
    setCsvRows([]);
    setCsvProgress(0);
    setCsvImporting(false);
    setCsvResult('');
  };

  const updateRole = async (username: string, role: string) => {
    await run(async () => {
      await lingxiFetch(`/api/admin/users/${encodeURIComponent(username)}/role`, {
        method: 'PUT',
        body: JSON.stringify({ role })
      });
      await Promise.all([loadUsers(), loadAudit(1)]);
    }, '角色已更新');
  };

  const savePassword = async () => {
    if (!passwordEdit) return;
    await run(async () => {
      await lingxiFetch(`/api/admin/users/${encodeURIComponent(passwordEdit.username)}/password`, {
        method: 'PUT',
        body: JSON.stringify({ password: passwordEdit.password })
      });
      setPasswordEdit(null);
      await loadAudit(1);
    }, '密码已更新');
  };

  const openUserDetail = async (username: string) => {
    await run(async () => {
      const detail = await lingxiFetch<AdminUserDetail>(
        `/api/admin/users/${encodeURIComponent(username)}`
      );
      setUserDetail(detail);
    });
  };

  const openConversationDetail = async (id: string) => {
    await run(async () => {
      const detail = await lingxiFetch<ConversationDetail>(
        `/api/admin/conversations/${encodeURIComponent(id)}`
      );
      setConversationDetail(detail);
    });
  };

  const saveScore = async () => {
    if (!scoreEdit) return;
    await run(async () => {
      await lingxiFetch(`/api/admin/leaderboard/${encodeURIComponent(scoreEdit.username)}`, {
        method: 'PUT',
        body: JSON.stringify({
          period: leaderboardPeriod,
          total_score: scoreEdit.total_score,
          highest_score: scoreEdit.highest_score
        })
      });
      setScoreEdit(null);
      await Promise.all([loadLearning(), loadAudit(1), loadOverview()]);
    }, '分数已更新');
  };

  const saveConfig = async () => {
    await run(async () => {
      const payload = { ...configDraft };
      if (!payload.service_token) delete payload.service_token;
      delete payload.jwt_expires_at;
      await lingxiFetch('/api/admin/config', {
        method: 'PUT',
        body: JSON.stringify(payload)
      });
      await Promise.all([loadConfig(), loadAudit(1), loadOverview()]);
    }, '配置已保存');
  };

  const testConnection = async () => {
    await run(async () => {
      const data = await lingxiFetch<{ success: boolean; message: string }>(
        '/api/admin/test-connection'
      );
      setMessage(data.message);
    });
  };

  const deleteUser = (username: string) => {
    setConfirm({
      title: '删除用户',
      description: `将删除用户 ${username} 的登录账号。学习和对话历史不会被自动清理。`,
      actionLabel: '确认删除',
      onConfirm: async () => {
        await lingxiFetch(`/api/admin/users/${encodeURIComponent(username)}`, {
          method: 'DELETE'
        });
        await Promise.all([loadUsers(1), loadAudit(1), loadOverview()]);
      }
    });
  };

  const resetLeaderboard = (username: string, period: string) => {
    setConfirm({
      title: period === 'today' ? '重置今日成绩' : '清空全部练习记录',
      description:
        period === 'today'
          ? `将删除 ${username} 今日练习记录并回滚今日分数。`
          : `将删除 ${username} 的排行榜、练习记录和错题明细。`,
      actionLabel: '确认重置',
      onConfirm: async () => {
        await lingxiFetch(
          `/api/admin/leaderboard/${encodeURIComponent(username)}${query({ period })}`,
          { method: 'DELETE' }
        );
        await Promise.all([loadLearning(), loadAudit(1), loadOverview()]);
      }
    });
  };

  if (authorized === false) return <Navigate to="/" replace />;
  if (authorized === null) {
    return (
      <div className="flex h-svh items-center justify-center text-sm text-muted-foreground">
        正在验证管理员权限...
      </div>
    );
  }

  const tokenState = overview?.token_health?.service_identity?.valid
    ? '正常'
    : overview?.token_health?.service_identity?.available
      ? '需更新'
      : '未配置';

  return (
    <main className="min-h-svh bg-muted/30 p-4 md:p-6">
      <div className="mx-auto flex max-w-[1500px] flex-col gap-5">
        <header className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-background px-4 py-3">
          <div>
            <div className="flex items-center gap-2">
              <Shield className="h-5 w-5" />
              <h1 className="text-2xl font-semibold">灵犀管理后台</h1>
            </div>
            <p className="text-sm text-muted-foreground">
              当前管理员：{adminName || '-'}，基于真实数据库的运营、排查和配置入口
            </p>
          </div>
          <div className="flex items-center gap-2">
            {loading ? <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" /> : null}
            <Button variant="outline" size="sm" onClick={() => run(loadInitial)}>
              <RefreshCw className="mr-2 h-4 w-4" />
              刷新
            </Button>
            <Button asChild size="sm">
              <a href="/">返回对话</a>
            </Button>
          </div>
        </header>

        {message ? (
          <div className="rounded-md border bg-background px-3 py-2 text-sm">
            {message}
          </div>
        ) : null}

        <Tabs value={activeTab} onValueChange={(value) => startTransition(() => setActiveTab(value))}>
          <TabsList className="h-auto flex-wrap justify-start">
            <TabsTrigger value="overview">总览</TabsTrigger>
            <TabsTrigger value="users">用户</TabsTrigger>
            <TabsTrigger value="conversations">对话</TabsTrigger>
            <TabsTrigger value="learning">学习</TabsTrigger>
            <TabsTrigger value="config">配置</TabsTrigger>
            <TabsTrigger value="audit">审计</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-5">
            <div className="flex justify-end">
              <Select value={overviewRange} onValueChange={setOverviewRange}>
                <SelectTrigger className="w-36">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="7d">近 7 天</SelectItem>
                  <SelectItem value="30d">近 30 天</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <section className="grid gap-4 md:grid-cols-4">
              <StatCard title="总用户" value={overview?.kpis?.total_users || 0} icon={Users} note={`普通用户 ${overview?.kpis?.normal_users || 0}`} />
              <StatCard title="今日活跃" value={overview?.kpis?.active_today || 0} icon={Activity} note={`占比 ${overview?.active_user_proportion?.percent || 0}%`} />
              <StatCard title="对话总数" value={overview?.kpis?.total_conversations || 0} icon={MessageSquareText} note={`${overview?.kpis?.total_messages || 0} 条消息`} />
              <StatCard title="Token 状态" value={tokenState} icon={KeyRound} note={overview?.token_health?.recommendation || 'Service Identity'} />
            </section>

            <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <BarChart3 className="h-4 w-4" />
                    运营趋势
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {(overview?.daily || []).map((day) => {
                    const max = Math.max(
                      1,
                      ...(overview?.daily || []).map((item) => item.conversations + item.practices)
                    );
                    const width = Math.round(((day.conversations + day.practices) / max) * 100);
                    return (
                      <div key={day.date} className="grid grid-cols-[56px_1fr_120px] items-center gap-3 text-sm">
                        <span className="text-muted-foreground">{day.date}</span>
                        <div className="h-3 overflow-hidden rounded-full bg-muted">
                          <div className="h-full bg-primary" style={{ width: `${width}%` }} />
                        </div>
                        <span className="text-right text-muted-foreground">
                          对话 {day.conversations} / 练习 {day.practices}
                        </span>
                      </div>
                    );
                  })}
                  {!overview?.daily?.length ? <div className="py-10 text-center text-sm text-muted-foreground">暂无趋势数据</div> : null}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">热门人设</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {(overview?.persona_stats || []).map((item) => (
                    <div key={item.name} className="space-y-1">
                      <div className="flex items-center justify-between text-sm">
                        <span>{item.name}</span>
                        <span className="text-muted-foreground">{item.count} 次 / {item.percentage}%</span>
                      </div>
                      <div className="h-2 overflow-hidden rounded-full bg-muted">
                        <div className="h-full bg-emerald-500" style={{ width: `${item.percentage}%` }} />
                      </div>
                    </div>
                  ))}
                  {!overview?.persona_stats?.length ? <div className="py-10 text-center text-sm text-muted-foreground">暂无人设使用数据</div> : null}
                </CardContent>
              </Card>
            </section>

            <section className="grid gap-4 xl:grid-cols-3">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">今日活跃用户</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {(overview?.today_active_users || []).map((item) => (
                    <div key={item.username} className="flex items-center justify-between text-sm">
                      <span>{item.username}</span>
                      <Badge variant="secondary">{item.count} 个对话</Badge>
                    </div>
                  ))}
                  {!overview?.today_active_users?.length ? <div className="py-8 text-center text-sm text-muted-foreground">今天暂无活跃用户</div> : null}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">对话深度</CardTitle>
                </CardHeader>
                <CardContent>
                  <ConversationDepthChart data={overview?.conversation_depth} />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">最近活动</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {(overview?.recent_activity || []).slice(0, 6).map((item, index) => (
                    <div key={`${item.created_at}-${index}`} className="text-sm">
                      <div>{item.actor || item.target || '-'} {item.action}</div>
                      <div className="text-xs text-muted-foreground">{formatTime(item.created_at)}</div>
                    </div>
                  ))}
                  {!overview?.recent_activity?.length ? <div className="py-8 text-center text-sm text-muted-foreground">暂无活动记录</div> : null}
                </CardContent>
              </Card>
            </section>
          </TabsContent>

          <TabsContent value="users" className="space-y-4">
            <section className="grid gap-4 xl:grid-cols-[1fr_360px]">
              <Card>
                <CardHeader className="space-y-3">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Users className="h-4 w-4" />
                    用户管理
                  </CardTitle>
                  <div className="flex flex-wrap gap-2">
                    <div className="relative min-w-64 flex-1">
                      <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                      <Input className="pl-8" placeholder="搜索用户名" value={userQ} onChange={(event) => setUserQ(event.target.value)} />
                    </div>
                    <Select value={userRole} onValueChange={setUserRole}>
                      <SelectTrigger className="w-36"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">全部角色</SelectItem>
                        <SelectItem value="admin">管理员</SelectItem>
                        <SelectItem value="user">普通用户</SelectItem>
                      </SelectContent>
                    </Select>
                    <Button variant="outline" onClick={() => run(() => loadUsers(1))}>查询</Button>
                    <Button variant="outline" onClick={() => setCsvOpen(true)}>
                      <Upload className="h-4 w-4" />
                      CSV 导入
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>用户名</TableHead>
                        <TableHead>角色</TableHead>
                        <TableHead>对话</TableHead>
                        <TableHead>练习</TableHead>
                        <TableHead>总分</TableHead>
                        <TableHead>最近登录</TableHead>
                        <TableHead className="text-right">操作</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {users.items?.length ? (users.items || []).map((user) => (
                        <TableRow key={user.username}>
                          <TableCell>
                            <button className="font-medium underline-offset-4 hover:underline" onClick={() => openUserDetail(user.username)}>
                              {user.username}
                            </button>
                          </TableCell>
                          <TableCell>
                            <Select value={user.role} onValueChange={(role) => updateRole(user.username, role)}>
                              <SelectTrigger className="w-28"><SelectValue /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="admin">管理员</SelectItem>
                                <SelectItem value="user">普通用户</SelectItem>
                              </SelectContent>
                            </Select>
                          </TableCell>
                          <TableCell>{user.conversation_count || 0}</TableCell>
                          <TableCell>{user.practice_count || 0}</TableCell>
                          <TableCell>{user.total_score || 0}</TableCell>
                          <TableCell>{formatTime(user.last_login)}</TableCell>
                          <TableCell className="text-right">
                            <Button variant="ghost" size="icon" title="修改密码" onClick={() => setPasswordEdit({ username: user.username, password: '' })}>
                              <KeyRound className="h-4 w-4" />
                            </Button>
                            <Button variant="ghost" size="icon" title="删除用户" onClick={() => deleteUser(user.username)}>
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      )) : <EmptyRow colSpan={7} text="暂无用户数据" />}
                    </TableBody>
                  </Table>
                  <Pager page={users.page} totalPages={users.total_pages} onPage={(page) => run(() => loadUsers(page))} />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <UserPlus className="h-4 w-4" />
                    创建用户
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="space-y-2">
                    <Label>用户名</Label>
                    <Input value={newUser.username} onChange={(event) => setNewUser({ ...newUser, username: event.target.value })} />
                  </div>
                  <div className="space-y-2">
                    <Label>密码</Label>
                    <Input type="password" value={newUser.password} onChange={(event) => setNewUser({ ...newUser, password: event.target.value })} />
                  </div>
                  <div className="space-y-2">
                    <Label>角色</Label>
                    <Select value={newUser.role} onValueChange={(role) => setNewUser({ ...newUser, role })}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="user">普通用户</SelectItem>
                        <SelectItem value="admin">管理员</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <Button className="w-full" onClick={createUser}>创建用户</Button>
                </CardContent>
              </Card>
            </section>
          </TabsContent>

          <TabsContent value="conversations" className="space-y-4">
            <Card>
              <CardHeader className="space-y-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <MessageSquareText className="h-4 w-4" />
                  对话排查
                </CardTitle>
                <div className="flex flex-wrap gap-2">
                  <Input className="max-w-sm" placeholder="搜索标题、用户、conversation id" value={conversationQ} onChange={(event) => setConversationQ(event.target.value)} />
                  <Select value={conversationPersona} onValueChange={setConversationPersona}>
                    <SelectTrigger className="w-36"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">全部人设</SelectItem>
                      <SelectItem value="新手小白">新手小白</SelectItem>
                      <SelectItem value="辩论对手">辩论对手</SelectItem>
                      <SelectItem value="计网专家">计网专家</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button variant="outline" onClick={() => run(() => loadConversations(1))}>查询</Button>
                </div>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>标题</TableHead>
                      <TableHead>用户</TableHead>
                      <TableHead>人设</TableHead>
                      <TableHead>消息</TableHead>
                      <TableHead>Coze 会话</TableHead>
                      <TableHead>创建时间</TableHead>
                      <TableHead className="text-right">操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {conversations.items?.length ? (conversations.items || []).map((item) => (
                      <TableRow key={item.id}>
                        <TableCell className="max-w-[280px] truncate">{item.name || item.id}</TableCell>
                        <TableCell>{item.username}</TableCell>
                        <TableCell><Badge variant="outline">{item.persona}</Badge></TableCell>
                        <TableCell>{item.message_count}</TableCell>
                        <TableCell className="max-w-[180px] truncate">{item.conversation_id || '-'}</TableCell>
                        <TableCell>{formatTime(item.created_at)}</TableCell>
                        <TableCell className="text-right">
                          <Button variant="ghost" size="icon" onClick={() => openConversationDetail(item.id)}>
                            <Eye className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    )) : <EmptyRow colSpan={7} text="暂无对话数据" />}
                  </TableBody>
                </Table>
                <Pager page={conversations.page} totalPages={conversations.total_pages} onPage={(page) => run(() => loadConversations(page))} />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="learning" className="space-y-4">
            <section className="grid gap-4 md:grid-cols-4">
              <StatCard title="参与人数" value={leaderboard.stats?.total_participants || 0} icon={Users} />
              <StatCard title="最高分" value={leaderboard.stats?.highest_score || 0} icon={CheckCircle2} />
              <StatCard title="平均分" value={leaderboard.stats?.avg_score || 0} icon={BarChart3} />
              <StatCard title="今日练习" value={leaderboard.stats?.today_sessions || 0} icon={BookOpen} />
            </section>

            <Card>
              <CardHeader className="space-y-3">
                <CardTitle className="text-base">学习数据</CardTitle>
                <div className="flex flex-wrap gap-2">
                  <Input className="max-w-xs" placeholder="按用户名筛选明细" value={learningUser} onChange={(event) => setLearningUser(event.target.value)} />
                  <Select value={leaderboardPeriod} onValueChange={setLeaderboardPeriod}>
                    <SelectTrigger className="w-36"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">历史排行</SelectItem>
                      <SelectItem value="today">今日排行</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button variant="outline" onClick={() => run(loadLearning)}>查询</Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-6">
                <div>
                  <h3 className="mb-2 text-sm font-medium">排行榜</h3>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>排名</TableHead>
                        <TableHead>用户名</TableHead>
                        <TableHead>总分</TableHead>
                        <TableHead>最高分</TableHead>
                        <TableHead>次数</TableHead>
                        <TableHead className="text-right">操作</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {leaderboard.leaderboard?.length ? (leaderboard.leaderboard || []).map((item) => (
                        <TableRow key={item.username}>
                          <TableCell>{item.rank}</TableCell>
                          <TableCell>{item.username}</TableCell>
                          <TableCell>{item.total_score}</TableCell>
                          <TableCell>{item.highest_score || 0}</TableCell>
                          <TableCell>{item.practice_count || 0}</TableCell>
                          <TableCell className="text-right">
                            <Button variant="ghost" size="sm" onClick={() => setScoreEdit({ username: item.username, total_score: item.total_score || 0, highest_score: item.highest_score || 0 })}>修正</Button>
                            <Button variant="ghost" size="sm" onClick={() => resetLeaderboard(item.username, leaderboardPeriod)}>重置</Button>
                          </TableCell>
                        </TableRow>
                      )) : <EmptyRow colSpan={6} text="暂无排行数据" />}
                    </TableBody>
                  </Table>
                </div>

                <div className="grid gap-4 xl:grid-cols-3">
                  <div>
                    <h3 className="mb-2 text-sm font-medium">练习记录</h3>
                    <Table>
                      <TableHeader><TableRow><TableHead>用户</TableHead><TableHead>得分</TableHead><TableHead>正确/错误</TableHead><TableHead>时间</TableHead></TableRow></TableHeader>
                      <TableBody>
                        {records.items?.length ? (records.items || []).map((item) => (
                          <TableRow key={item.id}>
                            <TableCell>{item.username}</TableCell>
                            <TableCell>{item.score}</TableCell>
                            <TableCell>{item.correct_count}/{item.wrong_count}</TableCell>
                            <TableCell>{formatTime(item.created_at)}</TableCell>
                          </TableRow>
                        )) : <EmptyRow colSpan={4} text="暂无练习记录" />}
                      </TableBody>
                    </Table>
                  </div>

                  <div>
                    <h3 className="mb-2 text-sm font-medium">错题明细</h3>
                    <Table>
                      <TableHeader><TableRow><TableHead>用户</TableHead><TableHead>题目</TableHead><TableHead>时间</TableHead></TableRow></TableHeader>
                      <TableBody>
                        {mistakes.items?.length ? (mistakes.items || []).map((item) => (
                          <TableRow key={item.id}>
                            <TableCell>{item.username}</TableCell>
                            <TableCell className="max-w-[220px] truncate" title={item.question_text}>{item.question_text || item.question_id}</TableCell>
                            <TableCell>{formatTime(item.created_at)}</TableCell>
                          </TableRow>
                        )) : <EmptyRow colSpan={3} text="暂无错题数据" />}
                      </TableBody>
                    </Table>
                  </div>

                  <div>
                    <h3 className="mb-2 text-sm font-medium">作业记录</h3>
                    <Table>
                      <TableHeader><TableRow><TableHead>用户</TableHead><TableHead>分数</TableHead><TableHead>反馈</TableHead><TableHead>时间</TableHead></TableRow></TableHeader>
                      <TableBody>
                        {assignments.items?.length ? (assignments.items || []).map((item) => (
                          <TableRow key={item.id}>
                            <TableCell>{item.username}</TableCell>
                            <TableCell>{item.score}</TableCell>
                            <TableCell className="max-w-[180px] truncate" title={item.feedback}>{item.feedback || '-'}</TableCell>
                            <TableCell>{formatTime(item.created_at)}</TableCell>
                          </TableRow>
                        )) : <EmptyRow colSpan={4} text="暂无作业记录" />}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="config" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <KeyRound className="h-4 w-4" />
                  Coze 配置
                </CardTitle>
              </CardHeader>
              <CardContent className="grid gap-4 xl:grid-cols-[1fr_320px]">
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label>Bot ID</Label>
                    <Input value={configDraft.bot_id || ''} onChange={(event) => setConfigDraft({ ...configDraft, bot_id: event.target.value })} />
                  </div>
                  <div className="space-y-2">
                    <Label>API Base URL</Label>
                    <Input value={configDraft.base_url || ''} onChange={(event) => setConfigDraft({ ...configDraft, base_url: event.target.value })} />
                  </div>
                  <div className="space-y-2">
                    <Label>Service Identity Token</Label>
                    <Input type="password" placeholder={config.masked_service_token || '留空则不覆盖'} value={configDraft.service_token || ''} onChange={(event) => setConfigDraft({ ...configDraft, service_token: event.target.value })} />
                  </div>
                </div>
                <div className="space-y-3 rounded-md border p-4 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Token</span>
                    <Badge variant={config.has_service_token ? 'secondary' : 'destructive'}>{config.has_service_token ? '已配置' : '未配置'}</Badge>
                  </div>
                  <Button className="w-full gap-2" onClick={saveConfig}><Save className="h-4 w-4" />保存配置</Button>
                  <Button className="w-full" variant="outline" onClick={testConnection}>测试连接</Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="audit" className="space-y-4">
            <Card>
              <CardHeader className="space-y-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <FileText className="h-4 w-4" />
                  操作审计
                </CardTitle>
                <div className="flex flex-wrap gap-2">
                  <Input className="max-w-xs" placeholder="按目标用户或对象筛选" value={auditTarget} onChange={(event) => setAuditTarget(event.target.value)} />
                  <Button variant="outline" onClick={() => run(() => loadAudit(1))}>查询</Button>
                </div>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>管理员</TableHead>
                      <TableHead>动作</TableHead>
                      <TableHead>目标</TableHead>
                      <TableHead>详情</TableHead>
                      <TableHead>时间</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {audit.items?.length ? (audit.items || []).map((item) => (
                      <TableRow key={item.id || `${item.created_at}-${item.action}`}>
                        <TableCell>{item.actor || '-'}</TableCell>
                        <TableCell>{item.action}</TableCell>
                        <TableCell>{item.target || '-'}</TableCell>
                        <TableCell>{item.detail || '-'}</TableCell>
                        <TableCell>{formatTime(item.created_at)}</TableCell>
                      </TableRow>
                    )) : <EmptyRow colSpan={5} text="暂无审计记录" />}
                  </TableBody>
                </Table>
                <Pager page={audit.page} totalPages={audit.total_pages} onPage={(page) => run(() => loadAudit(page))} />
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>

      <Dialog
        open={csvOpen}
        onOpenChange={(open) => {
          setCsvOpen(open);
          if (!open) resetCsvDialog();
        }}
      >
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>CSV 批量导入用户</DialogTitle>
            <DialogDescription>
              CSV 每行一个用户，列顺序为：username,password,role。role 可省略，默认 user；可选值为 user 或 admin。
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4">
            <div className="rounded-md border bg-muted/40 p-3 text-sm text-muted-foreground">
              示例：
              <pre className="mt-2 whitespace-pre-wrap rounded bg-background p-2 font-mono text-xs text-foreground">
                username,password,role{'\n'}student001,Passw0rd,user{'\n'}teacher001,Passw0rd,admin
              </pre>
            </div>

            <Label
              className="flex min-h-44 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed bg-background p-6 text-center transition-colors hover:bg-muted/50"
              onDragOver={(event) => {
                event.preventDefault();
              }}
              onDrop={(event) => {
                event.preventDefault();
                parseCsvFile(event.dataTransfer.files?.[0]).catch((error) =>
                  setCsvResult(error instanceof Error ? error.message : '解析失败')
                );
              }}
            >
              <Upload className="mb-3 h-8 w-8 text-muted-foreground" />
              <span className="font-medium">
                {csvFile ? csvFile.name : '点击选择 CSV，或拖拽文件到此处'}
              </span>
              <span className="mt-1 text-xs text-muted-foreground">
                支持 UTF-8，GBK 会自动尝试解析
              </span>
              <Input
                className="hidden"
                type="file"
                accept=".csv,text/csv"
                onChange={(event) =>
                  parseCsvFile(event.target.files?.[0]).catch((error) =>
                    setCsvResult(error instanceof Error ? error.message : '解析失败')
                  )
                }
              />
            </Label>

            {csvProgress ? (
              <div className="space-y-2">
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>解析进度</span>
                  <span>{csvProgress}%</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-muted">
                  <div className="h-full bg-primary" style={{ width: `${csvProgress}%` }} />
                </div>
              </div>
            ) : null}

            {csvRows.length ? (
              <div className="max-h-72 overflow-auto rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>行号</TableHead>
                      <TableHead>用户名</TableHead>
                      <TableHead>密码</TableHead>
                      <TableHead>角色</TableHead>
                      <TableHead>状态</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {csvRows.map((row) => (
                      <TableRow key={`${row.line}-${row.username}`}>
                        <TableCell>{row.line}</TableCell>
                        <TableCell>{row.username || '-'}</TableCell>
                        <TableCell>{row.password ? '已填写' : '-'}</TableCell>
                        <TableCell>{row.role}</TableCell>
                        <TableCell>
                          {row.error ? (
                            <Badge variant="destructive">{row.error}</Badge>
                          ) : (
                            <Badge variant="secondary">可导入</Badge>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : null}

            {csvResult ? (
              <div className="rounded-md border px-3 py-2 text-sm">{csvResult}</div>
            ) : null}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setCsvOpen(false)}>
              关闭
            </Button>
            <Button
              disabled={!csvRows.length || csvRows.some((row) => row.error) || csvImporting}
              onClick={confirmCsvImport}
            >
              {csvImporting ? '导入中...' : '确认导入'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!passwordEdit} onOpenChange={(open) => !open && setPasswordEdit(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>修改密码</DialogTitle>
            <DialogDescription>{passwordEdit?.username}</DialogDescription>
          </DialogHeader>
          <Input type="password" value={passwordEdit?.password || ''} onChange={(event) => passwordEdit && setPasswordEdit({ ...passwordEdit, password: event.target.value })} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setPasswordEdit(null)}>取消</Button>
            <Button onClick={savePassword}>保存</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!scoreEdit} onOpenChange={(open) => !open && setScoreEdit(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>修正排行榜分数</DialogTitle>
            <DialogDescription>{scoreEdit?.username}，周期：{leaderboardPeriod === 'today' ? '今日' : '历史'}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-3">
            <div className="space-y-2">
              <Label>总分</Label>
              <Input type="number" value={scoreEdit?.total_score || 0} onChange={(event) => scoreEdit && setScoreEdit({ ...scoreEdit, total_score: Number(event.target.value) || 0 })} />
            </div>
            <div className="space-y-2">
              <Label>最高分</Label>
              <Input type="number" value={scoreEdit?.highest_score || 0} onChange={(event) => scoreEdit && setScoreEdit({ ...scoreEdit, highest_score: Number(event.target.value) || 0 })} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setScoreEdit(null)}>取消</Button>
            <Button onClick={saveScore}>保存</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!userDetail} onOpenChange={(open) => !open && setUserDetail(null)}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>{userDetail?.profile.username}</DialogTitle>
            <DialogDescription>用户运营详情</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 md:grid-cols-3">
            <StatCard title="对话" value={userDetail?.summary.conversation_count || 0} icon={MessageSquareText} />
            <StatCard title="练习" value={userDetail?.summary.practice_count || 0} icon={BookOpen} />
            <StatCard title="总分" value={userDetail?.learning.total_score || 0} icon={BarChart3} />
          </div>
          <div className="max-h-[360px] overflow-auto rounded-md border">
            <Table>
              <TableHeader><TableRow><TableHead>最近动作</TableHead><TableHead>目标</TableHead><TableHead>时间</TableHead></TableRow></TableHeader>
              <TableBody>
                {userDetail?.activity?.length ? (userDetail.activity || []).map((item, index) => (
                  <TableRow key={`${item.created_at}-${index}`}>
                    <TableCell>{item.action}</TableCell>
                    <TableCell>{item.target || '-'}</TableCell>
                    <TableCell>{formatTime(item.created_at)}</TableCell>
                  </TableRow>
                )) : <EmptyRow colSpan={3} text="暂无用户活动" />}
              </TableBody>
            </Table>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={!!conversationDetail} onOpenChange={(open) => !open && setConversationDetail(null)}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>{conversationDetail?.thread.name || '对话详情'}</DialogTitle>
            <DialogDescription>
              {conversationDetail?.thread.username} / {conversationDetail?.thread.persona} / {conversationDetail?.thread.conversation_id || '-'}
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-[560px] space-y-3 overflow-auto">
            {conversationDetail?.messages?.length ? (conversationDetail.messages || []).map((message) => (
              <div key={message.id} className="rounded-md border p-3">
                <div className="mb-2 flex items-center justify-between text-xs text-muted-foreground">
                  <span>{message.author} · {message.type}</span>
                  <span>{formatTime(message.created_at)}</span>
                </div>
                <pre className="whitespace-pre-wrap break-words text-sm font-sans">{message.content}</pre>
              </div>
            )) : <div className="py-10 text-center text-sm text-muted-foreground">暂无消息</div>}
          </div>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!confirm} onOpenChange={(open) => !open && setConfirm(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{confirm?.title}</AlertDialogTitle>
            <AlertDialogDescription>{confirm?.description}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (!confirm) return;
                run(confirm.onConfirm, '操作已完成').finally(() => setConfirm(null));
              }}
            >
              {confirm?.actionLabel || '确认'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </main>
  );
}
