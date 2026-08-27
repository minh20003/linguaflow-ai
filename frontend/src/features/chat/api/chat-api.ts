import { API_BASE } from "@/config/env";
import { getApiErrorMessage, parseJson, type ApiErrorBody } from "@/shared/api/response";
import type { AuthUser } from "@/shared/types/auth";
import type { Conversation, Message, MessageAttachment, User } from "../types";
import { interactionText } from "../i18n";

interface ApiMention {
  type: "user" | "assistant";
  user_id?: string | null;
}

export interface ApiUser {
  id: string;
  email: string;
  username: string;
  display_name: string;
  preferred_language: string;
  interface_language?: string;
  bio?: string | null;
  role?: string;
  group_role?: "owner" | "admin" | "member" | string;
}

export interface ApiConversation {
  id: string;
  type: "direct" | "group";
  title: string | null;
  description?: string | null;
  member_ids: string[];
  members: ApiUser[];
  last_message: string | null;
  last_message_at: string | null;
  last_message_type?: "text" | "voice" | null;
  last_message_transcription_status?: null | "pending" | "completed" | "failed";
  online_member_ids: string[];
  unread_count: number;
  created_by?: string;
  is_pinned?: boolean;
  pinned_at?: string | null;
  created_at?: string;
  is_muted?: boolean;
}

interface ApiTranslation {
  translation_id: string;
  target_language: string;
  translated_text: string;
  my_rating?: number | null;
  my_correction?: string | null;
  my_edit?: { edited_text: string } | null;
}

export interface TranslationDisplayContext {
  currentUserId: string;
  isDirect: boolean;
  recipientLanguage?: string;
}

export interface ApiMessage {
  id: string;
  client_message_id: string;
  conversation_id: string;
  sender_id: string;
  original_text: string;
  message_type: "text" | "voice";
  transcription_status: null | "pending" | "completed" | "failed";
  source_language: string;
  translations: ApiTranslation[];
  created_at: string;
  deleted_at: string | null;
  reply_to_message_id: string | null;
  forwarded_from_message_id?: string | null;
  attachment?: ApiAttachment | null;
  mentions?: ApiMention[];
  assistant_generated?: boolean;
  is_saved?: boolean;
  reactions?: ApiMessageReaction[];
}

export interface ApiRealtimeMessage {
  id: string;
  conversation_id: string;
  sender_id: string;
  original_text: string;
  message_type: "text" | "voice";
  transcription_status: null | "pending" | "completed" | "failed";
  created_at: string;
  reply_to_message_id?: string | null;
  forwarded_from_message_id?: string | null;
  attachment?: ApiAttachment | null;
  mentions?: ApiMention[];
  assistant_generated?: boolean;
}

export interface ApiMessageReaction {
  emoji: string;
  count: number;
  user_ids: string[];
}

export interface ApiMessageSearchResult {
  message: ApiMessage;
  matched_in: "original" | "translation";
  snippet: string;
}

export interface ApiMessageSearchResponse {
  items: ApiMessageSearchResult[];
  has_more: boolean;
  next_before_created_at: string | null;
  next_before_id: string | null;
}

export interface ApiSavedMessagesPage {
  items: ApiMessage[];
  has_more: boolean;
  next_before_created_at?: string | null;
  next_before_id?: string | null;
}

export interface ApiUserSettings {
  auto_translate: boolean;
  show_original_by_default: boolean;
  translation_tone: "natural" | "formal" | "casual" | "friendly";
  sound_enabled: boolean;
  read_receipts: boolean;
  ai_smart_assistance: boolean;
}

export interface ApiAttachment {
  id: string;
  conversation_id: string;
  filename: string;
  content_type: string;
  size: number;
  created_at: string;
  download_url: string;
}

export interface ApiCall {
  call_id: string;
  conversation_id: string;
  caller_id: string;
  callee_id: string;
  call_type: "voice" | "video";
  status: "ringing" | "accepted" | "rejected" | "ended" | "missed" | "failed";
  room_url: string | null;
  join_token: string | null;
  created_at: string;
  answered_at: string | null;
  ended_at: string | null;
}

function avatar(seed: string): string {
  return `https://api.dicebear.com/9.x/initials/svg?seed=${encodeURIComponent(seed)}&backgroundColor=bfdbfe&fontColor=1d4ed8`;
}

