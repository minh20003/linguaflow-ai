import { refreshSession, type LoginResponse } from "./api";

const ACCESS_KEY = "access_token";
const REFRESH_KEY = "refresh_token";
const USER_KEY = "user";
const REMEMBER_KEY = "remember_session";

function stores(remember: boolean) {
  return remember ? localStorage : sessionStorage;
}

export function saveSession(session: LoginResponse, remember: boolean) {
  clearSession();
  const storage = stores(remember);
  storage.setItem(ACCESS_KEY, session.access_token);
  storage.setItem(REFRESH_KEY, session.refresh_token);
  storage.setItem(USER_KEY, JSON.stringify(session.user));
  localStorage.setItem(REMEMBER_KEY, remember ? "1" : "0");
}

export function clearSession() {
  for (const storage of [localStorage, sessionStorage]) {
    storage.removeItem(ACCESS_KEY);
    storage.removeItem(REFRESH_KEY);
    storage.removeItem(USER_KEY);
  }
  localStorage.removeItem(REMEMBER_KEY);
}

export function getStoredRefreshToken() {
  return localStorage.getItem(REFRESH_KEY) || sessionStorage.getItem(REFRESH_KEY);
}

export function getStoredUser() {
  const raw = localStorage.getItem(USER_KEY) || sessionStorage.getItem(USER_KEY);
  if (!raw) return null;
  try { return JSON.parse(raw) as LoginResponse["user"]; } catch { return null; }
}

export async function restoreSession(): Promise<LoginResponse | null> {
  const refreshToken = getStoredRefreshToken();
  if (!refreshToken) return null;
  const remember = localStorage.getItem(REMEMBER_KEY) === "1";
  try {
    const session = await refreshSession(refreshToken);
    saveSession(session, remember);
    return session;
  } catch {
    clearSession();
    return null;
  }
}
