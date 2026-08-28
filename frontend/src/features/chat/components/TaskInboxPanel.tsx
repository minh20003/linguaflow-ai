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

/** What the approver may still decide at the moment they approve.
 *
 *  None of it can be extracted from the message: nobody writes how long
 *  beforehand they want to be nudged, and a chat message rarely states a
 *  duration either. `ConfirmProposalRequest` accepts all of it, but this panel
 *  used to send an empty body — so every approval silently took the server
 *  defaults of a thirty-minute event and a fifteen-minute reminder, even when
 *  the person had said something different out loud.
 */
interface ApprovalOptions {
  /** Event length in minutes. */
  durationMinutes: number;
  /** Minutes of warning, or null for "do not remind me". */
  reminderMinutesBefore: number | null;
}

const DEFAULT_APPROVAL: ApprovalOptions = {
  durationMinutes: 30,
  reminderMinutesBefore: 15,
};

const DURATION_CHOICES = [15, 30, 45, 60, 90, 120];
const REMINDER_CHOICES: Array<{ value: number | null; label: string }> = [
  { value: 0, label: "Đúng giờ" },
  { value: 5, label: "5 phút" },
  { value: 15, label: "15 phút" },
  { value: 30, label: "30 phút" },
  { value: 60, label: "1 giờ" },
  { value: 1440, label: "1 ngày" },
  { value: null, label: "Không nhắc" },
];

/** Turn the approver's choices into a `ConfirmProposalRequest` body.
 *
 *  The timezone always travels, the way the clarify call already sends it: the
 *  server stores UTC and has no other way to learn which wall clock the person
 *  was reading. The end time is only sent for a proposal that has a start —
 *  a task with a deadline and no start has no duration to speak of.
 */
