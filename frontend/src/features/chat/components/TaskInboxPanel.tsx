"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { AlertCircle, Check, Clock3, ListTodo, MessageSquareQuote, Trash2, X } from "lucide-react";
import type { ApiActionProposal } from "../api/chat-api";
import {
  clarifyActionProposal,
  confirmActionProposal,
  deleteTerminalActionProposal,
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

function toDateTimeLocal(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
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
  const [editingProposal, setEditingProposal] = useState<ApiActionProposal | null>(null);

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

  const remove = (proposalId: string) =>
    setProposals((current) => current.filter((item) => item.id !== proposalId));

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
          </div>
        )}

        {ordered.map((proposal) => {
          const busy = busyId === proposal.id;
          const needsAnswer = proposal.status === "needs_clarification";
          const decided = proposal.status !== "pending_confirmation" && !needsAnswer;

          return (
            <article
              key={proposal.id}
              onClick={(event) => {
                if ((event.target as HTMLElement).closest("button, input, textarea")) return;
                if (proposal.status === "pending_confirmation") setEditingProposal(proposal);
              }}
              className={`relative overflow-hidden rounded-2xl border bg-white shadow-sm transition-shadow hover:shadow-md dark:bg-[#1C1F27] ${
                needsAnswer
                  ? "border-amber-300 dark:border-amber-400/30"
                  : "border-[#E8EAF0] dark:border-[#2A2E3D]"
              }`}
            >
              <div className={`absolute inset-y-0 left-0 w-1 ${needsAnswer ? "bg-amber-400" : proposal.status === "confirmed" ? "bg-emerald-500" : "bg-[#2563EB]"}`} />
              <div className={`p-4 pl-5 sm:p-5 sm:pl-6 ${proposal.status === "pending_confirmation" ? "cursor-pointer" : ""}`}>
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
                    <dl className="mt-3 grid max-w-3xl grid-cols-1 gap-x-5 gap-y-1.5 border-t border-[#EEF0F5] pt-3 text-xs text-[#62687B] dark:border-[#2A2E3D] dark:text-[#C6CAD6] sm:grid-cols-2">
                      <div className="flex gap-2"><dt className="shrink-0 text-[#8A8F9E]">Loại</dt><dd className="font-medium">{proposal.action_type === 'appointment' ? 'Sự kiện' : 'Việc cần làm'}</dd></div>
                      <div className="flex gap-2"><dt className="shrink-0 text-[#8A8F9E]">Nguồn</dt><dd className="font-medium">{proposal.source_mode === 'proactive' ? 'Agent tự quét hội thoại' : 'Yêu cầu từ hội thoại'}</dd></div>
                      {proposal.location && <div className="flex gap-2 sm:col-span-2"><dt className="shrink-0 text-[#8A8F9E]">Địa điểm / liên kết</dt><dd className="min-w-0 break-words font-medium">{proposal.location}</dd></div>}
                    </dl>
                  </div>

                  {!decided && !needsAnswer && (
                    <div className="flex shrink-0 items-center gap-2">
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void act(proposal, () => confirmActionProposal(token, proposal.id), "Đã duyệt và thêm vào lịch")}
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
                  {(proposal.status === "rejected" || proposal.status === "stale") && (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => {
                        setBusyId(proposal.id);
                        void deleteTerminalActionProposal(token, proposal.id)
                          .then(() => {
                            remove(proposal.id);
                            onNotify?.("Đã xóa đề xuất", proposal.title, "success");
                          })
                          .catch((error) => onNotify?.("Không thể xóa đề xuất", error instanceof Error ? error.message : undefined, "warning"))
                          .finally(() => setBusyId(null));
                      }}
                      className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-rose-200 px-3.5 py-2 text-xs font-semibold text-rose-600 hover:bg-rose-50 disabled:opacity-50 dark:border-rose-400/25 dark:text-rose-300 dark:hover:bg-rose-500/10"
                    >
                      <Trash2 className="h-3.5 w-3.5" /> Xóa
                    </button>
                  )}
                </div>

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
                        () => confirmActionProposal(token, proposal.id),
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
      {editingProposal && (
        <ProposalEditModal
          proposal={editingProposal}
          onClose={() => setEditingProposal(null)}
          onConfirm={(corrections) => {
            void act(
              editingProposal,
              () => confirmActionProposal(token, editingProposal.id, corrections),
              "Đã duyệt và thêm vào lịch",
            );
            setEditingProposal(null);
          }}
        />
      )}
    </section>
  );
};

const ProposalEditModal: React.FC<{
  proposal: ApiActionProposal;
  onClose: () => void;
  onConfirm: (corrections: Record<string, unknown>) => void;
}> = ({ proposal, onClose, onConfirm }) => {
  const [title, setTitle] = useState(proposal.title);
  const [location, setLocation] = useState(proposal.location ?? "");
  const [details, setDetails] = useState(proposal.details ?? "");
  const [startsAt, setStartsAt] = useState(toDateTimeLocal(proposal.scheduled_start_at));
  const [endsAt, setEndsAt] = useState(toDateTimeLocal(proposal.scheduled_end_at));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-[2px]" role="dialog" aria-modal="true">
      <form
        className="w-full max-w-xl rounded-3xl bg-white p-6 shadow-2xl dark:bg-[#1C1F27]"
        onSubmit={(event) => {
          event.preventDefault();
          onConfirm({
            title: title.trim(),
            location: location.trim() || null,
            details: details.trim() || null,
            scheduled_start_at: startsAt ? new Date(startsAt).toISOString() : null,
            scheduled_end_at: endsAt ? new Date(endsAt).toISOString() : null,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
          });
        }}
      >
        <div className="mb-5 flex items-center justify-between"><div><h3 className="text-lg font-bold text-[#1E2230] dark:text-[#F5F6FA]">Chỉnh sửa {proposal.action_type === "appointment" ? "sự kiện" : "việc cần làm"}</h3><p className="mt-1 text-xs text-[#74798C]">Kiểm tra thông tin trước khi thêm vào lịch.</p></div><button type="button" onClick={onClose} className="rounded-full p-2 text-[#74798C] hover:bg-[#F1F3F4] dark:hover:bg-[#2A2E3D]"><X className="h-5 w-5" /></button></div>
        <label className="block text-xs font-semibold text-[#3C4043] dark:text-[#E3E3E3]">Tiêu đề<input required value={title} onChange={(event) => setTitle(event.target.value)} className="mt-1.5 w-full rounded-xl border border-[#D8DCE7] bg-white px-3 py-2.5 text-sm outline-none focus:border-[#2563EB] dark:border-[#3A3F50] dark:bg-[#232630]" /></label>
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2"><label className="text-xs font-semibold text-[#3C4043] dark:text-[#E3E3E3]">Bắt đầu<input type="datetime-local" value={startsAt} onChange={(event) => setStartsAt(event.target.value)} className="mt-1.5 w-full rounded-xl border border-[#D8DCE7] bg-white px-3 py-2.5 text-sm outline-none focus:border-[#2563EB] dark:border-[#3A3F50] dark:bg-[#232630]" /></label><label className="text-xs font-semibold text-[#3C4043] dark:text-[#E3E3E3]">Kết thúc<input type="datetime-local" value={endsAt} onChange={(event) => setEndsAt(event.target.value)} className="mt-1.5 w-full rounded-xl border border-[#D8DCE7] bg-white px-3 py-2.5 text-sm outline-none focus:border-[#2563EB] dark:border-[#3A3F50] dark:bg-[#232630]" /></label></div>
        <label className="mt-4 block text-xs font-semibold text-[#3C4043] dark:text-[#E3E3E3]">Địa điểm hoặc liên kết họp<input value={location} onChange={(event) => setLocation(event.target.value)} className="mt-1.5 w-full rounded-xl border border-[#D8DCE7] bg-white px-3 py-2.5 text-sm outline-none focus:border-[#2563EB] dark:border-[#3A3F50] dark:bg-[#232630]" /></label>
        <label className="mt-4 block text-xs font-semibold text-[#3C4043] dark:text-[#E3E3E3]">Mô tả<textarea value={details} onChange={(event) => setDetails(event.target.value)} rows={4} className="mt-1.5 w-full resize-none rounded-xl border border-[#D8DCE7] bg-white px-3 py-2.5 text-sm outline-none focus:border-[#2563EB] dark:border-[#3A3F50] dark:bg-[#232630]" /></label>
        <div className="mt-6 flex justify-end gap-3"><button type="button" onClick={onClose} className="rounded-lg px-4 py-2 text-sm font-semibold text-[#62687B] hover:bg-[#F7F8FC]">Hủy</button><button type="submit" className="rounded-lg bg-[#2563EB] px-4 py-2 text-sm font-bold text-white hover:bg-[#1D4ED8]">Duyệt và thêm vào lịch</button></div>
      </form>
    </div>
  );
};
