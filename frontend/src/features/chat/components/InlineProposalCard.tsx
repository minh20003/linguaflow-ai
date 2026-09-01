"use client";

import type { LanguageCode } from "../types";
import React, { useState } from "react";
import { CalendarPlus, Check, X } from "lucide-react";
import { ASSISTANT_AVATAR_URL, type ApiActionProposal } from "../api/chat-api";
import {
  ApprovalOptions,
  DEFAULT_APPROVAL,
  ProposalDraft,
  canApprove,
  decisionCorrections,
  decisionReply,
  draftFromProposal,
  formatProposalWhen,
  isAwaitingDecision,
} from "../proposal-approval";
import { ProposalDecisionForm } from "./ProposalDecisionForm";
import { useTFor } from "../language-context";

interface InlineProposalCardProps {
  /** The reader's interface language. Used for the date only.
   *
   *  A date format is a reading convention rather than content -- day/month
   *  order, AM/PM -- so it stays uniform across the app even here, where
   *  every word around it follows the translation language. */
  language: LanguageCode;
  /** The reader's translation language, for the words the assistant says and
   *  for the date.
   *
   *  Two languages because this card sits in the message thread: the
   *  appointment it is about arrived translated into `contentLanguage`, so the
   *  assistant confirming it in a different one would read as a second voice in
   *  the conversation. The buttons around it are interface, and follow the
   *  interface setting. The two are usually the same, which is why one prop
   *  looked sufficient until they were not. */
  contentLanguage: LanguageCode;
  proposal: ApiActionProposal;
  busy: boolean;
  onApprove: (proposal: ApiActionProposal, corrections: Record<string, unknown>) => void;
  onReject: (proposal: ApiActionProposal) => void;
}

/** The assistant's proposal, offered as a turn in the conversation itself.
 *
 *  Routing every approval through the task inbox made the assistant's most
 *  common answer a detour: it replied in the chat that it had prepared
 *  something, and the person then had to leave the conversation to act on it.
 *  Deciding costs two clicks, so it belongs next to the sentence that prompted
 *  it — the inbox stays the place for proposals nobody dealt with at the time.
 *
 *  It is laid out as an assistant message rather than as a panel pinned above
 *  the composer, because that is what it is: the assistant answering. It sits
 *  after the message it was extracted from and scrolls away with it, and once
 *  it is answered the assistant says what it did with the answer instead of the
 *  card silently vanishing.
 *
 *  It is still a proposal, not a booking. Nothing reaches the calendar until
 *  this card is approved (ADR-30), and the same duration and reminder choices
 *  the inbox offers are here, because a proposal approved from the chat must
 *  not quietly land with different defaults.
 */
export const InlineProposalCard: React.FC<InlineProposalCardProps> = ({
  proposal,
  language,
  contentLanguage,
  busy,
  onApprove,
  onReject,
}) => {
  // Everything here follows the translation language, buttons included: a
  // card whose sentence is in one language and whose buttons are in another
  // reads as two voices talking about the same appointment.
  const ui = useTFor(contentLanguage);
  const [chosen, setChosen] = useState<ApprovalOptions>(DEFAULT_APPROVAL);
  const [draft, setDraft] = useState<ProposalDraft>(() => draftFromProposal(proposal));
  const ready = canApprove(proposal, draft);
  const open = isAwaitingDecision(proposal);
  const reply = decisionReply(proposal, contentLanguage, language);
  const approved = proposal.status === "confirmed";

  return (
    <div className="flex justify-start gap-2.5 my-1">
      {/* One avatar for the whole turn, at its foot — the same cluster rule
          `MessageBubble` follows for consecutive messages from one sender. */}
      <div className="flex w-8 flex-shrink-0 items-end">
        <img
          src={ASSISTANT_AVATAR_URL}
          alt={ui("Smart Assistant")}
          className="h-8 w-8 rounded-full object-cover ring-1 ring-violet-200 dark:ring-violet-400/30"
          referrerPolicy="no-referrer"
        />
      </div>

      <div className="flex max-w-[85%] flex-col gap-1.5 sm:max-w-[72%] md:max-w-[62%]">
        <div
          className={`rounded-2xl rounded-bl-sm border p-3.5 transition-colors ${
            open
              ? "border-violet-200 bg-violet-50/70 dark:border-violet-400/25 dark:bg-violet-500/10"
              : "border-[#E8EAF0] bg-white/70 dark:border-[#2E3342] dark:bg-[#232630]/70"
          }`}
        >
          <p
            className={`flex items-center gap-2 text-xs font-semibold ${
              open
                ? "text-violet-800 dark:text-violet-200"
                : "text-[#74798C] dark:text-[#9DA3B4]"
            }`}
          >
            <CalendarPlus className="h-4 w-4 flex-none" />
            Trợ lý đề xuất thêm vào lịch
          </p>

          {open ? (
            <>
              <ProposalDecisionForm
                proposal={proposal}
                draft={draft}
                chosen={chosen}
                compact
          language={contentLanguage}
                onDraftChange={(patch) => setDraft((current) => ({ ...current, ...patch }))}
                onOptionsChange={(patch) => setChosen((current) => ({ ...current, ...patch }))}
              />

              <div className="mt-3 flex items-center gap-2">
                <button
                  type="button"
                  disabled={busy || !ready}
                  title={ready ? undefined : ui("Fill in the missing information above")}
                  onClick={() => onApprove(proposal, decisionCorrections(proposal, draft, chosen))}
                  className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-[#2563EB] px-3.5 py-2 text-xs font-bold text-white hover:bg-[#1D4ED8] disabled:opacity-50"
                >
                  <Check className="h-3.5 w-3.5" /> Duyệt và thêm vào lịch
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => onReject(proposal)}
                  className="inline-flex items-center gap-1 rounded-lg border border-[#D8DCE7] px-3 py-2 text-xs font-semibold text-[#62687B] hover:bg-white disabled:opacity-50 dark:border-[#3A3F50] dark:text-[#C6CAD6]"
                >
                  <X className="h-3.5 w-3.5" /> Từ chối
                </button>
              </div>
            </>
          ) : (
            /* Answered: the question is over, so the form goes and only what was
               decided stays — the transcript should still read back sensibly. */
            <div className="mt-2 text-xs text-[#4E5568] dark:text-[#C6CAD6]">
              <p className={`font-bold ${approved ? "" : "line-through opacity-70"}`}>
                {proposal.title}
              </p>
              <p className="mt-0.5 text-[11px] text-[#74798C] dark:text-[#9DA3B4]">
                {formatProposalWhen(proposal, language)}
                {proposal.location ? ` · ${proposal.location}` : ""}
              </p>
            </div>
          )}
        </div>

        {reply && (
          <div className="rounded-2xl rounded-bl-sm border border-[#E8EAF0] bg-white px-4 py-2.5 text-sm leading-relaxed text-[#1E2230] shadow-sm dark:border-[#2E3342] dark:bg-[#232630] dark:text-[#F5F6FA]">
            <p>{reply}</p>
          </div>
        )}
      </div>
    </div>
  );
};
