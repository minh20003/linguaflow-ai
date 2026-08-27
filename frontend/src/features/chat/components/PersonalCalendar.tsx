"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ApiCalendarEvent } from "../api/chat-api";
import { GoogleCalendarControls } from "./GoogleCalendarControls";
import {
  cancelCalendarEvent,
  createCalendarEvent,
  listCalendarEvents,
  updateCalendarEvent,
} from "../api/chat-api";
import {
  Bot, CalendarDays, Check, CheckCircle2, ChevronLeft, ChevronRight,
  CirclePlus, Clock3, ExternalLink, ListTodo, Plus, RefreshCw, Search, SendHorizontal, Settings, Trash2, X,
} from "lucide-react";

type TaskStatus = "pending" | "approved" | "rejected" | "done";
type TaskSource = "assistant" | "manual" | "google";
type CalendarMode = "day" | "week" | "month";

interface CalendarTask {
  id: string;
  title: string;
  note?: string;
  dueAt: string;
  duration: number;
  status: TaskStatus;
  source: TaskSource;
  priority: "low" | "medium" | "high";
  category?: "task" | "meeting" | "deadline" | "personal" | "focus";
  location?: string;
  tags?: string[];
  kind?: "task" | "event";
  link?: string;
}

/** Map one stored event onto the shape this component was written around.
 *
 *  The component predates the API and models a "task" with a duration and a
 *  status; the server models an event with a start and an end. Converting here
 *  keeps the whole rendering layer — day, week and month grids, the detail
 *  modal, the filters — working unchanged, which is most of the file.
 */
function toCalendarTask(event: ApiCalendarEvent): CalendarTask {
  const starts = new Date(event.starts_at);
  const ends = event.ends_at ? new Date(event.ends_at) : null;
  const minutes = ends ? Math.max(15, Math.round((+ends - +starts) / 60000)) : 60;
  return {
    id: event.id,
    title: event.title,
    note: event.details ?? undefined,
    dueAt: event.starts_at,
    duration: event.all_day ? 1440 : minutes,
    // Everything on the calendar has already been decided; a pending proposal
    // is in the task inbox, not here.
    status: event.status === "cancelled" ? "rejected" : "approved",
    source: event.source,
    priority: "medium",
    category: event.all_day ? "personal" : "task",
    location: event.location ?? undefined,
    kind: event.all_day ? "event" : "task",
  };
}

const HOUR_HEIGHT = 64;
const DEFAULT_START_HOUR = 7;
const DEFAULT_END_HOUR = 22;
const MIN_DURATION = 15;

interface PositionedTask {
  task: CalendarTask;
  top: number;
  height: number;
  left: number;
  width: number;
}

const minutesOf = (value: Date) => value.getHours() * 60 + value.getMinutes();
const taskSpan = (task: CalendarTask) => {
  const start = minutesOf(new Date(task.dueAt));
  return { start, end: start + Math.max(MIN_DURATION, task.duration) };
};

/** Grid chỉ hiển thị 7h–22h theo mặc định, nhưng nới ra nếu có việc nằm ngoài khung đó. */
function hourRange(tasks: CalendarTask[]) {
  let first = DEFAULT_START_HOUR;
  let last = DEFAULT_END_HOUR;
  for (const task of tasks) {
    if (task.kind === "event") continue;
    const { start, end } = taskSpan(task);
    first = Math.min(first, Math.floor(start / 60));
    last = Math.max(last, Math.min(23, Math.ceil(end / 60) - 1));
  }
  return Array.from({ length: last - first + 1 }, (_, index) => first + index);
}

/** Xếp các việc trùng giờ thành nhiều cột cạnh nhau thay vì đè lên nhau. */
function layoutDay(tasks: CalendarTask[], startHour: number): PositionedTask[] {
  const timed = tasks
    .filter((task) => task.kind !== "event")
    .sort((left, right) => taskSpan(left).start - taskSpan(right).start || taskSpan(right).end - taskSpan(left).end);

  const clusters: CalendarTask[][] = [];
  let cluster: CalendarTask[] = [];
  let clusterEnd = -1;
  for (const task of timed) {
    const { start, end } = taskSpan(task);
    if (cluster.length && start < clusterEnd) {
      cluster.push(task);
      clusterEnd = Math.max(clusterEnd, end);
    } else {
      if (cluster.length) clusters.push(cluster);
      cluster = [task];
      clusterEnd = end;
    }
  }
  if (cluster.length) clusters.push(cluster);

  const positioned: PositionedTask[] = [];
  const offset = startHour * 60;
  for (const group of clusters) {
    const columns: CalendarTask[][] = [];
    for (const task of group) {
      const { start } = taskSpan(task);
      const column = columns.find((items) => taskSpan(items[items.length - 1]).end <= start);
      if (column) column.push(task);
      else columns.push([task]);
    }
    const width = 100 / columns.length;
    columns.forEach((items, index) => items.forEach((task) => {
      const { start, end } = taskSpan(task);
      positioned.push({
        task,
        top: ((start - offset) / 60) * HOUR_HEIGHT,
        height: Math.max(26, ((end - start) / 60) * HOUR_HEIGHT - 2),
        left: index * width,
        width,
      });
    }));
  }
  return positioned;
}

function tasksOfDay(tasks: CalendarTask[], day: Date) {
  return tasks.filter((task) => sameDay(new Date(task.dueAt), day));
}

function startOfWeek(value: Date) {
  const date = new Date(value);
  const offset = (date.getDay() + 6) % 7;
  date.setDate(date.getDate() - offset);
  date.setHours(0, 0, 0, 0);
  return date;
}

function sameDay(left: Date, right: Date) {
  return left.getFullYear() === right.getFullYear() && left.getMonth() === right.getMonth() && left.getDate() === right.getDate();
}

function toInputValue(value: Date) {
  const offset = value.getTimezoneOffset();
  return new Date(value.getTime() - offset * 60_000).toISOString().slice(0, 16);
}

function sourceLabel(source: TaskSource) {
  if (source === "assistant") return "Trợ lý đề xuất";
  if (source === "google") return "Google Calendar";
  return "Tạo thủ công";
}

function statusLabel(status: TaskStatus) {
  return ({ pending: "Chờ duyệt", approved: "Đã lên lịch", rejected: "Đã từ chối", done: "Hoàn thành" })[status];
}

interface PersonalCalendarProps {
  token: string;
  onNotify?: (title: string, detail?: string, tone?: "success" | "warning") => void;
  /** Bumped by the parent when a socket event says the calendar moved. */
  refreshToken?: number;
}

