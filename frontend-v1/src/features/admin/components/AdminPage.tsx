"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { BarChart3, MessagesSquare, Settings as SettingsIcon } from "lucide-react";
import { getStoredUser } from "@/shared/lib/auth-session";
import { useDocumentMetadata, useUiText } from "@/shared/lib/use-ui-text";
import Logo from "@/shared/ui/Logo";
import FeedbackPanel from "./FeedbackPanel";
import GlossaryPanel from "./GlossaryPanel";
import StatsPanel from "./StatsPanel";
import styles from "./AdminPage.module.css";

type Tab = "stats" | "glossary" | "feedback";

/**
 * The administrator screen: what the agent did, what readers said about it, and
 * the terms it is bound by.
 *
 * Tabs rather than routes. They are read by the same person in the same sitting
 * — a term is approved because of what the numbers say about it — and a route
 * change would drop the fetched state of whichever one is left behind.
 *
 * `users.role === "admin"` is the entire permission model; there is no
 * middleware behind it. This screen therefore checks twice: once here so a
 * non-administrator is told rather than shown an empty page, and once per
 * request, where the server's 403 is the check that actually matters. The one
 * here is courtesy, not security.
 */
export default function AdminPage() {
  useDocumentMetadata("meta.title.admin", "meta.desc.admin");
  const t = useUiText();
  const me = useMemo(() => getStoredUser(), []);
  const [tab, setTab] = useState<Tab>("stats");

  if (me?.role !== "admin") {
    return (
      <main className={styles.shell}>
        <div className={styles.content}>
          <header className={styles.head}><h1>{t("admin.title")}</h1></header>
          <p className={styles.error} role="alert">{t("stats.adminRequired")}</p>
        </div>
      </main>
    );
  }

  return (
    <main className={styles.shell}>
      <nav className={styles.navRail} aria-label={t("nav.main")}>
        <span className={styles.navRailLogo}><Logo size={30} title="LinguaFlow" /></span>
        <Link className={styles.navRailButton} href="/chat" aria-label={t("nav.messages")} title={t("nav.messages")}>
          <MessagesSquare size={20} strokeWidth={1.8} aria-hidden="true" />
        </Link>
        <Link className={styles.navRailButton} href="/settings" aria-label={t("nav.settings")} title={t("nav.settings")}>
          <SettingsIcon size={20} strokeWidth={1.8} aria-hidden="true" />
        </Link>
        <Link
          className={styles.navRailButton}
          href="/admin"
          aria-current="page"
          aria-label={t("nav.admin")}
          title={t("nav.admin")}
        >
          <BarChart3 size={20} strokeWidth={1.8} aria-hidden="true" />
        </Link>
      </nav>

      <div className={styles.content}>
        <header className={styles.head}>
          <h1>{t("admin.title")}</h1>
          <p>{t("admin.subtitle")}</p>
        </header>

        <div className={styles.tabs} role="tablist" aria-label={t("admin.title")}>
          <button
            type="button"
            role="tab"
            id="admin-tab-stats"
            className={styles.tab}
            aria-selected={tab === "stats"}
            aria-controls="admin-panel-stats"
            onClick={() => setTab("stats")}
          >
            {t("admin.tab.stats")}
          </button>
          <button
            type="button"
            role="tab"
            id="admin-tab-glossary"
            className={styles.tab}
            aria-selected={tab === "glossary"}
            aria-controls="admin-panel-glossary"
            onClick={() => setTab("glossary")}
          >
            {t("admin.tab.glossary")}
          </button>
          <button
            type="button"
            role="tab"
            id="admin-tab-feedback"
            className={styles.tab}
            aria-selected={tab === "feedback"}
            aria-controls="admin-panel-feedback"
            onClick={() => setTab("feedback")}
          >
            {t("admin.tab.feedback")}
          </button>
        </div>

        {/* Only the selected panel is mounted. Each tab fetches on mount, and
            keeping them all alive would mean three loads on arrival for two
            that are not being looked at. */}
        {tab === "stats" && (
          <div role="tabpanel" id="admin-panel-stats" aria-labelledby="admin-tab-stats">
            <StatsPanel />
          </div>
        )}
        {tab === "glossary" && (
          <div role="tabpanel" id="admin-panel-glossary" aria-labelledby="admin-tab-glossary">
            <GlossaryPanel />
          </div>
        )}
        {tab === "feedback" && (
          <div role="tabpanel" id="admin-panel-feedback" aria-labelledby="admin-tab-feedback">
            <FeedbackPanel />
          </div>
        )}
      </div>
    </main>
  );
}
