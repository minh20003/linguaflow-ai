/** REST client for conversations, history and member lookup. */

import { authHeaders } from "./auth";
import { API_BASE } from "./constants";

export interface ConversationMember {
  id: string;
  email: string;
  preferred_language: string;
}

export interface Conversation {
  id: string;
  type: "direct" | "group";
  title: string | null;
  created_by: string;
  created_at: string;
  member_ids: string[];
  members: ConversationMember[];
}

export interface TranslationSummary {
  translation_id: string;
  target_language: string;
  translated_text: string;
  model: string;
  latency_ms: number;
  is_fallback: boolean;
  /** This account's own rating, null until it votes (F-05). */
  my_rating: number | null;
  my_correction: string | null;
}

export interface HistoryMessage {
  id: string;
  client_message_id: string;
  conversation_id: string;
  sender_id: string;
  original_text: string;
  source_language: string;
  translations: TranslationSummary[];
  created_at: string;
}

/**
 * Every call takes an optional token.
 *
 * Without one it uses the session in localStorage, which is what the app does.
 * Passing one explicitly is what lets the side-by-side demo hold two accounts
 * at once in a single tab — localStorage has room for exactly one.
 */
function headersFor(token?: string): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : authHeaders();
}

async function request<T>(path: string, token?: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}/api/v1${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...headersFor(token), ...init?.headers },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail || `Yêu cầu thất bại (${response.status}).`);
  }
  return (await response.json()) as T;
}

/** Conversations the signed-in account belongs to. */
export function listConversations(token?: string): Promise<Conversation[]> {
  return request<Conversation[]>("/conversations", token);
}

/**
 * Recent messages, oldest first, each carrying whatever translations exist.
 *
 * This is also how a client recovers translations that completed while its
 * socket was down — they are not replayed over the socket on reconnect.
 */
export function getMessages(
  conversationId: string,
  limit = 50,
  token?: string,
): Promise<HistoryMessage[]> {
  return request<HistoryMessage[]>(
    `/conversations/${conversationId}/messages?limit=${limit}`,
    token,
  );
}

/** Create a direct or group conversation. The creator is added automatically. */
export function createConversation(
  input: { type: "direct" | "group"; member_ids: string[]; title?: string | null },
  token?: string,
): Promise<Conversation> {
  return request<Conversation>("/conversations", token, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

/**
 * Resolve an email to an account, or null when there is no such account.
 *
 * The group form collects emails while the conversation endpoint wants ids,
 * so every address is resolved before the conversation is created — which
 * also lets the form reject a typo while the user is still looking at it.
 */
export async function lookupUserByEmail(
  email: string,
  token?: string,
): Promise<ConversationMember | null> {
  const matches = await request<ConversationMember[]>(
    `/users?email=${encodeURIComponent(email.trim())}`,
    token,
  );
  return matches[0] ?? null;
}

/**
 * Rate a translation, optionally suggesting better wording (F-05).
 *
 * Thumbs up and down are sent as the extremes of the server's 1-5 range, and a
 * second call from the same account replaces its earlier verdict rather than
 * adding another one — so a reader can change their mind freely.
 *
 * Lives here rather than in `api.ts` because this is the client that already
 * carries the session header and the shared error handling.
 */
export function submitTranslationFeedback(
  translationId: string,
  rating: number,
  correction?: string | null,
  token?: string,
): Promise<{ feedback_id: string }> {
  return request<{ feedback_id: string }>(
    `/translations/${encodeURIComponent(translationId)}/feedback`,
    token,
    { method: "POST", body: JSON.stringify({ rating, correction: correction ?? null }) },
  );
}