export const PersonalCalendar: React.FC<PersonalCalendarProps> = ({
  token,
  onNotify,
  refreshToken = 0,
}) => {
  const [tasks, setTasks] = useState<CalendarTask[]>([]);
  const [mode, setMode] = useState<CalendarMode>("week");
  const [cursor, setCursor] = useState(() => new Date());
  const [query, setQuery] = useState("");
  const [showProposalDialog, setShowProposalDialog] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [newItemKind, setNewItemKind] = useState<"task" | "event">("task");
  const [showCreateMenu, setShowCreateMenu] = useState(false);
  const [showAssistant, setShowAssistant] = useState(false);
  const [selectedTask, setSelectedTask] = useState<CalendarTask | null>(null);
  const [editingTask, setEditingTask] = useState<CalendarTask | null>(null);
  const [sourceFilter, setSourceFilter] = useState<TaskSource | "all">("all");
  const [statusFilter, setStatusFilter] = useState<TaskStatus | "all">("all");
  const [showSidebar, setShowSidebar] = useState(false);
  const [now, setNow] = useState(() => new Date());
  const createMenuRef = useRef<HTMLDivElement | null>(null);
  const hydrated = useRef(false);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 60_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!showCreateMenu) return;
    const handleOutside = (event: MouseEvent) => {
      if (!createMenuRef.current?.contains(event.target as Node)) setShowCreateMenu(false);
    };
    window.addEventListener("mousedown", handleOutside);
    return () => window.removeEventListener("mousedown", handleOutside);
  }, [showCreateMenu]);

  // The calendar lives on the server, not in this browser. It used to be held
  // in localStorage, which meant it existed only on one machine, could not be
  // reminded about, and could never reach Google.
  const reload = useCallback(async () => {
    try {
      const events = await listCalendarEvents(token);
      setTasks(events.map(toCalendarTask));
      hydrated.current = true;
    } catch (error) {
      onNotify?.(
        "Không tải được lịch",
        error instanceof Error ? error.message : undefined,
        "warning",
      );
    }
  }, [token, onNotify]);

  useEffect(() => {
    void reload();
  }, [reload, refreshToken]);

  const visibleTasks = useMemo(() => tasks.filter((task) => {
    const matchesSearch = `${task.title} ${task.note ?? ""}`.toLocaleLowerCase().includes(query.toLocaleLowerCase());
    return matchesSearch && task.status !== "pending" && (sourceFilter === "all" || task.source === sourceFilter) && (statusFilter === "all" || task.status === statusFilter);
  }), [query, sourceFilter, statusFilter, tasks]);

  const scheduledTasks = useMemo(
    () => visibleTasks.filter((task) => task.status === "approved" || task.status === "done" || task.source === "google"),
    [visibleTasks],
  );
  const proposals = useMemo(() => tasks.filter((task) => {
    const matchesSearch = `${task.title} ${task.note ?? ""}`.toLocaleLowerCase().includes(query.toLocaleLowerCase());
    return task.status === "pending" && matchesSearch && (sourceFilter === "all" || task.source === sourceFilter);
  }), [query, sourceFilter, tasks]);
  const upcoming = useMemo(
    () => [...visibleTasks].sort((left, right) => +new Date(left.dueAt) - +new Date(right.dueAt)),
    [visibleTasks],
  );
  const weekDays = useMemo(() => {
    const weekStart = startOfWeek(cursor);
    return Array.from({ length: 7 }, (_, index) => {
      const date = new Date(weekStart);
      date.setDate(weekStart.getDate() + index);
      return date;
    });
  }, [cursor]);
  const weekStart = weekDays[0];
  const hours = useMemo(() => hourRange(scheduledTasks), [scheduledTasks]);

  const updateTask = (id: string, update: Partial<CalendarTask>) =>
    setTasks((items) => items.map((task) => (task.id === id ? { ...task, ...update } : task)));

  // Approval lives in the task inbox, where the proposal and its clarification
  // question are. The calendar shows what was already decided, so these three
  // only exist for entries that reached it.
  const approve = (task: CalendarTask) => updateTask(task.id, { status: "approved" });
  const reject = (task: CalendarTask) => updateTask(task.id, { status: "rejected" });
  const finish = (task: CalendarTask) => updateTask(task.id, { status: "done" });

  const removeTask = async (task: CalendarTask) => {
    // Optimistic, then reconciled by `reload`. The server cancels rather than
    // deletes, so a failure leaves the entry visible rather than losing it.
    setTasks((items) => items.filter((item) => item.id !== task.id));
    try {
      await cancelCalendarEvent(token, task.id);
    } catch (error) {
      onNotify?.(
        "Không xoá được",
        error instanceof Error ? error.message : undefined,
        "warning",
      );
    } finally {
      await reload();
    }
  };

  const saveTask = async (task: CalendarTask) => {
    try {
      if (tasks.some((item) => item.id === task.id)) {
        await updateCalendarEvent(token, task.id, {
          title: task.title,
          details: task.note ?? null,
          location: task.location ?? null,
          starts_at: new Date(task.dueAt).toISOString(),
          all_day: task.kind === "event",
        });
      } else {
        await createCalendarEvent(token, {
          title: task.title,
          starts_at: new Date(task.dueAt).toISOString(),
          details: task.note ?? null,
          location: task.location ?? null,
          all_day: task.kind === "event",
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        });
      }
    } catch (error) {
      onNotify?.(
        "Không lưu được",
        error instanceof Error ? error.message : undefined,
        "warning",
      );
    } finally {
      await reload();
    }
  };

  const navigate = useCallback((direction: -1 | 1) => setCursor((date) => {
    const next = new Date(date);
    if (mode === "day") next.setDate(next.getDate() + direction);
    else if (mode === "week") next.setDate(next.getDate() + direction * 7);
    else next.setMonth(next.getMonth() + direction);
    return next;
  }), [mode]);

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return;
      if (event.key === "ArrowLeft") navigate(-1);
      else if (event.key === "ArrowRight") navigate(1);
      else if (event.key.toLowerCase() === "t") setCursor(new Date());
      else if (event.key.toLowerCase() === "d") setMode("day");
      else if (event.key.toLowerCase() === "w") setMode("week");
      else if (event.key.toLowerCase() === "m") setMode("month");
      else return;
      event.preventDefault();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [navigate]);

  const currentPeriod = mode === "day"
    ? cursor.toLocaleDateString("vi-VN", { weekday: "long", day: "numeric", month: "long", year: "numeric" })
    : mode === "week"
    ? `${weekStart.toLocaleDateString("vi-VN", { day: "numeric", month: "short" })} – ${weekDays[6].toLocaleDateString("vi-VN", { day: "numeric", month: "short", year: "numeric" })}`
    : cursor.toLocaleDateString("vi-VN", { month: "long", year: "numeric" });

  return (
    <section className="flex h-screen min-w-0 flex-1 bg-[#F7F8FC] dark:bg-[#14161C]" aria-label="Lịch cá nhân">
      <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <header className="border-b border-[#E8EAF0] bg-white px-5 py-4 dark:border-[#2E3342] dark:bg-[#1C1F27] sm:px-7">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#EFF6FF] text-[#2563EB] dark:bg-[#2563EB]/20 dark:text-[#60A5FA]"><CalendarDays className="h-5 w-5" /></span>
                <div><h1 className="text-xl font-bold text-[#1E2230] dark:text-[#F5F6FA]">Lịch cá nhân</h1><p className="text-xs text-[#74798C] dark:text-[#9DA3B4]">Sắp xếp công việc, dành thời gian cho điều quan trọng.</p></div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <GoogleCalendarControls token={token} onSynced={() => void reload()} onNotify={onNotify} />
              <button onClick={() => setShowAssistant(true)} className="rounded-xl border border-violet-200 bg-violet-50 px-3 py-2 text-xs font-semibold text-violet-700 hover:bg-violet-100 dark:border-violet-400/30 dark:bg-violet-500/10 dark:text-violet-300">Lập lịch bằng Trợ lý</button>
              <button onClick={() => setShowSidebar(true)} aria-label="Mở danh sách việc" className="inline-flex items-center gap-1.5 rounded-xl border border-[#E8EAF0] bg-white px-3 py-2 text-xs font-semibold text-[#4E5568] hover:bg-[#F7F8FC] dark:border-[#2E3342] dark:bg-[#232630] dark:text-[#C6CAD6] dark:hover:bg-[#2E3342] xl:hidden"><ListTodo className="h-4 w-4" />Việc</button>
              <div className="relative" ref={createMenuRef}><button onClick={() => setShowCreateMenu((value) => !value)} className="inline-flex items-center gap-1.5 rounded-xl bg-[#2563EB] px-3 py-2 text-xs font-semibold text-white shadow-sm hover:bg-[#1D4ED8]"><Plus className="h-4 w-4" />Thêm</button>{showCreateMenu && <div className="absolute right-0 top-full z-30 mt-2 w-56 overflow-hidden rounded-xl border border-[#E8EAF0] bg-white p-1.5 shadow-xl dark:border-[#2E3342] dark:bg-[#232630]"><button onClick={() => { setNewItemKind("event"); setShowForm(true); setShowCreateMenu(false); }} className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left hover:bg-[#F7F8FC] dark:hover:bg-[#2E3342]"><span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#EFF6FF] text-[#2563EB] dark:bg-[#2563EB]/20 dark:text-[#60A5FA]"><CalendarDays className="h-4 w-4" /></span><span className="text-xs font-bold text-[#1E2230] dark:text-[#F5F6FA]">Sự kiện</span></button><button onClick={() => { setNewItemKind("task"); setShowForm(true); setShowCreateMenu(false); }} className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left hover:bg-[#F7F8FC] dark:hover:bg-[#2E3342]"><span className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-300"><CheckCircle2 className="h-4 w-4" /></span><span className="text-xs font-bold text-[#1E2230] dark:text-[#F5F6FA]">Việc</span></button></div>}</div>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-[#F1F2F5] pt-3 dark:border-[#2A2E3D]">
            <div className="flex items-center gap-2">
              <div className="flex items-center rounded-lg border border-[#E8EAF0] bg-[#F7F8FC] p-0.5 dark:border-[#2E3342] dark:bg-[#232630]">
                <button aria-label="Kỳ trước" onClick={() => navigate(-1)} className="rounded-md p-1.5 text-[#74798C] hover:bg-white hover:text-[#1E2230] dark:hover:bg-[#2E3342]"><ChevronLeft className="h-4 w-4" /></button>
                <h2 className="min-w-[180px] px-2 text-center text-sm font-bold text-[#1E2230] dark:text-[#F5F6FA] sm:min-w-[235px]">{currentPeriod}</h2>
                <button aria-label="Kỳ sau" onClick={() => navigate(1)} className="rounded-md p-1.5 text-[#74798C] hover:bg-white hover:text-[#1E2230] dark:hover:bg-[#2E3342]"><ChevronRight className="h-4 w-4" /></button>
              </div>
              <button onClick={() => setCursor(new Date())} className="rounded-lg border border-[#E8EAF0] bg-white px-2.5 py-1.5 text-xs font-semibold text-[#1E2230] hover:bg-[#F7F8FC] dark:border-[#2E3342] dark:bg-[#232630] dark:text-[#F5F6FA] dark:hover:bg-[#2E3342]">Hôm nay</button>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => setShowProposalDialog(true)} className="rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-1.5 text-xs font-medium text-amber-700 hover:bg-amber-100">Đề xuất ({proposals.length})</button>
              <div className="flex rounded-lg bg-[#F1F2F5] p-1 dark:bg-[#232630]">
                {(["day", "week", "month"] as CalendarMode[]).map((item) => <button key={item} onClick={() => setMode(item)} className={`rounded-md px-2.5 py-1 text-xs font-semibold ${mode === item ? "bg-white text-[#2563EB] shadow-sm dark:bg-[#2E3342] dark:text-[#60A5FA]" : "text-[#74798C]"}`}>{item === "day" ? "Ngày" : item === "week" ? "Tuần" : "Tháng"}</button>)}
              </div>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-[#F1F2F5] pt-3 text-xs dark:border-[#2A2E3D]">
            <span className="font-semibold text-[#74798C]">Lọc:</span>
            <select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value as TaskSource | "all")} className="rounded-lg border border-[#E8EAF0] bg-white px-2 py-1.5 text-xs text-[#4E5568] outline-none dark:border-[#2E3342] dark:bg-[#232630] dark:text-[#C6CAD6]"><option value="all">Mọi nguồn</option><option value="assistant">Trợ lý</option><option value="manual">Thủ công</option><option value="google">Google</option></select>
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as TaskStatus | "all")} className="rounded-lg border border-[#E8EAF0] bg-white px-2 py-1.5 text-xs text-[#4E5568] outline-none dark:border-[#2E3342] dark:bg-[#232630] dark:text-[#C6CAD6]"><option value="all">Mọi trạng thái</option><option value="approved">Đã lên lịch</option><option value="done">Hoàn thành</option><option value="rejected">Đã từ chối</option></select>
            
          </div>
        </header>

        <div className="flex min-h-0 flex-1 overflow-hidden">
          <div className="flex min-w-0 flex-1 flex-col overflow-hidden bg-white dark:bg-[#1C1F27]">
            {mode === "day" ? <DayGrid day={cursor} hours={hours} now={now} tasks={scheduledTasks} onSelect={setSelectedTask} /> : mode === "week" ? <WeekGrid days={weekDays} hours={hours} now={now} tasks={scheduledTasks} onSelect={setSelectedTask} /> : <MonthGrid cursor={cursor} tasks={scheduledTasks} onSelect={setSelectedTask} />}
          </div>
          {showSidebar && <button aria-label="Đóng danh sách" onClick={() => setShowSidebar(false)} className="fixed inset-0 z-30 bg-[#111827]/40 xl:hidden" />}
          <aside className={`${showSidebar ? "fixed inset-y-0 right-0 z-40 flex w-[300px] max-w-[85vw] flex-col shadow-2xl" : "hidden"} shrink-0 border-l border-[#E8EAF0] bg-white dark:border-[#2E3342] dark:bg-[#1C1F27] xl:static xl:z-auto xl:flex xl:w-[300px] xl:flex-col xl:shadow-none`}>
            <div className="flex items-center justify-between border-b border-[#E8EAF0] px-4 py-3 dark:border-[#2E3342] xl:hidden">
              <h3 className="text-xs font-bold uppercase tracking-wide text-[#74798C]">Việc &amp; đề xuất</h3>
              <button onClick={() => setShowSidebar(false)} aria-label="Đóng" className="rounded-lg p-1 text-[#74798C] hover:bg-[#F4F5F8] dark:hover:bg-[#2E3342]"><X className="h-4 w-4" /></button>
            </div>
            <div className="border-b border-[#E8EAF0] p-4 dark:border-[#2E3342]"><div className="relative"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8A8F9E]" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm việc..." className="w-full rounded-xl border border-[#E8EAF0] bg-[#F7F8FC] py-2 pl-9 pr-3 text-xs text-[#1E2230] outline-none focus:border-[#2563EB] dark:border-[#2E3342] dark:bg-[#232630] dark:text-white" /></div></div>
            <div className="border-b border-[#E8EAF0] p-4 dark:border-[#2E3342]"><div className="mb-2 flex items-center justify-between"><h3 className="text-xs font-bold uppercase tracking-wide text-[#74798C]">Cần bạn duyệt</h3><span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-700">{proposals.length}</span></div><p className="text-[11px] leading-relaxed text-[#8A8F9E]">Trợ lý không tự thêm việc vào lịch. Hãy duyệt hoặc từ chối từng đề xuất.</p></div>
            <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-4">
              {proposals.length === 0 ? <Empty label="Không còn đề xuất chờ duyệt" /> : proposals.map((task) => <TaskCard key={task.id} task={task} onSelect={setSelectedTask} onApprove={approve} onReject={reject} onFinish={finish} />)}
              <h3 className="pt-3 text-xs font-bold uppercase tracking-wide text-[#74798C]">Sắp tới</h3>
              {upcoming.length === 0 ? <Empty label="Không có việc nào khớp bộ lọc" /> : upcoming.map((task) => <TaskCard key={task.id} task={task} onSelect={setSelectedTask} onApprove={approve} onReject={reject} onFinish={finish} />)}
            </div>
          </aside>
        </div>
      </main>
      {showForm && <TaskForm initialKind={newItemKind} onClose={() => setShowForm(false)} onSubmit={(task) => { setTasks((items) => [...items, task]); setShowForm(false); }} />}
      {editingTask && <TaskForm initialTask={editingTask} onClose={() => setEditingTask(null)} onSubmit={(task) => { setTasks((items) => items.map((item) => item.id === editingTask.id ? { ...task, id: editingTask.id, source: item.source, status: item.status } : item)); setEditingTask(null); setSelectedTask(null); }} />}
      {showAssistant && <AssistantForm onClose={() => setShowAssistant(false)} onSubmit={(task) => { setTasks((items) => [...items, task]); setShowAssistant(false); }} />}
      {showProposalDialog && <ProposalReviewDialog proposals={proposals} onClose={() => setShowProposalDialog(false)} onApprove={approve} onReject={reject} />}
      {selectedTask && <TaskDetails task={selectedTask} onClose={() => setSelectedTask(null)} onApprove={approve} onReject={reject} onFinish={finish} onEdit={() => setEditingTask(selectedTask)} onDelete={() => { setTasks((items) => items.filter((task) => task.id !== selectedTask.id)); setSelectedTask(null); }} />}
    </section>
  );
};

