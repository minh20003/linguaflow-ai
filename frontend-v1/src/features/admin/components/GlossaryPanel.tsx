"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Archive, PencilLine, RotateCcw, Trash2 } from "lucide-react";
import {
  approveGlossaryProposal,
  createGlossaryEntry,
  deleteGlossaryEntry,
  fetchGlossaryEntries,
  fetchGlossaryProposals,
  rejectGlossaryProposal,
  restoreGlossaryEntry,
  retireGlossaryEntry,
  updateGlossaryEntry,
  type GlossaryEntry,
  type GlossaryProposal,
  type ProposalStatus,
} from "@/shared/lib/glossary-api";
import type { UiTextKey } from "@/shared/lib/ui-text";
import { formatUiText } from "@/shared/lib/ui-text";
import { useInterfaceLanguage, useUiText } from "@/shared/lib/use-ui-text";
import LanguagePicker from "@/shared/ui/LanguagePicker";
import ScopeField from "./ScopeField";
import styles from "./AdminPage.module.css";

const STATUSES: ProposalStatus[] = ["pending", "approved", "rejected"];

/** Errors this screen has a sentence for; anything else reads as a plain failure. */
function messageKeyFor(error: unknown): UiTextKey {
  const code = error instanceof Error ? error.message : "";
  if (code === "glossary_conflict") return "glossary.error.conflict";
  if (code === "glossary_missing") return "glossary.error.missing";
  return "glossary.error.failed";
}

/** The five fields that make a term, wherever it is being written. */
type TermDraft = {
  sourceTerm: string;
  targetTerm: string;
  domain: string;
  audience: string;
  keepVerbatim: boolean;
};

type ChangeTermField = <K extends keyof TermDraft>(key: K, value: TermDraft[K]) => void;

/**
 * A term being written, with the one rule that ties two of its fields together.
 *
 * "Keep as is" means the model is told to leave the term in the source
 * language, so the target term stops being a translation and becomes a copy of
 * the source — which is what the miner is asked to produce for such terms, and
 * what the column has to hold either way because it is not nullable. Keeping
 * the two in step here is what makes the checkbox comprehensible: before this,
 * the form asked for a translation it was about to ignore.
 */
function useTermDraft(initial: TermDraft) {
  const [draft, setDraft] = useState(initial);

  const change = useCallback<ChangeTermField>((key, value) => {
    setDraft((current) => {
      const next = { ...current, [key]: value };
      if (next.keepVerbatim) next.targetTerm = next.sourceTerm;
      return next;
    });
  }, []);

  return [draft, change, setDraft] as const;
}

type TermFieldsProps = {
  idPrefix: string;
  draft: TermDraft;
  change: ChangeTermField;
  disabled?: boolean;
};

/**
 * The editable body of a term, shared by every screen that writes one.
 *
 * One component rather than three copies because the rule above only holds if
 * every form obeys it, and a form that forgot would store a translation for a
 * term nothing translates.
 */
