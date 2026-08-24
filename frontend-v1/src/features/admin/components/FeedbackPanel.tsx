"use client";

import { useEffect, useState } from "react";
import { Eye, X } from "lucide-react";
import {
  fetchFeedbackOverview,
  type FeedbackOverview,
  type SharedCorrection,
} from "@/shared/lib/feedback-api";
import { languageLabel } from "@/shared/lib/constants";
import { formatUiText } from "@/shared/lib/ui-text";
import { useInterfaceLanguage, useUiText } from "@/shared/lib/use-ui-text";
import styles from "./AdminPage.module.css";

type LoadState = "loading" | "ready" | "error";

/**
 * What readers said about the translations, in the two forms it arrives in.
 *
 * Both were invisible before this tab existed. A vote went into `feedbacks`
 * and was never read back, and the only visible output of the whole correction
 * pipeline was a proposal — which appears once several people have
 * independently agreed, so everything below that threshold looked exactly like
 * nothing arriving at all.
 *
 * The boundary is the server's, not this screen's: counts, and the anonymised
 * fragment the recorder prepared at edit time. No author, no conversation, no
 * message id (docs/CONTRACT.md §3.12).
 */
export default function FeedbackPanel() {
  const t = useUiText();
  const language = useInterfaceLanguage();
  const [overview, setOverview] = useState<FeedbackOverview | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  // Which row's context is open, lifted here rather than into the row: the
  // dialog is one overlay for the whole screen, not one per row, so only one
  // can ever be open regardless of how many rows exist.
  const [viewing, setViewing] = useState<SharedCorrection | null>(null);

  const number = new Intl.NumberFormat(language);
  const percent = new Intl.NumberFormat(language, { style: "percent", maximumFractionDigits: 1 });

  useEffect(() => {
    let active = true;
    fetchFeedbackOverview()
      .then((response) => {
        if (!active) return;
        setOverview(response);
        setState("ready");
      })
      .catch(() => active && setState("error"));
    return () => { active = false; };
  }, []);

  if (state === "loading") {
    return <section className={styles.card} aria-busy="true"><p className={styles.hint}>{t("feedback.loading")}</p></section>;
  }
  if (state === "error" || !overview) {
    return <section className={styles.card}><p className={styles.error} role="alert">{t("feedback.loadFailed")}</p></section>;
  }

  const { votes, shared_corrections: shared } = overview;

  return (
    <>
      <section className={styles.card} aria-labelledby="admin-feedback-votes">
        <h2 id="admin-feedback-votes">{t("feedback.votes.title")}</h2>
        <p className={styles.hint}>{t("feedback.votes.hint")}</p>

        {votes.total ? (
          /* Two named tiles, not three: the interface offers a thumb up and a
             thumb down and nothing between them, so a third "neutral" tile
             would always read zero and look like an opinion nobody holds. */
          <div className={styles.tiles}>
            <div className={styles.tile}>
              <span className={styles.tileLabel}>{t("feedback.up")}</span>
              <strong className={`${styles.tileValue} ${styles.tileValueGood}`}>{number.format(votes.up)}</strong>
            </div>
            <div className={styles.tile}>
              <span className={styles.tileLabel}>{t("feedback.down")}</span>
              <strong className={`${styles.tileValue} ${votes.down ? styles.tileValueWarn : ""}`}>
                {number.format(votes.down)}
              </strong>
            </div>
            <div className={styles.tile}>
              <span className={styles.tileLabel}>{t("feedback.total")}</span>
              <strong className={styles.tileValue}>{number.format(votes.total)}</strong>
            </div>
            <div className={styles.tile}>
              <span className={styles.tileLabel}>{t("feedback.upRate")}</span>
              <strong className={styles.tileValue}>{percent.format(votes.up_rate)}</strong>
            </div>
          </div>
        ) : (
          <p className={styles.empty}>{t("stats.noData")}</p>
        )}
      </section>

      <section className={styles.card} aria-labelledby="admin-feedback-shared">
        <h2 id="admin-feedback-shared">{t("feedback.shared.title")}</h2>
        <p className={styles.hint}>{t("feedback.shared.hint")}</p>

        {shared.length ? (
          <>
            <div className={`${styles.tableScroll} ${styles.tableScrollTall}`}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th scope="col" style={{ width: 180 }}>{t("feedback.shared.phrase")}</th>
                    <th scope="col" style={{ width: 180 }}>{t("feedback.shared.correction")}</th>
                    <th scope="col" style={{ width: 140 }}>{t("feedback.shared.scope")}</th>
                    <th scope="col" style={{ width: 220 }}>{t("feedback.shared.snippet")}</th>
                    <th scope="col" style={{ width: 140 }}>{t("feedback.shared.when")}</th>
                  </tr>
                </thead>
                <tbody>
                  {shared.map((row, index) => (
                    <SharedCorrectionRow
                      key={`${row.observed_at}-${index}`}
                      row={row}
                      onViewContext={() => setViewing(row)}
                    />
                  ))}
                </tbody>
              </table>
            </div>
            <p className={styles.hint}>
              {formatUiText(language, "feedback.shared.counted", {
                shown: shared.length,
                total: overview.shared_total,
              })}
            </p>
          </>
        ) : (
          <p className={styles.empty}>{t("feedback.shared.empty")}</p>
        )}

        {/* Said whether or not anything was shared. A screen that showed only
            what it is allowed to show would read as the whole picture; this is
            the line that says part of it is being left out on purpose. */}
        {overview.withheld_total > 0 && (
          <p className={styles.hint}>
            {formatUiText(language, "feedback.withheld", { count: overview.withheld_total })}
          </p>
        )}
      </section>

      {viewing && <ContextDialog row={viewing} onClose={() => setViewing(null)} />}
    </>
  );
}