interface GridProps {
  hours: number[];
  now: Date;
  tasks: CalendarTask[];
  onSelect: (task: CalendarTask) => void;
}

/** Canh khung giờ về gần thời điểm hiện tại khi mở lịch hoặc đổi chế độ xem. */
function useScrollToNow(startHour: number) {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const target = ((minutesOf(new Date()) - startHour * 60) / 60) * HOUR_HEIGHT - HOUR_HEIGHT * 1.5;
    node.scrollTop = Math.max(0, target);
  }, [startHour]);
  return ref;
}

const WeekGrid: React.FC<GridProps & { days: Date[] }> = ({ days, hours, now, tasks, onSelect }) => {
  const startHour = hours[0];
  const gridHeight = hours.length * HOUR_HEIGHT;
  const scrollRef = useScrollToNow(startHour);
  const columns = useMemo(() => days.map((day) => {
    const dayTasks = tasksOfDay(tasks, day);
    return { day, allDay: dayTasks.filter((task) => task.kind === "event"), timed: layoutDay(dayTasks, startHour) };
  }), [days, tasks, startHour]);
  const hasAllDay = columns.some((column) => column.allDay.length > 0);

  return (
    <div ref={scrollRef} className="flex min-h-0 flex-1 flex-col overflow-auto pb-4">
      <div className="sticky top-0 z-20 min-w-[760px] border-b border-[#E8EAF0] bg-white dark:border-[#2E3342] dark:bg-[#1C1F27]">
        <div className="grid grid-cols-[60px_repeat(7,minmax(100px,1fr))] text-center">
          <div className="flex items-center justify-center border-r border-[#F1F2F5] p-3 text-[10px] font-bold uppercase tracking-wider text-[#8A8F9E] dark:border-[#2A2E3D]">GMT+7</div>
          {days.map((day) => <div key={day.toISOString()} className={`border-r border-[#F1F2F5] px-1 py-2 last:border-r-0 dark:border-[#2A2E3D] ${sameDay(day, now) ? "bg-[#EFF6FF]/60 dark:bg-[#2563EB]/10" : ""}`}><div className="text-[11px] font-bold uppercase tracking-wider text-[#8A8F9E]">{day.toLocaleDateString("vi-VN", { weekday: "short" })}</div><span className={`mt-0.5 inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${sameDay(day, now) ? "bg-[#2563EB] text-white shadow-sm" : "text-[#1E2230] dark:text-[#F5F6FA]"}`}>{day.getDate()}</span></div>)}
        </div>
        {hasAllDay && (
          <div className="grid grid-cols-[60px_repeat(7,minmax(100px,1fr))] border-t border-[#F1F2F5] dark:border-[#2A2E3D]">
            <div className="flex items-start justify-end border-r border-[#F1F2F5] px-2 py-1.5 text-[9px] font-bold uppercase tracking-wide text-[#8A8F9E] dark:border-[#2A2E3D]">Cả ngày</div>
            {columns.map(({ day, allDay }) => <div key={day.toISOString()} className="space-y-1 border-r border-[#F1F2F5] p-1 last:border-r-0 dark:border-[#2A2E3D]">{allDay.map((task) => <AllDayChip key={task.id} task={task} onSelect={onSelect} />)}</div>)}
          </div>
        )}
      </div>
      <div className="grid min-w-[760px] grid-cols-[60px_repeat(7,minmax(100px,1fr))] divide-x divide-[#F1F2F5] bg-white dark:divide-[#2A2E3D] dark:bg-[#1C1F27]">
        <div className="bg-white dark:bg-[#1C1F27]">{hours.map((hour) => <div key={hour} style={{ height: HOUR_HEIGHT }} className="border-b border-[#F1F2F5] pr-2 pt-1 text-right text-[10px] font-bold text-[#8A8F9E] dark:border-[#2A2E3D]">{`${String(hour).padStart(2, "0")}:00`}</div>)}</div>
        {columns.map(({ day, timed }) => (
          <div key={day.toISOString()} className={`relative ${sameDay(day, now) ? "bg-[#EFF6FF]/25 dark:bg-[#2563EB]/5" : "bg-white dark:bg-[#1C1F27]"}`} style={{ height: gridHeight }}>
            {hours.map((hour) => <div key={hour} style={{ height: HOUR_HEIGHT }} className="border-b border-[#F1F2F5] dark:border-[#2A2E3D]" />)}
            {timed.map((item) => <TimedTask key={item.task.id} item={item} onSelect={onSelect} />)}
            {sameDay(day, now) && <NowLine now={now} startHour={startHour} gridHeight={gridHeight} />}
          </div>
        ))}
      </div>
    </div>
  );
};

