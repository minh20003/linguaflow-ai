import type { AuthSession } from "@/shared/types/auth";

const KEYS = ["access_token", "refresh_token", "user"] as const;
const cookieValue = (name: string): string | null => document.cookie.split("; ").find((item) => item.startsWith(`${name}=`))?.split("=").slice(1).join("=") ?? null;
const writeCookie = (name: string, value: string, persistent = true) => { document.cookie = `${name}=${encodeURIComponent(value)}; Path=/; SameSite=Lax${persistent ? "; Max-Age=2592000" : ""}`; };

export function saveSession(session: AuthSession, persistent: boolean): void {
  const destination = persistent ? window.localStorage : window.sessionStorage;
  const other = persistent ? window.sessionStorage : window.localStorage;

  for (const key of KEYS) other.removeItem(key);
  destination.setItem("access_token", session.access_token);
  destination.setItem("refresh_token", session.refresh_token);
  destination.setItem("user", JSON.stringify(session.user));
  writeCookie("access_token", session.access_token, persistent);
  writeCookie("refresh_token", session.refresh_token, persistent);
}

export function updateStoredUser(user: AuthSession["user"]): void {
  const storage = window.localStorage.getItem("access_token")
    ? window.localStorage
    : window.sessionStorage;
  storage.setItem("user", JSON.stringify(user));
}

export function getAccessToken(): string | null {
  return window.localStorage.getItem("access_token") ?? window.sessionStorage.getItem("access_token") ?? (cookieValue("access_token") ? decodeURIComponent(cookieValue("access_token")!) : null);
}

export function getRefreshToken(): string | null {
  return window.localStorage.getItem("refresh_token") ?? window.sessionStorage.getItem("refresh_token") ?? (cookieValue("refresh_token") ? decodeURIComponent(cookieValue("refresh_token")!) : null);
}

export function clearSession(): void {
  for (const storage of [window.localStorage, window.sessionStorage]) {
    for (const key of KEYS) storage.removeItem(key);
  }
  document.cookie = "access_token=; Path=/; Max-Age=0; SameSite=Lax";
  document.cookie = "refresh_token=; Path=/; Max-Age=0; SameSite=Lax";
}