export const ASSISTANT_AVATAR_URL = "https://api.dicebear.com/9.x/bottts-neutral/svg?seed=linguachat-assistant&backgroundColor=ede9fe";
export const ASSISTANT_CONVERSATION_TITLE = "__linguachat_assistant__";

function assistantAvatar(): string {
  return ASSISTANT_AVATAR_URL;
}

export function toLanguageCode(value: string): User["nativeLanguage"] {
  const supported = ["en", "vi", "ja", "ko", "zh", "es", "fr", "de", "th", "id", "pt", "ru", "ar", "hi"];
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
    bio: "bio" in user ? user.bio ?? undefined : undefined,
    role: "group_role" in user ? (user.group_role as "admin" | "member" | undefined) : ("role" in user ? (user.role as "admin" | "member" | undefined) : undefined),
  };
}

export function toConversation(
  item: ApiConversation,
  currentUserId: string,
  interfaceLanguage: User["nativeLanguage"] = "en",
): Conversation {
  const others = item.members.filter((member) => member.id !== currentUserId);
  const recipient = others[0] ? toChatUser(others[0]) : undefined;
  const isGroup = item.type === "group";
  const name = isGroup ? (item.title || "Untitled group") : (recipient?.name || "Direct message");
  const members: User[] = item.members.map(toChatUser).map((member) => ({
    ...member,
    onlineStatus: (item.online_member_ids.includes(member.id) ? "online" : "offline") as User["onlineStatus"],
  }));
  const voiceWithoutTranscript = item.last_message_type === "voice"
    && (item.last_message_transcription_status === "pending"
      || item.last_message_transcription_status === "failed");
  return {
    id: item.id,
    type: item.type,
    name,
    avatar: avatar(name),
    isOnline: Boolean(recipient && item.online_member_ids.includes(recipient.id)),
    recipient: recipient && { ...recipient, onlineStatus: item.online_member_ids.includes(recipient.id) ? "online" : "offline" },
    members: isGroup ? members : undefined,
    memberCount: isGroup ? members.length : undefined,
    lastMessage: voiceWithoutTranscript
      ? interactionText(interfaceLanguage, "Voice message")
      : item.last_message || "No messages yet",
    lastMessageTime: time(item.last_message_at),
    lastMessageType: item.last_message_type ?? undefined,
    lastMessageTranscriptionStatus: item.last_message_transcription_status ?? null,
    unreadCount: item.unread_count,
    isPinned: item.is_pinned ?? false,
    pinnedAt: item.pinned_at ?? null,
    createdAt: item.created_at ?? null,
    isMuted: item.is_muted ?? false,
    description: item.description ?? undefined,
    createdBy: item.created_by,
    currentUserRole: item.members.find((member) => member.id === currentUserId)?.group_role as "owner" | "admin" | "member" | undefined,
  };
}

export function compareConversations(a: Conversation, b: Conversation): number {
  const aPinned = Boolean(a.isPinned);
  const bPinned = Boolean(b.isPinned);
  if (aPinned !== bPinned) {
    return aPinned ? -1 : 1;
  }
  if (aPinned && bPinned) {
    const aPinnedAt = a.pinnedAt ? new Date(a.pinnedAt).getTime() : 0;
    const bPinnedAt = b.pinnedAt ? new Date(b.pinnedAt).getTime() : 0;
    if (aPinnedAt !== bPinnedAt) {
      return bPinnedAt - aPinnedAt; // pinned_at DESC (newest pinned first)
    }
  }
  const aCreated = a.createdAt ? new Date(a.createdAt).getTime() : 0;
  const bCreated = b.createdAt ? new Date(b.createdAt).getTime() : 0;
  if (aCreated !== bCreated) {
    return bCreated - aCreated; // created_at DESC
  }
  return b.id.localeCompare(a.id);
}

