/** Authentication API client. */

import { API_BASE } from "./constants";

interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: {
    id: string;
    username: string;
    email: string;
    display_name: string;
    preferred_language: string;
  };
}

interface RegisterData {
  username: string;
  email: string;
  password: string;
  display_name?: string;
  preferred_language: string;
}

async function responseBody(response: Response) {
  return response.json().catch(() => null) as Promise<Record<string, string> | null>;
}

/**
 * Login with the backend, then load the authenticated account profile.
 * The backend currently has no username/display_name fields, so the UI derives
 * both from the email until that profile contract is available.
 */
export async function login(email: string, password: string): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const token = await responseBody(response);
  if (!response.ok || !token?.access_token) {
    throw new Error(token?.detail || "Email hoặc mật khẩu không đúng.");
  }

  return withProfile(token.access_token, token.token_type);
}

/**
 * Create an account, then load its profile.
 *
 * The chosen language is sent with the registration rather than set
 * afterwards: it is the language the account reads in, so collecting it later
 * would leave the first messages untranslated.
 */
export async function register(data: RegisterData): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: data.email.trim(),
      password: data.password,
      preferred_language: data.preferred_language,
    }),
  });
  const token = await responseBody(response);

  if (response.status === 409) {
    throw new Error("Email này đã có người dùng.");
  }
  if (!response.ok || !token?.access_token) {
    throw new Error(token?.detail || "Không tạo được tài khoản.");
  }

  return withProfile(token.access_token, token.token_type);
}

/** Load the account profile for a token and shape it for the UI. */
async function withProfile(accessToken: string, tokenType?: string): Promise<LoginResponse> {
  const profileResponse = await fetch(`${API_BASE}/api/v1/auth/me`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  const profile = await responseBody(profileResponse);
  if (!profileResponse.ok || !profile?.email || !profile.id) {
    throw new Error(profile?.detail || "Không thể tải thông tin tài khoản.");
  }

  const accountName = profile.email.split("@")[0];
  return {
    access_token: accessToken,
    refresh_token: "",
    token_type: tokenType || "bearer",
    user: {
      id: profile.id,
      username: accountName,
      email: profile.email,
      display_name: accountName,
      preferred_language: profile.preferred_language || "en",
    },
  };
}

/** Language codes the backend accepts. The frontend keeps only the labels. */
export async function fetchSupportedLanguages(): Promise<string[]> {
  const response = await fetch(`${API_BASE}/api/v1/languages`);
  if (!response.ok) return [];
  return (await response.json()) as string[];
}

/** Persist the reading language for the signed-in account. */
export async function updatePreferredLanguage(
  language: string,
  headers: Record<string, string>,
): Promise<string> {
  const response = await fetch(`${API_BASE}/api/v1/auth/me/language`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify({ preferred_language: language }),
  });
  const profile = await responseBody(response);
  if (!response.ok) {
    throw new Error(profile?.detail || "Không đổi được ngôn ngữ.");
  }
  return profile?.preferred_language || language;
}