function approvalCorrections(
  proposal: ApiActionProposal,
  chosen: ApprovalOptions,
): Record<string, unknown> {
  const body: Record<string, unknown> = {
    reminder_minutes_before: chosen.reminderMinutesBefore,
    resolved_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  };
  if (proposal.scheduled_start_at) {
    const start = new Date(proposal.scheduled_start_at);
    body.scheduled_end_at = new Date(
      start.getTime() + chosen.durationMinutes * 60_000,
    ).toISOString();
  }
  return body;
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
  // What the approver chose for this proposal, keyed by id. Empty until they
  // touch a control, so an untouched card still approves with the server's
  // defaults and the extra fields are genuinely optional.
  const [options, setOptions] = useState<Record<string, ApprovalOptions>>({});

  const optionsFor = (id: string): ApprovalOptions => options[id] ?? DEFAULT_APPROVAL;

  const setOption = (id: string, patch: Partial<ApprovalOptions>) =>
    setOptions((current) => ({
      ...current,
      [id]: { ...(current[id] ?? DEFAULT_APPROVAL), ...patch },
    }));

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
    <section className="flex h-full w-full flex-col bg-[#F7F8FC] dark:bg-[#14161C]">
      <header className="flex min-h-16 items-center border-b border-[#E8EAF0] bg-white px-5 dark:border-[#2A2E3D] dark:bg-[#1C1F27] sm:px-7">
        <div className="flex min-w-0 items-center gap-3">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-[#EFF6FF] text-[#2563EB] dark:bg-[#2563EB]/15 dark:text-[#93C5FD]">
            <ListTodo className="h-5 w-5" />
          </span>
          <div>
            <h2 className="text-base font-bold text-[#1E2230] dark:text-[#F5F6FA]">Hộp nhiệm vụ</h2>
            <p className="text-xs text-[#74798C] dark:text-[#9DA3B4]">Các đề xuất của trợ lý đang chờ bạn xử lý</p>
          </div>
        </div>
        {pendingCount > 0 && (
          <span className="ml-auto shrink-0 rounded-full bg-[#EFF6FF] px-3 py-1 text-xs font-bold text-[#2563EB] dark:bg-[#2563EB]/15 dark:text-[#93C5FD]">
            {pendingCount} cần xử lý
          </span>
        )}
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-7">
        <div className="mx-auto max-w-5xl space-y-3">
        {isLoading && (
          <p className="px-1 py-6 text-center text-xs text-[#74798C]">Đang tải…</p>
        )}

        {!isLoading && ordered.length === 0 && (
          <div className="rounded-2xl border border-dashed border-[#D8DCE7] bg-white px-3 py-14 text-center dark:border-[#3A3F50] dark:bg-[#1C1F27]">
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
              className={`relative overflow-hidden rounded-2xl border bg-white shadow-sm transition-shadow hover:shadow-md dark:bg-[#1C1F27] ${
                needsAnswer
                  ? "border-amber-300 dark:border-amber-400/30"
                  : "border-[#E8EAF0] dark:border-[#2A2E3D]"
              }`}
            >
              <div className={`absolute inset-y-0 left-0 w-1 ${needsAnswer ? "bg-amber-400" : proposal.status === "confirmed" ? "bg-emerald-500" : "bg-[#2563EB]"}`} />
              <div className="p-4 pl-5 sm:p-5 sm:pl-6">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-sm font-bold leading-snug text-[#1E2230] dark:text-[#F5F6FA]">
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
                    <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-[#74798C] dark:text-[#9DA3B4]">
                      <span className="inline-flex items-center gap-1.5"><Clock3 className="h-3.5 w-3.5 flex-none" />{formatWhen(proposal)}</span>
                      {proposal.source_mode === "proactive" && (
                        <span className="rounded bg-violet-100 px-1.5 py-0.5 text-[10px] font-semibold text-violet-700 dark:bg-violet-500/20 dark:text-violet-200">tự phát hiện</span>
                      )}
                    </p>
                    {proposal.details && (
                      <p className="mt-2 max-w-3xl text-xs leading-relaxed text-[#4E5568] dark:text-[#C6CAD6]">{proposal.details}</p>
                    )}
                  </div>

                  {!decided && !needsAnswer && (
                    <div className="flex shrink-0 items-center gap-2">
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void act(proposal, () => confirmActionProposal(token, proposal.id, approvalCorrections(proposal, optionsFor(proposal.id))), "Đã duyệt và thêm vào lịch")}
                        className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-[#2563EB] px-3.5 py-2 text-xs font-bold text-white hover:bg-[#1D4ED8] disabled:opacity-50"
                      >
                        <Check className="h-3.5 w-3.5" /> Duyệt
                      </button>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void act(proposal, () => rejectActionProposal(token, proposal.id), "Đã từ chối")}
                        className="rounded-lg border border-[#D8DCE7] px-3.5 py-2 text-xs font-semibold text-[#62687B] hover:bg-[#F7F8FC] disabled:opacity-50 dark:border-[#3A3F50] dark:text-[#C6CAD6] dark:hover:bg-[#232630]"
                      >Từ chối</button>
                    </div>
                  )}
                </div>

              {!decided && (
                <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 rounded-xl border border-[#E4E7F0] bg-[#F7F8FC]/70 px-3 py-2.5 dark:border-[#3A3F50] dark:bg-[#232630]/60">
                  {proposal.scheduled_start_at && (
                    <label className="flex items-center gap-2 text-xs text-[#62687B] dark:text-[#C6CAD6]">
                      <span className="font-semibold">Thời lượng</span>
                      <select
                        value={optionsFor(proposal.id).durationMinutes}
                        onChange={(event) =>
                          setOption(proposal.id, {
                            durationMinutes: Number(event.target.value),
                          })
                        }
                        className="rounded-lg border border-[#D8DCE7] bg-white px-2 py-1 text-xs outline-none focus:border-[#2563EB] dark:border-[#3A3F50] dark:bg-[#1B1D25]"
                      >
                        {DURATION_CHOICES.map((minutes) => (
                          <option key={minutes} value={minutes}>
                            {minutes < 60 ? `${minutes} phút` : `${minutes / 60} giờ`}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}
                  <label className="flex items-center gap-2 text-xs text-[#62687B] dark:text-[#C6CAD6]">
                    <span className="font-semibold">Nhắc trước</span>
                    <select
                      value={String(optionsFor(proposal.id).reminderMinutesBefore)}
                      onChange={(event) =>
                        setOption(proposal.id, {
                          reminderMinutesBefore:
                            event.target.value === "null"
                              ? null
                              : Number(event.target.value),
                        })
                      }
                      className="rounded-lg border border-[#D8DCE7] bg-white px-2 py-1 text-xs outline-none focus:border-[#2563EB] dark:border-[#3A3F50] dark:bg-[#1B1D25]"
                    >
                      {REMINDER_CHOICES.map((choice) => (
                        <option key={String(choice.value)} value={String(choice.value)}>
                          {choice.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              )}

              {needsAnswer && (
                <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50/70 p-3 dark:border-amber-400/20 dark:bg-amber-500/10">
                  <p className="flex items-start gap-1.5 text-xs font-medium text-amber-900 dark:text-amber-200">
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
                      className="min-w-0 flex-1 rounded-lg border border-amber-300 bg-white px-3 py-2 text-xs outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-200 dark:border-amber-400/30 dark:bg-[#232630]"
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
                      className="rounded-lg bg-amber-600 px-4 py-2 text-xs font-bold text-white hover:bg-amber-700 disabled:opacity-50"
                    >
                      Gửi
                    </button>
                  </div>
                </div>
              )}

              {!decided && needsAnswer && (
                <div className="mt-3 flex justify-end gap-2">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() =>
                      void act(
                        proposal,
                        () =>
                          confirmActionProposal(
                            token,
                            proposal.id,
                            approvalCorrections(proposal, optionsFor(proposal.id)),
                          ),
                        "Đã duyệt và thêm vào lịch",
                      )
                    }
                    className="inline-flex items-center justify-center gap-1 rounded-lg bg-[#2563EB] px-3.5 py-2 text-xs font-bold text-white hover:bg-[#1D4ED8] disabled:opacity-50"
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
                    className="inline-flex items-center gap-1 rounded-lg border border-[#D8DCE7] px-3.5 py-2 text-xs font-semibold text-[#74798C] hover:bg-[#F7F8FC] disabled:opacity-50 dark:border-[#3A3F50] dark:hover:bg-[#2E3342]"
                  >
                    <X className="h-3 w-3" />
                    Từ chối
                  </button>
                </div>
              )}

              {proposal.status === "stale" && (
                <p className="mt-3 flex items-center gap-1 text-[11px] text-[#74798C]">
                  <AlertCircle className="h-3 w-3 flex-none" />
                  Tin nhắn gốc đã bị sửa hoặc gỡ, nên đề xuất này không còn dùng được.
                </p>
              )}
              </div>
            </article>
          );
        })}
        </div>
      </div>
    </section>
  );
};
