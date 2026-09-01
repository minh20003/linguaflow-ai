"use client";

import React from "react";
import { AlertCircle } from "lucide-react";
import type { LanguageCode } from "../types";
import type { ApiActionProposal } from "../api/chat-api";
import {
  ApprovalOptions,
  DURATION_CHOICES,
  ProposalDraft,
  reminderChoices,
  durationLabel,
  missingFields,
} from "../proposal-approval";
import { useTFor } from "../language-context";

interface ProposalDecisionFormProps {
  /** The reader's interface language. */
  language: LanguageCode;
  proposal: ApiActionProposal;
  draft: ProposalDraft;
  chosen: ApprovalOptions;
  onDraftChange: (patch: Partial<ProposalDraft>) => void;
  onOptionsChange: (patch: Partial<ApprovalOptions>) => void;
  /** Slightly tighter styling for the card that sits inside a conversation. */
  compact?: boolean;
}

const MISSING_LABELS: Record<string, string> = {
  time: "thời gian",
  timezone: "múi giờ",
  location: "địa điểm",
  title: "tiêu đề",
  details: "nội dung",
};

/** The editable half of a proposal decision, shared by both places it happens.
 *
 *  One component rather than two, for the reason `proposal-approval.ts` gives:
 *  the task inbox and the in-chat card are the same decision reached from two
 *  places, and a proposal must not land on the calendar differently depending
 *  on which one the person happened to be looking at.
 *
 *  Everything here is editable on purpose. The assistant extracts from a
 *  sentence somebody typed in a hurry; a wrong title or a time it read as next
 *  Tuesday are obvious to the owner and tedious to fix by rejecting and asking
 *  again. Editing is also the only route to approving a proposal the extractor
 *  left incomplete — the server clears a field out of `missing_fields` when a
 *  correction supplies it.
 */
export const ProposalDecisionForm: React.FC<ProposalDecisionFormProps> = ({
  proposal,
  language,
  draft,
  chosen,
  onDraftChange,
  onOptionsChange,
  compact = false,
}) => {
  // Bound to the prop, not the ambient interface language: the task inbox
  // passes the interface one and the in-chat card passes the translation one,
  // and this form has to answer to whichever asked for it.
  const ui = useTFor(language);
  const missing = missingFields(proposal);
  const field = `w-full rounded-lg border bg-white px-2.5 py-1.5 text-xs outline-none focus:border-[#2563EB] dark:bg-[#1B1D25] ${
    compact
      ? "border-violet-200 dark:border-violet-400/30"
      : "border-[#D8DCE7] dark:border-[#3A3F50]"
  }`;
  const label = "mb-1 block text-[11px] font-semibold text-[#62687B] dark:text-[#9DA3B4]";

  return (
    <div className="mt-3 space-y-3">
      {missing.length > 0 && (
        <p className="flex items-start gap-1.5 rounded-lg bg-amber-50 px-2.5 py-2 text-[11px] text-amber-900 dark:bg-amber-500/10 dark:text-amber-200">
          <AlertCircle className="mt-0.5 h-3.5 w-3.5 flex-none" />
          Trợ lý chưa xác định được {missing.map((item) => MISSING_LABELS[item] ?? item).join(", ")}.
          Bạn điền giúp rồi bấm duyệt.
        </p>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <label className={label}>{ui("Title")}</label>
          <input
            value={draft.title}
            onChange={(event) => onDraftChange({ title: event.target.value })}
            className={field}
            placeholder={ui("Example: Architecture review meeting")}
          />
        </div>
        <div>
          <label className={label}>{ui("Start")}</label>
          <input
            type="datetime-local"
            value={draft.startsAtLocal}
            onChange={(event) => onDraftChange({ startsAtLocal: event.target.value })}
            className={field}
          />
        </div>
        <div>
          <label className={label}>{ui("Location")}</label>
          <input
            value={draft.location}
            onChange={(event) => onDraftChange({ location: event.target.value })}
            className={field}
            placeholder={ui("Optional")}
          />
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
        {draft.startsAtLocal && (
          <label className="flex items-center gap-2 text-xs text-[#62687B] dark:text-[#C6CAD6]">
            <span className="font-semibold">{ui("Duration")}</span>
            <select
              value={chosen.durationMinutes}
              onChange={(event) => onOptionsChange({ durationMinutes: Number(event.target.value) })}
              className={field.replace("w-full ", "")}
            >
              {DURATION_CHOICES.map((minutes) => (
                <option key={minutes} value={minutes}>{durationLabel(minutes, language)}</option>
              ))}
            </select>
          </label>
        )}
        <label className="flex items-center gap-2 text-xs text-[#62687B] dark:text-[#C6CAD6]">
          <span className="font-semibold">{ui("Remind before")}</span>
          <select
            value={String(chosen.reminderMinutesBefore)}
            onChange={(event) =>
              onOptionsChange({
                reminderMinutesBefore:
                  event.target.value === "null" ? null : Number(event.target.value),
              })
            }
            className={field.replace("w-full ", "")}
          >
            {reminderChoices(language).map((choice) => (
              <option key={String(choice.value)} value={String(choice.value)}>{choice.label}</option>
            ))}
          </select>
        </label>
      </div>
    </div>
  );
};
