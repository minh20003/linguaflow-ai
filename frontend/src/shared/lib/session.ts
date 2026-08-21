import type { AuthSession } from "@/shared/types/auth";

const KEYS = ["access_token", "refresh_token", "user"] as const;

export function saveSession(session: AuthSession, persistent: boolean): void {
  const destination = persistent ? window.localStorage : window.sessionStorage;
  const other = persistent ? window.sessionStorage : window.localStorage;

  for (const key of KEYS) other.removeItem(key);
  destination.setItem("access_token", session.access_token);
  destination.setItem("refresh_token", session.refresh_token);
  destination.setItem("user", JSON.stringify(session.user));
}

export function updateStoredUser(user: AuthSession["user"]): void {
  const storage = window.localStorage.getItem("access_token")
    ? window.localStorage
    : window.sessionStorage;
  storage.setItem("user", JSON.stringify(user));
}

export function getAccessToken(): string | null {
  return window.localStorage.getItem("access_token") ?? window.sessionStorage.getItem("access_token");
}

export function getRefreshToken(): string | null {
  return window.localStorage.getItem("refresh_token") ?? window.sessionStorage.getItem("refresh_token");
}

export function clearSession(): void {
  for (const storage of [window.localStorage, window.sessionStorage]) {
    for (const key of KEYS) storage.removeItem(key);
  }
}
