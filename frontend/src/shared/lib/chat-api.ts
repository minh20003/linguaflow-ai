/** REST client for conversations, history and member lookup. */

import { authHeaders } from "./auth";
import { API_BASE } from "./constants";

export interface ConversationMember {
  id: string;
  email: string;
  /** Never null in a response: the server fills both from the email (§3.1). */
  username: string | null;
  display_name: string | null;
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
  /**
   * Newest message, in this account's own language where a translation exists.
   * Null until someone writes in the conversation (docs/CONTRACT.md §3.5).
   */
  last_message: string | null;
  last_message_at: string | null;
  /** Members holding a live socket when this list was fetched, not since. */
  online_member_ids: string[];
  /** Messages from other people since this account last read (§3.8). */
  unread_count: number;
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
  /** Set once the sender edits or withdraws the message (F-06). */
  edited_at: string | null;
  deleted_at: string | null;
  /** The file this message carries, and the message it answers (§3.7). */
  attachment: AttachmentSummary | null;
  reply_to_message_id: string | null;
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
  // A 204 carries no body, and parsing one as JSON throws.
  if (response.status === 204) return null as T;
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

export interface AttachmentSummary {
  id: string;
  conversation_id: string;
  filename: string;
  content_type: string;
  size: number;
  download_url: string;
}

/**
 * Upload one file and report progress while it goes.
 *
 * XMLHttpRequest rather than fetch: fetch cannot report upload progress, and a
 * progress bar that is not driven by the transfer is a lie — the previous one
 * was a `setInterval` that finished whether or not anything was sent.
 */
export function uploadAttachment(
  conversationId: string,
  file: File,
  onProgress?: (percent: number) => void,
): Promise<AttachmentSummary> {
  return new Promise((resolve, reject) => {
    const body = new FormData();
    body.append("file", file);

    const request = new XMLHttpRequest();
    request.open("POST", `${API_BASE}/api/v1/conversations/${encodeURIComponent(conversationId)}/attachments`);
    for (const [header, value] of Object.entries(authHeaders())) {
      request.setRequestHeader(header, value);
    }

    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress?.(Math.round((event.loaded / event.total) * 100));
    };
    request.onload = () => {
      if (request.status === 201) {
        resolve(JSON.parse(request.responseText) as AttachmentSummary);
        return;
      }
      const detail = (() => {
        try { return (JSON.parse(request.responseText) as { detail?: string }).detail; } catch { return null; }
      })();
      reject(new Error(detail || `Không tải tệp lên được (${request.status}).`));
    };
    request.onerror = () => reject(new Error("Không tải tệp lên được."));
    request.send(body);
  });
}

/**
 * Fetch an attachment's bytes.
 *
 * The download endpoint checks conversation membership, so it needs the session
 * header — a plain link would arrive unauthenticated and be refused.
 */
export async function downloadAttachment(downloadUrl: string): Promise<Blob> {
  const response = await fetch(`${API_BASE}${downloadUrl}`, { headers: authHeaders() });
  if (!response.ok) throw new Error("Không tải được tệp đính kèm.");
  return response.blob();
}

/** Mark a conversation read up to now, clearing its unread count (§3.8). */
export function markConversationRead(
  conversationId: string,
  token?: string,
): Promise<{ unread_count: number }> {
  return request<{ unread_count: number }>(
    `/conversations/${encodeURIComponent(conversationId)}/read`,
    token,
    { method: "POST" },
  );
}

/**
 * Rewrite a message this account sent (F-06).
 *
 * The server discards the old translations and starts new ones, so the reply
 * carries an empty `translations` array — the fresh ones arrive over the socket.
 */
export function editMessage(
  conversationId: string,
  messageId: string,
  text: string,
  token?: string,
): Promise<HistoryMessage> {
  return request<HistoryMessage>(
    `/conversations/${encodeURIComponent(conversationId)}/messages/${encodeURIComponent(messageId)}`,
    token,
    { method: "PATCH", body: JSON.stringify({ text }) },
  );
}

/** Withdraw a message this account sent. The row survives; its text does not. */
export async function deleteMessage(
  conversationId: string,
  messageId: string,
  token?: string,
): Promise<void> {
  await request<null>(
    `/conversations/${encodeURIComponent(conversationId)}/messages/${encodeURIComponent(messageId)}`,
    token,
    { method: "DELETE" },
  );
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

/**
 * Accounts whose email, username or display name starts with `query`.
 *
 * This is the only way to reach someone you have never talked to: the
 * conversation endpoint wants user ids, and nothing else in the app hands them
 * out. Fewer than two characters is rejected by the server, so callers should
 * not send them (docs/CONTRACT.md §3.1).
 */
export function searchUsers(query: string, token?: string): Promise<ConversationMember[]> {
  return request<ConversationMember[]>(
    `/users?q=${encodeURIComponent(query.trim())}`,
    token,
  );
}
