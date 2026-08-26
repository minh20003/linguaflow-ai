"use client";

import { useEffect, useState } from "react";
import RequireAuth from "@/features/auth/components/RequireAuth";
import { getStoredUser } from "@/shared/lib/auth-session";
import { fetchStats, type StatsResponse } from "@/shared/lib/stats-api";
import { useInterfaceLanguage, useUiText } from "@/shared/lib/use-ui-text";

type LoadState = "loading" | "ready" | "error";

function Entries({ entries }: { entries: Record<string, number> }) {
  const t = useUiText();
  const items = Object.entries(entries);
  if (!items.length) return <p>{t("stats.noData")}</p>;
  return (
    <ul>
      {items.map(([name, count]) => <li key={name}>{name}: {count}</li>)}
    </ul>
  );
}

function AdminStats() {
  const t = useUiText();
  const language = useInterfaceLanguage();
  const [user] = useState(() => getStoredUser());
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState("");
  const isAdmin = user?.role === "admin";
  const number = new Intl.NumberFormat(language);

  useEffect(() => {
    if (!isAdmin) return;
    let active = true;
    fetchStats()
      .then((response) => {
        if (!active) return;
        setStats(response);
        setState("ready");
      })
      .catch((caught: Error) => {
        if (!active) return;
        setError(caught.message);
        setState("error");
      });
    return () => { active = false; };
  }, [isAdmin]);

  if (!isAdmin || error === "admin_required") {
    return <main style={{ maxWidth: 960, margin: "0 auto", padding: 32 }}><h1>{t("stats.title")}</h1><p role="alert">{t("stats.adminRequired")}</p></main>;
  }
  if (state === "loading") {
    return <main aria-busy="true" style={{ maxWidth: 960, margin: "0 auto", padding: 32 }}><h1>{t("stats.title")}</h1><p>{t("stats.loading")}</p></main>;
  }
  if (state === "error" || !stats) {
    return <main style={{ maxWidth: 960, margin: "0 auto", padding: 32 }}><h1>{t("stats.title")}</h1><p role="alert">{t("stats.loadFailed")}</p></main>;
  }

  const pairs = Object.entries(stats.language_pairs);
  return (
    <main style={{ maxWidth: 960, margin: "0 auto", padding: 32 }}>
      <h1>{t("stats.title")}</h1>
      <table>
        <tbody>
          <tr><th scope="row">{t("stats.totalAttempts")}</th><td>{number.format(stats.total_attempts)}</td></tr>
          <tr><th scope="row">{t("stats.fallbackRate")}</th><td>{new Intl.NumberFormat(language, { style: "percent", maximumFractionDigits: 2 }).format(stats.fallback_rate)}</td></tr>
          <tr><th scope="row">{t("stats.inputTokens")}</th><td>{number.format(stats.input_tokens)}</td></tr>
          <tr><th scope="row">{t("stats.outputTokens")}</th><td>{number.format(stats.output_tokens)}</td></tr>
          <tr><th scope="row">{t("stats.totalLatencyP50")}</th><td>{number.format(stats.total_ms_p50)} {t("stats.milliseconds")}</td></tr>
          <tr><th scope="row">{t("stats.totalLatencyP95")}</th><td>{number.format(stats.total_ms_p95)} {t("stats.milliseconds")}</td></tr>
        </tbody>
      </table>

      <h2>{t("stats.languagePairs")}</h2>
      {pairs.length ? (
        <table>
          <tbody>
            {pairs.map(([pair, value]) => <tr key={pair}><th scope="row">{pair}</th><td>{number.format(value.count)} · {t("stats.p50")} {number.format(value.p50_ms)} {t("stats.milliseconds")} · {t("stats.p95")} {number.format(value.p95_ms)} {t("stats.milliseconds")}</td></tr>)}
          </tbody>
        </table>
      ) : <p>{t("stats.noData")}</p>}

      <h2>{t("stats.modelsServed")}</h2>
      <Entries entries={stats.models_served} />
    </main>
  );
}

export default function AdminPage() {
  return <RequireAuth><AdminStats /></RequireAuth>;
}
