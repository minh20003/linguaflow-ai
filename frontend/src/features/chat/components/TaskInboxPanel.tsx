"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { AlertCircle, Check, Clock3, ListTodo, MessageSquareQuote, X } from "lucide-react";
import type { ApiActionProposal } from "../api/chat-api";
import {
  clarifyActionProposal,
  confirmActionProposal,
  listActionProposals,
  rejectActionProposal,
} from "../api/chat-api";

interface TaskInboxPanelProps {
  token: string;
  /** Proposals arriving live over the socket, newest first. */
  incoming?: ApiActionProposal[];
  onCountChange?: (pending: number) => void;
  onNotify?: (title: string, detail?: string, tone?: "success" | "warning") => void;
}

/** Rank one proposal. Lower sorts first.
 *
 *  "Priority" is an acceptance criterion rather than a flourish, so the order is
 *  stated here with its reasoning rather than left to whatever the API returned.
 *
 *  0. Waiting on the user to answer a question. The agent has stopped and cannot
 *     continue until they reply, so this is the only category where nothing at
 *     all happens without them.
 *  1. Awaiting approval and dated. These expire: approve it after the meeting
 *     and the approval was pointless.
 *  2. Awaiting approval, undated. Still needs a decision, but nothing is lost by
 *     deciding tomorrow.
 *  3. Already approved. Shown for confirmation that it landed, not for action.
 *
 *  Within a band, sooner first, and undated items by recency — a proposal made
 *  five minutes ago is the one the user still remembers saying.
 */
function rank(proposal: ApiActionProposal): number {
  if (proposal.status === "needs_clarification") return 0;
  if (proposal.status === "pending_confirmation") {
    return proposal.scheduled_start_at || proposal.due_at ? 1 : 2;
  }
  return 3;
}

function whenOf(proposal: ApiActionProposal): number {
  const at = proposal.scheduled_start_at || proposal.due_at;
  return at ? new Date(at).getTime() : Number.POSITIVE_INFINITY;
}

function orderProposals(items: ApiActionProposal[]): ApiActionProposal[] {
  return [...items].sort((a, b) => {
    const byBand = rank(a) - rank(b);
    if (byBand !== 0) return byBand;
    const byWhen = whenOf(a) - whenOf(b);
    if (byWhen !== 0 && Number.isFinite(byWhen)) return byWhen;
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });
}