const DayGrid: React.FC<GridProps & { day: Date }> = ({ day, hours, now, tasks, onSelect }) => {
  const startHour = hours[0];
  const gridHeight = hours.length * HOUR_HEIGHT;
  const scrollRef = useScrollToNow(startHour);
  const dayTasks = tasksOfDay(tasks, day);
  const allDay = dayTasks.filter((task) => task.kind === "event");
  const timed = layoutDay(dayTasks, startHour);

  return <div ref={scrollRef} className="flex min-h-0 flex-1 flex-col overflow-auto pb-4">
    <div className="sticky top-0 z-20 min-w-[520px] border-b border-[#E8EAF0] bg-white px-5 py-3 dark:border-[#2E3342] dark:bg-[#1C1F27]">
      <div className="text-xs font-bold uppercase tracking-wide text-[#8A8F9E]">{day.toLocaleDateString("vi-VN", { weekday: "long" })}</div>
      <div className={`mt-1 inline-flex h-9 w-9 items-center justify-center rounded-full text-sm font-bold ${sameDay(day, now) ? "bg-[#2563EB] text-white" : "bg-[#F1F2F5] text-[#1E2230] dark:bg-[#2E3342] dark:text-[#F5F6FA]"}`}>{day.getDate()}</div>
      {allDay.length > 0 && <div className="mt-3 flex items-start gap-3"><span className="pt-1 text-[10px] font-bold uppercase tracking-wide text-[#8A8F9E]">Cả ngày</span><div className="flex flex-1 flex-wrap gap-1.5">{allDay.map((task) => <AllDayChip key={task.id} task={task} onSelect={onSelect} />)}</div></div>}
    </div>
    <div className="grid min-w-[520px] grid-cols-[72px_minmax(0,1fr)] bg-white dark:bg-[#1C1F27]">
      <div className="border-r border-[#E8EAF0] bg-white dark:border-[#2E3342] dark:bg-[#1C1F27]">{hours.map((hour) => <div key={hour} style={{ height: HOUR_HEIGHT }} className="border-b border-[#F1F2F5] pr-3 pt-1 text-right text-[10px] font-bold text-[#8A8F9E] dark:border-[#2A2E3D]">{String(hour).padStart(2, "0")}:00</div>)}</div>
      <div className={`relative ${sameDay(day, now) ? "bg-[#EFF6FF]/25 dark:bg-[#2563EB]/5" : "bg-white dark:bg-[#1C1F27]"}`} style={{ height: gridHeight }}>
        {hours.map((hour) => <div key={hour} style={{ height: HOUR_HEIGHT }} className="border-b border-[#F1F2F5] dark:border-[#2A2E3D]" />)}
        {timed.map((item) => <TimedTask key={item.task.id} item={item} onSelect={onSelect} />)}
        {sameDay(day, now) && <NowLine now={now} startHour={startHour} gridHeight={gridHeight} />}
        {timed.length === 0 && <div className="absolute inset-x-0 top-20 text-center text-xs text-[#8A8F9E]">Chưa có việc nào trong ngày này.</div>}
      </div>
    </div>
  </div>;
};

