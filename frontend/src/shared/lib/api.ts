/** Authentication API client. */

import { API_BASE } from "./constants";

export interface AuthUser {
  id: string;
  username: string;
  email: string;
  display_name: string;
  preferred_language: string;
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
  return response.json().catch(() => null) as Promise<Record<string, string> | null>;
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
    throw new Error(payload?.detail || "Email hoặc mật khẩu không đúng.");
  }
  return payload as unknown as LoginResponse;
}

/**
 * Create a durable backend account and start an authenticated session.
 */
export async function register(data: RegisterData): Promise<LoginResponse> {
  const username = data.username.trim();
  const registrationData = { ...data, username, display_name: username };

  const response = await fetch(`${API_BASE}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(registrationData),
  });
  const payload = await responseBody(response);
  if (!response.ok || !payload?.access_token || !payload.user) {
    throw new Error(payload?.detail || "Không thể tạo tài khoản.");
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
    throw new Error(payload?.detail || "Phiên đăng nhập đã hết hạn.");
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
  if (!response.ok) throw new Error(payload?.detail || "Không thể gửi yêu cầu đặt lại mật khẩu.");
  return {
    message: payload?.message || "Đã tiếp nhận yêu cầu.",
    reset_token: payload?.reset_token || undefined,
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
    throw new Error(payload?.detail || "Liên kết đặt lại mật khẩu không hợp lệ.");
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
    throw new Error(payload?.detail || "Không thể tải tệp lên.");
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
    throw new Error(payload?.detail || "Không đổi được ngôn ngữ.");
  }
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
