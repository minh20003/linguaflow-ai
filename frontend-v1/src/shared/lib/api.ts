/** Authentication API client. */

import { API_BASE } from "./constants";

export interface AuthUser {
  id: string;
  username: string;
  email: string;
  display_name: string;
  role: string;
  preferred_language: string;
  /** The language the interface is drawn in, separate from the one above. */
  interface_language: string;
  /** True when a Google account is linked (Batch G). */
  google_linked: boolean;
  /** True when the user has a password set (Batch G). */
  has_password?: boolean;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: AuthUser;
}

interface RegisterData {
  username: string;
  email: string;
  password: string;
  display_name?: string;
  preferred_language: string;
}

export interface AttachmentUpload {
  id: string;
  conversation_id: string;
  filename: string;
  content_type: string;
  size: number;
  download_url: string;
}

async function responseBody(response: Response) {
  return response.json().catch(() => null) as Promise<Record<string, unknown> | null>;
}

/**
 * Login with the backend, then load the authenticated account profile.
 * The backend currently has no username/display_name fields, so the UI derives
 * both from the email until that profile contract is available.
 */
export async function login(email: string, password: string, remember = false): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, remember }),
  });
  const payload = await responseBody(response);
  if (!response.ok || !payload?.access_token || !payload.user) {
    throw new Error("login_failed");
  }
  return payload as unknown as LoginResponse;
}

export interface PendingRegisterResponse {
  pending_id: string;
  email: string;
  expires_in_seconds: number;
  cooldown_seconds: number;
  message: string;
}

export interface ResendRegisterOtpResponse {
  pending_id: string;
  expires_in_seconds: number;
  cooldown_seconds: number;
  message: string;
}

function extractErrorCode(payload: Record<string, unknown> | null): string | null {
  if (!payload) return null;
  if (typeof payload.detail === "string") return payload.detail;
  if (typeof payload.detail === "object" && payload.detail !== null) {
    const detailObj = payload.detail as Record<string, unknown>;
    if (typeof detailObj.code === "string") return detailObj.code;
  }
  if (typeof payload.code === "string") return payload.code;
  return null;
}

/**
 * Request registration and receive a pending identity awaiting email OTP verification (Batch F).
 */