const taskColor = (task: CalendarTask) => task.source === "google"
  ? "border-sky-500 bg-sky-50 text-sky-800 dark:bg-sky-500/15 dark:text-sky-200"
  : task.status === "done"
    ? "border-emerald-500 bg-emerald-50 text-emerald-800 opacity-70 dark:bg-emerald-500/15 dark:text-emerald-200"
    : "border-[#2563EB] bg-[#EFF6FF] text-[#1D4ED8] dark:bg-[#2563EB]/15 dark:text-[#93C5FD]";

const TimedTask: React.FC<{ item: PositionedTask; onSelect: (task: CalendarTask) => void }> = ({ item, onSelect }) => {
  const { task } = item;
  const date = new Date(task.dueAt);
  return <button onClick={() => onSelect(task)} style={{ top: item.top + 1, height: item.height, left: `calc(${item.left}% + 4px)`, width: `calc(${item.width}% - 8px)` }} className={`absolute overflow-hidden rounded-lg border-l-4 p-1.5 text-left shadow-sm transition-shadow hover:shadow-md ${taskColor(task)}`}><span className="block truncate text-[10px] font-bold">{task.title}</span><span className="block text-[9px] opacity-75">{date.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })}</span></button>;
};

const AllDayChip: React.FC<{ task: CalendarTask; onSelect: (task: CalendarTask) => void }> = ({ task, onSelect }) => <button onClick={() => onSelect(task)} className={`max-w-full truncate rounded-md border-l-4 px-2 py-1 text-left text-[10px] font-bold ${taskColor(task)}`}>{task.title}</button>;

const NowLine: React.FC<{ now: Date; startHour: number; gridHeight: number }> = ({ now, startHour, gridHeight }) => {
  const offset = (minutesOf(now) - startHour * 60) / 60 * HOUR_HEIGHT;
  if (offset < 0 || offset > gridHeight) return null;
  return <div aria-label="Thời điểm hiện tại" className="pointer-events-none absolute inset-x-0 z-10 flex items-center" style={{ top: offset }}><span className="ml-[-4px] h-2 w-2 rounded-full bg-rose-500" /><span className="h-px flex-1 bg-rose-500" /></div>;
};

