"use client";

import { useCallback, useEffect, useMemo, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { MessagesSquare, Settings as SettingsIcon } from "lucide-react";
import { listLanguages, updateLanguage } from "@/shared/lib/api";
import {
  getStoredAccessToken,
  getStoredRefreshToken,
  getStoredUser,
  isRememberedSession,
  saveSession,
} from "@/shared/lib/auth-session";
import { languageLabel } from "@/shared/lib/constants";
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
  const me = useMemo(() => getStoredUser(), []);
  const [language, setLanguage] = useState(me?.preferred_language ?? "vi");
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
      setStatus(`Từ giờ bạn đọc tin nhắn bằng ${languageLabel(updated.preferred_language)}.`);
    } catch (caught) {
      setLanguage(previous);
      setError((caught as Error).message);
    } finally {
      setSaving(false);
    }
  }, [language]);

  const toggleActivity = useCallback((next: boolean) => {
    localStorage.setItem(ACTIVITY_KEY, next ? "1" : "0");
    activityListeners.forEach((notify) => notify());
  }, []);

  return (
    <main className={styles.shell}>
      <nav className={styles.navRail} aria-label="Điều hướng chính">
        <span className={styles.navRailLogo}><Logo size={30} title="LinguaFlow" /></span>
        <Link className={styles.navRailButton} href="/chat" aria-label="Tin nhắn" title="Tin nhắn">
          <MessagesSquare size={20} strokeWidth={1.8} aria-hidden="true" />
        </Link>
        <Link
          className={styles.navRailButton}
          href="/settings"
          aria-current="page"
          aria-label="Cài đặt"
          title="Cài đặt"
        >
          <SettingsIcon size={20} strokeWidth={1.8} aria-hidden="true" />
        </Link>
      </nav>

      <div className={styles.content}>
        <header className={styles.head}>
          <h1>Cài đặt</h1>
          <p>{me?.email ?? "Chưa đăng nhập"}</p>
        </header>

        <section className={styles.card} aria-labelledby="settings-language">
          <h2 id="settings-language">Ngôn ngữ đọc</h2>
          <p className={styles.hint}>
            Mọi tin nhắn người khác gửi sẽ được dịch sang ngôn ngữ này. Bạn vẫn
            xem được bản gốc trên từng tin.
          </p>
          <LanguagePicker
            id="reading-language"
            value={language}
            onChange={chooseLanguage}
            label="Ngôn ngữ bạn muốn đọc"
            codes={codes}
            disabled={saving}
          />
          <p className={styles.feedback} role="status">
            {saving ? "Đang lưu…" : status}
          </p>
          {error && <p className={styles.error} role="alert">{error}</p>}
        </section>

        <section className={styles.card} aria-labelledby="settings-activity">
          <h2 id="settings-activity">Trạng thái hoạt động</h2>
          <p className={styles.hint}>
            Hiện chấm báo đang trực tuyến cạnh tên người khác.
          </p>
          <label className={styles.switchRow}>
            <input
              type="checkbox"
              checked={showActivity}
              onChange={(event) => toggleActivity(event.target.checked)}
            />
            <span>Hiển thị trạng thái hoạt động</span>
          </label>
          <p className={styles.hint}>
            Tuỳ chọn này chỉ áp dụng cho trình duyệt này. Máy chủ chưa phát đi
            trạng thái trực tuyến, nên nó không đổi những gì người khác thấy về bạn.
          </p>
        </section>

        <section className={styles.card} aria-labelledby="settings-theme">
          <h2 id="settings-theme">Giao diện</h2>
          <p className={styles.hint}>Chọn nền sáng, nền tối, hoặc theo hệ thống.</p>
          <ThemeToggle />
        </section>
      </div>
    </main>
  );
}
