"use client";

import { useEffect, useState } from "react";
import { fetchStats, type StatsResponse } from "@/shared/lib/stats-api";
import { useInterfaceLanguage, useUiText } from "@/shared/lib/use-ui-text";
import styles from "./AdminPage.module.css";

type LoadState = "loading" | "ready" | "error";

/**
 * What the agent actually did: attempts, fallbacks, tokens, latency.
 *
 * Lifted out of the admin page unchanged in behaviour when the glossary queue
 * arrived and the page grew tabs. It reads `/stats`, which is a different
 * endpoint from the glossary one, so each tab fetches on its own and a failure
 * in one leaves the other readable.
 */
export default function StatsPanel() {
  const t = useUiText();
  const language = useInterfaceLanguage();
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [state, setState] = useState<LoadState>("loading");

  const number = new Intl.NumberFormat(language);
  const percent = new Intl.NumberFormat(language, { style: "percent", maximumFractionDigits: 2 });

  useEffect(() => {
    let active = true;
    fetchStats()
      .then((response) => {
        if (!active) return;
        setStats(response);
        setState("ready");
      })
      .catch(() => active && setState("error"));
    return () => { active = false; };
  }, []);

  if (state === "loading") {
    return <section className={styles.card} aria-busy="true"><p className={styles.hint}>{t("stats.loading")}</p></section>;
  }
  if (state === "error" || !stats) {
    return <section className={styles.card}><p className={styles.error} role="alert">{t("stats.loadFailed")}</p></section>;
  }

  const pairs = Object.entries(stats.language_pairs);
  const models = Object.entries(stats.models_served);

  return (
    <>
      <section className={styles.card} aria-labelledby="admin-stats-summary">
        <h2 id="admin-stats-summary">{t("stats.title")}</h2>
        <div className={styles.tableScroll}>
          <table className={styles.table}>
            <tbody>
              <tr><th scope="row">{t("stats.totalAttempts")}</th><td>{number.format(stats.total_attempts)}</td></tr>
              <tr><th scope="row">{t("stats.fallbackRate")}</th><td>{percent.format(stats.fallback_rate)}</td></tr>
              <tr><th scope="row">{t("stats.inputTokens")}</th><td>{number.format(stats.input_tokens)}</td></tr>
              <tr><th scope="row">{t("stats.outputTokens")}</th><td>{number.format(stats.output_tokens)}</td></tr>
              <tr><th scope="row">{t("stats.totalLatencyP50")}</th><td>{number.format(stats.total_ms_p50)} {t("stats.milliseconds")}</td></tr>
              <tr><th scope="row">{t("stats.totalLatencyP95")}</th><td>{number.format(stats.total_ms_p95)} {t("stats.milliseconds")}</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className={styles.card} aria-labelledby="admin-stats-pairs">
        <h2 id="admin-stats-pairs">{t("stats.languagePairs")}</h2>
        {pairs.length ? (
          <div className={styles.tableScroll}>
            <table className={styles.table}>
              <tbody>
                {pairs.map(([pair, value]) => (
                  <tr key={pair}>
                    <th scope="row" className={styles.term}>{pair}</th>
                    <td>
                      {number.format(value.count)} · {t("stats.p50")} {number.format(value.p50_ms)} {t("stats.milliseconds")}
                      {" · "}{t("stats.p95")} {number.format(value.p95_ms)} {t("stats.milliseconds")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <p className={styles.hint}>{t("stats.noData")}</p>}
      </section>

      <section className={styles.card} aria-labelledby="admin-stats-models">
        <h2 id="admin-stats-models">{t("stats.modelsServed")}</h2>
        {models.length ? (
          <div className={styles.tableScroll}>
            <table className={styles.table}>
              <tbody>
                {models.map(([name, count]) => (
                  <tr key={name}><th scope="row" className={styles.term}>{name}</th><td>{number.format(count)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <p className={styles.hint}>{t("stats.noData")}</p>}
      </section>
    </>
  );
}