const MonthGrid: React.FC<{ cursor: Date; tasks: CalendarTask[]; onSelect: (task: CalendarTask) => void }> = ({ cursor, tasks, onSelect }) => {
  const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1); const offset = (first.getDay() + 6) % 7; const start = new Date(first); start.setDate(first.getDate() - offset);
  const days = Array.from({ length: 42 }, (_, index) => { const date = new Date(start); date.setDate(start.getDate() + index); return date; });
  return <div className="flex min-h-0 flex-1 flex-col overflow-auto pr-4 pb-4"><div className="grid min-w-[680px] grid-cols-7 border-b border-[#E8EAF0] bg-white dark:border-[#2E3342] dark:bg-[#1C1F27]">{["T2", "T3", "T4", "T5", "T6", "T7", "CN"].map((day) => <div key={day} className="py-2 text-center text-[10px] font-bold text-[#8A8F9E]">{day}</div>)}</div><div className="grid min-h-[600px] min-w-[680px] flex-1 grid-cols-7 grid-rows-6">{days.map((day) => { const items = tasks.filter((task) => sameDay(new Date(task.dueAt), day)); return <div key={day.toISOString()} className={`border-b border-r border-[#F1F2F5] p-1.5 dark:border-[#2A2E3D] ${day.getMonth() !== cursor.getMonth() ? "bg-[#F7F8FC] opacity-50 dark:bg-[#171920]" : ""}`}><span className={`inline-flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold ${sameDay(day, new Date()) ? "bg-[#2563EB] text-white" : "text-[#1E2230] dark:text-[#F5F6FA]"}`}>{day.getDate()}</span><div className="mt-1 space-y-1">{items.slice(0, 3).map((task) => <button key={task.id} onClick={() => onSelect(task)} className={`block w-full truncate rounded px-1.5 py-1 text-left text-[10px] font-semibold ${task.source === "google" ? "bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-200" : task.status === "done" ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-200" : "bg-[#EFF6FF] text-[#2563EB] dark:bg-[#2563EB]/15 dark:text-[#93C5FD]"}`}>{task.title}</button>)}</div></div>; })}</div></div>;
};

