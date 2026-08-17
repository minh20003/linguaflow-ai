import { API_BASE } from "@/config/env";
import type { AuthUser } from "@/features/auth/api/auth-api";
import type { Conversation, Message, User } from "../types";

interface ApiUser {
  id: string;
  email: string;
  username: string;
  display_name: string;
  preferred_language: string;
}

interface ApiConversation {
  id: string;
  type: "direct" | "group";
  title: string | null;
  member_ids: string[];
  members: ApiUser[];
  last_message: string | null;
  last_message_at: string | null;
  online_member_ids: string[];
  unread_count: number;
}

interface ApiTranslation {
  translation_id: string;
  target_language: string;
  translated_text: string;
}

export interface ApiMessage {
  id: string;
  client_message_id: string;
  conversation_id: string;
  sender_id: string;
  original_text: string;
  source_language: string;
  translations: ApiTranslation[];
  created_at: string;
  deleted_at: string | null;
  reply_to_message_id: string | null;
  attachment?: { id: string; filename: string; content_type: string; size: number; download_url: string } | null;
}

function avatar(seed: string): string {
  return `https://api.dicebear.com/9.x/initials/svg?seed=${encodeURIComponent(seed)}&backgroundColor=eff6ff`;
}

export function toLanguageCode(value: string): User["nativeLanguage"] {
  const supported = ["en", "vi", "ja", "ko", "zh", "es", "fr", "de", "th", "id"];
  return (supported.includes(value) ? value : "en") as User["nativeLanguage"];
}

function time(value: string | null): string {
  if (!value) return "";
  return new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

export function toChatUser(user: ApiUser | AuthUser): User {
  return {
    id: user.id,
    email: user.email,
    name: user.display_name || user.username || user.email,
    username: user.username || user.email.split("@", 1)[0],
    avatar: avatar(user.display_name || user.username || user.email),
    nativeLanguage: toLanguageCode(user.preferred_language),
    onlineStatus: "offline",
  };
}

export function toConversation(item: ApiConversation, currentUserId: string): Conversation {
  const others = item.members.filter((member) => member.id !== currentUserId);
  const recipient = others[0] ? toChatUser(others[0]) : undefined;
  const isGroup = item.type === "group";
  const name = isGroup ? (item.title || "Untitled group") : (recipient?.name || "Direct message");
  const members: User[] = item.members.map(toChatUser).map((member) => ({
    ...member,
    onlineStatus: (item.online_member_ids.includes(member.id) ? "online" : "offline") as User["onlineStatus"],
  }));
  return {
    id: item.id,
    type: item.type,
    name,
    avatar: avatar(name),
    isOnline: Boolean(recipient && item.online_member_ids.includes(recipient.id)),
    recipient: recipient && { ...recipient, onlineStatus: item.online_member_ids.includes(recipient.id) ? "online" : "offline" },
    members: isGroup ? members : undefined,
    memberCount: isGroup ? members.length : undefined,
    lastMessage: item.last_message || "No messages yet",
    lastMessageTime: time(item.last_message_at),
    unreadCount: item.unread_count,
  };
}

export function toMessage(item: ApiMessage, users: Map<string, User>, preferredLanguage: string): Message {
  const sender = users.get(item.sender_id);
  const translation = item.translations.find((entry) => entry.target_language === preferredLanguage);
  return {
    id: item.id,
    senderId: item.sender_id,
    senderName: sender?.name,
    senderAvatar: sender?.avatar,
    conversationId: item.conversation_id,
    content: item.deleted_at ? "This message was deleted" : item.original_text,
    translation: translation ? {
      originalText: item.original_text,
      originalLanguage: toLanguageCode(item.source_language),
      translatedText: translation.translated_text,
      targetLanguage: toLanguageCode(translation.target_language),
      status: "success",
    } : undefined,
    timestamp: time(item.created_at),
    status: "delivered",
    replyTo: item.reply_to_message_id ? { id: item.reply_to_message_id, senderName: "Reply", content: "" } : undefined,
    attachments: item.attachment ? [{
      id: item.attachment.id,
      type: item.attachment.content_type.startsWith("image/") ? "image" : "file",
      name: item.attachment.filename,
      size: `${Math.ceil(item.attachment.size / 1024)} KB`,
      url: `${API_BASE}${item.attachment.download_url}`,
    }] : undefined,
  };
}

/**
 * The API returns a reply ID rather than embedding the original message.
 * Resolve it from the conversation payload so reply previews still work after
 * a page refresh.
 */
export function toMessages(items: ApiMessage[], users: Map<string, User>, preferredLanguage: string): Message[] {
  const originals = new Map(items.map((item) => [item.id, item]));

  return items.map((item) => {
    const message = toMessage(item, users, preferredLanguage);
    const original = item.reply_to_message_id ? originals.get(item.reply_to_message_id) : undefined;
    if (!message.replyTo || !original) return message;

    const originalSender = users.get(original.sender_id);
    const translatedReply = original.translations.find(
      (translation) => translation.target_language === preferredLanguage,
    );
    return {
      ...message,
      replyTo: {
        id: original.id,
        senderName: originalSender?.name || "Message",
        // A quote should match the language this reader sees in the thread;
        // otherwise the composer preview and the persisted reply disagree.
        content: original.deleted_at
          ? "This message was deleted"
          : translatedReply?.translated_text || original.original_text,
      },
    };
  });
}

async function request<T>(path: string, accessToken: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${accessToken}`, ...init.headers },
  });
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => null) as T | { detail?: string } | null;
  if (!response.ok) throw new Error((body as { detail?: string } | null)?.detail || "Request failed");
  return body as T;
}

export function getMe(token: string) { return request<AuthUser>("/api/v1/auth/me", token); }
export function listUsers(token: string, query: string) { return request<ApiUser[]>(`/api/v1/users?q=${encodeURIComponent(query)}`, token); }
export function listConversations(token: string) { return request<ApiConversation[]>("/api/v1/conversations", token); }
export function getMessages(token: string, conversationId: string) { return request<ApiMessage[]>(`/api/v1/conversations/${conversationId}/messages`, token); }
export function createConversation(token: string, type: "direct" | "group", memberIds: string[], title?: string) {
  return request<ApiConversation>("/api/v1/conversations", token, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ type, member_ids: memberIds, title }) });
}
export function markRead(token: string, conversationId: string) { return request<void>(`/api/v1/conversations/${conversationId}/read`, token, { method: "POST" }); }
export function deleteMessage(token: string, conversationId: string, messageId: string) { return request<void>(`/api/v1/conversations/${conversationId}/messages/${messageId}`, token, { method: "DELETE" }); }
export function uploadAttachment(token: string, conversationId: string, file: File) {
  const form = new FormData(); form.append("file", file);
  return request<{ id: string }>(`/api/v1/conversations/${conversationId}/attachments`, token, { method: "POST", body: form });
}
