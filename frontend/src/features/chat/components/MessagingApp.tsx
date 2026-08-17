"use client";

import { memo, useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent, type FormEvent, type ReactNode, type Ref } from "react";
import { useRouter } from "next/navigation";
import {
  Avatar,
  ChatContainer,
  TypingIndicator,
  Conversation,
  ConversationHeader,
  ConversationList,
  InputToolbox,
  MainContainer,
  Message,
  MessageGroup,
  MessageInput,
  MessageList,
  MessageSeparator,
  Search,
  Sidebar,
} from "@chatscope/chat-ui-kit-react";
import Link from "next/link";
import { BarChart3, Forward, Info, MessagesSquare, MoreVertical, PencilLine, Settings, ThumbsDown, ThumbsUp, UserRoundPlus, X } from "lucide-react";
import { logoutSession } from "@/shared/lib/api";
import { clearSession, getStoredRefreshToken, getStoredUser, restoreSession } from "@/shared/lib/auth-session";
import {
  createConversation,
  deleteMessage,
  downloadAttachment,
  editMessage,
  getMessages,
  listConversations,
  markConversationRead,
  searchUsers,
  submitTranslationEdit,
  submitTranslationFeedback,
  uploadAttachment,
  type Conversation as ApiConversation,
  type ConversationMember,
  type HistoryMessage,
} from "@/shared/lib/chat-api";
import { DEFAULT_LANGUAGE, languageLabel, type LanguageCode } from "@/shared/lib/constants";
import { formatUiText, uiText, type UiTextKey } from "@/shared/lib/ui-text";
import { useDocumentMetadata, useInterfaceLanguage } from "@/shared/lib/use-ui-text";
import { useWebSocket, type MessageDeleted, type MessageUpdated, type MessageRead, type RealtimeMessage, type TranslationCompleted, type TypingNotice } from "@/shared/lib/use-websocket";
import EmojiPicker from "@/shared/ui/EmojiPicker";
import Logo from "@/shared/ui/Logo";
import TranslationToggleSwitch from "@/shared/ui/TranslationToggleSwitch";
import styles from "./MessagingApp.module.css";


/**
 * How long a newly arrived message keeps saying "đang dịch…".
 *
 * The server sends nothing at all when a message is already in the reader's
 * language, so the client cannot tell "translating" from "no translation is
 * coming" — it can only stop waiting.
 */
const TRANSLATION_WAIT_MS = 8000;

/**
 * Shortest query the directory search accepts, and how long typing must pause.
 *
 * Two characters is the server's own minimum (docs/CONTRACT.md §3.1) — sending
 * one would only earn a 422. The pause keeps one request per word typed rather
 * than one per keystroke.
 */
const MIN_USER_QUERY_LENGTH = 2;
const USER_SEARCH_DEBOUNCE_MS = 250;

/** How often a still-typing notice repeats, and when silence ends it. */
const TYPING_PING_MS = 2000;
const TYPING_IDLE_MS = 3000;

type Delivery = "sending" | "delivered" | "read" | "failed";
type PendingSend = {
  clientMessageId: string;
  conversationId: string;
  text: string;
  attachmentId: string | null;
  replyToMessageId: string | null;
};

type ChatMessage = {
  /** Server id once persisted; the client id until message_created arrives. */
  id: string;
  clientMessageId?: string;
  author: "me" | "them";
  senderId: string;
  originalText: string;
  translatedText?: string;
  translationId?: string;
  isFallback?: boolean;
  sourceLanguage?: string;
  /** Which language `translatedText` is in — mine when reading, the other
   *  person's when this is my own message in a one-to-one chat (§3.10). */
  translationLanguage?: string;
  /** F-04: the reader flipped this bubble away from its default view. */
  flipped?: boolean;
  /** F-05: this account's own verdict on the translation, if it has one. */
  myRating?: number | null;
  /** Legacy private suggestion; still read from history, no longer written. */
  myCorrection?: string | null;
  /** F-05 (§3.10): this account's own newest wording, nobody else's. */
  myEdit?: { editId: string; editedText: string; editedAt: string } | null;
  /** Set once no translation can still be expected for this reader. */
  translationSettled?: boolean;
  sentAt?: string;
  delivery?: Delivery;
  edited?: boolean;
  deleted?: boolean;
  reply?: string;
  /** Which message this answers; the quote is resolved from the thread. */
  replyToMessageId?: string;
  attachmentId?: string | null;
  file?: { name: string; size?: number; url?: string };
};

/** Stands in until the conversation list has loaded, or when there are none. */
const EMPTY_CONVERSATION: ConversationItem = {
  id: "",
  type: "direct",
  name: "",
  initials: "—",
  preview: "",
  members: [],
  empty: true,
};

/**
 * Whether the bubble is currently showing the original rather than a translation.
 *
 * The two directions start from opposite defaults, which is the whole subtlety
 * here: a message I received opens on the translation, because that is the
 * version I can read, while a message I sent opens on my own words — nobody
 * wants their own sentence replaced by a language they do not speak a second
 * after pressing send. One flag with two defaults keeps the switch's own labels
 * ("đang hiện bản gốc" / "đang hiện bản dịch") true on both sides.
 */
function showingOriginal(message: ChatMessage) {
  const startsOnOriginal = message.author === "me";
  return message.flipped ? !startsOnOriginal : startsOnOriginal;
}

/** What the bubble shows, given the direction and any flip. */
function displayText(message: ChatMessage) {
  if (!message.translatedText || showingOriginal(message)) return message.originalText;
  return message.translatedText;
}

type ConversationItem = {
  id: string;
  name: string;
  initials: string;
  preview: string;
  previewWithdrawn?: boolean;
  empty?: boolean;
  /**
   * Raw timestamp of the newest message. Deliberately not stored in display
   * form: "vừa xong" is only true for a minute, so the label is derived at
   * render and a ticker re-renders the list.
   */
  lastActivityAt?: string | null;
  /** Which message the preview is showing, so its translation can replace it. */
  lastMessageId?: string;
  /** Needed beyond display: the F-05 controls on my own bubbles exist only in
   *  a one-to-one chat (docs/CONTRACT.md §3.10). */
  type: "direct" | "group";
  members: ConversationMember[];
  unread?: number;
  mention?: boolean;
  muted?: boolean;
  pinned?: boolean;
  online?: boolean;
};

/**
 * Calendar day in the reader's own timezone.
 *
 * Deliberately not the first ten characters of the ISO string: those are the
 * UTC day, so east of UTC every message sent before 07:00 local was filed under
 * yesterday and "Hôm nay" only began mid-morning.
 */
function dayKey(value?: string | Date) {
  if (!value) return "";
  const date = value instanceof Date ? value : new Date(value);
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
}

// Messages only exist after a fetch, so locale formatting runs on the client
// and cannot disagree with server-rendered markup.
function dateLabel(value: string | undefined, lang: LanguageCode) {
  const date = value ? new Date(value) : new Date();
  const today = new Date();
  if (dayKey(date) === dayKey(today)) return uiText(lang, "chat.today");
  return new Intl.DateTimeFormat(lang, date.getFullYear() === today.getFullYear()
    ? { weekday: "long", day: "2-digit", month: "2-digit" }
    : { weekday: "long", day: "2-digit", month: "2-digit", year: "numeric" }).format(date);
}

function clockTime(value: string | undefined, lang: LanguageCode) {
  const date = value ? new Date(value) : new Date();
  return new Intl.DateTimeFormat(lang, { hour: "2-digit", minute: "2-digit" }).format(date);
}

function messageTime(value: string | undefined, lang: LanguageCode) {
  if (!value) return "";
  const date = new Date(value);
  const today = new Date();
  const clock = clockTime(value, lang);
  if (dayKey(date) === dayKey(today)) return clock;
  const dateOptions: Intl.DateTimeFormatOptions = date.getFullYear() === today.getFullYear()
    ? { day: "2-digit", month: "2-digit" }
    : { day: "2-digit", month: "2-digit", year: "numeric" };
  return `${new Intl.DateTimeFormat(lang, dateOptions).format(date)} · ${clock}`;
}

/**
 * How long ago, in the shortest form that still reads unambiguously.
 *
 * The conversation list is scanned, not read, so it gets "5 phút" rather than a
 * timestamp — and falls back to a date once "N ngày" stops being informative.
 */
function relativeTime(value: string | null | undefined, lang: LanguageCode) {
  if (!value) return "";
  const then = new Date(value);
  const elapsedSeconds = Math.max(0, (Date.now() - then.getTime()) / 1000);
  if (elapsedSeconds < 60) return uiText(lang, "chat.justNow");
  if (elapsedSeconds < 3600) return formatUiText(lang, "chat.minutesAgo", { count: Math.floor(elapsedSeconds / 60) });
  if (elapsedSeconds < 86400) return formatUiText(lang, "chat.hoursAgo", { count: Math.floor(elapsedSeconds / 3600) });
  if (elapsedSeconds < 604800) return formatUiText(lang, "chat.daysAgo", { count: Math.floor(elapsedSeconds / 86400) });
  return new Intl.DateTimeFormat(lang, then.getFullYear() === new Date().getFullYear()
    ? { day: "2-digit", month: "2-digit" }
    : { day: "2-digit", month: "2-digit", year: "2-digit" }).format(then);
}

function deliveryIndicator(delivery: Delivery | undefined, lang: LanguageCode) {
  if (delivery === "sending") return { symbol: "◷", label: uiText(lang, "chat.sending"), className: "sending" };
  if (delivery === "delivered") return { symbol: "✓", label: uiText(lang, "chat.delivered"), className: "delivered" };
  if (delivery === "read") return { symbol: "✓✓", label: uiText(lang, "chat.read"), className: "read" };
  return null;
}

function formatFileSize(bytes: number, lang: LanguageCode) {
  const formatter = new Intl.NumberFormat(lang, { maximumFractionDigits: bytes < 1024 * 1024 ? 0 : 1 });
  if (bytes < 1024 * 1024) return `${formatter.format(Math.max(1, Math.round(bytes / 1024)))} KB`;
  return `${formatter.format(bytes / (1024 * 1024))} MB`;
}

function fileKind(name: string, lang: LanguageCode) {
  const extension = name.split(".").pop()?.toUpperCase();
  return extension && extension.length <= 4 ? extension : uiText(lang, "chat.file");
}

function highlight(text: string, query: string): ReactNode {
  const cleaned = query.trim();
  if (!cleaned) return text;
  const index = text.toLocaleLowerCase().indexOf(cleaned.toLocaleLowerCase());
  if (index < 0) return text;
  return <>{text.slice(0, index)}<mark className={styles.match}>{text.slice(index, index + cleaned.length)}</mark>{text.slice(index + cleaned.length)}</>;
}

