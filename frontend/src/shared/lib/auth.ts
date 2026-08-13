/** Session storage and request authorisation.
 *
 * The token and the cached profile were previously written by two form
 * components and read by nobody. Everything that needs either goes through
 * here, so there is one place that knows the storage keys.
 */

const TOKEN_KEY = "access_token";
const USER_KEY = "user";

export interface AuthUser {
  id: string;
  username: string;
  email: string;
  display_name: string;
  preferred_language: string;
}

/** Return the stored JWT, or null when signed out or rendering on the server. */
export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

/** Return the cached profile, or null if absent or unreadable. */
export function getUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

/** Persist a session after login or registration. */
export function setSession(token: string, user: AuthUser): void {
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
}

/** Update only the cached profile, leaving the token in place. */
export function updateCachedUser(user: AuthUser): void {
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
}

/** Clear the session. */
export function clearSession(): void {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
}

/** Headers carrying the bearer token, for authenticated requests. */
export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