type SharedCorrectionRowProps = {
  row: SharedCorrection;
  onViewContext: () => void;
};

/**
 * One shared correction, one line tall.
 *
 * The phrase carries only `target_language`: it is a correction to what the
 * machine rendered, so both `source_phrase` and `corrected_target` are already
 * in that one language, and naming a single language answers what a reader of
 * this row actually asks — which glossary this term belongs to. The full pair
 * is one thing more than that, and it lives in the context dialog instead of
 * sitting on every row whether or not anyone needed it.
 */
function SharedCorrectionRow({ row, onViewContext }: SharedCorrectionRowProps) {
  const t = useUiText();
  const language = useInterfaceLanguage();
  const when = new Intl.DateTimeFormat(language, { dateStyle: "medium", timeStyle: "short" });

  return (
    <tr>
      <th scope="row" className={styles.term} title={row.source_phrase}>
        {row.source_phrase}
        <span className={styles.pairNote}>{row.target_language}</span>
      </th>
      <td className={styles.term} title={row.corrected_target}>{row.corrected_target}</td>
      <td title={[row.domain, row.audience].filter(Boolean).join(" · ") || undefined}>
        {row.domain || <span className={styles.arrow}>{t("glossary.scopeAny")}</span>}
        {" · "}
        {row.audience || <span className={styles.arrow}>{t("glossary.scopeAny")}</span>}
      </td>
      <td>
        <div className={styles.snippetRow}>
          <span className={styles.snippet} title={row.anonymized_snippet}>{row.anonymized_snippet}</span>
          <button
            type="button"
            className={styles.iconAction}
            onClick={onViewContext}
            aria-label={t("feedback.shared.viewContext")}
            title={t("feedback.shared.viewContext")}
          >
            <Eye size={16} strokeWidth={1.8} aria-hidden="true" />
          </button>
        </div>
      </td>
      <td>{when.format(new Date(row.observed_at))}</td>
    </tr>
  );
}

type ContextDialogProps = {
  row: SharedCorrection;
  onClose: () => void;
};

/**
 * The one correction's full context: the language pair, and both anonymised
 * fragments it was seen in — the sender's own wording, and the window around
 * the corrected phrase in the machine's rendering.
 *
 * A dialog rather than an inline expansion, so a long fragment never grows
 * the row it came from — every row on the table behind it stays one line,
 * whether its context is three words or thirty.
 */
function ContextDialog({ row, onClose }: ContextDialogProps) {
  const t = useUiText();
  const language = useInterfaceLanguage();

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  return (
    <div
      className={styles.modalBackdrop}
      onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}
    >
      <section className={styles.contextModal} role="dialog" aria-modal="true" aria-labelledby="feedback-context-title">
        <header>
          <h2 id="feedback-context-title">{t("feedback.shared.contextTitle")}</h2>
          <button type="button" aria-label={t("common.close")} onClick={onClose}>
            <X size={18} aria-hidden="true" />
          </button>
        </header>
        <p className={styles.contextLabel}>{t("feedback.shared.languagePair")}</p>
        <p className={styles.contextPair}>
          {languageLabel(row.source_language)} → {languageLabel(row.target_language)}
        </p>

        {/* The sender's own wording, in whichever language they wrote it —
            the side of the translation `anonymized_snippet` alone never
            showed. Both fragments come anonymised from the server and exist
            because a term pair with no usage around it cannot be judged.
            Empty rather than missing for a correction recorded before this
            field existed (`original_snippet` shipped 24/08) — blank space
            here would read as a bug, not as "this row predates the column". */}
        <p className={styles.contextLabel}>
          {formatUiText(language, "feedback.shared.originalLabel", { language: languageLabel(row.source_language) })}
        </p>
        {row.original_snippet ? (
          <p className={styles.contextSnippet}>{row.original_snippet}</p>
        ) : (
          <p className={styles.contextSnippetEmpty}>{t("feedback.shared.originalUnavailable")}</p>
        )}

        <p className={styles.contextLabel}>
          {formatUiText(language, "feedback.shared.translatedLabel", { language: languageLabel(row.target_language) })}
        </p>
        <p className={styles.contextSnippet}>{row.anonymized_snippet}</p>
      </section>
    </div>
  );
}
