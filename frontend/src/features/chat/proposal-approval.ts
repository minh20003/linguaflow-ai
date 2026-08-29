/** What an approver still decides at the moment they approve a proposal.
 *
 *  Shared by the task inbox and the card the assistant shows inline in the
 *  chat. One definition on purpose: the two are the same decision reached from
 *  two places, and if they disagreed about what a default is, the same proposal
 *  would land on the calendar differently depending on where it was approved.
 *
 *  None of this can be extracted from the message. Nobody writes how much
 *  warning they want in a chat message, and a message rarely states a duration
 *  either — `ProposeCalendarEventArguments` says as much where it declines to
 *  accept them, and leaves both to the approval step.
 */
import type { ApiActionProposal } from "./api/chat-api";

export interface ApprovalOptions {
  /** Event length in minutes. */
  durationMinutes: number;
  /** Minutes of warning, or null for "do not remind me". */
  reminderMinutesBefore: number | null;
}

export const DEFAULT_APPROVAL: ApprovalOptions = {
  durationMinutes: 30,
  reminderMinutesBefore: 15,
};

export const DURATION_CHOICES = [15, 30, 45, 60, 90, 120];

export const REMINDER_CHOICES: Array<{ value: number | null; label: string }> = [
  { value: 0, label: "Đúng giờ" },
  { value: 5, label: "5 phút" },
  { value: 15, label: "15 phút" },
  { value: 30, label: "30 phút" },
  { value: 60, label: "1 giờ" },
  { value: 1440, label: "1 ngày" },
  { value: null, label: "Không nhắc" },
];

export function durationLabel(minutes: number): string {
  return minutes < 60 ? `${minutes} phút` : `${minutes / 60} giờ`;
}

/** Whether this proposal is still waiting on a decision. */
export function isAwaitingDecision(proposal: ApiActionProposal): boolean {
  return proposal.status === "pending_confirmation" || proposal.status === "needs_clarification";
}

/** Turn the approver's choices into a `ConfirmProposalRequest` body.
 *
 *  The timezone always travels, the way the clarify call already sends it: the
 *  server stores UTC and has no other way to learn which wall clock the person
 *  was reading. The end time is only sent for a proposal that has a start — a
 *  task with a deadline and no start has no duration to speak of.
 */
export function approvalCorrections(
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

/** Render a proposal's time the way both surfaces show it. */
export function formatProposalWhen(proposal: ApiActionProposal): string {
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