const TaskCard: React.FC<{ task: CalendarTask; onSelect: (task: CalendarTask) => void; onApprove: (task: CalendarTask) => void; onReject: (task: CalendarTask) => void; onFinish: (task: CalendarTask) => void }> = ({ task, onSelect, onApprove, onReject, onFinish }) => <article className={`rounded-xl border p-3 ${task.status === "pending" ? "border-amber-200 bg-amber-50/50 dark:border-amber-400/30 dark:bg-amber-500/10" : "border-[#E8EAF0] bg-white dark:border-[#2E3342] dark:bg-[#232630]"}`}><button onClick={() => onSelect(task)} className="w-full text-left"><div className="flex items-start justify-between gap-2"><span className="line-clamp-2 text-xs font-bold text-[#1E2230] dark:text-[#F5F6FA]">{task.title}</span><span className={`shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-bold ${task.status === "pending" ? "bg-amber-100 text-amber-700" : task.status === "done" ? "bg-emerald-100 text-emerald-700" : "bg-[#EFF6FF] text-[#2563EB]"}`}>{statusLabel(task.status)}</span></div><div className="mt-2 flex items-center gap-1 text-[10px] text-[#74798C]"><Clock3 className="h-3 w-3" />{new Date(task.dueAt).toLocaleString("vi-VN", { weekday: "short", day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit" })}</div></button>{task.status === "pending" && <div className="mt-2 flex gap-1.5 border-t border-amber-200/80 pt-2 dark:border-amber-400/20"><button onClick={() => onApprove(task)} className="flex-1 rounded-lg bg-emerald-600 py-1 text-[10px] font-bold text-white hover:bg-emerald-700">Duyệt</button><button onClick={() => onReject(task)} className="rounded-lg px-2 text-[10px] font-semibold text-[#74798C] hover:bg-white dark:hover:bg-[#2E3342]">Từ chối</button></div>}{task.status === "approved" && task.source !== "google" && <button onClick={() => onFinish(task)} className="mt-2 inline-flex items-center gap-1 text-[10px] font-bold text-emerald-700 hover:underline dark:text-emerald-300"><Check className="h-3 w-3" />Đánh dấu xong</button>}</article>;

const Empty: React.FC<{ label: string }> = ({ label }) => <div className="rounded-xl border border-dashed border-[#D8DCE7] px-3 py-7 text-center text-xs text-[#8A8F9E] dark:border-[#3A3F50]">{label}</div>;

const TaskForm: React.FC<{ initialTask?: CalendarTask; initialKind?: "task" | "event"; onClose: () => void; onSubmit: (task: CalendarTask) => void }> = ({ initialTask, initialKind = "task", onClose, onSubmit }) => {
  const kind = initialTask?.kind ?? initialKind; const isEvent = kind === "event";
  const [title, setTitle] = useState(initialTask?.title ?? ""); const [when, setWhen] = useState(initialTask ? toInputValue(new Date(initialTask.dueAt)) : toInputValue(new Date())); const [eventDate, setEventDate] = useState(initialTask ? initialTask.dueAt.slice(0, 10) : toInputValue(new Date()).slice(0, 10)); const [note, setNote] = useState(initialTask?.note ?? ""); const [priority, setPriority] = useState<CalendarTask["priority"]>(initialTask?.priority ?? "medium"); const [category, setCategory] = useState<NonNullable<CalendarTask["category"]>>(initialTask?.category ?? (isEvent ? "personal" : "task")); const [location, setLocation] = useState(initialTask?.location ?? ""); const [link, setLink] = useState(initialTask?.link ?? ""); const [tags, setTags] = useState(initialTask?.tags?.join(", ") ?? "");
  return <Modal title={initialTask ? `Chỉnh sửa ${isEvent ? "sự kiện" : "công việc"}` : isEvent ? "Thêm sự kiện" : "Thêm việc vào lịch"} onClose={onClose}><form onSubmit={(event) => { event.preventDefault(); if (!title.trim()) return; onSubmit({ id: initialTask?.id ?? `manual-${Date.now()}`, title: title.trim(), note: note.trim() || undefined, dueAt: isEvent ? new Date(`${eventDate}T00:00:00`).toISOString() : new Date(when).toISOString(), duration: isEvent ? 1440 : initialTask?.duration ?? 60, status: initialTask?.status ?? "approved", source: initialTask?.source ?? "manual", priority, category, location: location.trim() || undefined, link: link.trim() || undefined, kind, tags: tags.split(",").map((value) => value.trim()).filter(Boolean) }); }} className="space-y-4"><Field label={isEvent ? "Tên sự kiện" : "Tên công việc"}><input autoFocus required value={title} onChange={(event) => setTitle(event.target.value)} placeholder={isEvent ? "Ví dụ: Sinh nhật, kỳ nghỉ, hội thảo" : "Ví dụ: Chuẩn bị báo cáo"} /></Field>{isEvent ? <Field label="Ngày diễn ra"><input type="date" required value={eventDate} onChange={(event) => setEventDate(event.target.value)} /></Field> : <Field label="Thời gian"><input type="datetime-local" required value={when} onChange={(event) => setWhen(event.target.value)} /></Field>}<div className="grid grid-cols-2 gap-3"><Field label="Loại"><select value={category} onChange={(event) => setCategory(event.target.value as NonNullable<CalendarTask["category"]>)}><option value="task">Công việc</option><option value="meeting">Cuộc họp</option><option value="deadline">Hạn chót</option><option value="personal">Cá nhân</option><option value="focus">Tập trung</option></select></Field><Field label="Ưu tiên"><select value={priority} onChange={(event) => setPriority(event.target.value as CalendarTask["priority"])}><option value="low">Thấp</option><option value="medium">Trung bình</option><option value="high">Cao</option></select></Field></div><Field label="Địa điểm"><input value={location} onChange={(event) => setLocation(event.target.value)} placeholder="Tuỳ chọn" /></Field>{isEvent && <Field label="Liên kết"><input type="url" value={link} onChange={(event) => setLink(event.target.value)} placeholder="https://meet.google.com/..." /></Field>}<Field label="Nhãn (cách nhau bằng dấu phẩy)"><input value={tags} onChange={(event) => setTags(event.target.value)} placeholder="Ví dụ: dự án, khẩn" /></Field><Field label="Ghi chú"><textarea value={note} onChange={(event) => setNote(event.target.value)} placeholder="Thông tin thêm (tuỳ chọn)" rows={3} /></Field><ModalActions onClose={onClose} label={initialTask ? "Lưu thay đổi" : isEvent ? "Thêm sự kiện" : "Thêm vào lịch"} /></form></Modal>;
};

const AssistantForm: React.FC<{ onClose: () => void; onSubmit: (task: CalendarTask) => void }> = ({ onClose, onSubmit }) => {
  const [prompt, setPrompt] = useState(""); const [isProcessing, setIsProcessing] = useState(false); const [success, setSuccess] = useState(false);
  const schedule = (value = prompt) => { const clean = value.trim(); if (!clean || isProcessing) return; setIsProcessing(true); window.setTimeout(() => { const tomorrow = new Date(); tomorrow.setDate(tomorrow.getDate() + 1); tomorrow.setHours(9, 0, 0, 0); onSubmit({ id: `proposal-${Date.now()}`, title: clean, note: `Được Trợ lý thông minh đề xuất từ yêu cầu: “${clean}”. Cần được duyệt trước khi vào lịch.`, dueAt: tomorrow.toISOString(), duration: 60, status: "pending", source: "assistant", priority: /ưu tiên cao|hạn chót|deadline/i.test(clean) ? "high" : "medium", category: /họp|1:1/i.test(clean) ? "meeting" : /gym|cá nhân/i.test(clean) ? "personal" : /hạn chót|deadline/i.test(clean) ? "deadline" : "task", tags: ["Trợ lý đề xuất"] }); setIsProcessing(false); setSuccess(true); window.setTimeout(onClose, 800); }, 550); };
  return <Modal title="Trợ lý lập lịch" onClose={onClose}><div className="space-y-4"><div className="flex items-start gap-3 rounded-xl border border-violet-200 bg-violet-50 p-3 dark:border-violet-400/25 dark:bg-violet-500/10"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-violet-600 text-white"><Bot className="h-5 w-5" /></span><div><div className="flex items-center gap-2"><h3 className="text-sm font-bold text-violet-950 dark:text-violet-100">Trợ lý lập lịch</h3><span className="rounded-full bg-emerald-100 px-1.5 py-0.5 text-[9px] font-bold text-emerald-700">Đang hoạt động</span></div><p className="mt-0.5 text-[11px] text-violet-700 dark:text-violet-300">Lập lịch bằng ngôn ngữ tự nhiên và điều phối công việc</p></div></div><div><label className="mb-1.5 flex items-center gap-1.5 text-xs font-bold text-[#4E5568] dark:text-[#C6CAD6]"><Bot className="h-3.5 w-3.5 text-violet-600" />Bạn muốn Trợ lý lập kế hoạch gì?</label><textarea autoFocus value={prompt} onChange={(event) => setPrompt(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); schedule(); } }} rows={3} placeholder="Ví dụ: Lên lịch 2 giờ làm việc tập trung vào sáng thứ Ba" className="w-full resize-none rounded-xl border border-[#DDE1EA] bg-white p-3 text-sm text-[#1E2230] outline-none focus:border-violet-500 dark:border-[#3A4050] dark:bg-[#1C1F27] dark:text-[#F5F6FA]" /></div>{success && <div className="rounded-lg bg-emerald-50 p-2.5 text-xs font-semibold text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300">Đã tạo đề xuất chờ duyệt trong lịch.</div>}<div className="flex items-center justify-between border-t border-[#E8EAF0] pt-4 dark:border-[#2E3342]"><span className="max-w-[210px] text-[10px] leading-relaxed text-[#8A8F9E]">Trợ lý luôn tạo task ở trạng thái <strong>Chờ duyệt</strong>.</span><div className="flex gap-2"><button onClick={onClose} className="rounded-lg px-3 py-2 text-xs font-semibold text-[#74798C] hover:bg-[#F4F5F8] dark:hover:bg-[#2E3342]">Huỷ</button><button onClick={() => schedule()} disabled={!prompt.trim() || isProcessing} className="inline-flex rounded-lg bg-violet-600 px-3 py-2 text-xs font-bold text-white hover:bg-violet-700 disabled:opacity-50">{isProcessing ? "Đang lập lịch" : "Lập lịch với Trợ lý"}</button></div></div></div></Modal>;
};

const ProposalReviewDialog: React.FC<{ proposals: CalendarTask[]; onClose: () => void; onApprove: (task: CalendarTask) => void; onReject: (task: CalendarTask) => void }> = ({ proposals, onClose, onApprove, onReject }) => <Modal title="Xác nhận đề xuất" onClose={onClose}><div className="space-y-3"><p className="text-xs leading-relaxed text-[#74798C] dark:text-[#9DA3B4]">Các đề xuất chỉ được thêm vào lịch sau khi bạn duyệt.</p>{proposals.length === 0 ? <Empty label="Không có đề xuất chờ duyệt" /> : proposals.map((task) => <article key={task.id} className="rounded-xl border border-amber-200 bg-amber-50/60 p-3 dark:border-amber-400/30 dark:bg-amber-500/10"><h3 className="text-sm font-bold text-[#1E2230] dark:text-[#F5F6FA]">{task.title}</h3><p className="mt-1 text-[11px] text-[#74798C]">{new Date(task.dueAt).toLocaleString("vi-VN", { dateStyle: "medium", timeStyle: "short" })} · {task.duration} phút</p><div className="mt-3 flex justify-end gap-2"><button onClick={() => onReject(task)} className="rounded-lg border border-[#E8EAF0] bg-white px-3 py-1.5 text-xs font-semibold text-[#74798C] hover:bg-[#F7F8FC] dark:border-[#2E3342] dark:bg-[#232630]">Từ chối</button><button onClick={() => onApprove(task)} className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-emerald-700">Duyệt</button></div></article>)}</div></Modal>;

const TaskDetails: React.FC<{ task: CalendarTask; onClose: () => void; onApprove: (task: CalendarTask) => void; onReject: (task: CalendarTask) => void; onFinish: (task: CalendarTask) => void; onEdit: () => void; onDelete: () => void }> = ({ task, onClose, onApprove, onReject, onFinish, onEdit, onDelete }) => <Modal title={task.kind === "event" ? "Chi tiết sự kiện" : "Chi tiết công việc"} onClose={onClose}><div className="space-y-4"><div><h3 className="text-base font-bold text-[#1E2230] dark:text-[#F5F6FA]">{task.title}</h3><div className="mt-3 rounded-xl bg-[#F7F8FC] p-3 dark:bg-[#1C1F27]"><span className="block text-[10px] font-bold uppercase tracking-wide text-[#8A8F9E]">Mô tả</span><p className="mt-1 text-xs leading-relaxed text-[#4E5568] dark:text-[#C6CAD6]">{task.note || "Chưa có mô tả."}</p></div></div><div className="grid grid-cols-2 gap-2 text-xs"><Info label={task.kind === "event" ? "Ngày" : "Bắt đầu"} value={new Date(task.dueAt).toLocaleString("vi-VN", task.kind === "event" ? { dateStyle: "medium" } : { dateStyle: "medium", timeStyle: "short" })} />{task.kind !== "event" && <Info label="Thời lượng" value={`${task.duration} phút`} />}<Info label="Trạng thái" value={statusLabel(task.status)} /><Info label="Ưu tiên" value={task.priority === "high" ? "Cao" : task.priority === "low" ? "Thấp" : "Trung bình"} /><Info label="Danh mục" value={({ task: "Công việc", meeting: "Cuộc họp", deadline: "Hạn chót", personal: "Cá nhân", focus: "Tập trung" })[task.category ?? "task"]} /><Info label="Nguồn" value={sourceLabel(task.source)} /></div><div className="space-y-2 rounded-xl border border-[#E8EAF0] p-3 text-xs dark:border-[#2E3342]"><div><span className="text-[10px] font-bold uppercase tracking-wide text-[#8A8F9E]">Địa điểm</span><p className="mt-0.5 font-medium text-[#4E5568] dark:text-[#C6CAD6]">{task.location || "Chưa có địa điểm"}</p></div><div><span className="text-[10px] font-bold uppercase tracking-wide text-[#8A8F9E]">Nhãn</span><div className="mt-1 flex flex-wrap gap-1">{task.tags?.length ? task.tags.map((tag) => <span key={tag} className="rounded-full bg-[#EFF6FF] px-2 py-0.5 text-[10px] font-semibold text-[#2563EB] dark:bg-[#2563EB]/15 dark:text-[#93C5FD]">{tag}</span>) : <span className="text-[#74798C]">Chưa có nhãn</span>}</div></div></div>{task.link && <a href={task.link} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs font-semibold text-[#2563EB] hover:underline"><ExternalLink className="h-3.5 w-3.5" />Mở liên kết sự kiện</a>}{task.source === "google" && <div className="rounded-lg bg-sky-50 p-2.5 text-[11px] text-sky-700 dark:bg-sky-500/10 dark:text-sky-200"><ExternalLink className="mr-1 inline h-3.5 w-3.5" />Sự kiện đồng bộ từ Google Calendar — chỉ đọc.</div>}<div className="flex flex-wrap justify-between gap-2 border-t border-[#E8EAF0] pt-4 dark:border-[#2E3342]"><button onClick={onDelete} className="inline-flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs font-semibold text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-500/10"><Trash2 className="h-3.5 w-3.5" />Xoá</button><div className="flex gap-2">{task.source !== "google" && <button onClick={onEdit} className="rounded-lg border border-[#E8EAF0] px-3 py-1.5 text-xs font-semibold text-[#4E5568] dark:border-[#2E3342]">Chỉnh sửa</button>}{task.status === "pending" && <><button onClick={() => { onReject(task); onClose(); }} className="rounded-lg border border-[#E8EAF0] px-3 py-1.5 text-xs font-semibold text-[#74798C] dark:border-[#2E3342]">Từ chối</button><button onClick={() => { onApprove(task); onClose(); }} className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-bold text-white">Duyệt và lên lịch</button></>}{task.status === "approved" && task.source !== "google" && <button onClick={() => { onFinish(task); onClose(); }} className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-bold text-white">Hoàn thành</button>}</div></div></div></Modal>;

const Modal: React.FC<{ title: string; onClose: () => void; children: React.ReactNode }> = ({ title, onClose, children }) => <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#111827]/45 p-4" role="dialog" aria-modal="true"><div className="w-full max-w-md rounded-2xl bg-white p-5 shadow-xl dark:bg-[#232630]"><div className="mb-4 flex items-center justify-between"><h2 className="text-base font-bold text-[#1E2230] dark:text-[#F5F6FA]">{title}</h2><button onClick={onClose} aria-label="Đóng" className="rounded-lg p-1 text-[#74798C] hover:bg-[#F4F5F8] dark:hover:bg-[#2E3342]"><X className="h-5 w-5" /></button></div>{children}</div></div>;
const Field: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => <label className="block text-xs font-semibold text-[#4E5568] dark:text-[#C6CAD6]"><span className="mb-1.5 block">{label}</span>{React.Children.map(children, (child) => React.isValidElement(child) ? React.cloneElement(child as React.ReactElement<{ className?: string }>, { className: "w-full rounded-lg border border-[#DDE1EA] bg-white px-3 py-2 text-sm font-normal text-[#1E2230] outline-none focus:border-[#2563EB] dark:border-[#3A4050] dark:bg-[#1C1F27] dark:text-[#F5F6FA]" }) : child)}</label>;
const ModalActions: React.FC<{ onClose: () => void; label: string }> = ({ onClose, label }) => <div className="flex justify-end gap-2 pt-1"><button type="button" onClick={onClose} className="rounded-lg px-3 py-2 text-xs font-semibold text-[#74798C] hover:bg-[#F4F5F8] dark:hover:bg-[#2E3342]">Huỷ</button><button className="rounded-lg bg-[#2563EB] px-3 py-2 text-xs font-bold text-white hover:bg-[#1D4ED8]">{label}</button></div>;
const Info: React.FC<{ label: string; value: string }> = ({ label, value }) => <div className="rounded-lg bg-[#F7F8FC] p-2 dark:bg-[#1C1F27]"><span className="block text-[10px] font-bold uppercase tracking-wide text-[#8A8F9E]">{label}</span><span className="mt-0.5 block text-xs font-medium text-[#1E2230] dark:text-[#F5F6FA]">{value}</span></div>;