/** Turn an API conversation into what the sidebar renders. */
function toConversationItem(conversation: ApiConversation, myId: string): ConversationItem {
  const others = conversation.members.filter((member) => member.id !== myId);
  const name = conversation.title
    || others.map((member) => member.display_name || member.email.split("@")[0]).join(", ");
  return {
    id: conversation.id,
    name,
    initials: initialsOf(name),
    // A withdrawn newest message comes back with empty text (§3.6), which would
    // leave the row with no second line at all. The server cannot supply the
    // wording — it is interface copy and belongs to the reader's language — so
    // the client says it. Text can never be empty otherwise: the send endpoint
    // rejects a blank message, so "" plus a timestamp means withdrawn.
    preview: conversation.last_message || "",
    previewWithdrawn: !conversation.last_message && Boolean(conversation.last_message_at),
    lastActivityAt: conversation.last_message_at,
    unread: conversation.unread_count || undefined,
    // Anyone but me holding a socket makes the row read as active.
    online: others.some((member) => conversation.online_member_ids.includes(member.id)),
    type: conversation.type,
    members: conversation.members,
  };
}

function conversationName(conversation: ConversationItem, lang: LanguageCode): string {
  if (conversation.empty) return uiText(lang, "chat.emptyConversation");
  return conversation.name || uiText(lang, "chat.myNotes");
}

function conversationSubtitle(conversation: ConversationItem, myId: string, lang: LanguageCode): string {
  if (conversation.empty) return uiText(lang, "chat.emptyConversationHint");
  const others = conversation.members.filter((member) => member.id !== myId);
  if (conversation.type !== "group") {
    return others.map((member) => languageLabel(member.preferred_language)).join(", ");
  }
  const languages = [...new Set(conversation.members.map((member) => member.preferred_language))]
    .map(languageLabel)
    .join(", ");
  return formatUiText(lang, "chat.groupSummary", {
    count: conversation.members.length,
    language: languages,
  });
}

function conversationPreview(conversation: ConversationItem, lang: LanguageCode): string {
  return conversation.previewWithdrawn ? uiText(lang, "chat.withdrawn") : conversation.preview;
}

/**
 * The language the other person reads, in a one-to-one chat.
 *
 * Undefined for a group, and that absence is load-bearing: it is what stops the
 * sender's own bubbles from getting a toggle, a rating and an edit box in a
 * conversation where their message has several translations and no single one
 * of them is "the" translation (docs/CONTRACT.md §3.10).
 */
function counterpartLanguageOf(conversation: ConversationItem, myId: string) {
  if (conversation.type !== "direct") return undefined;
  const other = conversation.members.find((member) => member.id !== myId);
  return other?.preferred_language;
}

/**
 * Turn a history row into a bubble, attaching the one translation this bubble's
 * controls act on.
 *
 * For a message I received that is the translation into my own language. For a
 * message I sent it is the one the other person reads, and only in a
 * one-to-one chat — `counterpartLanguage` is undefined in a group, where a
 * message has several translations and none of them belongs to my bubble, so
 * nothing is attached and no controls appear (docs/CONTRACT.md §3.10).
 */
function toChatMessage(
  row: HistoryMessage,
  myId: string,
  myLanguage: string,
  counterpartLanguage?: string,
): ChatMessage {
  const outgoing = row.sender_id === myId;
  const wanted = outgoing ? counterpartLanguage : myLanguage;
  const attached = wanted
    ? row.translations.find((translation) => translation.target_language === wanted)
    : undefined;
  return {
    id: row.id,
    clientMessageId: row.client_message_id,
    author: outgoing ? "me" : "them",
    senderId: row.sender_id,
    originalText: row.original_text,
    translatedText: attached?.translated_text,
    translationId: attached?.translation_id,
    translationLanguage: attached?.target_language,
    isFallback: attached?.is_fallback,
    myRating: attached?.my_rating ?? null,
    myCorrection: attached?.my_correction ?? null,
    myEdit: attached?.my_edit
      ? {
          editId: attached.my_edit.edit_id,
          editedText: attached.my_edit.edited_text,
          editedAt: attached.my_edit.edited_at,
        }
      : null,
    edited: Boolean(row.edited_at),
    deleted: Boolean(row.deleted_at),
    replyToMessageId: row.reply_to_message_id ?? undefined,
    attachmentId: row.attachment?.id ?? null,
    file: row.attachment
      ? {
          name: row.attachment.filename,
          size: row.attachment.size,
          url: row.attachment.download_url,
        }
      : undefined,
    sourceLanguage: row.source_language,
    sentAt: row.created_at,
    delivery: "delivered",
    // History is complete: whatever translations exist are already attached.
    translationSettled: true,
  };
}

/**
 * History remains canonical after a reconnect, but any optimistic bubbles that
 * the server has not persisted yet must survive the replacement. Both ids are
 * checked because the server row and local bubble deliberately have different
 * identities until message_created acknowledges the send.
 */
function mergeHistory(
  current: Record<string, ChatMessage[]>,
  conversationId: string,
  rows: HistoryMessage[],
  myId: string,
  myLanguage: string,
  counterpartLanguage?: string,
): Record<string, ChatMessage[]> {
  const fromServer = rows.map((row) => toChatMessage(row, myId, myLanguage, counterpartLanguage));
  const known = new Set<string>();
  for (const row of rows) {
    known.add(row.id);
    if (row.client_message_id) known.add(row.client_message_id);
  }
  const stillPending = (current[conversationId] ?? []).filter((message) =>
    !known.has(message.id)
    && !(message.clientMessageId && known.has(message.clientMessageId)),
  );
  return { ...current, [conversationId]: [...fromServer, ...stillPending] };
}

function initialsOf(value: string) {
  const name = value.split("@")[0];
  const parts = name.split(/[.\s_-]+/).filter(Boolean);
  const letters = parts.length >= 2 ? parts[0][0] + parts[1][0] : name.slice(0, 2);
  return letters.toUpperCase();
}

/**
 * Thumbs map onto the ends of the server's 1-5 range; a correction with no
 * thumb sits in the middle rather than being recorded as a silent complaint.
 */
const RATING_UP = 5;
const RATING_NEUTRAL = 3;
const RATING_DOWN = 1;

type TranslationEditFormProps = {
  message: ChatMessage;
  lang: LanguageCode;
  onSaveEdit: (message: ChatMessage, editedText: string) => Promise<boolean>;
  onClose: () => void;
};

/**
 * The panel behind the pencil: this account's own wording for a translation.
 *
 * Two jobs in one box, which is what the pencil being a toggle asks for — it
 * shows the wording already saved and lets it be rewritten. Opening it
 * pre-filled rather than blank is the difference between "read what I wrote
 * last time" and "start again", and §3.10 says the reader gets the former.
 *
 * The bubble above keeps showing the machine's translation throughout. Nothing
 * here is sent to anyone else, so there is no realtime event to wait for and
 * the panel closes as soon as the server confirms.
 */
function TranslationEditForm({ message, lang, onSaveEdit, onClose }: TranslationEditFormProps) {
  const saved = message.myEdit?.editedText ?? "";
  const [draft, setDraft] = useState(saved);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const save = async (event: FormEvent) => {
    event.preventDefault();
    const editedText = draft.trim();
    if (!editedText || saving) return;
    setError("");
    setSaving(true);
    const stored = await onSaveEdit(message, editedText);
    setSaving(false);
    if (stored) onClose();
    else setError(uiText(lang, "chat.saveEditFailed"));
  };

  return (
    <form className={styles.correctionForm} onSubmit={save}>
      <label htmlFor={`edit-${message.id}`}>{uiText(lang, "chat.correctTranslation")}</label>
      {/* States what the box is for, because "private" is not something a text
          field can show on its own and the reader would otherwise reasonably
          assume they are correcting the message for everyone. */}
      <p className={styles.correctionHint}>
        {uiText(lang, "chat.correctTranslationHint")}
      </p>
      <textarea
        id={`edit-${message.id}`}
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        placeholder={uiText(lang, "chat.correctTranslationPlaceholder")}
        rows={2}
        autoFocus
      />
      {message.myEdit && (
        <p className={styles.correctionHint}>
          {formatUiText(lang, "chat.savedAt", { time: messageTime(message.myEdit.editedAt, lang) })}
        </p>
      )}
      {error && <p role="alert">{error}</p>}
      <div>
        <button type="button" onClick={onClose}>{uiText(lang, "common.close")}</button>
        <button type="submit" disabled={!draft.trim() || draft.trim() === saved || saving}>
          {saving ? uiText(lang, "chat.saving") : uiText(lang, "chat.saveEdit")}
        </button>
      </div>
    </form>
  );
}

type MessageClusterProps = {
  messages: ChatMessage[];
  name: string;
  initials: string;
  lang: LanguageCode;
  searchQuery: string;
  onReply: (message: ChatMessage) => void;
  onRetry: (id: string) => void;
  onEdit: (message: ChatMessage) => void;
  onDelete: (id: string) => void;
  openMenuId: string | null;
  onToggleMenu: (id: string) => void;
  /** F-04: flip one message between its translation and its original. */
  onToggleOriginal: (id: string) => void;
  /** F-05: rate a received translation, or suggest a better one. */
  onRate: (message: ChatMessage, rating: number) => Promise<boolean>;
  /** F-05 (§3.10): store this account's own wording, private to them. */
  onSaveEdit: (message: ChatMessage, editedText: string) => Promise<boolean>;
  onForward: (message: ChatMessage) => void;
  onDownload: (message: ChatMessage) => void;
  /** Message id to its displayed text, for resolving reply quotes. */
  quotes: Record<string, string>;
};

