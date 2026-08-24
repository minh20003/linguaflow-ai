"use client";

import { useEffect, useState } from "react";
import { fetchStats, type StatsResponse } from "@/shared/lib/stats-api";
import { useInterfaceLanguage, useUiText } from "@/shared/lib/use-ui-text";
import styles from "./AdminPage.module.css";

type LoadState = "loading" | "ready" | "error";

/**
 * What the agent actually did: attempts, fallbacks, tokens, latency, cost.
 *
 * It reads `/stats`, which is a different endpoint from the glossary one, so
 * each tab fetches on its own and a failure in one leaves the other readable.
 *
 * The headline figures are tiles rather than a two-column table of row
 * headings and values. Numbers of several different kinds — a count, a
 * proportion, three durations, two token totals, a cost — read as one
 * undifferentiated list when they are stacked in a table, and the ones that
 * matter on a bad day (the fallback rate, the slow tail) were the hardest to
 * find. A tile gives each one a size of its own and puts the unit next to the
 * figure instead of inside it.
 */
export default function StatsPanel() {
  const t = useUiText();
  const language = useInterfaceLanguage();
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [state, setState] = useState<LoadState>("loading");

  const number = new Intl.NumberFormat(language);
  const percent = new Intl.NumberFormat(language, { style: "percent", maximumFractionDigits: 2 });
  // Tokens run to six figures and the exact count is never the question, so
  // the tile carries a shortened form and the full number stays in `title`.
  const compact = new Intl.NumberFormat(language, { notation: "compact", maximumFractionDigits: 1 });
  // Costs on a project this size run to fractions of a cent; two decimals
  // would round every one of them to "$0.00" and say nothing.
  const usd = new Intl.NumberFormat(language, {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  });
  const usdRate = new Intl.NumberFormat(language, {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

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
  const models = Object.entries(stats.model_usage);

  return (
    <>
      <section className={styles.card} aria-labelledby="admin-stats-summary">
        <h2 id="admin-stats-summary">{t("stats.title")}</h2>
        <p className={styles.hint}>{t("stats.summaryHint")}</p>

        <div className={styles.tiles}>
          <div className={styles.tile}>
            <span className={styles.tileLabel}>{t("stats.totalAttempts")}</span>
            <strong className={styles.tileValue}>{number.format(stats.total_attempts)}</strong>
          </div>
          {/* The one figure that is bad when it is high, so it says so in
              colour as well as in the number — but only once there is anything
              to fall back from, since 0 of 0 is not a warning. */}
          <div className={styles.tile}>
            <span className={styles.tileLabel}>{t("stats.fallbackRate")}</span>
            <strong className={`${styles.tileValue} ${stats.fallback_rate > 0 ? styles.tileValueWarn : ""}`}>
              {percent.format(stats.fallback_rate)}
            </strong>
          </div>
          {/* Mean, median (P50) and P95 side by side: the mean is what
              "average" usually means and is what a few slow outliers can drag
              upward; P50 is the middle attempt once every duration is sorted,
              not the mean of the fast half. `stats.summaryHint` above spells
              out the difference in full. */}
          <div className={styles.tile}>
            <span className={styles.tileLabel}>{t("stats.averageLatency")}</span>
            <strong className={styles.tileValue}>
              {number.format(stats.total_ms_mean)}
              <span className={styles.tileUnit}>{t("stats.milliseconds")}</span>
            </strong>
          </div>
          <div className={styles.tile}>
            <span className={styles.tileLabel}>{t("stats.totalLatencyP50")}</span>
            <strong className={styles.tileValue}>
              {number.format(stats.total_ms_p50)}
              <span className={styles.tileUnit}>{t("stats.milliseconds")}</span>
            </strong>
          </div>
          <div className={styles.tile}>
            <span className={styles.tileLabel}>{t("stats.totalLatencyP95")}</span>
            <strong className={styles.tileValue}>
              {number.format(stats.total_ms_p95)}
              <span className={styles.tileUnit}>{t("stats.milliseconds")}</span>
            </strong>
          </div>
          <div className={styles.tile}>
            <span className={styles.tileLabel}>{t("stats.inputTokens")}</span>
            <strong className={styles.tileValue} title={number.format(stats.input_tokens)}>
              {compact.format(stats.input_tokens)}
            </strong>
          </div>
          <div className={styles.tile}>
            <span className={styles.tileLabel}>{t("stats.outputTokens")}</span>
            <strong className={styles.tileValue} title={number.format(stats.output_tokens)}>
              {compact.format(stats.output_tokens)}
            </strong>
          </div>
          <div className={styles.tile}>
            <span className={styles.tileLabel}>{t("stats.totalCost")}</span>
            <strong className={styles.tileValue}>
              {stats.cost_usd_partial && "≥ "}
              {usd.format(stats.total_cost_usd)}
            </strong>
          </div>
        </div>
        {stats.cost_usd_partial && <p className={styles.hint}>{t("stats.costPartialNote")}</p>}
      </section>

      <section className={styles.card} aria-labelledby="admin-stats-pairs">
        <h2 id="admin-stats-pairs">{t("stats.languagePairs")}</h2>
        {pairs.length ? (
          <div className={styles.tableScroll}>
            {/* One column per number instead of one sentence per row: the
                question a reader brings here is which pair is the slow one,
                and that can only be seen when the figures line up. */}
            <table className={styles.table}>
              <thead>
                <tr>
                  <th scope="col" style={{ width: 200 }}>{t("stats.pair")}</th>
                  <th scope="col" className={styles.numericHead} style={{ width: 120 }}>{t("stats.count")}</th>
                  <th scope="col" className={styles.numericHead} style={{ width: 120 }}>{t("stats.p50")}</th>
                  <th scope="col" className={styles.numericHead} style={{ width: 120 }}>{t("stats.p95")}</th>
                </tr>
              </thead>
              <tbody>
                {pairs.map(([pair, value]) => (
                  <tr key={pair}>
                    <th scope="row" className={styles.term} title={pair}>{pair}</th>
                    <td className={styles.numeric}>{number.format(value.count)}</td>
                    <td className={styles.numeric}>
                      {number.format(value.p50_ms)} <span className={styles.unit}>{t("stats.milliseconds")}</span>
                    </td>
                    <td className={styles.numeric}>
                      {number.format(value.p95_ms)} <span className={styles.unit}>{t("stats.milliseconds")}</span>
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
              <thead>
                <tr>
                  <th scope="col" style={{ width: 190 }}>{t("stats.model")}</th>
                  <th scope="col" className={styles.numericHead} style={{ width: 90 }}>{t("stats.count")}</th>
                  <th scope="col" className={styles.numericHead} style={{ width: 110 }}>{t("stats.inputTokens")}</th>
                  <th scope="col" className={styles.numericHead} style={{ width: 110 }}>{t("stats.outputTokens")}</th>
                  <th scope="col" className={styles.numericHead} style={{ width: 150 }}>{t("stats.unitPrice")}</th>
                  <th scope="col" className={styles.numericHead} style={{ width: 100 }}>{t("stats.cost")}</th>
                </tr>
              </thead>
              <tbody>
                {models.map(([name, usage]) => (
                  <tr key={name}>
                    <th scope="row" className={styles.term} title={name}>{name}</th>
                    <td className={styles.numeric}>{number.format(usage.count)}</td>
                    <td className={styles.numeric} title={number.format(usage.input_tokens)}>
                      {compact.format(usage.input_tokens)}
                    </td>
                    <td className={styles.numeric} title={number.format(usage.output_tokens)}>
                      {compact.format(usage.output_tokens)}
                    </td>
                    <td className={styles.numeric}>
                      {usage.input_price_per_million_usd !== null && usage.output_price_per_million_usd !== null ? (
                        <span title={t("stats.unitPrice")}>
                          {usdRate.format(usage.input_price_per_million_usd)}
                          {" · "}
                          {usdRate.format(usage.output_price_per_million_usd)}
                        </span>
                      ) : (
                        <span className={styles.arrow} title={t("stats.costUnknown")}>—</span>
                      )}
                    </td>
                    <td className={styles.numeric}>
                      {usage.cost_usd !== null ? (
                        usd.format(usage.cost_usd)
                      ) : (
                        <span className={styles.arrow} title={t("stats.costUnknown")}>—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <p className={styles.hint}>{t("stats.noData")}</p>}
      </section>
    </>
  );
}
