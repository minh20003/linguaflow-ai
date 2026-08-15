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
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY) || sessionStorage.getItem(REFRESH_KEY);
}

/**
 * The access token, from whichever store `saveSession` put it in.
 *
 * Both stores are read because the store depends on a choice made at sign-in:
 * "remember me" writes to `localStorage`, otherwise `sessionStorage`. A reader
 * that knows only one of them signs the other half of the users out.
 */
export function getStoredAccessToken() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_KEY) || sessionStorage.getItem(ACCESS_KEY);
}

/** Whether this session was asked to survive closing the browser. */
export function isRememberedSession() {
  if (typeof window === "undefined") return false;
  return localStorage.getItem(REMEMBER_KEY) === "1";
}

export function getStoredUser() {
  const raw = localStorage.getItem(USER_KEY) || sessionStorage.getItem(USER_KEY);
  if (!raw) return null;
  try { return JSON.parse(raw) as LoginResponse["user"]; } catch { return null; }
}

/**
 * The refresh request currently in flight, shared by every caller.
 *
 * Refresh tokens are single use and rotate on the server, so two concurrent
 * calls with the same token mean the second one is rejected — and the rejection
 * path clears the session the first call had just stored, signing the user
 * straight back out. React StrictMode mounts effects twice in development, so
 * this is not a rare race but the normal case for a guard that restores on
 * mount.
 */
let inFlight: Promise<LoginResponse | null> | null = null;

export async function restoreSession(): Promise<LoginResponse | null> {
  if (inFlight) return inFlight;

  const refreshToken = getStoredRefreshToken();
  if (!refreshToken) return null;
  const remember = isRememberedSession();

  inFlight = refreshSession(refreshToken)
    .then((session) => {
      saveSession(session, remember);
      return session;
    })
    .catch(() => {
      clearSession();
      return null;
    })
    .finally(() => {
      inFlight = null;
    });

  return inFlight;
}