const MessageCluster = memo(function MessageCluster({ messages, name, initials, lang, searchQuery, onReply, onRetry, onEdit, onDelete, openMenuId, onToggleMenu, onToggleOriginal, onRate, onSaveEdit, onForward, onDownload, quotes }: MessageClusterProps) {
  const outgoing = messages[0].author === "me";
  // Which bubble has its edit panel open. The pencil is a disclosure
  // toggle, so at most one is open at a time within a cluster.
  const [editingId, setEditingId] = useState<string | null>(null);
  return (
    <MessageGroup direction={outgoing ? "outgoing" : "incoming"} sender={outgoing ? uiText(lang, "chat.you") : name} avatarPosition={outgoing ? "cr" : "cl"}>
      {!outgoing && <Avatar name={name} size="sm"><span className={styles.initialsAvatar}>{initials}</span></Avatar>}
      <MessageGroup.Messages>
        {messages.map((message, index) => {
          const indicator = deliveryIndicator(message.delivery, lang);
          const position = messages.length === 1 ? "single" : index === 0 ? "first" : index === messages.length - 1 ? "last" : "normal";
          const shown = displayText(message);
          const hasTranslation = Boolean(message.translatedText);
          // Nothing has arrived yet and the deadline has not passed. A message
          // already in this reader's language never gets an event at all, which
          // is why this can only ever be a timeout rather than a completion.
          const awaiting = !outgoing && !hasTranslation && !message.translationSettled;
          // One flag gates the whole group — toggle, rating, edit box. It needs
          // no direction test of its own: a translation is attached to a bubble
          // only when this account may act on it, which for my own messages
          // happens in a one-to-one chat and never in a group (§3.10).
          const canTranslate = hasTranslation && Boolean(message.translationId);
          // Each feedback control is an outline icon until it carries this
          // account's verdict, at which point it fills in.
          const ratedUp = message.myRating === RATING_UP;
          const ratedDown = message.myRating === RATING_DOWN;
          const edited = Boolean(message.myEdit);
          // `reply` is only set on a message this tab just sent; everything
          // loaded from history resolves its quote through the id instead.
          const quoted = message.reply
            ?? (message.replyToMessageId ? quotes[message.replyToMessageId] : undefined);
          return (
            <Message key={message.id} model={{ message: shown, sender: outgoing ? uiText(lang, "chat.you") : name, sentTime: clockTime(message.sentAt, lang), direction: outgoing ? "outgoing" : "incoming", position }}>
              <Message.Header><time className={styles.messageTimestamp}>{messageTime(message.sentAt, lang)}{message.edited && !message.deleted && <span className={styles.editedMark}>{uiText(lang, "chat.edited")}</span>}</time></Message.Header>
              <Message.CustomContent>
                <div className={styles.messageBubble}>
                  <div className={styles.messageContent}>
                  {quoted && <blockquote className={styles.replyPreview}>{quoted}</blockquote>}
                  <p className={message.deleted ? styles.deletedMessage : undefined}>{message.deleted ? uiText(lang, "chat.withdrawn") : highlight(shown, searchQuery)}</p>
                  {message.file && !message.deleted && <button className={styles.fileCard} type="button" aria-label={formatUiText(lang, "chat.download", { name: message.file.name })} onClick={() => onDownload(message)}><span>{fileKind(message.file.name, lang)}</span><strong>{message.file.name}<small>{message.file.size === undefined ? fileKind(message.file.name, lang) : `${fileKind(message.file.name, lang)} · ${formatFileSize(message.file.size, lang)}`}</small></strong><b aria-hidden="true">↓</b></button>}
                  </div>
                  {!message.deleted && <>
                    <div className={styles.messageQuickActions} aria-label={uiText(lang, "chat.messageActions")}>
                      <button type="button" aria-label={uiText(lang, "chat.openMessageActions")} title={uiText(lang, "chat.actions")} aria-expanded={openMenuId === message.id} aria-haspopup="menu" onClick={() => onToggleMenu(message.id)}>
                        <MoreVertical size={14} strokeWidth={2} aria-hidden="true" />
                      </button>
                    </div>
                    {openMenuId === message.id && <div className={styles.messageMenu} role="menu">
                      <button type="button" role="menuitem" onClick={() => { onReply(message); onToggleMenu(message.id); }}>{uiText(lang, "chat.reply")}</button>
                      {outgoing && <button type="button" role="menuitem" onClick={() => { onEdit(message); onToggleMenu(message.id); }}>{uiText(lang, "chat.edit")}</button>}
                      <button type="button" role="menuitem" onClick={() => { onForward(message); onToggleMenu(message.id); }}>{uiText(lang, "chat.forward")}</button>
                      {/* Withdrawal is the sender's alone (docs/CONTRACT.md §3.6);
                          offering it on someone else's message would only 403. */}
                      {outgoing && <button type="button" role="menuitem" onClick={() => { onDelete(message.id); onToggleMenu(message.id); }}>{uiText(lang, "chat.removeMessage")}</button>}
                    </div>}
                    {editingId === message.id && (
                        <TranslationEditForm
                          message={message}
                          lang={lang}
                        onSaveEdit={onSaveEdit}
                        onClose={() => setEditingId(null)}
                      />
                    )}
                  </>}
                </div>
              </Message.CustomContent>
              <Message.Footer>
                {/* Everything about the translation lives under the bubble and
                    only on a message that actually has one. On a message I
                    received that is the version in my language; on one I sent,
                    in a one-to-one chat, it is the version my reader got. */}
                {canTranslate && !message.deleted && (
                  <span className={styles.translationTools}>
                    <TranslationToggleSwitch
                      className={styles.translationSwitch}
                      showOriginal={showingOriginal(message)}
                      onToggle={() => onToggleOriginal(message.id)}
                    />
                    <button
                      type="button"
                      aria-label={ratedUp ? uiText(lang, "chat.removePositiveRating") : uiText(lang, "chat.positiveTranslation")}
                      title={ratedUp ? uiText(lang, "chat.removePositiveRating") : uiText(lang, "chat.positiveTranslation")}
                      aria-pressed={ratedUp}
                      className={styles.feedbackButton}
                      onClick={() => onRate(message, RATING_UP)}
                    >
                      <ThumbsUp size={14} strokeWidth={1.75} fill={ratedUp ? "currentColor" : "none"} aria-hidden="true" />
                    </button>
                    <button
                      type="button"
                      aria-label={ratedDown ? uiText(lang, "chat.removeNegativeRating") : uiText(lang, "chat.negativeTranslation")}
                      title={ratedDown ? uiText(lang, "chat.removeNegativeRating") : uiText(lang, "chat.negativeTranslation")}
                      aria-pressed={ratedDown}
                      className={styles.feedbackButton}
                      onClick={() => onRate(message, RATING_DOWN)}
                    >
                      <ThumbsDown size={14} strokeWidth={1.75} fill={ratedDown ? "currentColor" : "none"} aria-hidden="true" />
                    </button>
                    <button
                      type="button"
                      aria-label={edited ? uiText(lang, "chat.viewYourTranslationEdit") : uiText(lang, "chat.editTranslationForYou")}
                      title={edited ? uiText(lang, "chat.viewYourEdit") : uiText(lang, "chat.editTranslationForYou")}
                      aria-expanded={editingId === message.id}
                      className={styles.feedbackButton}
                      onClick={() => setEditingId((current) => current === message.id ? null : message.id)}
                    >
                      <PencilLine size={14} strokeWidth={1.75} fill={edited ? "currentColor" : "none"} aria-hidden="true" />
                    </button>
                  </span>
                )}
                {message.isFallback && (
                  <span className={styles.deliveryIcon} role="img" aria-label={uiText(lang, "chat.fallbackTranslation")} title={uiText(lang, "chat.fallbackTranslation")}>⚠</span>
                )}
                {awaiting && <span className={styles.messageTimestamp}>{uiText(lang, "chat.translating")}</span>}
                {message.delivery === "failed" && <button className={styles.retryButton} type="button" onClick={() => onRetry(message.id)}>{uiText(lang, "chat.sendFailedRetry")}</button>}
                {/* Delivery is only ever about my own messages — a tick under
                    someone else's bubble would claim I had sent it. */}
                {outgoing && indicator && <span className={`${styles.deliveryIcon} ${styles[indicator.className]}`} role="img" aria-label={indicator.label} title={indicator.label}>{indicator.symbol}</span>}
              </Message.Footer>
            </Message>
          );
        })}
      </MessageGroup.Messages>
    </MessageGroup>
  );
});

