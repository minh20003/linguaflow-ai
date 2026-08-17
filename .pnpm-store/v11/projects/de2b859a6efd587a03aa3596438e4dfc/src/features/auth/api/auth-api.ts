import { API_BASE } from "@/config/env";

export interface AuthUser {
  id: string;
  email: string;
  username: string;
  display_name: string;
  role: string;
  preferred_language: string;
  created_at: string;
}

export interface AuthSession {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: AuthUser;
}

interface RegisterInput {
  fullName: string;
  email: string;
  password: string;
  preferredLanguage?: string;
}

interface ErrorBody {
  detail?: string | Array<{ msg?: string }>;
}

async function parseBody<T>(response: Response): Promise<T | null> {
  return response.json().catch(() => null) as Promise<T | null>;
}

function errorMessage(body: ErrorBody | null, fallback: string): string {
  if (typeof body?.detail === "string") return body.detail;
  if (Array.isArray(body?.detail)) {
    const message = body.detail.find((item) => item.msg)?.msg;
    if (message) return message;
  }
  return fallback;
}

async function request<T>(path: string, init: RequestInit, fallback: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init.headers },
  });
  const body = await parseBody<T & ErrorBody>(response);
  if (!response.ok || !body) {
    throw new Error(errorMessage(body, fallback));
  }
  return body;
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
  return request<AuthSession>(
    "/api/v1/auth/login",
    { method: "POST", body: JSON.stringify({ email: email.trim(), password, remember }) },
    "Unable to sign in. Please try again.",
  );
}

export async function signOut(refreshToken: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/v1/auth/logout`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) {
    const body = await parseBody<ErrorBody>(response);
    throw new Error(errorMessage(body, "Unable to sign out. Please try again."));
  }
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

export function updatePreferredLanguage(
  accessToken: string,
  preferredLanguage: string,
): Promise<AuthUser> {
  return request<AuthUser>(
    "/api/v1/auth/me/language",
    {
      method: "PUT",
      headers: { Authorization: `Bearer ${accessToken}` },
      body: JSON.stringify({ preferred_language: preferredLanguage }),
    },
    "Unable to save your preferred language.",
  );
}
