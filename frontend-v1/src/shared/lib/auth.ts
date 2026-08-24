/** Request authorisation.
 *
 * Storage itself belongs to `auth-session.ts` — it is what decides between
 * `localStorage` and `sessionStorage` at sign-in, so a second module keeping its
 * own copy of the keys can only get that choice wrong. This one turns the stored
 * token into the header every authenticated call needs.
 */

import { getStoredAccessToken } from "./auth-session";

/** Return the stored JWT, or null when signed out or rendering on the server. */
export function getToken(): string | null {
  return getStoredAccessToken();
}

/** Headers carrying the bearer token, for authenticated requests. */
export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
