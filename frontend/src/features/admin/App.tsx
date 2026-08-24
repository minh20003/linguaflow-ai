import React, { useCallback, useEffect, useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { AnalyticsView } from './components/analytics/AnalyticsView';
import { GlossaryView } from './components/glossary/GlossaryView';
import { SuggestionsView } from './components/suggestions/SuggestionsView';
import { LiveChatView } from './components/chat/LiveChatView';
import { ToastContainer, ToastMessage } from './components/Toast';
import {
  AdminTab,
  TimeRangeFilter,
  TermItem,
  TranslationSuggestion,
  LanguagePair,
  RequestLog,
  LanguageCode,
  TermCategory,
  MetricCardData,
  LanguagePairStat,
  ModelUsageStat,
} from './types';

type ApiPair = { count: number; p50_ms: number; p95_ms: number; avg_input_tokens: number; avg_output_tokens: number };
type ApiStats = { total_attempts: number; outcomes?: Record<string, number>; fallback_rate: number; input_tokens: number; output_tokens: number; estimated_cost_usd?: number; cost_coverage_rate?: number; total_ms_p50: number; total_ms_p95: number; models_served?: Record<string, number>; language_pairs?: Record<string, ApiPair> };
type ApiAttempt = { id:string; created_at:string; source_language:string; target_language:string; model:string; outcome:string; fallback_reason:string; total_ms:number; input_tokens:number; output_tokens:number };
type ApiGlossaryEntry = { id:string; source_term:string; target_term:string; source_language:string; target_language:string; domain:string; audience:string; keep_verbatim:boolean; status:string; created_at:string; updated_at:string };
type ApiProposal = { id:string; source_term:string; target_term:string; source_language:string; target_language:string; domain:string; keep_verbatim:boolean; distinct_user_count:number; rationale:string; status:'pending'|'approved'|'rejected'; created_at:string };
type ApiUser = { email:string; display_name?:string | null; username?:string | null; role:string; interface_language?:string | null };
type AdminTheme = 'light' | 'dark';
type AdminInterfaceLanguage = 'vi' | 'en';

const METRIC_DEFINITIONS: MetricCardData[] = [
  { id: 'total_translations', title: 'Tổng số lần dịch', value: 0, unit: 'lượt', description: 'Tổng lượt yêu cầu dịch trong khoảng thời gian đã chọn', iconName: 'Languages' },
  { id: 'fallback_rate', title: 'Tỷ lệ fallback', value: 0, description: 'Tỷ lệ yêu cầu chuyển sang đường dịch dự phòng', iconName: 'ShieldAlert' },
  { id: 'input_tokens', title: 'Input Tokens', value: 0, unit: 'tokens', description: 'Tổng token đầu vào thực tế', iconName: 'ArrowDownToLine' },
  { id: 'output_tokens', title: 'Output Tokens', value: 0, unit: 'tokens', description: 'Tổng token đầu ra thực tế', iconName: 'ArrowUpFromLine' },
  { id: 'estimated_ai_cost', title: 'Chi phí AI ước tính', value: 0, unit: 'USD', description: 'Ước tính từ token của các model đã nhận diện', iconName: 'Gauge' },
  { id: 'success_rate', title: 'Tỷ lệ dịch thành công', value: 0, description: 'Tỷ lệ yêu cầu hoàn tất trên đường dịch chính', iconName: 'Timer' },
  { id: 'p50_latency', title: 'Độ trễ P50', value: 0, unit: 'ms', description: 'Độ trễ phân vị 50', iconName: 'Gauge' },
  { id: 'p95_latency', title: 'Độ trễ P95', value: 0, unit: 'ms', description: 'Độ trễ phân vị 95', iconName: 'Timer' },
];

export default function App() {
  const [currentTab, setCurrentTab] = useState<AdminTab>('analytics');
  const [timeRange, setTimeRange] = useState<TimeRangeFilter>('7d');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [adminTheme, setAdminTheme] = useState<AdminTheme>('light');
  const [adminLanguage, setAdminLanguage] = useState<AdminInterfaceLanguage>('vi');
  const [adminProfile, setAdminProfile] = useState({ name: 'Quản trị viên', email: 'admin@test.com', role: 'admin' });

  // Core Data States
  const [metrics, setMetrics] = useState<MetricCardData[]>([]);
  const [languagePairs, setLanguagePairs] = useState<LanguagePairStat[]>([]);
  const [aiModels, setAiModels] = useState<ModelUsageStat[]>([]);
  const [requestLogs, setRequestLogs] = useState<RequestLog[]>([]);
  const [terms, setTerms] = useState<TermItem[]>([]);
  const [suggestions, setSuggestions] = useState<TranslationSuggestion[]>([]);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const savedTheme = window.localStorage.getItem('linguaflow_admin_theme');
      const savedLanguage = window.localStorage.getItem('linguaflow_admin_language');
      if (savedTheme === 'light' || savedTheme === 'dark') setAdminTheme(savedTheme);
      if (savedLanguage === 'vi' || savedLanguage === 'en') setAdminLanguage(savedLanguage);
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    window.localStorage.setItem('linguaflow_admin_theme', adminTheme);
    window.localStorage.setItem('linguaflow_admin_language', adminLanguage);
    document.documentElement.lang = adminLanguage;
    document.documentElement.classList.toggle('dark', adminTheme === 'dark');
  }, [adminLanguage, adminTheme]);

  const clearServerData = useCallback(() => {
    setMetrics([]);
    setLanguagePairs([]);
    setAiModels([]);
    setRequestLogs([]);
    setTerms([]);
    setSuggestions([]);
  }, []);

  const loadAdminData = useCallback(async () => {
    const token = window.localStorage.getItem('access_token') ?? window.sessionStorage.getItem('access_token');
    if (!token) {
      clearServerData();
      return;
    }

    setIsRefreshing(true);
    const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000';
    const headers = { Authorization: `Bearer ${token}` };
    const get = async <T,>(path: string): Promise<T> => {
      const response = await fetch(`${apiBase}/api/v1${path}`, { headers });
      if (!response.ok) throw new Error(`admin_api_${response.status}`);
      return response.json() as Promise<T>;
    };

    const days = timeRange === '24h' ? 1 : timeRange === '7d' ? 7 : timeRange === '30d' ? 30 : null;
    const statsPath = days ? `/stats?days=${days}` : '/stats';

    try {
      const [stats, attempts, glossary, queue, profile] = await Promise.all([
        get<ApiStats>(statsPath),
        get<ApiAttempt[]>(`/stats/attempts${days ? `?days=${days}&limit=20` : '?limit=20'}`),
        get<ApiGlossaryEntry[]>('/admin/glossary'),
        get<ApiProposal[]>('/admin/glossary/proposals?status=pending'),
        get<ApiUser>('/auth/me'),
      ]);

        setAdminProfile({
          name: profile.display_name || profile.username || (adminLanguage === 'vi' ? 'Quản trị viên' : 'Administrator'),
          email: profile.email,
          role: profile.role,
        });

        setMetrics(METRIC_DEFINITIONS.map((metric) => {
          const values: Record<string, string | number> = {
            total_translations: stats.total_attempts,
            fallback_rate: `${(stats.fallback_rate * 100).toFixed(2)}%`,
            input_tokens: stats.input_tokens,
            output_tokens: stats.output_tokens,
            estimated_ai_cost: (stats.estimated_cost_usd ?? 0).toFixed(4),
            success_rate: `${(stats.total_attempts ? ((stats.outcomes?.llm ?? 0) / stats.total_attempts) * 100 : 0).toFixed(2)}%`,
            p50_latency: stats.total_ms_p50,
            p95_latency: stats.total_ms_p95,
          };
          return { ...metric, value: values[metric.id] ?? 0, change: undefined, badge: undefined };
        }));
        const total = Math.max(stats.total_attempts || 0, 1);
        setLanguagePairs(Object.entries(stats.language_pairs ?? {}).map(([pair, value]) => ({
          pair: pair as LanguagePair,
          count: value.count,
          percentage: (value.count / total) * 100,
          p50: value.p50_ms,
          p95: value.p95_ms,
          avgInputTokens: value.avg_input_tokens,
          avgOutputTokens: value.avg_output_tokens,
          successRate: 100 - stats.fallback_rate * 100,
          fallbackRate: stats.fallback_rate * 100,
        })));
        setAiModels(Object.entries(stats.models_served ?? {}).map(([name, servedCount], index) => ({
          id: `model-${index}`,
          name,
          provider: 'LinguaFlow',
          servedCount,
          percentage: (servedCount / total) * 100,
          avgLatency: stats.total_ms_p50,
          status: 'active' as const,
          costPer1kTokens: 0,
          color: ['#2563EB', '#10B981', '#8B5CF6', '#F59E0B'][index % 4],
        })));
        setRequestLogs(attempts.map((attempt) => {
          const source = attempt.source_language.toUpperCase();
          const target = attempt.target_language.toUpperCase();
          const isFallback = attempt.outcome === 'secondary' || attempt.outcome === 'original';
          return {
            id: attempt.id,
            timestamp: new Date(attempt.created_at).toLocaleString('vi-VN'),
            pair: `${source} → ${target}` as LanguagePair,
            model: attempt.model,
            isFallback,
            status: isFallback ? 'warning' as const : attempt.outcome === 'primary' ? 'success' as const : 'error' as const,
            latency: attempt.total_ms,
            inputTokens: attempt.input_tokens,
            outputTokens: attempt.output_tokens,
            sourcePreview: `Yêu cầu dịch ${source} → ${target}`,
            targetPreview: attempt.fallback_reason || `Kết quả: ${attempt.outcome}`,
          };
        }));
        setTerms(glossary.map((entry) => ({
          id: entry.id,
          sourceTerm: entry.source_term,
          targetTerm: entry.target_term,
          sourceLang: entry.source_language.toUpperCase() as LanguageCode,
          targetLang: entry.target_language.toUpperCase() as LanguageCode,
          category: (entry.domain || 'Công nghệ & AI') as TermCategory,
          priority: entry.keep_verbatim ? 'Bắt buộc (High)' : 'Khuyên dùng (Medium)',
          isStrict: entry.keep_verbatim,
          notes: entry.audience,
          status: entry.status === 'active' ? 'active' : 'inactive',
          usageCount: 0,
          createdBy: 'LinguaFlow',
          createdAt: entry.created_at,
          updatedAt: entry.updated_at,
        })));
        setSuggestions(queue.map((proposal) => ({
          id: proposal.id,
          sourceText: proposal.source_term,
          currentAiTranslation: proposal.target_term,
          suggestedTranslation: proposal.target_term,
          sourceLang: proposal.source_language.toUpperCase() as LanguageCode,
          targetLang: proposal.target_language.toUpperCase() as LanguageCode,
          user: `${proposal.distinct_user_count} người dùng`,
          userEmail: '',
          reason: proposal.rationale,
          status: proposal.status,
          submittedAt: proposal.created_at,
          domain: proposal.domain,
          autoAddToGlossary: !proposal.keep_verbatim,
        })));
    } catch {
      clearServerData();
      setToasts([{ id: 'admin-api-error', message: 'Không thể đồng bộ dữ liệu quản trị từ máy chủ', type: 'error' }]);
    } finally {
      setIsRefreshing(false);
    }
  }, [adminLanguage, clearServerData, timeRange]);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => void loadAdminData());
    return () => window.cancelAnimationFrame(frame);
  }, [loadAdminData]);

  // Toast Helper
  const addToast = (message: string, type: 'success' | 'error' | 'info' = 'success') => {
    const id = `toast-${Date.now()}-${Math.random()}`;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  };

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  // Refresh handler
  const handleRefresh = () => {
    void loadAdminData();
  };

  // Glossary Handlers
  const handleAddTerm = (newTermData: Omit<TermItem, 'id' | 'createdAt' | 'updatedAt' | 'usageCount'>) => {
    const now = new Date().toISOString().split('T')[0];
    const newTerm: TermItem = {
      ...newTermData,
      id: `term-${Date.now()}`,
      usageCount: 0,
      createdAt: now,
      updatedAt: now,
    };
    setTerms((prev) => [newTerm, ...prev]);
  };

  const handleUpdateTerm = (id: string, updatedData: Partial<TermItem>) => {
    setTerms((prev) =>
      prev.map((t) => (t.id === id ? { ...t, ...updatedData } : t))
    );
  };

  const handleDeleteTerm = (id: string) => {
    setTerms((prev) => prev.filter((t) => t.id !== id));
  };

  const handleBatchImportTerms = (
    importedTerms: Omit<TermItem, 'id' | 'createdAt' | 'updatedAt' | 'usageCount'>[]
  ) => {
    const now = new Date().toISOString().split('T')[0];
    const newItems: TermItem[] = importedTerms.map((item, idx) => ({
      ...item,
      id: `term-imp-${Date.now()}-${idx}`,
      usageCount: 0,
      createdAt: now,
      updatedAt: now,
    }));
    setTerms((prev) => [...newItems, ...prev]);
  };

  // Suggestions Handlers
  const handleApproveSuggestion = (id: string, reviewNotes?: string, addToGlossary = true) => {
    const targetSug = suggestions.find((s) => s.id === id);
    if (!targetSug) return;

    setSuggestions((prev) =>
      prev.map((s) =>
        s.id === id
          ? {
              ...s,
              status: 'approved',
              reviewedAt: new Date().toLocaleString(),
              reviewedBy: 'Admin LinguaFlow',
              reviewNotes: reviewNotes || 'Đã kiểm duyệt và chấp thuận cập nhật.',
            }
          : s
      )
    );

    // If auto add to glossary
    if (addToGlossary) {
      // Create a sensible term pair
      handleAddTerm({
        sourceTerm: targetSug.sourceText.length > 40 ? targetSug.sourceText.slice(0, 40) + '...' : targetSug.sourceText,
        targetTerm: targetSug.suggestedTranslation.length > 50 ? targetSug.suggestedTranslation.slice(0, 50) + '...' : targetSug.suggestedTranslation,
        sourceLang: targetSug.sourceLang,
        targetLang: targetSug.targetLang,
        category: (targetSug.domain as TermCategory) || 'Công nghệ & AI',
        priority: 'Bắt buộc (High)',
        isStrict: false,
        notes: `Tự động tạo từ đề xuất #${id} của ${targetSug.user}`,
        status: 'active',
        createdBy: targetSug.userEmail,
      });
    }
  };

  const handleRejectSuggestion = (id: string, reason?: string) => {
    setSuggestions((prev) =>
      prev.map((s) =>
        s.id === id
          ? {
              ...s,
              status: 'rejected',
              reviewedAt: new Date().toLocaleString(),
              reviewedBy: 'Admin LinguaFlow',
              reviewNotes: reason || 'Chưa phù hợp với quy chuẩn dịch hiện tại.',
            }
          : s
      )
    );
  };

  const handleCreateSuggestionFromChat = (sugData: {
    sourceText: string;
    currentAiTranslation: string;
    suggestedTranslation: string;
    sourceLang: LanguageCode;
    targetLang: LanguageCode;
    user: string;
    userEmail: string;
    reason: string;
  }) => {
    const newSug: TranslationSuggestion = {
      id: `sug-${Date.now()}`,
      ...sugData,
      status: 'pending',
      submittedAt: new Date().toLocaleString(),
      domain: 'Công nghệ & AI',
      autoAddToGlossary: true,
    };
    setSuggestions((prev) => [newSug, ...prev]);
  };

  // Live translation completed from Chat view
  const handleNewTranslationFromChat = (data: {
    pair: LanguagePair;
    model: string;
    isFallback: boolean;
    latency: number;
    inputTokens: number;
    outputTokens: number;
    sourceText: string;
    targetText: string;
    matchedTerms: string[];
  }) => {
    // 1. Add to request logs
    const newLog: RequestLog = {
      id: `req-${Date.now()}`,
      timestamp: new Date().toLocaleString(),
      pair: data.pair,
      model: data.model,
      isFallback: data.isFallback,
      status: data.isFallback ? 'warning' : 'success',
      latency: data.latency,
      inputTokens: data.inputTokens,
      outputTokens: data.outputTokens,
      sourcePreview: data.sourceText,
      targetPreview: data.targetText,
      matchedGlossaryTerms: data.matchedTerms,
    };
    setRequestLogs((prev) => [newLog, ...prev.slice(0, 19)]);

    // 2. Increment stats
    setMetrics((prev) =>
      prev.map((m) => {
        if (m.id === 'total_translations') {
          return { ...m, value: Number(m.value) + 1 };
        }
        return m;
      })
    );

    // 3. Increment language pair count
    setLanguagePairs((prev) =>
      prev.map((lp) => {
        if (lp.pair === data.pair) {
          const newCount = lp.count + 1;
          return { ...lp, count: newCount };
        }
        return lp;
      })
    );

    // 4. Increment AI model count
    setAiModels((prev) =>
      prev.map((am) => {
        if (am.name.includes(data.model) || (data.isFallback && am.id === 'fallback-unknown')) {
          return { ...am, servedCount: am.servedCount + 1 };
        }
        return am;
      })
    );
  };

  const pendingSuggestionsCount = suggestions.filter((s) => s.status === 'pending').length;
  const totalTermsCount = terms.length;

  return (
    <div id="admin-app-shell" data-theme={adminTheme} className="min-h-screen overflow-x-hidden bg-[#F9FAFB] font-sans text-gray-900 antialiased">
      {/* Sidebar Navigation */}
      <Sidebar
        currentTab={currentTab}
        onTabChange={setCurrentTab}
        pendingSuggestionsCount={pendingSuggestionsCount}
        totalTermsCount={totalTermsCount}
        interfaceLanguage={adminLanguage}
        theme={adminTheme}
        onInterfaceLanguageChange={setAdminLanguage}
        onThemeChange={setAdminTheme}
        adminName={adminProfile.name}
        adminEmail={adminProfile.email}
        adminRole={adminProfile.role}
      />

      {/* Main Content Area */}
      <div
        className="flex min-h-screen min-w-0 flex-col bg-[#F9FAFB]"
        style={{ marginLeft: 72, width: 'calc(100% - 72px)' }}
      >
        {/* Global Header */}
        <Header
          currentTab={currentTab}
          interfaceLanguage={adminLanguage}
          timeRange={timeRange}
          onTimeRangeChange={setTimeRange}
          onRefresh={handleRefresh}
          isRefreshing={isRefreshing}
          onToggleMobileSidebar={() => setIsMobileSidebarOpen(!isMobileSidebarOpen)}
        />

        {/* Dynamic Body Content */}
        <main className="flex-1 p-6 sm:p-8 max-w-7xl w-full mx-auto space-y-6">
          {currentTab === 'analytics' && (
            <AnalyticsView
              metrics={metrics}
              languagePairs={languagePairs}
              aiModels={aiModels}
              timeSeriesData={[]}
              requestLogs={requestLogs}
              timeRange={timeRange}
              onOpenLiveChat={() => setCurrentTab('chat')}
            />
          )}

          {currentTab === 'glossary' && (
            <GlossaryView
              terms={terms}
              onAddTerm={handleAddTerm}
              onUpdateTerm={handleUpdateTerm}
              onDeleteTerm={handleDeleteTerm}
              onBatchImport={handleBatchImportTerms}
              onNotify={addToast}
            />
          )}

          {currentTab === 'suggestions' && (
            <SuggestionsView
              suggestions={suggestions}
              onApprove={handleApproveSuggestion}
              onReject={handleRejectSuggestion}
              onNotify={addToast}
            />
          )}

          {currentTab === 'chat' && (
            <LiveChatView
              terms={terms}
              onBackToAdmin={() => setCurrentTab('analytics')}
              onNewTranslationComplete={handleNewTranslationFromChat}
              onSubmitSuggestion={handleCreateSuggestionFromChat}
              onNotify={addToast}
            />
          )}
        </main>
      </div>

      {/* Toast Notification Container */}
      <ToastContainer toasts={toasts} onDismiss={removeToast} />
    </div>
  );
}
