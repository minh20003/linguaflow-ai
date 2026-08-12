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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}/api/v1${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...authHeaders(), ...init?.headers },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail || `Yêu cầu thất bại (${response.status}).`);
  }
  return (await response.json()) as T;
}

/** Conversations the signed-in account belongs to. */
export function listConversations(): Promise<Conversation[]> {
  return request<Conversation[]>("/conversations");
}

/**
 * Recent messages, oldest first, each carrying whatever translations exist.
 *
 * This is also how a client recovers translations that completed while its
 * socket was down — they are not replayed over the socket on reconnect.
 */
export function getMessages(conversationId: string, limit = 50): Promise<HistoryMessage[]> {
  return request<HistoryMessage[]>(`/conversations/${conversationId}/messages?limit=${limit}`);
}

/** Create a direct or group conversation. The creator is added automatically. */
export function createConversation(input: {
  type: "direct" | "group";
  member_ids: string[];
  title?: string | null;
}): Promise<Conversation> {
  return request<Conversation>("/conversations", {
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
export async function lookupUserByEmail(email: string): Promise<ConversationMember | null> {
  const matches = await request<ConversationMember[]>(
    `/users?email=${encodeURIComponent(email.trim())}`,
  );
  return matches[0] ?? null;
}