function formatWhen(proposal: ApiActionProposal): string {
  const at = proposal.scheduled_start_at || proposal.due_at;
  if (!at) return "Chưa có thời gian";
  return new Date(at).toLocaleString("vi-VN", {
    weekday: "short",
    day: "numeric",
    month: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export const TaskInboxPanel: React.FC<TaskInboxPanelProps> = ({
  token,
  incoming,
  onCountChange,
  onNotify,
}) => {
  const [proposals, setProposals] = useState<ApiActionProposal[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    try {
      setProposals(await listActionProposals(token));
    } catch (error) {
      onNotify?.(
        "Không tải được hộp nhiệm vụ",
        error instanceof Error ? error.message : undefined,
        "warning",
      );
    } finally {
      setIsLoading(false);
    }
  }, [token, onNotify]);

  useEffect(() => {
    void load();
  }, [load]);

  // Merge live arrivals by id rather than appending: the socket can deliver a
  // proposal the initial fetch already returned, and a duplicate row invites the
  // user to approve the same commitment twice.
  useEffect(() => {
    if (!incoming?.length) return;
    setProposals((current) => {
      const byId = new Map(current.map((item) => [item.id, item]));
      for (const item of incoming) byId.set(item.id, item);
      return [...byId.values()];
    });
  }, [incoming]);

  const ordered = useMemo(() => orderProposals(proposals), [proposals]);
  const pendingCount = useMemo(
    () =>
      proposals.filter(
        (item) => item.status === "pending_confirmation" || item.status === "needs_clarification",
      ).length,
    [proposals],
  );

  useEffect(() => {
    onCountChange?.(pendingCount);
  }, [pendingCount, onCountChange]);

  const replace = (updated: ApiActionProposal) =>
    setProposals((current) => current.map((item) => (item.id === updated.id ? updated : item)));

  const act = async (
    proposal: ApiActionProposal,
    run: () => Promise<ApiActionProposal>,
    success: string,
  ) => {
    setBusyId(proposal.id);
    try {
      replace(await run());
      onNotify?.(success, proposal.title, "success");
    } catch (error) {
      onNotify?.(
        "Không thực hiện được",
        error instanceof Error ? error.message : undefined,
        "warning",
      );
    } finally {
      setBusyId(null);
    }
  };

  return (
    <aside className="flex h-full w-full flex-col border-r border-[#E8EAF0] bg-white dark:border-[#2A2E3D] dark:bg-[#1C1F27]">
      <header className="flex items-center gap-2 border-b border-[#E8EAF0] px-4 py-3.5 dark:border-[#2A2E3D]">
        <ListTodo className="h-5 w-5 text-[#2563EB]" />
        <h2 className="text-sm font-bold text-[#1E2230] dark:text-[#F5F6FA]">Hộp nhiệm vụ</h2>
        {pendingCount > 0 && (
          <span className="ml-auto rounded-full bg-[#EFF6FF] px-2 py-0.5 text-[11px] font-bold text-[#2563EB] dark:bg-[#2563EB]/15 dark:text-[#93C5FD]">
            {pendingCount} chờ duyệt
          </span>
        )}
      </header>

      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
        {isLoading && (
          <p className="px-1 py-6 text-center text-xs text-[#74798C]">Đang tải…</p>
        )}

        {!isLoading && ordered.length === 0 && (
          <div className="px-3 py-10 text-center">
            <ListTodo className="mx-auto h-8 w-8 text-[#CED2DE] dark:text-[#3A3F50]" />
            <p className="mt-3 text-xs font-semibold text-[#1E2230] dark:text-[#F5F6FA]">
              Chưa có việc nào chờ bạn
            </p>
            <p className="mt-1 text-xs leading-relaxed text-[#74798C] dark:text-[#9DA3B4]">
              Khi bạn hứa làm gì đó trong hội thoại, trợ lý sẽ đề xuất ở đây để bạn duyệt.
            </p>
          </div>
        )}

        {ordered.map((proposal) => {
          const busy = busyId === proposal.id;
          const needsAnswer = proposal.status === "needs_clarification";
          const decided = proposal.status !== "pending_confirmation" && !needsAnswer;

          return (
            <article
              key={proposal.id}
              className={`rounded-2xl border p-3.5 ${
                needsAnswer
                  ? "border-amber-300 bg-amber-50/60 dark:border-amber-400/30 dark:bg-amber-500/10"
                  : "border-[#E8EAF0] bg-[#F7F8FC] dark:border-[#2A2E3D] dark:bg-[#232630]/60"
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <h3 className="text-xs font-bold leading-snug text-[#1E2230] dark:text-[#F5F6FA]">
                  {proposal.title}
                </h3>
                <span
                  className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold ${
                    proposal.status === "confirmed"
                      ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-200"
                      : needsAnswer
                        ? "bg-amber-100 text-amber-800 dark:bg-amber-500/20 dark:text-amber-200"
                        : "bg-[#EFF6FF] text-[#2563EB] dark:bg-[#2563EB]/15 dark:text-[#93C5FD]"
                  }`}
                >
                  {proposal.status === "confirmed"
                    ? "Đã duyệt"
                    : proposal.status === "rejected"
                      ? "Đã từ chối"
                      : proposal.status === "stale"
                        ? "Đã lỗi thời"
                        : needsAnswer
                          ? "Cần trả lời"
                          : "Chờ duyệt"}
                </span>
              </div>

              <p className="mt-2 flex items-center gap-1.5 text-[11px] text-[#74798C] dark:text-[#9DA3B4]">
                <Clock3 className="h-3 w-3 flex-none" />
                {formatWhen(proposal)}
                {proposal.source_mode === "proactive" && (
                  <span className="ml-1 rounded bg-violet-100 px-1.5 py-0.5 text-[10px] font-semibold text-violet-700 dark:bg-violet-500/20 dark:text-violet-200">
                    tự phát hiện
                  </span>
                )}
              </p>

              {proposal.details && (
                <p className="mt-1.5 line-clamp-2 text-[11px] leading-relaxed text-[#4E5568] dark:text-[#C6CAD6]">
                  {proposal.details}
                </p>
              )}

              {needsAnswer && (
                <div className="mt-3 border-t border-amber-200 pt-3 dark:border-amber-400/20">
                  <p className="flex items-start gap-1.5 text-[11px] font-medium text-amber-900 dark:text-amber-200">
                    <MessageSquareQuote className="mt-0.5 h-3 w-3 flex-none" />
                    {proposal.clarification_question ||
                      proposal.clarification_prompt ||
                      "Trợ lý cần thêm thông tin để lên lịch."}
                  </p>
                  <div className="mt-2 flex gap-2">
                    <input
                      value={answers[proposal.id] ?? ""}
                      onChange={(event) =>
                        setAnswers((current) => ({
                          ...current,
                          [proposal.id]: event.target.value,
                        }))
                      }
                      placeholder="Ví dụ: 9h sáng thứ năm"
                      className="min-w-0 flex-1 rounded-lg border border-amber-300 bg-white px-2 py-1.5 text-[11px] outline-none dark:border-amber-400/30 dark:bg-[#232630]"
                    />
                    <button
                      type="button"
                      disabled={busy || !(answers[proposal.id] ?? "").trim()}
                      onClick={() =>
                        void act(
                          proposal,
                          () =>
                            clarifyActionProposal(
                              token,
                              proposal.id,
                              (answers[proposal.id] ?? "").trim(),
                              Intl.DateTimeFormat().resolvedOptions().timeZone,
                            ),
                          "Đã gửi câu trả lời",
                        )
                      }
                      className="rounded-lg bg-amber-600 px-3 py-1.5 text-[11px] font-bold text-white disabled:opacity-50"
                    >
                      Gửi
                    </button>
                  </div>
                </div>
              )}

              {!decided && (
                <div className="mt-3 flex gap-2 border-t border-[#E8EAF0] pt-3 dark:border-[#2A2E3D]">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() =>
                      void act(
                        proposal,
                        () => confirmActionProposal(token, proposal.id),
                        "Đã duyệt và thêm vào lịch",
                      )
                    }
                    className="inline-flex flex-1 items-center justify-center gap-1 rounded-lg bg-emerald-600 py-1.5 text-[11px] font-bold text-white hover:bg-emerald-700 disabled:opacity-50"
                  >
                    <Check className="h-3 w-3" />
                    Duyệt
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() =>
                      void act(
                        proposal,
                        () => rejectActionProposal(token, proposal.id),
                        "Đã từ chối",
                      )
                    }
                    className="inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-[11px] font-semibold text-[#74798C] hover:bg-white disabled:opacity-50 dark:hover:bg-[#2E3342]"
                  >
                    <X className="h-3 w-3" />
                    Từ chối
                  </button>
                </div>
              )}

              {proposal.status === "stale" && (
                <p className="mt-2 flex items-center gap-1 text-[10px] text-[#74798C]">
                  <AlertCircle className="h-3 w-3 flex-none" />
                  Tin nhắn gốc đã bị sửa hoặc gỡ, nên đề xuất này không còn dùng được.
                </p>
              )}
            </article>
          );
        })}
      </div>
    </aside>
  );
};