export function toMessage(
  item: ApiMessage,
  users: Map<string, User>,
  preferredLanguage: string,
  context?: TranslationDisplayContext,
): Message {
  const sender = users.get(item.sender_id);
  const isAssistant = Boolean(item.assistant_generated);
  const isOwnDirectMessage = Boolean(
    context?.isDirect && item.sender_id === context.currentUserId && context.recipientLanguage,
  );
  const displayLanguage = isOwnDirectMessage ? context?.recipientLanguage : preferredLanguage;
  // Agent responses are already authored for the user-facing flow. Keep them
  // out of the per-message translation review pipeline entirely.
  const translation = isAssistant ? undefined : item.translations.find((entry) => entry.target_language === displayLanguage);
  // A same-language pipeline result is operational telemetry, not a user
  // translation. Keep the original message clean and do not surface review
  // controls for wording that was never translated.
  const isSameLanguage = toLanguageCode(item.source_language) === toLanguageCode(displayLanguage || item.source_language);
  const visibleTranslation = isSameLanguage ? undefined : translation;
  return {
    id: item.id,
    clientMessageId: item.client_message_id,
    senderId: item.sender_id,
    senderName: isAssistant ? 'Trợ lý thông minh' : sender?.name,
    senderAvatar: isAssistant ? assistantAvatar() : sender?.avatar,
    conversationId: item.conversation_id,
    content: item.deleted_at ? "This message was deleted" : item.original_text,
    messageType: item.message_type,
    transcriptionStatus: item.transcription_status,
    translation: visibleTranslation ? {
      translationId: visibleTranslation.translation_id,
      originalText: item.original_text,
      originalLanguage: toLanguageCode(item.source_language),
      translatedText: visibleTranslation.translated_text,
      targetLanguage: toLanguageCode(visibleTranslation.target_language),
      status: "success",
      // In a direct chat, a sender starts with their own wording and can opt
      // in to inspect the rendering their recipient receives.
      showOriginal: isOwnDirectMessage || undefined,
      rating: visibleTranslation.my_rating === 1 || visibleTranslation.my_rating === 5 ? visibleTranslation.my_rating : undefined,
      correction: visibleTranslation.my_correction ?? undefined,
      editedText: visibleTranslation.my_edit?.edited_text,
    } : undefined,
    timestamp: time(item.created_at),
    createdAt: item.created_at,
    deletedAt: item.deleted_at ?? undefined,
    status: "delivered",
    replyTo: item.reply_to_message_id ? { id: item.reply_to_message_id, senderName: "Reply", content: "" } : undefined,
    forwardedFromMessageId: item.forwarded_from_message_id ?? undefined,
    attachments: item.attachment ? [toMessageAttachment(item.attachment)] : undefined,
    mentions: item.mentions?.map((mention) => ({ type: mention.type, userId: mention.user_id ?? undefined })),
    isAssistant,
    isSaved: item.is_saved ?? false,
    reactions: item.reactions?.map((reaction) => ({
      emoji: reaction.emoji,
      count: reaction.count,
      users: reaction.user_ids,
    })),
  };
}

export function toMessageAttachment(item: ApiAttachment): MessageAttachment {
  const normalizedContentType = item.content_type.toLowerCase();
  return {
    id: item.id,
    type: normalizedContentType.startsWith("image/")
      ? "image"
      : normalizedContentType.startsWith("audio/")
        ? "audio"
        : "file",
    name: item.filename,
    size: item.size < 1024 * 1024
      ? `${Math.max(1, Math.ceil(item.size / 1024))} KB`
      : `${(item.size / (1024 * 1024)).toFixed(1)} MB`,
    url: `${API_BASE}${item.download_url}`,
    contentType: item.content_type,
    createdAt: item.created_at,
  };
}

export function toApiMessageFromRealtime(
  item: ApiRealtimeMessage,
  clientMessageId: string | undefined,
  fallbackSourceLanguage: string,
): ApiMessage {
  return {
    id: item.id,
    client_message_id: clientMessageId || item.id,
    conversation_id: item.conversation_id,
    sender_id: item.sender_id,
    original_text: item.original_text,
    message_type: item.message_type,
    transcription_status: item.transcription_status,
    source_language: fallbackSourceLanguage,
    translations: [],
    created_at: item.created_at,
    deleted_at: null,
    reply_to_message_id: item.reply_to_message_id ?? null,
    forwarded_from_message_id: item.forwarded_from_message_id ?? null,
    attachment: item.attachment,
    mentions: item.mentions,
    assistant_generated: Boolean(item.assistant_generated),
  };
}

