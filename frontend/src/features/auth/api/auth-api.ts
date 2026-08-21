import { API_BASE } from "@/config/env";
import {
  getApiErrorMessage,
  parseJson,
  type ApiErrorBody,
} from "@/shared/api/response";
import type { AuthSession, AuthUser } from "@/shared/types/auth";

export type { AuthSession, AuthUser } from "@/shared/types/auth";
export {
  signOut,
  updateInterfaceLanguage,
  updatePreferredLanguage,
} from "@/shared/api/account-api";

interface RegisterInput {
  fullName: string;
  email: string;
  password: string;
  preferredLanguage?: string;
}

async function request<T>(path: string, init: RequestInit, fallback: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init.headers },
  });
  const body = await parseJson<T & ApiErrorBody>(response);
  if (!response.ok || !body) {
    throw new Error(getApiErrorMessage(body, fallback));
  }
  return body;
}

function isAuthUser(value: unknown): value is AuthUser {
  return Boolean(
    value
      && typeof value === "object"
      && typeof (value as Partial<AuthUser>).id === "string"
      && typeof (value as Partial<AuthUser>).email === "string",
  );
}

/**
 * Accept both the current session response and the older token-only response.
 * A token-only response is completed from `/auth/me` before any screen reads
 * profile fields, preventing an opaque browser `undefined.display_name` error.
 */
async function requestAuthSession(path: string, init: RequestInit, fallback: string): Promise<AuthSession> {
  const session = await request<Partial<AuthSession>>(path, init, fallback);
  if (!session.access_token || !session.refresh_token) {
    throw new Error("The server returned an incomplete sign-in session. Please try again.");
  }
  if (isAuthUser(session.user)) return session as AuthSession;

  const response = await fetch(`${API_BASE}/api/v1/auth/me`, {
    headers: { Authorization: `Bearer ${session.access_token}` },
  });
  const user = await parseJson<AuthUser & ApiErrorBody>(response);
  if (!response.ok || !isAuthUser(user)) {
    throw new Error(getApiErrorMessage(user, "Unable to load your account after sign-in. Please try again."));
  }

  return { ...session, token_type: session.token_type ?? "bearer", user } as AuthSession;
}

function usernameFrom(fullName: string, email: string): string {
  const base = fullName
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "") || email.split("@", 1)[0].replace(/[^a-zA-Z0-9_-]/g, "-");
  let hash = 0;
  for (const character of email.trim().toLowerCase()) {
    hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
  }
  return `${base.slice(0, 41)}-${hash.toString(36).slice(0, 7)}`.slice(0, 50);
}

export function signIn(email: string, password: string, remember: boolean): Promise<AuthSession> {
  return requestAuthSession(
    "/api/v1/auth/login",
    { method: "POST", body: JSON.stringify({ email: email.trim(), password, remember }) },
    "Unable to sign in. Please try again.",
  );
}

export function signUp({
  fullName,
  email,
  password,
  preferredLanguage = "vi",
}: RegisterInput): Promise<AuthSession> {
  const normalizedEmail = email.trim().toLowerCase();
  return request<AuthSession>(
    "/api/v1/auth/register",
    {
      method: "POST",
      body: JSON.stringify({
        username: usernameFrom(fullName, normalizedEmail),
        display_name: fullName.trim(),
        email: normalizedEmail,
        password,
        preferred_language: preferredLanguage,
      }),
    },
    "Unable to create your account. Please try again.",
  );
}

export function requestPasswordReset(email: string): Promise<{ message: string; reset_token?: string }> {
  return request(
    "/api/v1/auth/password/forgot",
    { method: "POST", body: JSON.stringify({ email: email.trim() }) },
    "Unable to request a password reset. Please try again.",
  );
}

export function signInWithGoogle(credential: string, remember = true): Promise<AuthSession> {
  return requestAuthSession(
    "/api/v1/auth/google",
    { method: "POST", body: JSON.stringify({ credential, remember }) },
    "Unable to sign in with Google. Please try again.",
  );
}