function TermFields({ idPrefix, draft, change, disabled }: TermFieldsProps) {
  const t = useUiText();

  return (
    <>
      <div className={styles.fieldGrid}>
        <div className={styles.field}>
          <label htmlFor={`${idPrefix}-source`}>{t("glossary.field.sourceTerm")}</label>
          <input
            id={`${idPrefix}-source`}
            value={draft.sourceTerm}
            onChange={(event) => change("sourceTerm", event.target.value)}
            disabled={disabled}
            required
          />
        </div>
        <div className={styles.field}>
          <label htmlFor={`${idPrefix}-target`}>{t("glossary.field.targetTerm")}</label>
          {/* Locked, not hidden, while the term is kept as is: the value is
              still what gets stored, and hiding it would leave a reader unable
              to see what the entry says. */}
          <input
            id={`${idPrefix}-target`}
            value={draft.targetTerm}
            onChange={(event) => change("targetTerm", event.target.value)}
            disabled={disabled || draft.keepVerbatim}
            required
          />
        </div>
        <div className={styles.field}>
          <label htmlFor={`${idPrefix}-domain`}>{t("glossary.field.domain")}</label>
          <ScopeField
            id={`${idPrefix}-domain`}
            kind="domain"
            value={draft.domain}
            onChange={(value) => change("domain", value)}
            disabled={disabled}
          />
        </div>
        <div className={styles.field}>
          <label htmlFor={`${idPrefix}-audience`}>{t("glossary.field.audience")}</label>
          <ScopeField
            id={`${idPrefix}-audience`}
            kind="audience"
            value={draft.audience}
            onChange={(value) => change("audience", value)}
            disabled={disabled}
          />
        </div>
      </div>
      <p className={styles.hint}>{t("glossary.scope.hint")}</p>
      <label className={styles.checkRow}>
        <input
          type="checkbox"
          checked={draft.keepVerbatim}
          onChange={(event) => change("keepVerbatim", event.target.checked)}
          disabled={disabled}
        />
        <span>{t("glossary.field.keepVerbatim")}</span>
      </label>
      <p className={styles.hint}>{t("glossary.field.keepVerbatimHint")}</p>
    </>
  );
}

type ProposalCardProps = {
  proposal: GlossaryProposal;
  onDecided: () => void;
  onFailed: (key: UiTextKey) => void;
};

/**
 * One proposal, its evidence, and the two things a reviewer can do with it.
 *
 * The term fields are editable in place rather than read-only, because §3.12
 * lets an approval correct the proposal on the way through: the miner's answer
 * came from a model reading anonymised fragments, and forcing a reviewer to
 * reject and hand-add a nearly-right term is the fastest way for a queue to
 * stop being worked.
 *
 * What is not on this card — who wrote the corrections, which conversation they
 * came from — is absent because the server never sends it. An administrator is
 * barred from reading conversation content, and the DTO has nowhere to put it.
 */