export function toMessages(
  items: ApiMessage[],
  users: Map<string, User>,
  preferredLanguage: string,
  context?: TranslationDisplayContext,
): Message[] {
  const originals = new Map(items.map((item) => [item.id, item]));

  return items.map((item) => {
    const message = toMessage(item, users, preferredLanguage, context);
    const original = item.reply_to_message_id ? originals.get(item.reply_to_message_id) : undefined;
    if (!message.replyTo || !original) return message;

    const originalSender = users.get(original.sender_id);
    const replyLanguage = context?.isDirect && original.sender_id === context.currentUserId
      ? context.recipientLanguage
      : preferredLanguage;
    const translatedReply = original.translations.find(
      (translation) => translation.target_language === replyLanguage,
    );
    return {
      ...message,
      replyTo: {
        id: original.id,
        senderName: originalSender?.name || "Message",
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
  const body = await parseJson<T & ApiErrorBody>(response);
  if (!response.ok) throw new Error(getApiErrorMessage(body, "Request failed"));
  return body as T;
}

export function getMe(token: string) { return request<AuthUser>("/api/v1/auth/me", token); }
export function listUsers(token: string, query: string) { return request<ApiUser[]>(`/api/v1/users?q=${encodeURIComponent(query)}`, token); }
export function listConversations(token: string) { return request<ApiConversation[]>("/api/v1/conversations", token); }
export function getAssistantConversation(token: string) { return request<ApiConversation>("/api/v1/assistant/conversation", token, { method: "POST" }); }
export function getMessages(token: string, conversationId: string) { return request<ApiMessage[]>(`/api/v1/conversations/${conversationId}/messages`, token); }
export function searchMessages(token: string, conversationId: string, query: string) {
  return request<ApiMessageSearchResponse>(
    `/api/v1/conversations/${conversationId}/messages/search?q=${encodeURIComponent(query)}`,
    token,
  );
}
export function listAttachments(token: string, conversationId: string) {
  return request<ApiAttachment[]>(`/api/v1/conversations/${conversationId}/attachments`, token);
}
export function createConversation(token: string, type: "direct" | "group", memberIds: string[], title?: string) {
  return request<ApiConversation>("/api/v1/conversations", token, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ type, member_ids: memberIds, title }) });
}
export function updateConversationPreferences(
  token: string,
  conversationId: string,
  changes: { is_pinned?: boolean; is_muted?: boolean },
) {
  return request<ApiConversation>(`/api/v1/conversations/${conversationId}/preferences`, token, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(changes),
  });
}
export function leaveConversation(token: string, conversationId: string) {
  return request<void>(`/api/v1/conversations/${conversationId}/leave`, token, { method: "POST" });
}
export function blockContact(token: string, userId: string) {
  return request<void>(`/api/v1/users/${userId}/block`, token, { method: "PUT" });
}
export function markRead(token: string, conversationId: string) { return request<void>(`/api/v1/conversations/${conversationId}/read`, token, { method: "POST" }); }
export function deleteMessage(token: string, conversationId: string, messageId: string) { return request<void>(`/api/v1/conversations/${conversationId}/messages/${messageId}`, token, { method: "DELETE" }); }
export function saveMessage(token: string, conversationId: string, messageId: string) {
  return request<{ message_id: string; is_saved: boolean }>(`/api/v1/conversations/${conversationId}/messages/${messageId}/saved`, token, { method: "PUT" });
}
export function unsaveMessage(token: string, conversationId: string, messageId: string) {
  return request<{ message_id: string; is_saved: boolean }>(`/api/v1/conversations/${conversationId}/messages/${messageId}/saved`, token, { method: "DELETE" });
}
export function listSavedMessages(
  token: string,
  params?: {
    limit?: number;
    before_created_at?: string;
    before_id?: string;
  },
) {
  const search = new URLSearchParams();
  if (params?.limit !== undefined) search.set("limit", String(params.limit));
  if (params?.before_created_at) search.set("before_created_at", params.before_created_at);
  if (params?.before_id) search.set("before_id", params.before_id);
  const query = search.toString();
  return request<ApiSavedMessagesPage>(`/api/v1/saved-messages${query ? `?${query}` : ""}`, token);
}
export function addReaction(token: string, conversationId: string, messageId: string, emoji: string) {
  return request<{ message_id: string; reactions: ApiMessageReaction[] }>(`/api/v1/conversations/${conversationId}/messages/${messageId}/reactions`, token, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ emoji }),
  });
}
export function removeReaction(token: string, conversationId: string, messageId: string, emoji: string) {
  return request<{ message_id: string; reactions: ApiMessageReaction[] }>(`/api/v1/conversations/${conversationId}/messages/${messageId}/reactions`, token, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ emoji }),
  });
}
export function retryTranslation(token: string, conversationId: string, messageId: string, reviewRecipient = false) {
  const query = reviewRecipient ? "?review_recipient=true" : "";
  return request<{ message_id: string; status: "scheduled" }>(`/api/v1/conversations/${conversationId}/messages/${messageId}/translate${query}`, token, { method: "POST" });
}
export function retryVoiceTranscription(token: string, messageId: string) {
  return request<{
    message_id: string;
    conversation_id: string;
    transcription_status: "pending";
    status: "scheduled";
  }>(`/api/v1/messages/${messageId}/transcription/retry`, token, { method: "POST" });
}
export function getUserSettings(token: string) {
  return request<ApiUserSettings>("/api/v1/auth/me/settings", token);
}
export function updateUserSettings(token: string, changes: Partial<ApiUserSettings>) {
  return request<ApiUserSettings>("/api/v1/auth/me/settings", token, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(changes),
  });
}
export function updateProfile(token: string, changes: { display_name?: string; bio?: string }) {
  return request<AuthUser>("/api/v1/auth/me", token, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(changes),
  });
}
export function addGroupMembers(token: string, conversationId: string, userIds: string[]) { return request<void>(`/api/v1/conversations/${conversationId}/members`, token, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ user_ids: userIds }) }); }
export function removeGroupMember(token: string, conversationId: string, userId: string) { return request<void>(`/api/v1/conversations/${conversationId}/members/${userId}`, token, { method: "DELETE" }); }
export function updateGroupRole(token: string, conversationId: string, userId: string, role: "admin" | "member") { return request<void>(`/api/v1/conversations/${conversationId}/members/${userId}/role`, token, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ role }) }); }
export function transferGroupOwnership(token: string, conversationId: string, userId: string) { return request<void>(`/api/v1/conversations/${conversationId}/owner`, token, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ user_id: userId }) }); }
export function updateGroupDetails(token: string, conversationId: string, title: string, description: string) { return request<void>(`/api/v1/conversations/${conversationId}`, token, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title, description: description.trim() || null }) }); }
export function leaveGroup(token: string, conversationId: string) { return request<void>(`/api/v1/conversations/${conversationId}/leave`, token, { method: "POST" }); }
export function deleteGroup(token: string, conversationId: string) { return request<void>(`/api/v1/conversations/${conversationId}`, token, { method: "DELETE" }); }
export function uploadAttachment(token: string, conversationId: string, file: File) {
  const form = new FormData(); form.append("file", file);
  return request<ApiAttachment>(`/api/v1/conversations/${conversationId}/attachments`, token, { method: "POST", body: form });
}
export async function fetchAttachmentBlob(token: string, attachment: MessageAttachment) {
  const response = await fetch(attachment.url, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) {
    const body = await parseJson<ApiErrorBody>(response);
    throw new Error(getApiErrorMessage(body, "Could not download file"));
  }
  return response.blob();
}
export async function downloadAttachment(token: string, attachment: MessageAttachment) {
  const objectUrl = URL.createObjectURL(await fetchAttachmentBlob(token, attachment));
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = attachment.name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
}
export function submitTranslationFeedback(token: string, translationId: string, rating: 1 | 5) {
  return request<{ feedback_id: string }>(`/api/v1/translations/${translationId}/feedback`, token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rating }),
  });
}
export function submitTranslationEdit(token: string, translationId: string, editedText: string) {
  return request<{ edit_id: string; edited_text: string }>(`/api/v1/translations/${translationId}/edits`, token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ edited_text: editedText }),
  });
}

export function startCall(token: string, conversationId: string, callType: "voice" | "video") {
  return request<ApiCall>(`/api/v1/conversations/${conversationId}/calls`, token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ call_type: callType }),
  });
}

export function acceptCall(token: string, callId: string) {
  return request<ApiCall>(`/api/v1/calls/${callId}/accept`, token, { method: "POST" });
}

export function joinCall(token: string, callId: string) {
  return request<ApiCall>(`/api/v1/calls/${callId}/join`, token);
}

export function rejectCall(token: string, callId: string) {
  return request<ApiCall>(`/api/v1/calls/${callId}/reject`, token, { method: "POST" });
}

export function endCall(token: string, callId: string) {
  return request<ApiCall>(`/api/v1/calls/${callId}/end`, token, { method: "POST" });
}
