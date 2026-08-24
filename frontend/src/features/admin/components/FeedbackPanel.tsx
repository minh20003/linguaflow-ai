"use client";

import { useEffect, useState } from "react";
import {
  fetchFeedbackOverview,
  type FeedbackOverview,
} from "@/shared/lib/feedback-api";
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

  const number = new Intl.NumberFormat(language);
  const percent = new Intl.NumberFormat(language, { style: "percent", maximumFractionDigits: 1 });
  const when = new Intl.DateTimeFormat(language, { dateStyle: "medium", timeStyle: "short" });

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
          <div className={styles.tiles}>
            {/* Up and down are the two the interface actually sends, and they
                are the pair a reader compares, so they carry colour. The rest
                are context for them. */}
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
              <span className={styles.tileLabel}>{t("feedback.neutral")}</span>
              <strong className={styles.tileValue}>{number.format(votes.neutral)}</strong>
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
            <div className={styles.tableScroll}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th scope="col">{t("feedback.shared.phrase")}</th>
                    <th scope="col">{t("feedback.shared.correction")}</th>
                    <th scope="col">{t("feedback.shared.scope")}</th>
                    <th scope="col">{t("feedback.shared.snippet")}</th>
                    <th scope="col">{t("feedback.shared.when")}</th>
                  </tr>
                </thead>
                <tbody>
                  {shared.map((row, index) => (
                    <tr key={`${row.observed_at}-${index}`}>
                      <th scope="row" className={styles.term}>
                        {row.source_phrase}
                        <span className={styles.pairNote}>{row.source_language} → {row.target_language}</span>
                      </th>
                      <td className={styles.term}>{row.corrected_target}</td>
                      <td>
                        {row.domain || <span className={styles.arrow}>{t("glossary.scopeAny")}</span>}
                        {" · "}
                        {row.audience || <span className={styles.arrow}>{t("glossary.scopeAny")}</span>}
                      </td>
                      {/* The one message-derived text on this screen. It comes
                          anonymised from the server and exists because a term
                          pair with no usage around it cannot be judged. */}
                      <td className={styles.snippet}>{row.anonymized_snippet}</td>
                      <td>{when.format(new Date(row.observed_at))}</td>
                    </tr>
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
    </>
  );
}
