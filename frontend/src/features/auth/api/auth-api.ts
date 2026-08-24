import { API_BASE } from "@/config/env";
import {
  getApiErrorMessage,
  parseJson,
  type ApiErrorBody,
} from "@/shared/api/response";
import type { AuthSession } from "@/shared/types/auth";

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

export interface PendingRegistrationResponse {
  pending_id: string;
  email: string;
  expires_in_seconds: number;
  cooldown_seconds: number;
  message: string;
}

export function registerInit({
  fullName,
  email,
  password,
  preferredLanguage = "vi",
}: RegisterInput): Promise<PendingRegistrationResponse> {
  const normalizedEmail = email.trim().toLowerCase();
  return request<PendingRegistrationResponse>(
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

export function verifyRegisterOtp(pendingId: string, otp: string): Promise<AuthSession> {
  return request<AuthSession>(
    "/api/v1/auth/register/verify",
    {
      method: "POST",
      body: JSON.stringify({
        pending_id: pendingId,
        otp: otp.trim(),
      }),
    },
    "Invalid or expired verification code.",
  );
}

export function resendRegisterOtp(pendingId: string): Promise<{ pending_id: string; expires_in_seconds: number; cooldown_seconds: number; message: string }> {
  const normalizedPendingId = pendingId?.trim();
  if (!normalizedPendingId) {
    // JSON.stringify omits properties whose value is undefined. Failing here
    // makes the recovery action clear instead of issuing a guaranteed 422 with
    // an opaque `{}` request body.
    return Promise.reject(
      new Error("Your registration session is no longer available. Please return to the details form and register again."),
    );
  }
  return request(
    "/api/v1/auth/register/resend",
    {
      method: "POST",
      body: JSON.stringify({ pending_id: normalizedPendingId }),
    },
    "Unable to resend verification code.",
  );
}

export function signUp({
  fullName,
  email,
  password,
  preferredLanguage = "vi",
}: RegisterInput): Promise<PendingRegistrationResponse> {
  return registerInit({ fullName, email, password, preferredLanguage });
}

export function requestPasswordReset(email: string): Promise<{ message: string; reset_token?: string }> {
  return request(
    "/api/v1/auth/password/forgot",
    { method: "POST", body: JSON.stringify({ email: email.trim() }) },
    "Unable to request a password reset. Please try again.",
  );
}

export function signInWithGoogle(credential: string, remember = true): Promise<AuthSession> {
  return request<AuthSession>(
    "/api/v1/auth/google",
    { method: "POST", body: JSON.stringify({ credential, remember }) },
    "Unable to sign in with Google. Please try again.",
  );
}
