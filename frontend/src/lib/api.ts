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

  const profileResponse = await fetch(`${API_BASE}/api/v1/auth/me`, {
    headers: { Authorization: `Bearer ${token.access_token}` },
  });
  const profile = await responseBody(profileResponse);
  if (!profileResponse.ok || !profile?.email || !profile.id) {
    throw new Error(profile?.detail || "Không thể tải thông tin tài khoản.");
  }

  const accountName = profile.email.split("@")[0];
  return {
    access_token: token.access_token,
    refresh_token: "",
    token_type: token.token_type || "bearer",
    user: {
      id: profile.id,
      username: accountName,
      email: profile.email,
      display_name: accountName,
      preferred_language: profile.preferred_language || "en",
    },
  };
}

/**
 * Registration remains local until the backend exposes POST /auth/register.
 * It enforces one account identity: username is always the display name.
 */
export async function register(data: RegisterData): Promise<LoginResponse> {
  const username = data.username.trim();
  const registrationData = { ...data, username, display_name: username };

  await new Promise((resolve) => setTimeout(resolve, 1500));
  if (registrationData.email === "taken@test.com") {
    throw new Error("Email này đã có người dùng.");
  }

  return {
    access_token: `mock-access-token-${Date.now()}`,
    refresh_token: `mock-refresh-token-${Date.now()}`,
    token_type: "bearer",
    user: {
      id: `user-${Date.now()}`,
      username: registrationData.username,
      email: registrationData.email,
      display_name: registrationData.display_name,
      preferred_language: registrationData.preferred_language,
    },
  };
}