function ProposalCard({ proposal, onDecided, onFailed }: ProposalCardProps) {
  const t = useUiText();
  const language = useInterfaceLanguage();
  const [draft, change] = useTermDraft({
    sourceTerm: proposal.source_term,
    targetTerm: proposal.target_term,
    domain: proposal.domain,
    audience: proposal.audience,
    keepVerbatim: proposal.keep_verbatim,
  });
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  const when = new Intl.DateTimeFormat(language, { dateStyle: "medium" });
  const number = new Intl.NumberFormat(language);
  const pair = `${proposal.source_language} → ${proposal.target_language}`;

  const approve = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await approveGlossaryProposal(proposal.id, {
        source_term: draft.sourceTerm.trim(),
        target_term: draft.targetTerm.trim(),
        domain: draft.domain.trim(),
        audience: draft.audience.trim(),
        keep_verbatim: draft.keepVerbatim,
      });
      onDecided();
    } catch (caught) {
      onFailed(messageKeyFor(caught));
      setBusy(false);
    }
  };

  const reject = async (event: FormEvent) => {
    event.preventDefault();
    const text = reason.trim();
    if (!text || busy) return;
    setBusy(true);
    try {
      await rejectGlossaryProposal(proposal.id, text);
      onDecided();
    } catch (caught) {
      onFailed(messageKeyFor(caught));
      setBusy(false);
    }
  };

  const decided = proposal.status !== "pending";

  return (
    <article className={styles.proposal}>
      <div className={styles.proposalHead}>
        <span className={styles.proposalTerm}>
          {proposal.source_term}
          <span className={styles.arrow} aria-hidden="true">→</span>
          {proposal.target_term}
        </span>
        <span className={styles.badge}>{pair}</span>
        {/* No "kept as is" badge: the arrow above already shows source and
            target side by side, and for a verbatim term they read as the same
            word — the fact the badge would announce is already on screen. */}
      </div>

      {/* Two numbers, and the second is the one that decides. Five corrections
          from one person is a preference; two from two people is a house style
          forming (ADR-28). */}
      <p className={styles.evidence}>
        <span>{t("glossary.evidence.occurrences")} <strong>{number.format(proposal.occurrence_count)}</strong></span>
        <span>{t("glossary.evidence.people")} <strong>{number.format(proposal.distinct_user_count)}</strong></span>
        <span>{when.format(new Date(proposal.created_at))}</span>
      </p>

      {proposal.rationale && <p className={styles.rationale}>{proposal.rationale}</p>}

      {/* What the glossary already says. A reviewer approving into a blank
          state and one overturning a live entry are making different decisions,
          and the queue used to show them identically. */}
      {proposal.similar_entries.length > 0 && (
        <div className={proposal.conflicts_with_active ? styles.conflict : styles.known}>
          <p className={styles.hint}>
            {formatUiText(language, "glossary.similar.count", {
              count: String(proposal.similar_entries.length),
            })}
            {proposal.conflicts_with_active && (
              <> — <strong>{t("glossary.similar.conflict")}</strong></>
            )}
          </p>
          <ul className={styles.citations}>
            {proposal.similar_entries.map((entry) => (
              <li key={entry.id} className={styles.term}>
                {entry.source_term}
                <span className={styles.arrow} aria-hidden="true">→</span>
                {entry.target_term}
                {" "}
                <span className={styles.badge}>
                  {entry.domain || entry.audience
                    ? [entry.domain, entry.audience].filter(Boolean).join(" / ")
                    : t("glossary.scopeAny")}
                </span>
                {entry.status !== "active" && (
                  <> <span className={`${styles.badge} ${styles.badgeRetired}`}>
                    {t("glossary.entries.retiredBadge")}
                  </span></>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      {proposal.similar_entries.length === 0 && (
        <p className={styles.hint}>{t("glossary.similar.none")}</p>
      )}

      {proposal.citations.length > 0 && (
        <>
          <p className={styles.hint}>{t("glossary.citations")}</p>
          <ul className={styles.citations}>
            {proposal.citations.map((citation, index) => (
              <li key={`${proposal.id}-${index}`}>
                {citation.anonymized_snippet}{" "}
                <span className={styles.citationTime}>{when.format(new Date(citation.observed_at))}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      {decided ? (
        proposal.reject_reason ? <p className={styles.hint}>{t("glossary.rejectReason")}: {proposal.reject_reason}</p> : null
      ) : rejecting ? (
        <form onSubmit={reject}>
          <div className={styles.field}>
            <label htmlFor={`reject-${proposal.id}`}>{t("glossary.rejectReason")}</label>
            <textarea
              id={`reject-${proposal.id}`}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder={t("glossary.rejectReasonPlaceholder")}
              rows={2}
              autoFocus
            />
          </div>
          <div className={styles.actions}>
            <button type="button" className={styles.action} onClick={() => setRejecting(false)} disabled={busy}>
              {t("common.cancel")}
            </button>
            <button type="submit" className={`${styles.action} ${styles.actionDanger}`} disabled={!reason.trim() || busy}>
              {t("glossary.reject")}
            </button>
          </div>
        </form>
      ) : (
        <>
          <TermFields idPrefix={`proposal-${proposal.id}`} draft={draft} change={change} disabled={busy} />
          <div className={styles.actions}>
            <button
              type="button"
              className={`${styles.action} ${styles.actionPrimary}`}
              onClick={approve}
              disabled={!draft.sourceTerm.trim() || !draft.targetTerm.trim() || busy}
            >
              {t("glossary.approve")}
            </button>
            <button type="button" className={`${styles.action} ${styles.actionDanger}`} onClick={() => setRejecting(true)} disabled={busy}>
              {t("glossary.reject")}
            </button>
          </div>
        </>
      )}
    </article>
  );
}

type EntryRowProps = {
  entry: GlossaryEntry;
  onChanged: (key: UiTextKey) => void;
  onFailed: (key: UiTextKey) => void;
};

/**
 * One entry in force, and the three things that can happen to it.
 *
 * Retirement and restoration are a pair rather than a delete: a translation
 * delivered last month was shaped by whatever was active then, so the row is
 * the only explanation for wording somebody may still be reading. Editing
 * exists so a typo in an approved term does not have to be fixed by retiring it
 * and adding a near-identical row — which would leave two rows, permanently,
 * for a reader to compare. Offered only while active: a retired term shapes no
 * translation, so there is nothing left for a correction to fix.
 *
 * Deleting is the exception, and it is why the two states offer different
 * buttons: a retired term that never shaped anything explains nothing, and
 * while its row exists it keeps holding the scope against a corrected version
 * of itself. It is asked about twice before it happens.
 */
function EntryRow({ entry, onChanged, onFailed }: EntryRowProps) {
  const t = useUiText();
  const language = useInterfaceLanguage();
  const [editing, setEditing] = useState(false);
  // Two steps for the one action that cannot be undone. The row is where the
  // question is asked, so the term being deleted stays on screen while it is.
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [busy, setBusy] = useState(false);
  const [draft, change, setDraft] = useTermDraft({
    sourceTerm: entry.source_term,
    targetTerm: entry.target_term,
    domain: entry.domain,
    audience: entry.audience,
    keepVerbatim: entry.keep_verbatim,
  });

  const when = new Intl.DateTimeFormat(language, { dateStyle: "medium" });

  // The row survives the reload that follows a change — it is keyed by entry id
  // and the entry is still there — so unlike a decided proposal it has to put
  // itself back in order rather than relying on being unmounted.
  const run = async (action: () => Promise<unknown>, notice: UiTextKey) => {
    if (busy) return;
    setBusy(true);
    try {
      await action();
      setEditing(false);
      setConfirmingDelete(false);
      onChanged(notice);
    } catch (caught) {
      onFailed(messageKeyFor(caught));
    } finally {
      setBusy(false);
    }
  };

  const save = (event: FormEvent) => {
    event.preventDefault();
    return run(
      () =>
        updateGlossaryEntry(entry.id, {
          source_term: draft.sourceTerm.trim(),
          target_term: draft.targetTerm.trim(),
          domain: draft.domain.trim(),
          audience: draft.audience.trim(),
          keep_verbatim: draft.keepVerbatim,
        }),
      "glossary.updated",
    );
  };

  const cancel = () => {
    // Back to what the server last said, not to whatever was typed: the row is
    // reloaded after every successful change, so this is the only copy of it.
    setDraft({
      sourceTerm: entry.source_term,
      targetTerm: entry.target_term,
      domain: entry.domain,
      audience: entry.audience,
      keepVerbatim: entry.keep_verbatim,
    });
    setEditing(false);
  };

  if (editing) {
    return (
      <tr>
        <td colSpan={7}>
          <form onSubmit={save}>
            <TermFields idPrefix={`entry-${entry.id}`} draft={draft} change={change} disabled={busy} />
            <div className={styles.actions}>
              <button
                type="submit"
                className={`${styles.action} ${styles.actionPrimary}`}
                disabled={!draft.sourceTerm.trim() || !draft.targetTerm.trim() || busy}
              >
                {t("glossary.entries.save")}
              </button>
              <button type="button" className={styles.action} onClick={cancel} disabled={busy}>
                {t("common.cancel")}
              </button>
            </div>
          </form>
        </td>
      </tr>
    );
  }

  const retired = entry.status === "retired";

  return (
    <tr>
      {/* No "kept as is" badge here either: the next column already shows the
          target term, and for a verbatim entry it reads identical to this
          one — that identity is the fact the badge would otherwise announce. */}
      <td className={styles.term} title={entry.source_term}>{entry.source_term}</td>
      <td className={styles.term} title={entry.target_term}>{entry.target_term}</td>
      <td title={entry.domain || undefined}>{entry.domain || <span className={styles.arrow}>{t("glossary.scopeAny")}</span>}</td>
      <td title={entry.audience || undefined}>{entry.audience || <span className={styles.arrow}>{t("glossary.scopeAny")}</span>}</td>
      {/* Whether this term is binding translations right now, in its own column
          rather than as a badge among the buttons. Every row answers it, and a
          column is where a reader looks for an answer every row gives. */}
      <td>
        <span className={`${styles.badge} ${retired ? styles.badgeRetired : styles.badgeActive}`}>
          {t(retired ? "glossary.entries.retiredBadge" : "glossary.entries.activeBadge")}
        </span>
      </td>
      <td>{when.format(new Date(entry.created_at))}</td>
      <td>
        {confirmingDelete ? (
          /* Asked in the row rather than in a browser dialog: the question is
             about this term, so it should be readable next to it, and the
             answer that destroys something is never the one already focused. */
          <div className={styles.rowActions}>
            <span className={styles.confirmQuestion}>{t("glossary.entries.deleteConfirm")}</span>
            <button
              type="button"
              className={`${styles.action} ${styles.actionDanger}`}
              onClick={() => run(() => deleteGlossaryEntry(entry.id), "glossary.deleted")}
              disabled={busy}
            >
              {t("glossary.entries.deleteConfirmYes")}
            </button>
            <button
              type="button"
              className={styles.action}
              onClick={() => setConfirmingDelete(false)}
              disabled={busy}
            >
              {t("common.cancel")}
            </button>
          </div>
        ) : (
          /* Icons, not words, once a row settles into either state: the label
             next to every one of these already says "active" or "retired", so
             a text button repeated the same idea in a second, longer form. A
             retired row keeps only Restore and Delete — editing something that
             shapes no translation is the one action that stopped meaning
             anything the moment it stopped being active. */
          <div className={styles.rowActions}>
            {!retired && (
              <button
                type="button"
                className={styles.iconAction}
                onClick={() => setEditing(true)}
                disabled={busy}
                aria-label={t("glossary.entries.edit")}
                title={t("glossary.entries.edit")}
              >
                <PencilLine size={16} strokeWidth={1.8} aria-hidden="true" />
              </button>
            )}
            {retired ? (
              <>
                <button
                  type="button"
                  className={styles.iconAction}
                  onClick={() => run(() => restoreGlossaryEntry(entry.id), "glossary.restored")}
                  disabled={busy}
                  aria-label={t("glossary.entries.restore")}
                  title={t("glossary.entries.restore")}
                >
                  <RotateCcw size={16} strokeWidth={1.8} aria-hidden="true" />
                </button>
                {/* Offered only here, and the server agrees: deleting an active
                    entry is refused with a 409, because a term in use is the
                    only explanation for wording somebody may still be reading.
                    What is left is the term typed in by mistake. */}
                <button
                  type="button"
                  className={`${styles.iconAction} ${styles.iconActionDanger}`}
                  onClick={() => setConfirmingDelete(true)}
                  disabled={busy}
                  aria-label={t("glossary.entries.delete")}
                  title={t("glossary.entries.delete")}
                >
                  <Trash2 size={16} strokeWidth={1.8} aria-hidden="true" />
                </button>
              </>
            ) : (
              <button
                type="button"
                className={`${styles.iconAction} ${styles.iconActionDanger}`}
                onClick={() => run(() => retireGlossaryEntry(entry.id), "glossary.retired")}
                disabled={busy}
                aria-label={t("glossary.entries.retire")}
                title={t("glossary.entries.retire")}
              >
                <Archive size={16} strokeWidth={1.8} aria-hidden="true" />
              </button>
            )}
          </div>
        )}
      </td>
    </tr>
  );
}

/**
 * The review queue and the glossary it feeds.
 *
 * Both lists are reloaded after every decision rather than patched in place.
 * Two administrators can work this queue at the same time, and the server
 * answers a second decision with 409 — so the screen's job on any success is to
 * find out what the queue looks like now, not to assume.
 */
export default function GlossaryPanel() {
  const t = useUiText();
  const [status, setStatus] = useState<ProposalStatus>("pending");
  const [proposals, setProposals] = useState<GlossaryProposal[]>([]);
  const [entries, setEntries] = useState<GlossaryEntry[]>([]);
  const [includeRetired, setIncludeRetired] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [error, setError] = useState<UiTextKey | "">("");
  const [notice, setNotice] = useState<UiTextKey | "">("");

  // Both lists come from one effect keyed on what selects them, plus a counter
  // for "fetch again with the same selection". The spinner is turned on by
  // whatever the reader did — picking a status, deciding a proposal — rather
  // than by the effect, which only ever writes state once a response is back.
  useEffect(() => {
    let active = true;
    Promise.all([fetchGlossaryProposals(status), fetchGlossaryEntries(includeRetired)])
      .then(([queue, glossary]) => {
        if (!active) return;
        setProposals(queue);
        setEntries(glossary);
        setError("");
        setLoading(false);
      })
      .catch((caught) => {
        if (!active) return;
        setError(messageKeyFor(caught));
        setLoading(false);
      });
    return () => { active = false; };
  }, [status, includeRetired, refresh]);

  const reload = useCallback(() => {
    setLoading(true);
    setRefresh((count) => count + 1);
  }, []);

  const afterDecision = useCallback((key: UiTextKey) => {
    setNotice(key);
    setError("");
    // Retiring a term while the list is filtered to active ones would make the
    // row vanish at the moment it changed state, which reads as a deletion —
    // the one thing retirement is not. Show retired terms from here on, so what
    // happened stays on screen with its status and its way back.
    if (key === "glossary.retired") setIncludeRetired(true);
    reload();
  }, [reload]);

  return (
    <>
      <section className={styles.card} aria-labelledby="glossary-queue">
        <h2 id="glossary-queue">{t("glossary.queue.title")}</h2>
        <p className={styles.hint}>{t("glossary.queue.hint")}</p>

        <div className={styles.actions} role="group" aria-label={t("glossary.queue.title")}>
          {STATUSES.map((option) => (
            <button
              key={option}
              type="button"
              className={`${styles.action} ${option === status ? styles.actionPrimary : ""}`}
              aria-pressed={option === status}
              onClick={() => { setLoading(true); setStatus(option); }}
            >
              {t(`glossary.status.${option}` as UiTextKey)}
            </button>
          ))}
        </div>

        {error && <p className={styles.error} role="alert">{t(error)}</p>}
        {notice && !error && <p className={styles.feedback} role="status">{t(notice)}</p>}

        {loading ? (
          <p className={styles.hint} aria-busy="true">{t("glossary.loading")}</p>
        ) : proposals.length ? (
          <div>
            {proposals.map((proposal) => (
              <ProposalCard
                key={proposal.id}
                proposal={proposal}
                onDecided={() => afterDecision("glossary.decided")}
                onFailed={setError}
              />
            ))}
          </div>
        ) : (
          <p className={styles.empty}>{t("glossary.queue.empty")}</p>
        )}
      </section>

      <AddEntryForm onAdded={() => afterDecision("glossary.added")} onFailed={setError} />

      <section className={styles.card} aria-labelledby="glossary-entries">
        <h2 id="glossary-entries">{t("glossary.entries.title")}</h2>
        <p className={styles.hint}>{t("glossary.entries.hint")}</p>

        <label className={styles.checkRow}>
          <input
            type="checkbox"
            checked={includeRetired}
            onChange={(event) => { setLoading(true); setIncludeRetired(event.target.checked); }}
          />
          <span>{t("glossary.entries.showRetired")}</span>
        </label>

        {entries.length ? (
          <div className={`${styles.tableScroll} ${styles.tableScrollTall}`}>
            <table className={styles.table}>
              {/* Column widths pinned here rather than left to content: with
                  `table-layout: fixed` this row is what the browser measures,
                  and pinning it is what keeps every table on the page the same
                  width regardless of how long a term or a date happens to be. */}
              <thead>
                <tr>
                  <th scope="col" style={{ width: 170 }}>{t("glossary.field.sourceTerm")}</th>
                  <th scope="col" style={{ width: 170 }}>{t("glossary.field.targetTerm")}</th>
                  <th scope="col" style={{ width: 110 }}>{t("glossary.field.domain")}</th>
                  <th scope="col" style={{ width: 110 }}>{t("glossary.field.audience")}</th>
                  <th scope="col" style={{ width: 100 }}>{t("glossary.entries.status")}</th>
                  <th scope="col" style={{ width: 110 }}>{t("glossary.entries.added")}</th>
                  <th scope="col" style={{ width: 140 }}>{t("glossary.entries.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <EntryRow
                    key={entry.id}
                    entry={entry}
                    onChanged={afterDecision}
                    onFailed={setError}
                  />
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className={styles.empty}>{t("glossary.entries.empty")}</p>
        )}
      </section>
    </>
  );
}

type AddEntryFormProps = {
  onAdded: () => void;
  onFailed: (key: UiTextKey) => void;
};

/**
 * Add a term by hand.
 *
 * The queue only ever proposes what people have already been correcting, so
 * there has to be a way in for a term the team decided on before anyone typed
 * it wrong — a product name at launch, say. Same shape as an approval, which is
 * why both end up as one `glossary_entries` row.
 */
function AddEntryForm({ onAdded, onFailed }: AddEntryFormProps) {
  const t = useUiText();
  const [draft, change, setDraft] = useTermDraft({
    sourceTerm: "",
    targetTerm: "",
    domain: "",
    audience: "",
    keepVerbatim: false,
  });
  const [sourceLanguage, setSourceLanguage] = useState("en");
  const [targetLanguage, setTargetLanguage] = useState("vi");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy || !draft.sourceTerm.trim() || !draft.targetTerm.trim()) return;
    setBusy(true);
    try {
      await createGlossaryEntry({
        source_term: draft.sourceTerm.trim(),
        target_term: draft.targetTerm.trim(),
        source_language: sourceLanguage,
        target_language: targetLanguage,
        domain: draft.domain.trim(),
        audience: draft.audience.trim(),
        keep_verbatim: draft.keepVerbatim,
      });
      setDraft({
        sourceTerm: "",
        targetTerm: "",
        domain: "",
        audience: "",
        keepVerbatim: false,
      });
      onAdded();
    } catch (caught) {
      onFailed(messageKeyFor(caught));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className={styles.card} aria-labelledby="glossary-add">
      <h2 id="glossary-add">{t("glossary.add.title")}</h2>
      <p className={styles.hint}>{t("glossary.add.hint")}</p>
      <form onSubmit={submit}>
        <div className={styles.fieldGrid}>
          <div className={styles.field}>
            <label htmlFor="add-source-language">{t("glossary.field.sourceLanguage")}</label>
            <LanguagePicker id="add-source-language" value={sourceLanguage} onChange={setSourceLanguage} label={t("glossary.field.sourceLanguage")} disabled={busy} />
          </div>
          <div className={styles.field}>
            <label htmlFor="add-target-language">{t("glossary.field.targetLanguage")}</label>
            <LanguagePicker id="add-target-language" value={targetLanguage} onChange={setTargetLanguage} label={t("glossary.field.targetLanguage")} disabled={busy} />
          </div>
        </div>
        <TermFields idPrefix="add" draft={draft} change={change} disabled={busy} />
        <div className={styles.actions}>
          <button
            type="submit"
            className={`${styles.action} ${styles.actionPrimary}`}
            disabled={!draft.sourceTerm.trim() || !draft.targetTerm.trim() || busy}
          >
            {t("glossary.add.submit")}
          </button>
        </div>
      </form>
    </section>
  );
}