export async function register(data: RegisterData): Promise<PendingRegisterResponse> {
  const username = data.username.trim();
  const displayName = data.display_name?.trim() || username;
  const registrationData = { ...data, username, display_name: displayName };

  const response = await fetch(`${API_BASE}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(registrationData),
  });
  const payload = await responseBody(response);
  if (!response.ok || !payload?.pending_id) {
    if (response.status === 409) {
      throw new Error("duplicate_account");
    }
    if (response.status === 429) {
      throw new Error("rate_limit_exceeded");
    }
    if (response.status === 500) {
      const code = extractErrorCode(payload);
      if (code === "email_delivery_failed") {
        throw new Error("email_delivery_failed");
      }
    }
    throw new Error("register_failed");
  }
  return payload as unknown as PendingRegisterResponse;
}

/**
 * Verify 6-digit numeric OTP and receive the authenticated session (Batch F).
 */
export async function verifyRegisterOtp(
  pendingId: string,
  otp: string,
): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE}/api/v1/auth/register/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pending_id: pendingId, otp: otp.trim() }),
  });
  const payload = await responseBody(response);
  if (!response.ok || !payload?.access_token || !payload.user) {
    if (response.status === 400) {
      const detail = typeof payload?.detail === "string" ? payload.detail : "";
      if (detail.includes("expired")) {
        throw new Error("otp_expired");
      }
      if (detail.includes("Maximum verification") || detail.includes("exceeded")) {
        throw new Error("otp_max_attempts");
      }
      throw new Error("otp_invalid");
    }
    if (response.status === 409) {
      throw new Error("duplicate_account");
    }
    throw new Error("verify_failed");
  }
  return payload as unknown as LoginResponse;
}

/**
 * Request a replacement 6-digit OTP for a pending registration (Batch F).
 */
export async function resendRegisterOtp(
  pendingId: string,
): Promise<ResendRegisterOtpResponse> {
  const response = await fetch(`${API_BASE}/api/v1/auth/register/resend`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pending_id: pendingId }),
  });
  const payload = await responseBody(response);
  if (!response.ok || !payload?.pending_id) {
    if (response.status === 429) {
      throw new Error("rate_limit_exceeded");
    }
    if (response.status === 500) {
      const code = extractErrorCode(payload);
      if (code === "email_delivery_failed") {
        throw new Error("email_delivery_failed");
      }
    }
    throw new Error("resend_failed");
  }
  return payload as unknown as ResendRegisterOtpResponse;
}

export async function refreshSession(refreshToken: string): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  const payload = await responseBody(response);
  if (!response.ok || !payload?.access_token || !payload.user) {
    throw new Error("session_expired");
  }
  return payload as unknown as LoginResponse;
}

export async function logoutSession(refreshToken: string): Promise<void> {
  await fetch(`${API_BASE}/api/v1/auth/logout`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

export async function requestPasswordReset(email: string): Promise<{ message: string; reset_token?: string }> {
  const response = await fetch(`${API_BASE}/api/v1/auth/password/forgot`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  const payload = await responseBody(response);
  if (!response.ok) throw new Error("reset_request_failed");
  return {
    // Narrowed rather than cast: `responseBody` now says `unknown` per field,
    // which is the truth — the shape depends on the environment (§3.9).
    message: typeof payload?.message === "string" ? payload.message : "request_accepted",
    reset_token: typeof payload?.reset_token === "string" ? payload.reset_token : undefined,
  };
}

export async function resetPassword(token: string, newPassword: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/v1/auth/password/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, new_password: newPassword }),
  });
  if (!response.ok) {
    throw new Error("reset_password_failed");
  }
}

/** Upload a file for an authenticated conversation member. */
export async function uploadConversationAttachment(
  conversationId: string,
  file: File,
  accessToken: string,
): Promise<AttachmentUpload> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch(
    `${API_BASE}/api/v1/conversations/${encodeURIComponent(conversationId)}/attachments`,
    { method: "POST", headers: { Authorization: `Bearer ${accessToken}` }, body },
  );
  const payload = await responseBody(response);
  if (!response.ok || !payload?.id) {
    throw new Error("upload_failed");
  }
  return payload as unknown as AttachmentUpload;
}

/**
 * Change which language this account reads messages in.
 *
 * The server answers with the updated profile, which the caller stores so the
 * cached user and the next translation request agree on the language.
 */
export async function updateLanguage(code: string, accessToken: string): Promise<AuthUser> {
  const response = await fetch(`${API_BASE}/api/v1/auth/me/language`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({ preferred_language: code }),
  });
  const payload = await responseBody(response);
  if (!response.ok || !payload?.id) {
    throw new Error("update_language_failed");
  }
  return payload as unknown as AuthUser;
}

/**
 * Change the language the interface is drawn in (docs/CONTRACT.md §1.2).
 *
 * Costs nothing and takes effect immediately, unlike `updateLanguage` above,
 * which only decides how messages sent from now on are translated.
 */
export async function updateInterfaceLanguage(
  interfaceLanguage: string,
  token: string,
): Promise<AuthUser> {
  const response = await fetch(`${API_BASE}/api/v1/auth/me/interface-language`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ interface_language: interfaceLanguage }),
  });
  const payload = await responseBody(response);
  if (!response.ok) throw new Error("update_interface_language_failed");
  return payload as unknown as AuthUser;
}

/**
 * The language codes the server accepts.
 *
 * Fetched rather than hardcoded: `docs/CONTRACT.md` section 1 makes the backend
 * allowlist the single source of truth, and a second copy in the frontend is
 * how the selector came to be missing a language the server supports.
 */
export async function listLanguages(): Promise<string[]> {
  const response = await fetch(`${API_BASE}/api/v1/languages`);
  if (!response.ok) throw new Error("list_languages_failed");
  return (await response.json()) as string[];
}

// ----------------------------------------------------------------------
// Google Sign-In (Batch G)
// ----------------------------------------------------------------------

/**
 * Log in with a Google ID token. The backend resolves an existing Google
 * identity first, auto-links an unlinked verified-email account, or creates a
 * Google-native account when neither exists.
 *
 * Returns the same shape as `login()` so callers can treat both paths uniformly.
 */
export async function googleLogin(credential: string): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE}/api/v1/auth/google/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ credential }),
  });
  const payload = await responseBody(response);
  if (!response.ok || !payload?.access_token || !payload?.user) {
    if (response.status === 409) {
      throw new Error("google_conflict");
    }
    throw new Error("google_login_failed");
  }
  return payload as unknown as LoginResponse;
}

export interface GoogleLinkResponse {
  google_linked: boolean;
  message: string;
}

/**
 * Link a Google account to the current LinguaFlow account.
 *
 * The user must have a valid session (access token).
 */
export async function linkGoogle(
  credential: string,
  accessToken: string,
): Promise<GoogleLinkResponse> {
  const response = await fetch(`${API_BASE}/api/v1/auth/me/google/link`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify({ credential }),
  });
  const payload = await responseBody(response);
  if (!response.ok) {
    if (response.status === 409) {
      const detail = typeof payload?.detail === "string" ? payload.detail : "";
      if (detail.includes("already linked")) {
        throw new Error("google_already_linked");
      }
      throw new Error("google_link_conflict");
    }
    throw new Error("google_link_failed");
  }
  return payload as unknown as GoogleLinkResponse;
}

/**
 * Remove the Google link from the current account.
 *
 * After unlinking the user can only log in with email and password.
 */
export async function unlinkGoogle(accessToken: string): Promise<GoogleLinkResponse> {
  const response = await fetch(`${API_BASE}/api/v1/auth/me/google/link`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  const payload = await responseBody(response);
  if (!response.ok) {
    if (response.status === 409) {
      throw new Error("google_cannot_unlink_no_password");
    }
    throw new Error("google_unlink_failed");
  }
  return payload as unknown as GoogleLinkResponse;
}