export default function MessagingApp() {
  useDocumentMetadata("meta.title.chat", "meta.desc.chat");
  const router = useRouter();
  const lang = useInterfaceLanguage();

  // Read once per mount rather than copied into state by an effect: the signed
  // in account cannot change without a navigation.
  const me = useMemo(() => getStoredUser(), []);
  const myId = me?.id ?? "";
  const myLanguage = me?.preferred_language ?? DEFAULT_LANGUAGE;
  const accountName = me ? me.display_name || me.username || me.email.split("@")[0] : "";
  const accountEmail = me?.email ?? "";

  const [activeId, setActiveId] = useState("");
  const [mobileView, setMobileView] = useState<"list" | "chat">("chat");
  const [query, setQuery] = useState("");
  // One dialog for both kinds of conversation: a direct chat and a group start
  // the same way — by finding the people — and splitting them into two screens
  // would duplicate the search that is the hard half of the job.
  const [showComposer, setShowComposer] = useState(false);
  const [composerMode, setComposerMode] = useState<"direct" | "group">("direct");
  const [groupName, setGroupName] = useState("");
  // The people themselves, not their ids: a chosen person must keep their name
  // on screen after the search that found them is typed over.
  const [selectedMembers, setSelectedMembers] = useState<ConversationMember[]>([]);
  const [userQuery, setUserQuery] = useState("");
  // Results carry the query they answer, so the people found for "an" are never
  // shown for a moment under "ann" while the next request is in flight.
  const [userResults, setUserResults] = useState<{ query: string; members: ConversationMember[] }>(
    { query: "", members: [] },
  );
  const [composerError, setComposerError] = useState<UiTextKey | null>(null);
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const [conversationItems, setConversationItems] = useState<ConversationItem[]>([]);
  const [messages, setMessages] = useState<Record<string, ChatMessage[]>>({});
  const [loadedThreads, setLoadedThreads] = useState<Record<string, boolean>>({});
  const [notice, setNotice] = useState<UiTextKey | null>(null);
  const [replying, setReplying] = useState<ChatMessage | null>(null);
  const [forwarding, setForwarding] = useState<ChatMessage | null>(null);
  // Only the setter is used: see the ticker effect below.
  const [, setElapsedTick] = useState(0);
  const [typingBy, setTypingBy] = useState<Record<string, string[]>>({});
  const typingStopTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const typingSentAt = useRef(0);
  // Read by socket handlers, which are memoised once and would otherwise close
  // over the conversation that was open when the socket was created.
  const activeIdRef = useRef(activeId);
  const conversationItemsRef = useRef<ConversationItem[]>([]);
  const loadedThreadsRef = useRef<Record<string, boolean>>({});
  const pendingSendsRef = useRef<Map<string, PendingSend>>(new Map());
  const [editing, setEditing] = useState<ChatMessage | null>(null);
  const [messageQuery, setMessageQuery] = useState("");
  const [draft, setDraft] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  /** Id the server gave the uploaded bytes, until a message claims them. */
  const [pendingAttachmentId, setPendingAttachmentId] = useState<string | null>(null);
  const [openMessageMenuId, setOpenMessageMenuId] = useState<string | null>(null);
  const [showAccountMenu, setShowAccountMenu] = useState(false);
  const [showConversationInfo, setShowConversationInfo] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messageListRef = useRef<{ scrollToBottom: (behavior: ScrollBehavior) => void }>(null);

  /** Stop waiting for a translation that is never going to arrive. */
  const settleTranslation = useCallback((conversationId: string, messageId: string) => {
    setMessages((current) => {
      const thread = current[conversationId];
      if (!thread) return current;
      return {
        ...current,
        [conversationId]: thread.map((existing) =>
          existing.id === messageId ? { ...existing, translationSettled: true } : existing,
        ),
      };
    });
  }, []);

  /**
   * Move a conversation's preview onto a newer message.
   *
   * Guarded by time so an out-of-order event cannot pull the row backwards onto
   * a message that is no longer the latest one.
   */
  const touchConversation = useCallback((conversationId: string, messageId: string, preview: string, sentAt: string) => {
    setConversationItems((items) => items.map((item) => {
      if (item.id !== conversationId) return item;
      const isNewer = !item.lastActivityAt || Date.parse(sentAt) >= Date.parse(item.lastActivityAt);
      if (!isNewer) return item;
      return {
        ...item,
        preview,
        previewWithdrawn: false,
        lastActivityAt: sentAt,
        lastMessageId: messageId,
      };
    }));
  }, []);

  /**
   * Replace a conversation's preview when the message it quotes is withdrawn.
   *
   * Guarded by `lastMessageId`: withdrawing an older message must not overwrite
   * a preview that has already moved on to a newer one. Without this the
   * sidebar kept showing the text of a message that no longer exists anywhere
   * else in the app — the one place a withdrawal failed to take effect.
   */
  const withdrawPreview = useCallback((conversationId: string, messageId: string, sentAt?: string) => {
    setConversationItems((items) => items.map((item) => {
      if (item.id !== conversationId) return item;
      // `lastMessageId` is only known for messages this tab saw arrive:
      // `GET /conversations` carries the preview text and its timestamp but no
      // id, so after a reload the id is missing and matching on it alone would
      // silently do nothing — which is exactly how the first version of this
      // failed. The timestamp is the fallback: a withdrawal at or after the
      // conversation's newest activity is the previewed message.
      const isPreviewed = item.lastMessageId
        ? item.lastMessageId === messageId
        : Boolean(sentAt) && Boolean(item.lastActivityAt)
          && Date.parse(sentAt!) >= Date.parse(item.lastActivityAt!);
      return isPreviewed ? { ...item, preview: "", previewWithdrawn: true } : item;
    }));
  }, []);

  /** Swap a preview for its translation once one arrives for that message. */
  const retranslatePreview = useCallback((conversationId: string, messageId: string, translated: string) => {
    setConversationItems((items) => items.map((item) =>
      item.id === conversationId && item.lastMessageId === messageId
        ? { ...item, preview: translated, previewWithdrawn: false }
        : item,
    ));
  }, []);

  const applyIncoming = useCallback((message: RealtimeMessage, author: "me" | "them") => {
    window.setTimeout(
      () => settleTranslation(message.conversation_id, message.id),
      TRANSLATION_WAIT_MS,
    );
    touchConversation(message.conversation_id, message.id, message.original_text, message.created_at);
    // A message arriving somewhere the reader is not looking is unread; the one
    // they are looking at was marked read when they opened it.
    if (author === "them" && message.conversation_id !== activeIdRef.current) {
      setConversationItems((items) => items.map((item) => item.id === message.conversation_id
        ? { ...item, unread: (item.unread ?? 0) + 1 }
        : item));
    }
    setMessages((current) => {
      const thread = current[message.conversation_id] ?? [];
      if (thread.some((existing) => existing.id === message.id)) return current;
      const next: ChatMessage = {
        id: message.id,
        author,
        senderId: message.sender_id,
        originalText: message.original_text,
        sentAt: message.created_at,
        delivery: "delivered",
      };
      return { ...current, [message.conversation_id]: [...thread, next] };
    });
  }, [settleTranslation, touchConversation]);

  const recoverConversation = useCallback(async (conversationId: string) => {
    const conversation = conversationItemsRef.current.find((item) => item.id === conversationId);
    const counterpart = conversation ? counterpartLanguageOf(conversation, myId) : undefined;
    try {
      const rows = await getMessages(conversationId, 50);
      setMessages((current) => mergeHistory(
        current,
        conversationId,
        rows,
        myId,
        myLanguage,
        counterpart,
      ));
      const newest = rows.at(-1);
      if (newest) {
        setConversationItems((items) => items.map((item) =>
          item.id === conversationId ? { ...item, lastMessageId: newest.id } : item,
        ));
      }
      setLoadedThreads((current) => ({ ...current, [conversationId]: true }));
    } catch {
      setNotice("chat.loadMessagesFailed");
    }
  }, [myId, myLanguage]);

  const recoverAfterReconnect = useCallback(async (resend: (input: PendingSend) => boolean) => {
    const conversationIds = new Set(Object.keys(loadedThreadsRef.current));
    if (activeIdRef.current) conversationIds.add(activeIdRef.current);
    for (const pending of pendingSendsRef.current.values()) {
      conversationIds.add(pending.conversationId);
    }

    await Promise.all([...conversationIds].map((conversationId) => recoverConversation(conversationId)));

    // A history response may include a message whose acknowledgement was lost.
    // Keep it pending until message_created arrives; the same id makes this
    // resend idempotent on the server.
    for (const pending of pendingSendsRef.current.values()) {
      resend(pending);
    }
  }, [recoverConversation]);

  const socket = useWebSocket({
    onMessageCreated: useCallback((clientMessageId: string, message: RealtimeMessage) => {
      pendingSendsRef.current.delete(clientMessageId);
      // The sender waits for a translation too — they may read a language other
      // than the one they typed in.
      window.setTimeout(
        () => settleTranslation(message.conversation_id, message.id),
        TRANSLATION_WAIT_MS,
      );
      // The sidebar stored the client id when the message was sent, but the
      // translation arrives keyed by the server id — without this swap the
      // preview never picks up the translation of your own messages.
      setConversationItems((items) => items.map((item) =>
        item.id === message.conversation_id && item.lastMessageId === clientMessageId
          ? { ...item, lastMessageId: message.id }
          : item));
      // Swap the optimistic bubble for the server's row, keyed by the id the
      // client minted for exactly this purpose.
      setMessages((current) => {
        const thread = current[message.conversation_id] ?? [];
        if (!thread.some((existing) => existing.clientMessageId === clientMessageId)) return current;
        return {
          ...current,
          [message.conversation_id]: thread.map((existing) =>
            existing.clientMessageId === clientMessageId
              ? { ...existing, id: message.id, delivery: "delivered", sentAt: message.created_at }
              : existing,
          ),
        };
      });
    }, [settleTranslation]),

    onMessageReceived: useCallback((message: RealtimeMessage) => {
      applyIncoming(message, message.sender_id === myId ? "me" : "them");
    }, [applyIncoming, myId]),

    onTranslationCompleted: useCallback((event: TranslationCompleted) => {
      // Two kinds of event arrive here since §4.4 rule 3 grew its exception:
      // the translation into my own language, and — in a one-to-one chat — the
      // one my reader got for a message I sent. Both are attached to their
      // bubble, because both are what the F-05 controls act on; which of them a
      // bubble *shows* is decided by `showingOriginal`, so my own sentence is
      // not rewritten into a language I do not read.
      //
      // The sidebar preview is different: it is one line of text I have to be
      // able to read at a glance, so only my own language ever reaches it.
      if (event.target_language === myLanguage) {
        retranslatePreview(event.conversation_id, event.message_id, event.translated_text);
      }
      setMessages((current) => {
        const thread = current[event.conversation_id];
        if (!thread) return current;
        return {
          ...current,
          [event.conversation_id]: thread.map((existing) =>
            existing.id === event.message_id
              ? {
                  ...existing,
                  translatedText: event.translated_text,
                  translationId: event.translation_id,
                  translationLanguage: event.target_language,
                  isFallback: event.is_fallback,
                  sourceLanguage: event.source_language,
                }
              : existing,
          ),
        };
      });
    }, [myLanguage, retranslatePreview]),

    onTyping: useCallback((event: TypingNotice) => {
      setTypingBy((current) => {
        const inConversation = new Set(current[event.conversation_id] ?? []);
        if (event.is_typing) inConversation.add(event.user_id);
        else inConversation.delete(event.user_id);
        return { ...current, [event.conversation_id]: [...inConversation] };
      });
    }, []),

    onMessageUpdated: useCallback((event: MessageUpdated) => {
      setMessages((current) => {
        const thread = current[event.conversation_id];
        if (!thread) return current;
        return {
          ...current,
          [event.conversation_id]: thread.map((existing) =>
            existing.id === event.message_id
              ? {
                  ...existing,
                  originalText: event.original_text,
                  // Whatever was on screen translated the old wording, and the
                  // server discarded the rating along with it.
                  translatedText: undefined,
                  translationId: undefined,
                  translationLanguage: undefined,
                  translationSettled: false,
                  myRating: null,
                  myCorrection: null,
                  // The edit belonged to the translation that just went away, so
                  // it would otherwise sit behind the pencil as this account's
                  // wording for a sentence nobody sent.
                  myEdit: null,
                  edited: true,
                }
              : existing,
          ),
        };
      });
      // An edit starts a fresh translation, so it needs the same deadline a new
      // message gets — otherwise an edit into the reader's own language, which
      // the server answers with silence, shows "đang dịch…" forever.
      window.setTimeout(
        () => settleTranslation(event.conversation_id, event.message_id),
        TRANSLATION_WAIT_MS,
      );
      touchConversation(event.conversation_id, event.message_id, event.original_text, event.edited_at);
    }, [settleTranslation, touchConversation]),

    onMessageRead: useCallback((event: MessageRead) => {
      // Somebody else caught up, so everything I sent there has been seen.
      setMessages((current) => {
        const thread = current[event.conversation_id];
        if (!thread) return current;
        return {
          ...current,
          [event.conversation_id]: thread.map((existing) =>
            existing.author === "me" && existing.delivery === "delivered"
              ? { ...existing, delivery: "read" }
              : existing,
          ),
        };
      });
    }, []),

    onMessageDeleted: useCallback((event: MessageDeleted) => {
      setMessages((current) => {
        const thread = current[event.conversation_id];
        if (!thread) return current;
        return {
          ...current,
          [event.conversation_id]: thread.map((existing) =>
            existing.id === event.message_id
              ? { ...existing, deleted: true, originalText: "", translatedText: undefined, reply: undefined, file: undefined }
              : existing,
          ),
        };
      });
      withdrawPreview(event.conversation_id, event.message_id, new Date().toISOString());
    }, [withdrawPreview]),

    onError: useCallback(() => setNotice("chat.realtimeError"), []),
    onCredentialsRefreshNeeded: useCallback(async () => Boolean(await restoreSession()), []),
    onReconnect: recoverAfterReconnect,
    onAuthFailure: useCallback(() => router.replace("/login"), [router]),
  });

  const offline = !socket.connected;

  /**
   * Tell the conversation this account is composing, at most once per window.
   *
   * A notice per keystroke would put a membership query on the server for every
   * letter typed, so the "started" notice repeats only every TYPING_PING_MS and
   * a single timer sends the matching "stopped" once the keyboard goes quiet.
   */
  const noteTyping = useCallback(() => {
    if (!activeId) return;
    const now = Date.now();
    if (now - typingSentAt.current > TYPING_PING_MS) {
      typingSentAt.current = now;
      socket.sendTyping(activeId, true);
    }
    if (typingStopTimer.current) clearTimeout(typingStopTimer.current);
    typingStopTimer.current = setTimeout(() => {
      typingSentAt.current = 0;
      socket.sendTyping(activeId, false);
    }, TYPING_IDLE_MS);
  }, [activeId, socket]);

  /** Stop the indicator immediately, without waiting for the idle timer. */
  const stopTyping = useCallback((conversationId: string) => {
    if (typingStopTimer.current) clearTimeout(typingStopTimer.current);
    if (typingSentAt.current) socket.sendTyping(conversationId, false);
    typingSentAt.current = 0;
  }, [socket]);

  useEffect(() => {
    activeIdRef.current = activeId;
  }, [activeId]);

  useEffect(() => {
    conversationItemsRef.current = conversationItems;
  }, [conversationItems]);

  useEffect(() => {
    loadedThreadsRef.current = loadedThreads;
  }, [loadedThreads]);

  // "vừa xong" stops being true after a minute, and nothing else re-renders the
  // list while the user simply reads. The state is unread on purpose: the
  // re-render it causes is the whole point, since the time labels are computed
  // during render rather than stored.
  useEffect(() => {
    const ticker = window.setInterval(() => setElapsedTick((tick) => tick + 1), 60_000);
    return () => window.clearInterval(ticker);
  }, []);

  // Load the conversation list once.
  useEffect(() => {
    let cancelled = false;
    listConversations()
      .then((conversations) => {
        if (cancelled) return;
        const items = conversations.map((conversation) => toConversationItem(conversation, myId));
        setConversationItems(items);
        setNotice(null);
        setActiveId((current) => current || items[0]?.id || "");
      })
      .catch(() => !cancelled && setNotice("chat.loadConversationsFailed"));
    return () => { cancelled = true; };
  }, [myId]);

  // Load a thread's history the first time it is opened.
  useEffect(() => {
    if (!activeId || loadedThreads[activeId]) return;
    let cancelled = false;
    // The list always resolves first — `activeId` is set from it — so the
    // counterpart's language is known by the time a thread is opened.
    const conversation = conversationItems.find((item) => item.id === activeId);
    const counterpart = conversation ? counterpartLanguageOf(conversation, myId) : undefined;
    getMessages(activeId, 50)
      .then((rows) => {
        if (cancelled) return;
        setMessages((current) => mergeHistory(
          current,
          activeId,
          rows,
          myId,
          myLanguage,
          counterpart,
        ));
        // The list endpoint cannot say which message the preview quotes, so the
        // first history load is where that id becomes known.
        const newest = rows.at(-1);
        if (newest) {
          setConversationItems((items) => items.map((item) =>
            item.id === activeId ? { ...item, lastMessageId: newest.id } : item,
          ));
        }
        setLoadedThreads((current) => ({ ...current, [activeId]: true }));
        setNotice(null);
      })
      .catch(() => !cancelled && setNotice("chat.loadMessagesFailed"));
    return () => { cancelled = true; };
    // `conversationItems` changes whenever a preview moves, but the guard above
    // makes every re-run after the first a no-op.
  }, [activeId, conversationItems, loadedThreads, myId, myLanguage]);

  // The list starts empty and fills after a request, where the mock data it
  // replaced was always present — every `active.*` read below would throw on
  // the first render without a stand-in.
  const active = conversationItems.find((item) => item.id === activeId)
    ?? conversationItems[0]
    ?? EMPTY_CONVERSATION;
  const activeName = conversationName(active, lang);

  const activeMessages = useMemo(() => messages[activeId] ?? [], [activeId, messages]);

  /** What each message shows, so a reply can quote the one it answers. */
  const quotes = useMemo(
    () => Object.fromEntries(activeMessages.map((message) => [
      message.id,
      message.deleted ? uiText(lang, "chat.withdrawn") : displayText(message),
    ])),
    [activeMessages, lang],
  );

  // Only other people count: the server never echoes a typing notice back to
  // the person who sent it, but a stale entry could still name this account.
  const typingHere = useMemo(
    () => (typingBy[activeId] ?? []).filter((id) => id !== myId),
    [activeId, myId, typingBy],
  );

  // The library only re-scrolls when its own container resizes, so a translation
  // toggle appearing under the newest bubble grows the content after that
  // measurement and leaves the toggle hidden below the fold.
  useEffect(() => {
    const frame = requestAnimationFrame(() => messageListRef.current?.scrollToBottom("auto"));
    return () => cancelAnimationFrame(frame);
  }, [activeMessages]);

  const visibleConversations = useMemo(() => conversationItems
    .filter((item) => filter === "all" || Boolean(item.unread))
    .filter((item) => `${conversationName(item, lang)} ${conversationPreview(item, lang)}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()))
    // Newest activity first, the order that makes a preview worth showing at
    // all. Conversations nobody has written in sort last rather than first.
    .sort((a, b) => Number(Boolean(b.pinned)) - Number(Boolean(a.pinned))
      || Date.parse(b.lastActivityAt ?? "0") - Date.parse(a.lastActivityAt ?? "0")),
    [conversationItems, filter, lang, query]);

  // Ask the server, rather than filtering the people already on screen: a new
  // account shares no conversation with anyone, so a local list leaves it with
  // nobody to write to. The server also leaves this account out of its results.
  useEffect(() => {
    const needle = userQuery.trim();
    if (!showComposer || needle.length < MIN_USER_QUERY_LENGTH) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      searchUsers(needle)
        .then((members) => !cancelled && setUserResults({ query: needle, members }))
        .catch(() => {
          if (cancelled) return;
          setComposerError("chat.searchUsersFailed");
          // Recorded as an answer to this query, so the list stops saying it is
          // still searching for something that already failed.
          setUserResults({ query: needle, members: [] });
        });
    }, USER_SEARCH_DEBOUNCE_MS);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [showComposer, userQuery]);

  const searchNeedle = userQuery.trim();
  const foundUsers = userResults.query === searchNeedle ? userResults.members : [];
  const searchingUsers = searchNeedle.length >= MIN_USER_QUERY_LENGTH
    && userResults.query !== searchNeedle;

  const memberLabel = useCallback((member: ConversationMember) => ({
    name: member.display_name || member.email.split("@")[0],
    subtitle: `${member.email} · ${formatUiText(lang, "chat.readsLanguage", { language: languageLabel(member.preferred_language) })}`,
    initials: initialsOf(member.display_name || member.email),
  }), [lang]);

  const grouped = useMemo(() => activeMessages.reduce<ChatMessage[][]>((groups, message) => {
    const previous = groups.at(-1)?.[0];
    if (!previous || previous.author !== message.author || dayKey(previous.sentAt) !== dayKey(message.sentAt)) groups.push([message]);
    else groups.at(-1)?.push(message);
    return groups;
  }, []), [activeMessages]);

  const searchMatches = useMemo(() => messageQuery.trim()
    ? activeMessages.filter((message) => !message.deleted && displayText(message).toLocaleLowerCase().includes(messageQuery.trim().toLocaleLowerCase())).length
    : 0, [activeMessages, messageQuery]);

  useEffect(() => {
    document.querySelector(".cs-button--attachment")?.setAttribute("aria-label", uiText(lang, "chat.attachFile"));
    document.querySelector(".cs-button--send")?.setAttribute("aria-label", uiText(lang, "chat.sendMessage"));
  }, [activeId, lang, offline]);


  const updateActiveThread = useCallback((updater: (thread: ChatMessage[]) => ChatMessage[]) => {
    setMessages((current) => ({ ...current, [activeId]: updater(current[activeId] ?? []) }));
  }, [activeId]);

  /** Resend a message the socket refused while it was down. */
  const retry = useCallback((id: string) => {
    const thread = messages[activeId] ?? [];
    const failed = thread.find((message) => message.id === id);
    if (!failed) return;
    const clientMessageId = failed.clientMessageId ?? id;
    const pending: PendingSend = {
      clientMessageId,
      conversationId: activeId,
      text: failed.originalText,
      attachmentId: failed.attachmentId ?? null,
      replyToMessageId: failed.replyToMessageId ?? null,
    };
    if (!socket.sendMessage(pending)) return;
    pendingSendsRef.current.set(clientMessageId, pending);
    updateActiveThread((thread) => thread.map((message) => message.id === id ? { ...message, delivery: "sending" } : message));
  }, [activeId, messages, socket, updateActiveThread]);

  /** F-06: withdraw one of my messages, keeping the bubble as a tombstone. */
  const removeMessage = useCallback(async (id: string) => {
    const original = (messages[activeId] ?? []).find((message) => message.id === id);
    // Optimistic: the thread reads as withdrawn immediately.
    updateActiveThread((thread) => thread.map((message) => message.id === id ? { ...message, deleted: true, originalText: "", translatedText: undefined, reply: undefined, file: undefined } : message));
    const previousPreview = conversationItems.find((item) => item.id === activeId)?.preview;
    withdrawPreview(activeId, id, original?.sentAt);
    try {
      await deleteMessage(activeId, id);
    } catch {
      // Restore just this message. Putting back a snapshot of the whole thread
      // would silently drop anything that arrived while the request was in
      // flight.
      if (original) {
        updateActiveThread((thread) => thread.map((message) => message.id === id ? original : message));
      }
      // The preview was changed optimistically alongside the bubble, so a
      // refused withdrawal has to put both back, not just the bubble.
      if (previousPreview !== undefined) {
        setConversationItems((items) => items.map((item) =>
          item.id === activeId ? { ...item, preview: previousPreview } : item,
        ));
      }
      setNotice("chat.deleteMessageFailed");
    }
  }, [activeId, conversationItems, messages, updateActiveThread, withdrawPreview]);

  /** F-06: replace the text of one of my messages and drop its old translation. */
  const submitEdit = useCallback(async (message: ChatMessage, text: string) => {
    const cleanText = text.trim();
    if (!cleanText) return;
    try {
      const updated = await editMessage(activeId, message.id, cleanText);
      updateActiveThread((thread) => thread.map((existing) => existing.id === message.id
        ? {
            ...existing,
            originalText: updated.original_text,
            // The old translation described text that no longer exists; the new
            // one arrives over the socket.
            translatedText: undefined,
            translationId: undefined,
            translationLanguage: undefined,
            translationSettled: false,
            // The server dropped the old translation, and the rating and edit
            // went with it — keeping them would show a verdict, and this
            // account's wording, for text that is gone.
            myRating: null,
            myCorrection: null,
            myEdit: null,
            edited: true,
          }
        : existing));
      // Same deadline a new message gets: an edit whose text is already in this
      // reader's language never produces an event to clear the spinner.
      window.setTimeout(
        () => settleTranslation(activeId, message.id),
        TRANSLATION_WAIT_MS,
      );
      touchConversation(activeId, message.id, updated.original_text, updated.edited_at ?? new Date().toISOString());
      setEditing(null);
      setDraft("");
    } catch {
      setNotice("chat.editMessageFailed");
    }
  }, [activeId, settleTranslation, touchConversation, updateActiveThread]);

  /** F-04: show one message's original text instead of its translation. */
  const toggleOriginal = useCallback((id: string) => {
    updateActiveThread((thread) => thread.map((message) => message.id === id ? { ...message, flipped: !message.flipped } : message));
  }, [updateActiveThread]);

  /**
   * F-05: send one verdict on a translation and keep the button in step.
   *
   * The endpoint replaces this reader's whole row, so whichever half of the
   * feedback is not being changed has to be sent again or it is dropped.
   */
  const sendFeedback = useCallback(async (message: ChatMessage, rating: number, correction: string | null) => {
    if (!message.translationId) return false;
    try {
      await submitTranslationFeedback(message.translationId, rating, correction);
      updateActiveThread((thread) => thread.map((existing) =>
        existing.id === message.id ? { ...existing, myRating: rating, myCorrection: correction } : existing,
      ));
      return true;
    } catch {
      setNotice("chat.feedbackFailed");
      return false;
    }
  }, [updateActiveThread]);

  /**
   * F-05: set a thumb, or press the same one again to take it back.
   *
   * The endpoint has no way to say "no rating" — `FeedbackRequest.rating` is a
   * required 1-5 — so withdrawing a verdict sends the middle of the range, the
   * same value a correction with no thumb already carries. Neither thumb reads
   * as pressed at 3, which is what the reader asked for by clicking again.
   */
  const rateTranslation = useCallback(
    (message: ChatMessage, rating: number) => sendFeedback(
      message,
      message.myRating === rating ? RATING_NEUTRAL : rating,
      message.myCorrection ?? null,
    ),
    [sendFeedback],
  );

  /**
   * F-05 (§3.10): store this account's own wording for a translation.
   *
   * A separate endpoint from the rating above, and deliberately so: a rating
   * replaces the reader's previous verdict, while an edit is appended, keeping
   * every attempt for the comparison the feature exists to make. It also writes
   * nothing to `feedbacks.correction` any more — that column is legacy, read
   * from history so old suggestions still show, never written to again.
   */
  const saveTranslationEdit = useCallback(async (message: ChatMessage, editedText: string) => {
    if (!message.translationId) return false;
    try {
      const stored = await submitTranslationEdit(message.translationId, editedText);
      updateActiveThread((thread) => thread.map((existing) =>
        existing.id === message.id
          ? {
              ...existing,
              myEdit: {
                editId: stored.edit_id,
                editedText: stored.edited_text,
                editedAt: stored.edited_at,
              },
            }
          : existing,
      ));
      return true;
    } catch {
      setNotice("chat.saveEditFailed");
      return false;
    }
  }, [updateActiveThread]);

  const beginReply = useCallback((message: ChatMessage) => { setEditing(null); setReplying(message); }, []);
  /**
   * Open the composer on an existing message.
   *
   * The draft is seeded with the current text: the composer is bound to
   * `draft`, so leaving it empty meant typing one character and pressing enter
   * replaced the whole message with that character.
   */
  const beginEdit = useCallback((message: ChatMessage) => {
    setReplying(null);
    setEditing(message);
    setDraft(message.originalText);
  }, []);

  const send = useCallback((text: string) => {
    const cleanText = text.trim();
    if (!cleanText || !activeId) return;

    // The composer doubles as the edit box, so what the send button does
    // depends on whether an edit is in progress (F-06).
    if (editing) {
      submitEdit(editing, cleanText);
      return;
    }

    // The client mints the id so the optimistic bubble can be matched to the
    // server's row when message_created comes back, and so a resend after a
    // dropped connection is idempotent (docs/CONTRACT.md section 5).
    const clientMessageId = crypto.randomUUID();
    const now = new Date();
    const pending: PendingSend = {
      clientMessageId,
      conversationId: activeId,
      text: cleanText,
      attachmentId: null,
      replyToMessageId: replying?.id ?? null,
    };
    const accepted = socket.sendMessage(pending);
    if (accepted) pendingSendsRef.current.set(clientMessageId, pending);

    updateActiveThread((thread) => [...thread, {
      id: clientMessageId,
      clientMessageId,
      author: "me",
      senderId: myId,
      originalText: cleanText,
      sentAt: now.toISOString(),
      delivery: accepted ? "sending" : "failed",
      reply: replying ? displayText(replying) : undefined,
      replyToMessageId: replying?.id,
      attachmentId: null,
    }]);
    touchConversation(activeId, clientMessageId, cleanText, now.toISOString());
    stopTyping(activeId);
    setReplying(null);
    setDraft("");
  }, [activeId, editing, myId, replying, socket, stopTyping, submitEdit, touchConversation, updateActiveThread]);

  /**
   * Send an existing message's text into another conversation.
   *
   * Forwarding needs no endpoint of its own: it is an ordinary send, so the
   * text is translated for the new conversation's members like any other
   * message rather than carrying the old conversation's translations across.
   */
  const forwardTo = useCallback((conversationId: string) => {
    if (!forwarding) return;
    const clientMessageId = crypto.randomUUID();
    const now = new Date();
    const pending: PendingSend = {
      clientMessageId,
      conversationId,
      text: forwarding.originalText,
      attachmentId: null,
      replyToMessageId: null,
    };
    const accepted = socket.sendMessage(pending);
    if (accepted) pendingSendsRef.current.set(clientMessageId, pending);

    setMessages((current) => ({
      ...current,
      [conversationId]: [...(current[conversationId] ?? []), {
        id: clientMessageId,
        clientMessageId,
        author: "me",
        senderId: myId,
        originalText: forwarding.originalText,
        sentAt: now.toISOString(),
        delivery: accepted ? "sending" : "failed",
        attachmentId: null,
      }],
    }));
    touchConversation(conversationId, clientMessageId, forwarding.originalText, now.toISOString());
    setForwarding(null);
    setNotice(accepted ? null : "chat.forwardOffline");
  }, [forwarding, myId, socket, touchConversation]);

  const clearAttachment = useCallback(() => {
    setPendingFile(null);
    // The uploaded bytes stay on the server unclaimed, which the contract
    // treats as a normal state rather than something to clean up here.
    setPendingAttachmentId(null);
    setUploading(false);
    setUploadProgress(0);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, []);

  /** Send the bytes now; the message that carries them comes later (§3.7). */
  const uploadFile = useCallback(async (file: File) => {
    if (!activeId) return;
    setPendingFile(file);
    setUploading(true);
    setUploadProgress(0);
    try {
      const stored = await uploadAttachment(activeId, file, setUploadProgress);
      setPendingAttachmentId(stored.id);
    } catch {
      setNotice("chat.uploadFailed");
      setPendingFile(null);
      setPendingAttachmentId(null);
    } finally {
      setUploading(false);
    }
  }, [activeId]);

  /**
   * Save an attachment to disk.
   *
   * Fetched with the session header and handed over as a blob: the download
   * endpoint checks membership, so a plain link would be refused.
   */
  const downloadFile = useCallback(async (message: ChatMessage) => {
    if (!message.file?.url) return;
    try {
      const blob = await downloadAttachment(message.file.url);
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = message.file.name;
      anchor.click();
      URL.revokeObjectURL(objectUrl);
    } catch {
      setNotice("chat.downloadFailed");
    }
  }, []);

  const chooseFile = useCallback(() => {
    if (!offline && !uploading) fileInputRef.current?.click();
  }, [offline, uploading]);

  const handleFileSelection = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) uploadFile(file);
  }, [uploadFile]);

  /** Send the message that carries the already-uploaded file. */
  const sendFile = useCallback(() => {
    if (!pendingFile || !pendingAttachmentId || uploading || offline) return;
    const clientMessageId = crypto.randomUUID();
    const now = new Date();
    const file = pendingFile;
    const pending: PendingSend = {
      clientMessageId,
      conversationId: activeId,
      text: file.name,
      attachmentId: pendingAttachmentId,
      replyToMessageId: null,
    };
    const accepted = socket.sendMessage(pending);
    if (accepted) pendingSendsRef.current.set(clientMessageId, pending);

    updateActiveThread((thread) => [...thread, {
      id: clientMessageId,
      clientMessageId,
      author: "me",
      senderId: myId,
      originalText: file.name,
      sentAt: now.toISOString(),
      delivery: accepted ? "sending" : "failed",
      attachmentId: pendingAttachmentId,
      file: { name: file.name, size: file.size },
    }]);
    touchConversation(activeId, clientMessageId, file.name, now.toISOString());
    clearAttachment();
  }, [activeId, clearAttachment, myId, offline, pendingAttachmentId, pendingFile, socket, touchConversation, updateActiveThread, uploading]);

  const selectConversation = useCallback((id: string) => {
    // Leaving mid-sentence would otherwise leave the old conversation showing
    // this account as typing until the idle timer fires.
    if (activeId) stopTyping(activeId);
    setActiveId(id);
    // Opening the conversation is what marks it read; the badge clears below
    // straight away and the server tells the other members (§3.8).
    markConversationRead(id).catch(() => undefined);
    setReplying(null);
    setEditing(null);
    setOpenMessageMenuId(null);
    setMessageQuery("");
    setMobileView("chat");
    setConversationItems((items) => items.map((item) => item.id === id ? { ...item, unread: undefined, mention: false } : item));
  }, [activeId, stopTyping]);

  const closeComposer = useCallback(() => {
    setShowComposer(false);
    setGroupName("");
    setSelectedMembers([]);
    setUserQuery("");
    setUserResults({ query: "", members: [] });
    setComposerError(null);
  }, []);

  const startConversation = useCallback(async () => {
    const name = groupName.trim();
    if (!selectedMembers.length) return;
    if (composerMode === "group" && !name) return;
    setComposerError(null);

    try {
      const created = await createConversation({
        type: composerMode,
        title: composerMode === "group" ? name : null,
        member_ids: [...new Set([myId, ...selectedMembers.map((member) => member.id)])],
      });
      // Merged by id rather than appended: asking for a direct conversation that
      // already exists returns that same one (docs/CONTRACT.md §3.5), and
      // appending it would show the thread twice in the sidebar.
      setConversationItems((items) => {
        const item = toConversationItem(created, myId);
        return items.some((existing) => existing.id === item.id)
          ? items.map((existing) => existing.id === item.id ? item : existing)
          : [...items, item];
      });
      closeComposer();
      // History is not seeded here: an existing conversation has messages to
      // fetch, and selecting it is what fetches them.
      selectConversation(created.id);
    } catch {
      setComposerError("chat.createConversationFailed");
    }
  }, [closeComposer, composerMode, groupName, myId, selectedMembers, selectConversation]);

  const toggleMember = useCallback((member: ConversationMember) => {
    setSelectedMembers((current) => {
      if (current.some((chosen) => chosen.id === member.id)) {
        return current.filter((chosen) => chosen.id !== member.id);
      }
      // A direct conversation has room for exactly one other person, so picking
      // someone replaces the previous choice instead of being refused.
      return composerMode === "direct" ? [member] : [...current, member];
    });
  }, [composerMode]);

  const chooseComposerMode = useCallback((mode: "direct" | "group") => {
    setComposerMode(mode);
    setComposerError(null);
    // Switching back to a direct chat keeps the first person picked; the others
    // have nowhere to go in a conversation that holds two people.
    if (mode === "direct") setSelectedMembers((current) => current.slice(0, 1));
  }, []);

  const signOut = useCallback(async () => {
    const refreshToken = getStoredRefreshToken();
    try {
      if (refreshToken) await logoutSession(refreshToken);
    } finally {
      clearSession();
      router.replace("/login");
    }
  }, [router]);

  // A menu anchored to the rail has to close the two ways every menu does, or
  // it stays open behind whatever the user does next.
  useEffect(() => {
    if (!showAccountMenu) return;
    const close = (event: Event) => {
      if (event instanceof KeyboardEvent && event.key !== "Escape") return;
      if (event.type === "pointerdown"
        && (event.target as HTMLElement).closest(`.${styles.navRailAccount}`)) return;
      setShowAccountMenu(false);
    };
    document.addEventListener("keydown", close);
    document.addEventListener("pointerdown", close);
    return () => {
      document.removeEventListener("keydown", close);
      document.removeEventListener("pointerdown", close);
    };
  }, [showAccountMenu]);

  useEffect(() => {
    if (!showComposer) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeComposer();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [closeComposer, showComposer]);

  // The action menu has to close the two ways every menu does, or it stays open
  // over the next message the user goes to read.
  useEffect(() => {
    if (!openMessageMenuId) return;
    const close = (event: Event) => {
      if (event instanceof KeyboardEvent && event.key !== "Escape") return;
      if (event.type === "pointerdown"
        && (event.target as HTMLElement).closest(`.${styles.messageMenu}, .${styles.messageQuickActions}`)) return;
      setOpenMessageMenuId(null);
    };
    document.addEventListener("keydown", close);
    document.addEventListener("pointerdown", close);
    return () => {
      document.removeEventListener("keydown", close);
      document.removeEventListener("pointerdown", close);
    };
  }, [openMessageMenuId]);

  useEffect(() => {
    if (!forwarding) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setForwarding(null);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [forwarding]);

  return (
    <main className={`${styles.appShell} ${mobileView === "chat" ? styles.mobileChat : styles.mobileList}`}>
      <nav className={styles.navRail} aria-label={uiText(lang, "nav.main")}>
        <span className={styles.navRailLogo}>
          <Logo size={30} title="LinguaFlow" />
        </span>
        <Link
          className={styles.navRailButton}
          href="/chat"
          aria-current="page"
          aria-label={uiText(lang, "nav.messages")}
          title={uiText(lang, "nav.messages")}
        >
          <MessagesSquare size={20} strokeWidth={1.8} aria-hidden="true" />
        </Link>
        <Link
          className={styles.navRailButton}
          href="/settings"
          aria-label={uiText(lang, "nav.settings")}
          title={uiText(lang, "nav.settings")}
        >
          <Settings size={20} strokeWidth={1.8} aria-hidden="true" />
        </Link>
        {me?.role === "admin" && (
          <Link
            className={styles.navRailButton}
            href="/admin"
            aria-label={uiText(lang, "nav.admin")}
            title={uiText(lang, "nav.admin")}
          >
            <BarChart3 size={20} strokeWidth={1.8} aria-hidden="true" />
          </Link>
        )}
        <span className={styles.navRailSpacer} />
        <div className={styles.navRailAccount}>
          {showAccountMenu && (
            <div className={styles.accountMenu} role="menu">
              <p className={styles.accountMenuHead}>
                <strong>{accountName}</strong>
                <small>{accountEmail}</small>
              </p>
              <Link className={styles.accountMenuItem} role="menuitem" href="/settings">{uiText(lang, "nav.settings")}</Link>
              <button className={styles.accountMenuItem} type="button" role="menuitem" onClick={signOut}>
                {uiText(lang, "chat.signOut")}
              </button>
            </div>
          )}
          <button
            type="button"
            className={styles.navRailAvatar}
            aria-label={formatUiText(lang, "chat.account", { name: accountName })}
            title={accountName}
            aria-expanded={showAccountMenu}
            aria-haspopup="menu"
            onClick={() => setShowAccountMenu((current) => !current)}
          >
            {accountName.slice(0, 1).toUpperCase()}
          </button>
        </div>
      </nav>
      <MainContainer>
        <Sidebar position="left" scrollable={false} className={styles.chatSidebar}>
          <div className={styles.workspaceTop}><div><span className={styles.productMark}><Logo size={22} /></span><span><strong>LinguaFlow</strong></span></div></div>
          <div className={styles.sidebarTools}><div className={styles.sidebarSearchInline}><Search placeholder={uiText(lang, "chat.searchConversations")} value={query} onChange={setQuery} onClearClick={() => setQuery("")} /></div><button type="button" title={uiText(lang, "chat.newConversation")} aria-label={uiText(lang, "chat.newConversation")} aria-expanded={showComposer} onClick={() => setShowComposer(true)}><UserRoundPlus size={18} strokeWidth={1.8} aria-hidden="true" /></button></div>
          <div className={styles.conversationFilters} aria-label={uiText(lang, "chat.conversationFilters")}>
            <button type="button" aria-pressed={filter === "all"} onClick={() => setFilter("all")}>{uiText(lang, "chat.all")}</button>
            <button type="button" aria-pressed={filter === "unread"} onClick={() => setFilter("unread")}>{uiText(lang, "chat.unread")}</button>
          </div>
          <div className={styles.listTitle}><span>{uiText(lang, "chat.conversations")}</span><span>{visibleConversations.length}</span></div>
          <ConversationList className={styles.conversationIndex}>
            {visibleConversations.map((conversation) => (
              <Conversation key={conversation.id} name={conversationName(conversation, lang)} info={conversationPreview(conversation, lang)} unreadCnt={conversation.unread} unreadDot={conversation.mention} active={conversation.id === activeId} role="button" tabIndex={0}
                onClick={() => selectConversation(conversation.id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); selectConversation(conversation.id); } }} lastActivityTime={relativeTime(conversation.lastActivityAt, lang)}>
                {/* No Conversation.Content child: chatscope renders its own
                    from the name/info props and drops the child entirely. */}
                <Avatar name={conversationName(conversation, lang)} status={conversation.online ? "available" : "unavailable"}><span className={styles.initialsAvatar}>{conversation.initials}</span></Avatar>
              </Conversation>
            ))}
          </ConversationList>
          {!visibleConversations.length && <div className={styles.noResults}><strong>{uiText(lang, "chat.noConversationsFound")}</strong><button type="button" onClick={() => { setQuery(""); setFilter("all"); }}>{uiText(lang, "chat.clearFilters")}</button></div>}
        </Sidebar>

        <ChatContainer className={styles.chatWorkspace}>
          <ConversationHeader className={styles.chatHeader}>
            <ConversationHeader.Back><button type="button" aria-label={uiText(lang, "chat.backToList")} onClick={() => setMobileView("list")}>←</button></ConversationHeader.Back>
            <Avatar name={activeName} status={active.online ? "available" : "unavailable"}><span className={styles.initialsAvatar}>{active.initials}</span></Avatar>
            <ConversationHeader.Content>
              <button
                className={styles.headerIdentity}
                type="button"
                aria-expanded={showConversationInfo}
                onClick={() => setShowConversationInfo((open) => !open)}
              >
                <strong>{activeName}</strong>
              </button>
            </ConversationHeader.Content>
            <ConversationHeader.Actions>
              <button type="button" aria-label={uiText(lang, "chat.conversationInfo")} title={uiText(lang, "chat.conversationInfo")} aria-pressed={showConversationInfo} onClick={() => setShowConversationInfo((open) => !open)}>
                <Info size={18} strokeWidth={1.8} aria-hidden="true" />
              </button>
            </ConversationHeader.Actions>

          </ConversationHeader>

          {/* The shipped typings declare this ref as an HTMLDivElement, but the
              build wraps MessageList in a forwardRef whose useImperativeHandle
              exposes only scrollToBottom. The cast follows the runtime. */}
          <MessageList
            ref={messageListRef as unknown as Ref<HTMLDivElement>}
            typingIndicator={typingHere.length ? <TypingIndicator content={formatUiText(lang, "chat.typing", { name: activeName })} /> : undefined}
            autoScrollToBottom
            autoScrollToBottomOnMount
            scrollBehavior="smooth"
          >
            {(offline || notice) && <div className={styles.statusBanner} role="status"><strong>{offline ? uiText(lang, "chat.offline") : uiText(lang, "chat.error")}</strong><span>{notice ? uiText(lang, notice) : uiText(lang, "chat.reconnecting")}</span></div>}
            {activeMessages.length ? <>
              {grouped.map((cluster, index) => <div key={cluster[0].id} className={styles.messageRow}>{(index === 0 || dayKey(cluster[0].sentAt) !== dayKey(grouped[index - 1][0].sentAt)) && <MessageSeparator content={dateLabel(cluster[0].sentAt, lang)} />}<MessageCluster messages={cluster} name={activeName} initials={active.initials} lang={lang} searchQuery={messageQuery} onReply={beginReply} onRetry={retry} onEdit={beginEdit} onDelete={removeMessage} openMenuId={openMessageMenuId} onToggleMenu={(id) => setOpenMessageMenuId((current) => current === id ? null : id)} onToggleOriginal={toggleOriginal} onRate={rateTranslation} onSaveEdit={saveTranslationEdit} onForward={setForwarding} onDownload={downloadFile} quotes={quotes} /></div>)}
            </> : <div className={styles.emptyState}><span>✦</span><h2>{uiText(lang, "chat.emptyTitle")}</h2><p>{uiText(lang, "chat.emptyDescription")}</p></div>}
          </MessageList>

          {/* Wrapped in an InputToolbox for the same reason the reply bar is:
              ChatContainer keeps only children of its own known types, and a
              bare <div> here was dropped. The file uploaded fine — the panel
              that says so, and the button that actually sends it, never
              rendered, so a chosen file could never leave the browser. */}
          {pendingFile && <InputToolbox className={styles.fileUploadPreview}>
            <span className={styles.fileType}>{fileKind(pendingFile.name, lang)}</span>
            <div><strong>{pendingFile.name}</strong><small>{uploading ? formatUiText(lang, "chat.uploading", { progress: uploadProgress }) : formatUiText(lang, "chat.readyToSend", { size: formatFileSize(pendingFile.size, lang) })}</small>{uploading && <span className={styles.uploadProgress} aria-hidden="true"><span style={{ width: `${uploadProgress}%` }} /></span>}</div>
            {!uploading && <button className={styles.sendFileAction} type="button" onClick={sendFile}>{uiText(lang, "chat.sendFile")}</button>}
            <button className={styles.cancelAction} type="button" onClick={clearAttachment} aria-label={uiText(lang, "chat.cancelAttachment")}>×</button>
          </InputToolbox>}

          {(replying || editing) && <InputToolbox className={`${styles.composerToolbox} ${styles.composerToolboxActive}`}>
            <span className={styles.composerContext}><strong>{editing ? uiText(lang, "chat.editMessage") : formatUiText(lang, "chat.replyTo", { name: activeName })}</strong><small>{editing ? displayText(editing) : replying ? displayText(replying) : ""}</small></span><button className={styles.cancelAction} type="button" aria-label={uiText(lang, "chat.cancelAction")} onClick={() => { setReplying(null); setEditing(null); }}>×</button>
          </InputToolbox>}
          <InputToolbox className={styles.composerTools}>
            <EmojiPicker disabled={offline} onSelect={(emoji) => setDraft((current) => current + emoji)} />
          </InputToolbox>
          <MessageInput
            className={styles.composerInput}
            value={draft}
            onChange={(_innerHtml, textContent) => { setDraft(textContent); noteTyping(); }}
            onSend={(_, text) => send(text)}
            placeholder={offline ? uiText(lang, "chat.offline") : editing ? uiText(lang, "chat.editMessagePlaceholder") : replying ? formatUiText(lang, "chat.replyTo", { name: activeName }) : formatUiText(lang, "chat.messageTo", { name: activeName })}
            disabled={offline}
            sendButton
            attachButton
            onAttachClick={chooseFile}
          />
        </ChatContainer>
      </MainContainer>

      {/* Outside `MainContainer` on purpose. ChatContainer keeps only children
          of its own four known types and silently drops the rest, so while this
          lived in there it never reached the DOM at all: `fileInputRef` stayed
          null and the paperclip button did nothing, with no error to show for
          it. Attachments were dead from the button's first click. */}
      <input
        ref={fileInputRef}
        className={styles.fileInput}
        type="file"
        onChange={handleFileSelection}
        tabIndex={-1}
        aria-hidden="true"
      />

      {showConversationInfo && (
        <aside className={styles.infoPanel} aria-label={uiText(lang, "chat.conversationInfo")}>
          <header>
            <h2>{uiText(lang, "chat.conversationInfo")}</h2>
            <button type="button" aria-label={uiText(lang, "chat.closeInfoPanel")} onClick={() => setShowConversationInfo(false)}>
              <X size={18} strokeWidth={1.8} aria-hidden="true" />
            </button>
          </header>
          <p className={styles.infoName}>{activeName}</p>
          <p className={styles.infoHint}>
            {uiText(lang, "chat.infoDescription")}
          </p>
          <h3 className={styles.infoSectionTitle}>{uiText(lang, "chat.searchInConversation")}</h3>
          <div className={styles.panelSearch}>
            <input
              id="message-search"
              value={messageQuery}
              onChange={(event) => setMessageQuery(event.target.value)}
              placeholder={uiText(lang, "chat.searchMessagesPlaceholder")}
              aria-label={uiText(lang, "chat.searchConversation")}
            />
            {messageQuery.trim() && (
              <button type="button" aria-label={uiText(lang, "chat.clearSearch")} onClick={() => setMessageQuery("")}>
                <X size={15} strokeWidth={2} aria-hidden="true" />
              </button>
            )}
          </div>
          <p className={styles.infoHint} aria-live="polite">
            {messageQuery.trim() ? formatUiText(lang, "chat.searchResults", { count: searchMatches }) : uiText(lang, "chat.searchHighlightHint")}
          </p>

          <h3 className={styles.infoSectionTitle}>{formatUiText(lang, "chat.members", { count: active.members.length })}</h3>
          <ul className={styles.memberList}>
            {active.members.map((member) => (
              <li key={member.id} className={styles.memberRow}>
                <span className={styles.memberAvatar} aria-hidden="true">{memberLabel(member).initials}</span>
                <span className={styles.memberCopy}>
                  <strong>{memberLabel(member).name}{member.id === myId && uiText(lang, "chat.youSuffix")}</strong>
                  <small>{member.email}</small>
                </span>
                <span className={styles.memberLanguage}>{languageLabel(member.preferred_language)}</span>
              </li>
            ))}
          </ul>
          {!active.members.length && (
            <p className={styles.infoHint}>{uiText(lang, "chat.noMembersLoaded")}</p>
          )}
        </aside>
      )}
      {forwarding && <div className={styles.modalBackdrop} onMouseDown={(event) => { if (event.target === event.currentTarget) setForwarding(null); }}>
        <section className={styles.groupModal} role="dialog" aria-modal="true" aria-labelledby="forward-dialog-title">
          <header>
            <div><span className={styles.groupModalIcon}><Forward size={20} aria-hidden="true" /></span><span><h2 id="forward-dialog-title">{uiText(lang, "chat.forwardMessage")}</h2><p>{uiText(lang, "chat.forwardMessageDescription")}</p></span></div>
            <button type="button" aria-label={uiText(lang, "common.close")} onClick={() => setForwarding(null)}><X size={20} aria-hidden="true" /></button>
          </header>
          <div className={styles.forwardBody}>
            {/* The original is what gets sent and re-translated for the new
                audience, so previewing this reader's translation would show
                text nobody there will receive. */}
            <blockquote className={styles.forwardPreview}>{forwarding.originalText}</blockquote>
            <div className={styles.memberResults} role="group" aria-label={uiText(lang, "chat.conversationList")}>
              {conversationItems.filter((item) => item.id !== activeId).map((item) => (
                <button key={item.id} type="button" className={styles.forwardTarget} onClick={() => forwardTo(item.id)}>
                  <span className={styles.memberAvatar}>{item.initials}</span>
                  <span><strong>{conversationName(item, lang)}</strong><small>{conversationSubtitle(item, myId, lang)}</small></span>
                </button>
              ))}
              {conversationItems.filter((item) => item.id !== activeId).length === 0 && <p>{uiText(lang, "chat.noOtherConversations")}</p>}
            </div>
          </div>
        </section>
      </div>}
      {showComposer && <div className={styles.modalBackdrop} onMouseDown={(event) => { if (event.target === event.currentTarget) closeComposer(); }}>
        <section className={styles.groupModal} role="dialog" aria-modal="true" aria-labelledby="composer-dialog-title">
          <header><div><span className={styles.groupModalIcon}><UserRoundPlus size={20} aria-hidden="true" /></span><span><h2 id="composer-dialog-title">{uiText(lang, "chat.newConversation")}</h2><p>{uiText(lang, "chat.newConversationDescription")}</p></span></div><button type="button" aria-label={uiText(lang, "common.close")} onClick={closeComposer}><X size={20} aria-hidden="true" /></button></header>
          <div className={styles.composerTabs} role="tablist" aria-label={uiText(lang, "chat.conversationType")}>
            <button type="button" role="tab" aria-selected={composerMode === "direct"} className={composerMode === "direct" ? styles.composerTabActive : undefined} onClick={() => chooseComposerMode("direct")}>{uiText(lang, "chat.directConversation")}</button>
            <button type="button" role="tab" aria-selected={composerMode === "group"} className={composerMode === "group" ? styles.composerTabActive : undefined} onClick={() => chooseComposerMode("group")}>{uiText(lang, "chat.group")}</button>
          </div>
          <form onSubmit={(event) => { event.preventDefault(); startConversation(); }}>
            {composerMode === "group" && <><label htmlFor="group-name">{uiText(lang, "chat.groupName")}</label><input id="group-name" value={groupName} onChange={(event) => setGroupName(event.target.value)} placeholder={uiText(lang, "chat.groupNamePlaceholder")} /></>}
            <label htmlFor="composer-user-search">{composerMode === "direct" ? uiText(lang, "chat.messageRecipient") : uiText(lang, "chat.addMembers")}</label><div className={styles.groupUserSearch}><span aria-hidden="true">⌕</span><input id="composer-user-search" value={userQuery} onChange={(event) => setUserQuery(event.target.value)} placeholder={uiText(lang, "chat.memberSearchPlaceholder")} autoFocus autoComplete="off" /></div>
            {selectedMembers.length > 0 && <ul className={styles.composerChosen} aria-label={uiText(lang, "chat.selected")}>{selectedMembers.map((member) => <li key={member.id}><span>{memberLabel(member).name}</span><button type="button" aria-label={formatUiText(lang, "chat.removeSelectedMember", { name: memberLabel(member).name })} onClick={() => toggleMember(member)}><X size={12} aria-hidden="true" /></button></li>)}</ul>}
            <div className={styles.memberResults} role="group" aria-label={uiText(lang, "chat.searchResultsGroup")}>{foundUsers.map((member) => { const label = memberLabel(member); return <label key={member.id} className={styles.memberOption}><input type={composerMode === "direct" ? "radio" : "checkbox"} name="composer-member" checked={selectedMembers.some((chosen) => chosen.id === member.id)} onChange={() => toggleMember(member)} /><span className={styles.memberAvatar}>{label.initials}</span><span><strong>{label.name}</strong><small>{label.subtitle}</small></span></label>; })}{!foundUsers.length && <p>{searchNeedle.length < MIN_USER_QUERY_LENGTH ? formatUiText(lang, "chat.enterAtLeastCharacters", { count: MIN_USER_QUERY_LENGTH }) : searchingUsers ? uiText(lang, "chat.searching") : uiText(lang, "chat.noSearchResults")}</p>}</div>
            {composerError && <p className={styles.formError} role="alert">{uiText(lang, composerError)}</p>}
            <footer><span>{formatUiText(lang, "chat.peopleSelected", { count: selectedMembers.length })}</span><button type="button" onClick={closeComposer}>{uiText(lang, "common.cancel")}</button><button type="submit" disabled={!selectedMembers.length || (composerMode === "group" && !groupName.trim())}>{composerMode === "direct" ? uiText(lang, "chat.startConversation") : uiText(lang, "chat.createGroup")}</button></footer>
          </form>
        </section>
      </div>}
    </main>
  );
}
