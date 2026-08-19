"use client";

import { useCallback, useEffect, useMemo, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { MessagesSquare, Settings as SettingsIcon } from "lucide-react";
import { listLanguages, updateInterfaceLanguage, updateLanguage } from "@/shared/lib/api";
import {
  getStoredAccessToken,
  getStoredRefreshToken,
  getStoredUser,
  isRememberedSession,
  saveSession,
} from "@/shared/lib/auth-session";
import { languageLabel } from "@/shared/lib/constants";
import {
  readInterfaceLanguage,
  setInterfaceLanguage,
  subscribeToInterfaceLanguage,
} from "@/shared/lib/ui-language";
import { formatUiText, uiText } from "@/shared/lib/ui-text";
import { useDocumentMetadata, useUiText } from "@/shared/lib/use-ui-text";
import LanguagePicker from "@/shared/ui/LanguagePicker";
import Logo from "@/shared/ui/Logo";
import ThemeToggle from "@/shared/ui/ThemeToggle";
import styles from "./SettingsPage.module.css";

const ACTIVITY_KEY = "lingua_show_activity";

/* The preference lives in localStorage, which is state React does not own, so
   it is read through useSyncExternalStore rather than copied into state by an
   effect. The server snapshot is the default, matching what the markup shows
   before hydration. */
const activityListeners = new Set<() => void>();

function readShowActivity(): boolean {
  return localStorage.getItem(ACTIVITY_KEY) !== "0";
}

function subscribeToActivity(onStoreChange: () => void): () => void {
  activityListeners.add(onStoreChange);
  window.addEventListener("storage", onStoreChange);
  return () => {
    activityListeners.delete(onStoreChange);
    window.removeEventListener("storage", onStoreChange);
  };
}


/**
 * Account settings.
 *
 * A page with its own URL rather than a panel inside the chat: the reading
 * language decides what every message looks like, so it needs somewhere it can
 * be linked to and returned to, and F-06's privacy controls will land here too.
 */
export default function SettingsPage() {
  useDocumentMetadata("meta.title.settings", "meta.desc.settings");
  const me = useMemo(() => getStoredUser(), []);
  const [language, setLanguage] = useState(me?.preferred_language ?? "en");
  // Read through the store rather than copied into state: `saveSession` also
  // writes it, so a login in another tab has to move this screen too.
  const uiLang = useSyncExternalStore(
    subscribeToInterfaceLanguage,
    readInterfaceLanguage,
    () => "en" as const,
  );
  const t = useUiText();
  const [savingInterface, setSavingInterface] = useState(false);
  const [codes, setCodes] = useState<string[]>([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const showActivity = useSyncExternalStore(subscribeToActivity, readShowActivity, () => true);

  // The allowlist belongs to the backend (CONTRACT section 1). Failing to load
  // it is not fatal — the selector falls back to its built-in list.
  useEffect(() => {
    let cancelled = false;
    listLanguages()
      .then((list) => !cancelled && setCodes(list))
      .catch(() => undefined);
    return () => { cancelled = true; };
  }, []);

  const chooseLanguage = useCallback(async (code: string) => {
    const previous = language;
    setLanguage(code);
    setError("");
    setStatus("");
    setSaving(true);
    try {
      const accessToken = getStoredAccessToken() ?? "";
      const updated = await updateLanguage(code, accessToken);
      // Keep the cached profile in step, or the chat screen keeps picking
      // translations for the language the user just moved away from.
      saveSession(
        {
          access_token: accessToken,
          refresh_token: getStoredRefreshToken() ?? "",
          token_type: "bearer",
          user: updated,
        },
        isRememberedSession(),
      );
      setStatus(
        formatUiText(uiLang, "settings.reading.updated", {
          language: languageLabel(updated.preferred_language),
        }),
      );
    } catch {
      setLanguage(previous);
      setError(uiText(uiLang, "settings.error.saveReading"));
    } finally {
      setSaving(false);
    }
  }, [language, uiLang]);

  /**
   * Change the language of the app itself.
   *
   * Optimistic on purpose: the store is written first so the screen repaints
   * under the pointer, and rolled back if the server refuses. Waiting for the
   * round trip would make the one setting that costs nothing feel slower than
   * the one that spends LLM quota.
   */
  const chooseInterfaceLanguage = useCallback(async (code: string) => {
    const previous = readInterfaceLanguage();
    setInterfaceLanguage(code);
    setError("");
    setSavingInterface(true);
    try {
      const accessToken = getStoredAccessToken() ?? "";
      const updated = await updateInterfaceLanguage(code, accessToken);
      saveSession(
        {
          access_token: accessToken,
          refresh_token: getStoredRefreshToken() ?? "",
          token_type: "bearer",
          user: updated,
        },
        isRememberedSession(),
      );
    } catch {
      setInterfaceLanguage(previous);
      setError(uiText(uiLang, "settings.error.saveInterface"));
    } finally {
      setSavingInterface(false);
    }
  }, [uiLang]);

  const toggleActivity = useCallback((next: boolean) => {
    localStorage.setItem(ACTIVITY_KEY, next ? "1" : "0");
    activityListeners.forEach((notify) => notify());
  }, []);

  return (
    <main className={styles.shell}>
      <nav className={styles.navRail} aria-label={t("nav.main")}>
        <span className={styles.navRailLogo}><Logo size={30} title="LinguaFlow" /></span>
        <Link className={styles.navRailButton} href="/chat" aria-label={t("nav.messages")} title={t("nav.messages")}>
          <MessagesSquare size={20} strokeWidth={1.8} aria-hidden="true" />
        </Link>
        <Link
          className={styles.navRailButton}
          href="/settings"
          aria-current="page"
          aria-label={t("nav.settings")}
          title={t("nav.settings")}
        >
          <SettingsIcon size={20} strokeWidth={1.8} aria-hidden="true" />
        </Link>
      </nav>

      <div className={styles.content}>
        <header className={styles.head}>
          <h1>{t("settings.title")}</h1>
          <p>{me?.email ?? t("settings.signedOut")}</p>
        </header>

        {/* The interface language comes first: someone who cannot read this
            screen needs that control before any other one on it. */}
        <section className={styles.card} aria-labelledby="settings-interface">
          <h2 id="settings-interface">{t("settings.interface.title")}</h2>
          <p className={styles.hint}>{t("settings.interface.hint")}</p>
          <LanguagePicker
            id="interface-language"
            value={uiLang}
            onChange={chooseInterfaceLanguage}
            label={t("settings.interface.label")}
            codes={codes}
            disabled={savingInterface}
          />
        </section>

        <section className={styles.card} aria-labelledby="settings-language">
          <h2 id="settings-language">{t("settings.reading.title")}</h2>
          <p className={styles.hint}>{t("settings.reading.hint")}</p>
          <LanguagePicker
            id="reading-language"
            value={language}
            onChange={chooseLanguage}
            label={t("settings.reading.label")}
            codes={codes}
            disabled={saving}
          />
          <p className={styles.feedback} role="status">
            {saving ? t("settings.saving") : status}
          </p>
          {error && <p className={styles.error} role="alert">{error}</p>}
        </section>

        <section className={styles.card} aria-labelledby="settings-activity">
          <h2 id="settings-activity">{t("settings.activity.title")}</h2>
          <p className={styles.hint}>{t("settings.activity.hint")}</p>
          <label className={styles.switchRow}>
            <input
              type="checkbox"
              checked={showActivity}
              onChange={(event) => toggleActivity(event.target.checked)}
            />
            <span>{t("settings.activity.toggle")}</span>
          </label>
          <p className={styles.hint}>{t("settings.activity.note")}</p>
        </section>

        <section className={styles.card} aria-labelledby="settings-theme">
          <h2 id="settings-theme">{t("settings.theme.title")}</h2>
          <p className={styles.hint}>{t("settings.theme.hint")}</p>
          <ThemeToggle />
        </section>
      </div>
    </main>
  );
}
