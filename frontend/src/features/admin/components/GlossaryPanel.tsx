"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  approveGlossaryProposal,
  createGlossaryEntry,
  fetchGlossaryEntries,
  fetchGlossaryProposals,
  rejectGlossaryProposal,
  retireGlossaryEntry,
  type GlossaryEntry,
  type GlossaryProposal,
  type ProposalStatus,
} from "@/shared/lib/glossary-api";
import type { UiTextKey } from "@/shared/lib/ui-text";
import { formatUiText } from "@/shared/lib/ui-text";
import { useInterfaceLanguage, useUiText } from "@/shared/lib/use-ui-text";
import LanguagePicker from "@/shared/ui/LanguagePicker";
import styles from "./AdminPage.module.css";

const STATUSES: ProposalStatus[] = ["pending", "approved", "rejected"];

/** Errors this screen has a sentence for; anything else reads as a plain failure. */
function messageKeyFor(error: unknown): UiTextKey {
  const code = error instanceof Error ? error.message : "";
  if (code === "glossary_conflict") return "glossary.error.conflict";
  if (code === "glossary_missing") return "glossary.error.missing";
  return "glossary.error.failed";
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
  const [sourceTerm, setSourceTerm] = useState(proposal.source_term);
  const [targetTerm, setTargetTerm] = useState(proposal.target_term);
  const [domain, setDomain] = useState(proposal.domain);
  const [audience, setAudience] = useState(proposal.audience);
  const [keepVerbatim, setKeepVerbatim] = useState(proposal.keep_verbatim);
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
        source_term: sourceTerm.trim(),
        target_term: targetTerm.trim(),
        domain: domain.trim(),
        audience: audience.trim(),
        keep_verbatim: keepVerbatim,
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
        {proposal.keep_verbatim && <span className={`${styles.badge} ${styles.badgeVerbatim}`}>{t("glossary.verbatim")}</span>}
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
          <div className={styles.fieldGrid}>
            <div className={styles.field}>
              <label htmlFor={`src-${proposal.id}`}>{t("glossary.field.sourceTerm")}</label>
              <input id={`src-${proposal.id}`} value={sourceTerm} onChange={(event) => setSourceTerm(event.target.value)} />
            </div>
            <div className={styles.field}>
              <label htmlFor={`tgt-${proposal.id}`}>{t("glossary.field.targetTerm")}</label>
              <input id={`tgt-${proposal.id}`} value={targetTerm} onChange={(event) => setTargetTerm(event.target.value)} />
            </div>
            <div className={styles.field}>
              <label htmlFor={`dom-${proposal.id}`}>{t("glossary.field.domain")}</label>
              <input id={`dom-${proposal.id}`} value={domain} onChange={(event) => setDomain(event.target.value)} placeholder={t("glossary.scopeAny")} />
            </div>
            <div className={styles.field}>
              <label htmlFor={`aud-${proposal.id}`}>{t("glossary.field.audience")}</label>
              <input id={`aud-${proposal.id}`} value={audience} onChange={(event) => setAudience(event.target.value)} placeholder={t("glossary.scopeAny")} />
            </div>
          </div>
          <label className={styles.checkRow}>
            <input type="checkbox" checked={keepVerbatim} onChange={(event) => setKeepVerbatim(event.target.checked)} />
            <span>{t("glossary.field.keepVerbatim")}</span>
          </label>
          <div className={styles.actions}>
            <button type="button" className={`${styles.action} ${styles.actionPrimary}`} onClick={approve} disabled={!sourceTerm.trim() || !targetTerm.trim() || busy}>
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
  const language = useInterfaceLanguage();
  const [status, setStatus] = useState<ProposalStatus>("pending");
  const [proposals, setProposals] = useState<GlossaryProposal[]>([]);
  const [entries, setEntries] = useState<GlossaryEntry[]>([]);
  const [includeRetired, setIncludeRetired] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [error, setError] = useState<UiTextKey | "">("");
  const [notice, setNotice] = useState<UiTextKey | "">("");

  const when = new Intl.DateTimeFormat(language, { dateStyle: "medium" });

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
    reload();
  }, [reload]);

  const retire = async (entry: GlossaryEntry) => {
    try {
      await retireGlossaryEntry(entry.id);
      afterDecision("glossary.retired");
    } catch (caught) {
      setError(messageKeyFor(caught));
    }
  };

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
          <div className={styles.tableScroll}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th scope="col">{t("glossary.field.sourceTerm")}</th>
                  <th scope="col">{t("glossary.field.targetTerm")}</th>
                  <th scope="col">{t("glossary.field.domain")}</th>
                  <th scope="col">{t("glossary.field.audience")}</th>
                  <th scope="col">{t("glossary.entries.added")}</th>
                  <th scope="col"><span className="sr-only">{t("glossary.entries.retire")}</span></th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr key={entry.id}>
                    <td className={styles.term}>
                      {entry.source_term}
                      {entry.keep_verbatim && <> <span className={`${styles.badge} ${styles.badgeVerbatim}`}>{t("glossary.verbatim")}</span></>}
                    </td>
                    <td className={styles.term}>{entry.target_term}</td>
                    <td>{entry.domain || <span className={styles.arrow}>{t("glossary.scopeAny")}</span>}</td>
                    <td>{entry.audience || <span className={styles.arrow}>{t("glossary.scopeAny")}</span>}</td>
                    <td>{when.format(new Date(entry.created_at))}</td>
                    <td>
                      {entry.status === "retired" ? (
                        <span className={`${styles.badge} ${styles.badgeRetired}`}>{t("glossary.entries.retiredBadge")}</span>
                      ) : (
                        <button type="button" className={`${styles.action} ${styles.actionDanger}`} onClick={() => retire(entry)}>
                          {t("glossary.entries.retire")}
                        </button>
                      )}
                    </td>
                  </tr>
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
  const [sourceTerm, setSourceTerm] = useState("");
  const [targetTerm, setTargetTerm] = useState("");
  const [sourceLanguage, setSourceLanguage] = useState("en");
  const [targetLanguage, setTargetLanguage] = useState("vi");
  const [domain, setDomain] = useState("");
  const [audience, setAudience] = useState("");
  const [keepVerbatim, setKeepVerbatim] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy || !sourceTerm.trim() || !targetTerm.trim()) return;
    setBusy(true);
    try {
      await createGlossaryEntry({
        source_term: sourceTerm.trim(),
        target_term: targetTerm.trim(),
        source_language: sourceLanguage,
        target_language: targetLanguage,
        domain: domain.trim(),
        audience: audience.trim(),
        keep_verbatim: keepVerbatim,
      });
      setSourceTerm("");
      setTargetTerm("");
      setDomain("");
      setAudience("");
      setKeepVerbatim(false);
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
            <label htmlFor="add-source-term">{t("glossary.field.sourceTerm")}</label>
            <input id="add-source-term" value={sourceTerm} onChange={(event) => setSourceTerm(event.target.value)} required />
          </div>
          <div className={styles.field}>
            <label htmlFor="add-target-term">{t("glossary.field.targetTerm")}</label>
            <input id="add-target-term" value={targetTerm} onChange={(event) => setTargetTerm(event.target.value)} required />
          </div>
          <div className={styles.field}>
            <label htmlFor="add-source-language">{t("glossary.field.sourceLanguage")}</label>
            <LanguagePicker id="add-source-language" value={sourceLanguage} onChange={setSourceLanguage} label={t("glossary.field.sourceLanguage")} disabled={busy} />
          </div>
          <div className={styles.field}>
            <label htmlFor="add-target-language">{t("glossary.field.targetLanguage")}</label>
            <LanguagePicker id="add-target-language" value={targetLanguage} onChange={setTargetLanguage} label={t("glossary.field.targetLanguage")} disabled={busy} />
          </div>
          <div className={styles.field}>
            <label htmlFor="add-domain">{t("glossary.field.domain")}</label>
            <input id="add-domain" value={domain} onChange={(event) => setDomain(event.target.value)} placeholder={t("glossary.scopeAny")} />
          </div>
          <div className={styles.field}>
            <label htmlFor="add-audience">{t("glossary.field.audience")}</label>
            <input id="add-audience" value={audience} onChange={(event) => setAudience(event.target.value)} placeholder={t("glossary.scopeAny")} />
          </div>
        </div>
        <label className={styles.checkRow}>
          <input type="checkbox" checked={keepVerbatim} onChange={(event) => setKeepVerbatim(event.target.checked)} />
          <span>{t("glossary.field.keepVerbatim")}</span>
        </label>
        <div className={styles.actions}>
          <button type="submit" className={`${styles.action} ${styles.actionPrimary}`} disabled={!sourceTerm.trim() || !targetTerm.trim() || busy}>
            {t("glossary.add.submit")}
          </button>
        </div>
      </form>
    </section>
  );
}
