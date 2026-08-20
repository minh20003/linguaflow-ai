"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { MessagesSquare, Settings as SettingsIcon } from "lucide-react";
import {
  linkGoogle,
  listLanguages,
  unlinkGoogle,
  updateInterfaceLanguage,
  updateLanguage,
  type AuthUser,
} from "@/shared/lib/api";
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
import { getGisLocale, loadGis } from "@/shared/lib/google-gis";
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
  const [user, setUser] = useState<AuthUser | null>(() => getStoredUser());
  const [language, setLanguage] = useState(user?.preferred_language ?? "en");
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

  const [googleLoading, setGoogleLoading] = useState(false);
  const [googleError, setGoogleError] = useState("");
  const [googleSuccess, setGoogleSuccess] = useState("");
  const googleLinkButtonRef = useRef<HTMLDivElement>(null);

  // The allowlist belongs to the backend (CONTRACT section 1). Failing to load
  // it is not fatal — the selector falls back to its built-in list.
  useEffect(() => {
    let cancelled = false;
    listLanguages()
      .then((list) => !cancelled && setCodes(list))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  const chooseLanguage = useCallback(
    async (code: string) => {
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
        setUser(updated);
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
    },
    [language, uiLang],
  );

  /**
   * Change the language of the app itself.
   *
   * Optimistic on purpose: the store is written first so the screen repaints
   * under the pointer, and rolled back if the server refuses. Waiting for the
   * round trip would make the one setting that costs nothing feel slower than
   * the one that spends LLM quota.
   */
  const chooseInterfaceLanguage = useCallback(
    async (code: string) => {
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
        setUser(updated);
      } catch {
        setInterfaceLanguage(previous);
        setError(uiText(uiLang, "settings.error.saveInterface"));
      } finally {
        setSavingInterface(false);
      }
    },
    [uiLang],
  );

  const toggleActivity = useCallback((next: boolean) => {
    localStorage.setItem(ACTIVITY_KEY, next ? "1" : "0");
    activityListeners.forEach((notify) => notify());
  }, []);

  // Initialize and render the GIS button for linking when the user is unlinked
  useEffect(() => {
    const clientId = process.env.NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID;
    if (!clientId || user?.google_linked) return;

    let cancelled = false;
    const container = googleLinkButtonRef.current;

    loadGis()
      .then(() => {
        if (cancelled || !window.google?.accounts?.id || !container) return;

        // Clear container before rendering to prevent duplicate buttons
        container.innerHTML = "";

        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: async (response: { credential?: string; error?: string }) => {
            if (cancelled || !response.credential) return;

            setGoogleError("");
            setGoogleSuccess("");
            setGoogleLoading(true);
            try {
              const accessToken = getStoredAccessToken() ?? "";
              const result = await linkGoogle(response.credential, accessToken);
              const baseUser = user ?? getStoredUser();
              if (baseUser) {
                const updatedUser: AuthUser = {
                  ...baseUser,
                  google_linked: result.google_linked,
                };
                saveSession(
                  {
                    access_token: accessToken,
                    refresh_token: getStoredRefreshToken() ?? "",
                    token_type: "bearer",
                    user: updatedUser,
                  },
                  isRememberedSession(),
                );
                setUser(updatedUser);
              }
              setGoogleSuccess(uiText(uiLang, "settings.google.linked"));
            } catch (err) {
              const code = (err as Error)?.message;
              if (code === "google_already_linked") {
                setGoogleError(uiText(uiLang, "settings.google.alreadyLinked"));
              } else {
                setGoogleError(uiText(uiLang, "settings.google.linkError"));
              }
            } finally {
              setGoogleLoading(false);
            }
          },
          auto_select: false,
        });

        window.google.accounts.id.renderButton(container, {
          type: "standard",
          theme: "outline",
          size: "large",
          text: "signin_with",
          shape: "rectangular",
          width: container.offsetWidth || 280,
          locale: getGisLocale(uiLang),
        });
      })
      .catch(() => {
        if (!cancelled) {
          setGoogleError(uiText(uiLang, "settings.google.linkError"));
        }
      });

    return () => {
      cancelled = true;
      if (container) {
        container.innerHTML = "";
      }
    };
  }, [user, uiLang]);

  const handleUnlinkGoogle = useCallback(async () => {
    setGoogleError("");
    setGoogleSuccess("");
    setGoogleLoading(true);
    try {
      const accessToken = getStoredAccessToken() ?? "";
      const result = await unlinkGoogle(accessToken);
      const baseUser = user ?? getStoredUser();
      if (baseUser) {
        const updatedUser: AuthUser = {
          ...baseUser,
          google_linked: result.google_linked,
        };
        saveSession(
          {
            access_token: accessToken,
            refresh_token: getStoredRefreshToken() ?? "",
            token_type: "bearer",
            user: updatedUser,
          },
          isRememberedSession(),
        );
        setUser(updatedUser);
      }
      setGoogleSuccess(uiText(uiLang, "settings.google.unlinked"));
    } catch (err) {
      const code = (err as Error)?.message;
      if (code === "google_cannot_unlink_no_password") {
        setGoogleError(uiText(uiLang, "settings.google.cannotUnlinkNoPassword"));
      } else {
        setGoogleError(uiText(uiLang, "settings.google.unlinkError"));
      }
    } finally {
      setGoogleLoading(false);
    }
  }, [user, uiLang]);

  return (
    <main className={styles.shell}>
      <nav className={styles.navRail} aria-label={t("nav.main")}>
        <span className={styles.navRailLogo}>
          <Logo size={30} title="LinguaFlow" />
        </span>
        <Link
          className={styles.navRailButton}
          href="/chat"
          aria-label={t("nav.messages")}
          title={t("nav.messages")}
        >
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
          <p>{user?.email ?? t("settings.signedOut")}</p>
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
          {error && (
            <p className={styles.error} role="alert">
              {error}
            </p>
          )}
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

        {user?.google_linked !== undefined && (
          <section className={styles.card} aria-labelledby="settings-google">
            <h2 id="settings-google">{t("settings.google.title")}</h2>
            <p className={styles.hint}>{t("settings.google.hint")}</p>
            {user.google_linked ? (
              <>
                <p className={styles.success}>{t("settings.google.linked")}</p>
                {user.has_password === false && (
                  <p className={styles.hint}>{t("settings.google.cannotUnlinkNoPassword")}</p>
                )}
                <button
                  type="button"
                  className={styles.googleButton}
                  onClick={handleUnlinkGoogle}
                  disabled={googleLoading || user.has_password === false}
                  title={user.has_password === false ? t("settings.google.cannotUnlinkNoPassword") : undefined}
                >
                  {googleLoading ? t("settings.google.unlinking") : t("settings.google.unlink")}
                </button>
              </>
            ) : (
              <div
                ref={googleLinkButtonRef}
                className={styles.googleButton}
                aria-label={t("settings.google.link")}
              />
            )}
            {googleError && (
              <p className={styles.error} role="alert">
                {googleError}
              </p>
            )}
            {googleSuccess && (
              <p className={styles.success} role="status">
                {googleSuccess}
              </p>
            )}
          </section>
        )}
      </div>
    </main>
  );
}
