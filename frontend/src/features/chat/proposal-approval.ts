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
import { interactionText } from "./i18n";
import type { LanguageCode } from "./types";
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

/** How long before the event to nudge, in the reader's own language.
 *
 *  A function rather than a constant because the labels are language-dependent
 *  and a module-level array is evaluated once, before anybody has logged in.
 */
export function reminderChoices(
  language: LanguageCode,
): Array<{ value: number | null; label: string }> {
  return [
    { value: 0, label: interactionText(language, "On time") },
    { value: 5, label: durationLabel(5, language) },
    { value: 15, label: durationLabel(15, language) },
    { value: 30, label: durationLabel(30, language) },
    { value: 60, label: durationLabel(60, language) },
    { value: 1440, label: durationLabel(1440, language) },
    { value: null, label: interactionText(language, "No reminder") },
  ];
}

/** A duration, spelled the way the reader's language spells it.
 *
 *  `Intl` rather than a catalogue entry per number: it already knows that
 *  English wants "30 minutes", Vietnamese "30 phút" and Japanese "30 分", and a
 *  translated string per value would be a row nobody can check for fourteen
 *  languages times six durations.
 */
export function durationLabel(minutes: number, language: LanguageCode): string {
  const [value, unit] =
    minutes < 60
      ? [minutes, "minute" as const]
      : minutes < 1440
        ? [minutes / 60, "hour" as const]
        : [minutes / 1440, "day" as const];
  try {
    return new Intl.NumberFormat(language, {
      style: "unit",
      unit,
      unitDisplay: "long",
    }).format(value);
  } catch {
    // An engine without unit formatting, or a language tag it will not take.
    return `${value} ${unit}`;
  }
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
export function formatProposalWhen(
  proposal: ApiActionProposal,
  language: LanguageCode,
): string {
  const at = proposal.scheduled_start_at || proposal.due_at;
  if (!at) return interactionText(language, "No time set yet");
  // The reader's locale, not "vi-VN". A Japanese reader was shown a Vietnamese
  // date order for an appointment on their own calendar.
  return new Date(at).toLocaleString(language, {
    weekday: "short",
    day: "numeric",
    month: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** The fields a person may correct before approving.
 *
 *  Human-in-the-loop is not only a confirm button: the assistant reads a
 *  sentence someone typed in a hurry, and the title it lifts, the time it
 *  resolves and the place it guesses are all things the owner can see are wrong
 *  at a glance. Letting them fix it here is faster than rejecting and asking
 *  again, and it is the only way to approve a proposal the extractor left
 *  incomplete: `confirm_proposal` clears a field out of `missing_fields` when a
 *  correction supplies it, so a proposal stuck on `needs_clarification` becomes
 *  confirmable the moment the missing value is typed in.
 */
export interface ProposalDraft {
  title: string;
  /** `datetime-local` value, empty when the proposal carries no start. */
  startsAtLocal: string;
  location: string;
}

/** Seed the form from what the assistant proposed. */
export function draftFromProposal(proposal: ApiActionProposal): ProposalDraft {
  return {
    title: proposal.title ?? "",
    startsAtLocal: toLocalInputValue(proposal.scheduled_start_at),
    location: proposal.location ?? "",
  };
}

/** ISO instant -> the `YYYY-MM-DDTHH:mm` a `datetime-local` input wants.
 *
 *  Built from the local parts rather than by slicing `toISOString()`, which
 *  would render the UTC clock and silently shift the time the person sees.
 */
export function toLocalInputValue(iso: string | null | undefined): string {
  if (!iso) return "";
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return "";
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}T${pad(at.getHours())}:${pad(at.getMinutes())}`;
}

/** Which required fields the extractor could not fill.
 *
 *  `scheduled_time` and `time` are the same gap under two names — the extractor
 *  writes the first, everything that resolves one speaks of the second — so
 *  they are folded together here the way the server folds them.
 */
const MISSING_ALIASES: Record<string, string> = {
  scheduled_time: "time",
  scheduled_start_at: "time",
};

export function missingFields(proposal: ApiActionProposal): string[] {
  try {
    const parsed = JSON.parse(proposal.missing_fields || "[]");
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((item): item is string => typeof item === "string")
      .map((item) => MISSING_ALIASES[item] ?? item);
  } catch {
    return [];
  }
}

/** Whether this proposal can be approved as it stands.
 *
 *  The interface used to offer "Duyệt" on anything undecided, including
 *  proposals the server would refuse with "still has unresolved required
 *  fields" — the button looked available and answered with an error.
 */
export function canApprove(proposal: ApiActionProposal, draft: ProposalDraft): boolean {
  const missing = missingFields(proposal);
  if (missing.includes("time") && !draft.startsAtLocal) return false;
  if (missing.includes("location") && !draft.location.trim()) return false;
  if (missing.includes("title") && !draft.title.trim()) return false;
  return Boolean(draft.title.trim());
}

/** The full `ConfirmProposalRequest` body: the approver's edits and their choices. */
export function decisionCorrections(
  proposal: ApiActionProposal,
  draft: ProposalDraft,
  chosen: ApprovalOptions,
): Record<string, unknown> {
  const body: Record<string, unknown> = {
    reminder_minutes_before: chosen.reminderMinutesBefore,
    resolved_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  };
  if (draft.title.trim()) body.title = draft.title.trim();
  if (draft.location.trim()) body.location = draft.location.trim();

  const start = draft.startsAtLocal ? new Date(draft.startsAtLocal) : null;
  if (start && !Number.isNaN(start.getTime())) {
    body.scheduled_start_at = start.toISOString();
    body.scheduled_end_at = new Date(
      start.getTime() + chosen.durationMinutes * 60_000,
    ).toISOString();
  }
  return body;
}

/** What the assistant says once the proposal has been answered.
 *
 *  A decision is a turn in the conversation, so it reads as one: the card asks,
 *  the person answers, and the assistant confirms what it did with the answer.
 *  `null` while the question is still open — there is nothing to report yet.
 */
export function decisionReply(
  proposal: ApiActionProposal,
  language: LanguageCode,
  dateLanguage: LanguageCode = language,
): string | null {
  // Composed rather than interpolated into a translated sentence. A catalogue
  // string carrying a `{title}` token is a token a machine translator can drop,
  // and losing it would silently produce a sentence about nothing in
  // particular; a fixed phrase followed by the quoted title cannot fail that
  // way in any of the fourteen languages.
  const when =
    proposal.scheduled_start_at || proposal.due_at
      // The sentence is in the reader's translation language; the date inside
      // it still formats on the interface one, which is a reading convention
      // rather than content and stays uniform across the app.
      ? ` — ${formatProposalWhen(proposal, dateLanguage)}`
      : "";
  switch (proposal.status) {
    case "confirmed":
      return `${interactionText(language, "Added to your personal calendar")}: "${proposal.title}"${when}.`;
    case "rejected":
      return `${interactionText(language, "Turned down, and left off your calendar")}: "${proposal.title}".`;
    case "stale":
      return `${interactionText(language, "This suggestion expired, so it was skipped")}: "${proposal.title}".`;
    default:
      return null;
  }
}
