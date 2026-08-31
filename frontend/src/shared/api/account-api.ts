import { API_BASE } from "@/config/env";
import { getApiErrorMessage, parseJson, type ApiErrorBody } from "@/shared/api/response";
import type { AuthUser } from "@/shared/types/auth";

async function updateAccount(
  path: string,
  accessToken: string,
  body: Record<string, string>,
  fallback: string,
): Promise<AuthUser> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  const responseBody = await parseJson<AuthUser & ApiErrorBody>(response);

  if (!response.ok || !responseBody) {
    throw new Error(getApiErrorMessage(responseBody, fallback));
  }

  return responseBody;
}

export async function signOut(refreshToken: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/v1/auth/logout`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!response.ok) {
    const body = await parseJson<ApiErrorBody>(response);
    throw new Error(getApiErrorMessage(body, "Unable to sign out. Please try again."));
  }
}

export function updatePreferredLanguage(
  accessToken: string,
  preferredLanguage: string,
): Promise<AuthUser> {
  return updateAccount(
    "/api/v1/auth/me/language",
    accessToken,
    { preferred_language: preferredLanguage },
    "Unable to save your preferred language.",
  );
}

export function updateInterfaceLanguage(
  accessToken: string,
  interfaceLanguage: string,
): Promise<AuthUser> {
  return updateAccount(
    "/api/v1/auth/me/interface-language",
    accessToken,
    { interface_language: interfaceLanguage },
    "Unable to save your interface language.",
  );
}


/** Tell the server which timezone this browser is in.
 *
 *  Sent once when the app loads rather than asked for in settings: the browser
 *  already knows, and a question nobody can answer wrongly is a question not
 *  worth asking. The server needs it before a proposal can carry a real time —
 *  "3 giờ chiều thứ Sáu" is a wall clock, and without an offset it reaches the
 *  owner as an empty field they have to fill in again.
 */
export function updateTimezone(
  accessToken: string,
  timezone: string,
): Promise<AuthUser> {
  return updateAccount(
    "/api/v1/auth/me/timezone",
    accessToken,
    { timezone },
    "Unable to save your timezone.",
  );
}
