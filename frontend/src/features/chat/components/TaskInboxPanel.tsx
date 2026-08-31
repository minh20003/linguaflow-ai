"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { AlertCircle, Check, Clock3, ListTodo, MessageSquareQuote, Trash2, X } from "lucide-react";
import type { ApiActionProposal } from "../api/chat-api";
import {
  ApprovalOptions,
  DEFAULT_APPROVAL,
  ProposalDraft,
  canApprove,
  decisionCorrections,
  missingFields,
  draftFromProposal,
  formatProposalWhen,
} from "../proposal-approval";
import { ProposalDecisionForm } from "./ProposalDecisionForm";
import {
  clarifyActionProposal,
  confirmActionProposal,
  dismissActionProposal,
  dismissDecidedActionProposals,
  listActionProposals,
  rejectActionProposal,
} from "../api/chat-api";

interface TaskInboxPanelProps {
  token: string;
  /** Proposals arriving live over the socket, newest first. */
  incoming?: ApiActionProposal[];
  onCountChange?: (pending: number) => void;
  /** Report a decision back, so the card for it in the chat stops asking.
   *
   *  Without this the sync ran one way only: approving in the chat updated this
   *  list through `incoming`, but approving here left the in-chat card offering
   *  the same choice for a proposal that had already been decided. */
  onProposalChanged?: (proposal: ApiActionProposal, removed?: boolean) => void;
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

export const TaskInboxPanel: React.FC<TaskInboxPanelProps> = ({
  token,
  incoming,
  onCountChange,
  onNotify,
  onProposalChanged,
}) => {
  const [proposals, setProposals] = useState<ApiActionProposal[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  // What the approver chose for this proposal, keyed by id. Empty until they
  // touch a control, so an untouched card still approves with the server's
  // defaults and the extra fields are genuinely optional.
  const [options, setOptions] = useState<Record<string, ApprovalOptions>>({});

  const [drafts, setDrafts] = useState<Record<string, ProposalDraft>>({});
  const [tab, setTab] = useState<"awaiting" | "decided">("awaiting");

  const optionsFor = (id: string): ApprovalOptions => options[id] ?? DEFAULT_APPROVAL;

  const draftFor = (proposal: ApiActionProposal): ProposalDraft =>
    drafts[proposal.id] ?? draftFromProposal(proposal);

  const setDraft = (proposal: ApiActionProposal, patch: Partial<ProposalDraft>) =>
    setDrafts((current) => ({
      ...current,
      [proposal.id]: { ...(current[proposal.id] ?? draftFromProposal(proposal)), ...patch },
    }));

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
  // Two lists, because they answer different questions. "Cần duyệt" is work
  // waiting on the person; "Đã duyệt" is a record of what already happened, and
  // mixing them buries the first under the second as the second grows.
  const awaiting = useMemo(
    () => ordered.filter((item) =>
      item.status === "pending_confirmation" || item.status === "needs_clarification"),
    [ordered],
  );
  const decidedList = useMemo(
    () => ordered.filter((item) =>
      item.status !== "pending_confirmation" && item.status !== "needs_clarification"),
    [ordered],
  );

  /** Remove a decided proposal from this list only.
   *
   *  Nothing is cancelled. An approved proposal already put an event on the
   *  calendar, and that event still fires its reminder — clearing a finished
   *  list is not a request to un-book a meeting.
   */
  const dismissOne = async (proposal: ApiActionProposal) => {
    setBusyId(proposal.id);
    try {
      await dismissActionProposal(token, proposal.id);
      setProposals((current) => current.filter((item) => item.id !== proposal.id));
      onProposalChanged?.(proposal, true);
    } catch (error) {
      onNotify?.("Không xoá được", error instanceof Error ? error.message : undefined, "warning");
    } finally {
      setBusyId(null);
    }
  };

  const dismissAllDecided = async () => {
    try {
      await dismissDecidedActionProposals(token);
      setProposals((current) => current.filter(
        (item) => item.status === "pending_confirmation" || item.status === "needs_clarification"));
      onNotify?.("Đã xoá khỏi danh sách", "Lịch và nhắc hẹn giữ nguyên", "success");
    } catch (error) {
      onNotify?.("Không xoá được", error instanceof Error ? error.message : undefined, "warning");
    }
  };
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

  const replace = (updated: ApiActionProposal) => {
    setProposals((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    onProposalChanged?.(updated);
  };

  const act = async (
    proposal: ApiActionProposal,
    run: () => Promise<ApiActionProposal>,
    success: string,
  ) => {
    setBusyId(proposal.id);
    try {
      const updated = await run();
      replace(updated);
      // A call that returns 200 having changed nothing is the worst outcome to
      // render silently: the card looks identical and the button looks broken.
      if (
        updated.status === proposal.status &&
        updated.missing_fields === proposal.missing_fields
      ) {
        onNotify?.(
          "Chưa dùng được câu trả lời đó",
          "Bạn điền trực tiếp vào ô Bắt đầu ở trên rồi bấm Duyệt.",
          "warning",
        );
      } else {
        onNotify?.(success, proposal.title, "success");
      }
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

  const renderProposal = (proposal: ApiActionProposal) => {
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
                      <span className="inline-flex items-center gap-1.5"><Clock3 className="h-3.5 w-3.5 flex-none" />{formatProposalWhen(proposal)}</span>
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
                        disabled={busy || !canApprove(proposal, draftFor(proposal))}
                        title={canApprove(proposal, draftFor(proposal)) ? undefined : "Điền nốt thông tin còn thiếu ở trên"}
                        onClick={() => void act(proposal, () => confirmActionProposal(token, proposal.id, decisionCorrections(proposal, draftFor(proposal), optionsFor(proposal.id))), "Đã duyệt và thêm vào lịch")}
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

                  {decided && (
                    <div className="flex shrink-0 items-center">
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void dismissOne(proposal)}
                        title="Chỉ ẩn khỏi danh sách. Lịch và nhắc hẹn giữ nguyên."
                        className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-semibold text-[#74798C] hover:bg-[#F7F8FC] hover:text-[#1E2230] disabled:opacity-50 dark:text-[#9DA3B4] dark:hover:bg-[#232630]"
                      >
                        <Trash2 className="h-3.5 w-3.5" /> Xoá
                      </button>
                    </div>
                  )}
                </div>

              {!decided && (
                <ProposalDecisionForm
                  proposal={proposal}
                  draft={draftFor(proposal)}
                  chosen={optionsFor(proposal.id)}
                  onDraftChange={(patch) => setDraft(proposal, patch)}
                  onOptionsChange={(patch) => setOption(proposal.id, patch)}
                />
              )}

              {/* Only for clarifications a date picker cannot express. When the
                  missing field is the time, the form above already has a
                  datetime input, and a free-text answer there was worse than
                  useless: the server understands a deliberately tiny grammar
                  ("mai 14h", "sáng mai", "next friday") and silently resolves
                  nothing else, so a perfectly reasonable "9h sáng thứ năm" left
                  the card unchanged and looked like a dead button. */}
              {needsAnswer && !missingFields(proposal).includes("time") && (
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
                            decisionCorrections(proposal, draftFor(proposal), optionsFor(proposal.id)),
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

        {/* Two tabs, not one long list. They answer different questions —
            "what needs me" against "what already happened" — and the second
            grows without bound, so merged it buries the first. */}
        <div className="flex items-center gap-1 rounded-xl bg-white p-1 dark:bg-[#1C1F27]">
          {([
            ["awaiting", "Cần duyệt", awaiting.length],
            ["decided", "Đã duyệt", decidedList.length],
          ] as const).map(([key, caption, count]) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              className={`flex-1 rounded-lg px-3 py-2 text-xs font-bold transition-colors ${
                tab === key
                  ? "bg-[#EFF6FF] text-[#2563EB] dark:bg-[#2563EB]/15 dark:text-[#93C5FD]"
                  : "text-[#74798C] hover:bg-[#F7F8FC] dark:text-[#9DA3B4] dark:hover:bg-[#232630]"
              }`}
            >
              {caption} ({count})
            </button>
          ))}
        </div>

        {tab === "decided" && decidedList.length > 0 && (
          <div className="flex justify-end px-1">
            <button
              type="button"
              onClick={() => void dismissAllDecided()}
              className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-semibold text-[#74798C] hover:bg-white hover:text-[#1E2230] dark:text-[#9DA3B4] dark:hover:bg-[#232630]"
              title="Chỉ ẩn khỏi danh sách. Lịch và nhắc hẹn giữ nguyên."
            >
              <Trash2 className="h-3.5 w-3.5" /> Xoá tất cả
            </button>
          </div>
        )}

        {(tab === "awaiting" ? awaiting : decidedList).map(renderProposal)}

        {!isLoading && (tab === "awaiting" ? awaiting : decidedList).length === 0 && (
          <p className="px-1 py-10 text-center text-xs text-[#74798C] dark:text-[#9DA3B4]">
            {tab === "awaiting" ? "Không có việc nào chờ bạn duyệt." : "Chưa có việc nào đã duyệt."}
          </p>
        )}
        </div>
      </div>
    </section>
  );
};
