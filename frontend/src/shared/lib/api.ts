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
 * The readable half of an error response, whatever shape FastAPI sent.
 *
 * FastAPI answers a rejected body with `detail` as an **array of objects**, not
 * a string. Passing that straight to `new Error()` stringifies it to
 * "[object Object]", which is what every caller here used to show: the account
 * could not be created and the reason was unreadable. A 4xx raised by our own
 * code sends `detail` as a plain string, so both shapes have to be handled.
 *
 * The server writes these in English. They are shown as a last resort, when the
 * client had no rule of its own to catch the problem first — a localised
 * message from the form beats anything recovered here.
 */
function errorDetail(payload: Record<string, unknown> | null, fallback: string): string {
  const detail = payload?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (typeof item === "object" && item !== null ? String((item as { msg?: unknown }).msg ?? "") : ""))
      // Pydantic prefixes its own text with "Value error, "; the reader does
      // not need to know which validator produced the complaint.
      .map((message) => message.replace(/^Value error,\s*/u, ""))
      .filter(Boolean);
    if (messages.length) return messages.join(" ");
  }
  return fallback;
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
    throw new Error(errorDetail(payload, "Email hoặc mật khẩu không đúng."));
  }
  return payload as unknown as LoginResponse;
}

/**
 * Create a durable backend account and start an authenticated session.
 */
export async function register(data: RegisterData): Promise<LoginResponse> {
  const username = data.username.trim();
  // The display name is the caller's to decide. This used to overwrite it with
  // the username, from when the form had no separate field for it — which
  // silently discarded whatever the new "Họ và tên" box collected. The username
  // remains the fallback for callers that send no name at all.
  const displayName = data.display_name?.trim() || username;
  const registrationData = { ...data, username, display_name: displayName };

  const response = await fetch(`${API_BASE}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(registrationData),
  });
  const payload = await responseBody(response);
  if (!response.ok || !payload?.access_token || !payload.user) {
    throw new Error(errorDetail(payload, "Không thể tạo tài khoản."));
  }
  return payload as unknown as LoginResponse;
}

export async function refreshSession(refreshToken: string): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  const payload = await responseBody(response);
  if (!response.ok || !payload?.access_token || !payload.user) {
    throw new Error(errorDetail(payload, "Phiên đăng nhập đã hết hạn."));
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
  if (!response.ok) throw new Error(errorDetail(payload, "Không thể gửi yêu cầu đặt lại mật khẩu."));
  return {
    // Narrowed rather than cast: `responseBody` now says `unknown` per field,
    // which is the truth — the shape depends on the environment (§3.9).
    message: typeof payload?.message === "string" ? payload.message : "Đã tiếp nhận yêu cầu.",
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
    const payload = await responseBody(response);
    throw new Error(errorDetail(payload, "Liên kết đặt lại mật khẩu không hợp lệ."));
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
    throw new Error(errorDetail(payload, "Không thể tải tệp lên."));
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
    throw new Error(errorDetail(payload, "Không đổi được ngôn ngữ."));
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
  if (!response.ok) throw new Error(errorDetail(payload, "Không đổi được ngôn ngữ giao diện."));
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
  if (!response.ok) throw new Error("Không tải được danh sách ngôn ngữ.");
  return (await response.json()) as string[];
}
