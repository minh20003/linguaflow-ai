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
import { Forward, Info, MessagesSquare, MoreVertical, PencilLine, Settings, ThumbsDown, ThumbsUp, UserRoundPlus, X } from "lucide-react";
import { logoutSession } from "@/shared/lib/api";
import { clearSession, getStoredRefreshToken, getStoredUser } from "@/shared/lib/auth-session";
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
import { languageLabel } from "@/shared/lib/constants";
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
  time: string;
  sentAt?: string;
  delivery?: Delivery;
  edited?: boolean;
  deleted?: boolean;
  reply?: string;
  /** Which message this answers; the quote is resolved from the thread. */
  replyToMessageId?: string;
  file?: { name: string; meta: string; url?: string };
};

/** Stands in until the conversation list has loaded, or when there are none. */
const EMPTY_CONVERSATION: ConversationItem = {
  id: "",
  type: "direct",
  name: "Chưa có hội thoại",
  initials: "—",
  subtitle: "Tạo một nhóm để bắt đầu trò chuyện",
  preview: "",
  members: [],
};

/** What a withdrawn message reads as, everywhere it is still referred to. */
const WITHDRAWN_TEXT = "Tin nhắn đã được thu hồi";

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
  subtitle: string;
  preview: string;
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
function dateLabel(value?: string) {
  const date = value ? new Date(value) : new Date();
  const today = new Date();
  if (dayKey(date) === dayKey(today)) return "Hôm nay";
  return new Intl.DateTimeFormat("vi-VN", date.getFullYear() === today.getFullYear()
    ? { weekday: "long", day: "2-digit", month: "2-digit" }
    : { weekday: "long", day: "2-digit", month: "2-digit", year: "numeric" }).format(date);
}

function clockTime(value?: string) {
  const date = value ? new Date(value) : new Date();
  return new Intl.DateTimeFormat("vi-VN", { hour: "2-digit", minute: "2-digit" }).format(date);
}

function messageTime(value?: string) {
  if (!value) return "";
  const date = new Date(value);
  const today = new Date();
  const clock = clockTime(value);
  if (dayKey(date) === dayKey(today)) return clock;
  const dateOptions: Intl.DateTimeFormatOptions = date.getFullYear() === today.getFullYear()
    ? { day: "2-digit", month: "2-digit" }
    : { day: "2-digit", month: "2-digit", year: "numeric" };
  return `${new Intl.DateTimeFormat("vi-VN", dateOptions).format(date)} · ${clock}`;
}

/**
 * How long ago, in the shortest form that still reads unambiguously.
 *
 * The conversation list is scanned, not read, so it gets "5 phút" rather than a
 * timestamp — and falls back to a date once "N ngày" stops being informative.
 */
function relativeTime(value?: string | null) {
  if (!value) return "";
  const then = new Date(value);
  const elapsedSeconds = Math.max(0, (Date.now() - then.getTime()) / 1000);
  if (elapsedSeconds < 60) return "vừa xong";
  if (elapsedSeconds < 3600) return `${Math.floor(elapsedSeconds / 60)} phút`;
  if (elapsedSeconds < 86400) return `${Math.floor(elapsedSeconds / 3600)} giờ`;
  if (elapsedSeconds < 604800) return `${Math.floor(elapsedSeconds / 86400)} ngày`;
  return new Intl.DateTimeFormat("vi-VN", then.getFullYear() === new Date().getFullYear()
    ? { day: "2-digit", month: "2-digit" }
    : { day: "2-digit", month: "2-digit", year: "2-digit" }).format(then);
}

function deliveryIndicator(delivery?: Delivery) {
  if (delivery === "sending") return { symbol: "◷", label: "Đang gửi", className: "sending" };
  if (delivery === "delivered") return { symbol: "✓", label: "Đã gửi", className: "delivered" };
  if (delivery === "read") return { symbol: "✓✓", label: "Đã xem", className: "read" };
  return null;
}

function formatFileSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} MB`;
}

function fileKind(name: string) {
  const extension = name.split(".").pop()?.toUpperCase();
  return extension && extension.length <= 4 ? extension : "TỆP";
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
    || others.map((member) => member.display_name || member.email.split("@")[0]).join(", ")
    || "Ghi chú của tôi";
  const languages = [...new Set(conversation.members.map((member) => member.preferred_language))];
  return {
    id: conversation.id,
    name,
    initials: initialsOf(name),
    subtitle: conversation.type === "group"
      ? `Nhóm · ${conversation.members.length} thành viên · ${languages.map(languageLabel).join(", ")}`
      : others.map((member) => languageLabel(member.preferred_language)).join(", "),
    // A withdrawn newest message comes back with empty text (§3.6), which would
    // leave the row with no second line at all. The server cannot supply the
    // wording — it is interface copy and belongs to the reader's language — so
    // the client says it. Text can never be empty otherwise: the send endpoint
    // rejects a blank message, so "" plus a timestamp means withdrawn.
    preview: conversation.last_message
      || (conversation.last_message_at ? WITHDRAWN_TEXT : ""),
    lastActivityAt: conversation.last_message_at,
    unread: conversation.unread_count || undefined,
    // Anyone but me holding a socket makes the row read as active.
    online: others.some((member) => conversation.online_member_ids.includes(member.id)),
    type: conversation.type,
    members: conversation.members,
  };
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
    file: row.attachment
      ? {
          name: row.attachment.filename,
          meta: `${fileKind(row.attachment.filename)} · ${formatFileSize(row.attachment.size)}`,
          url: row.attachment.download_url,
        }
      : undefined,
    sourceLanguage: row.source_language,
    time: clockTime(row.created_at),
    sentAt: row.created_at,
    delivery: "delivered",
    // History is complete: whatever translations exist are already attached.
    translationSettled: true,
  };
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
function TranslationEditForm({ message, onSaveEdit, onClose }: TranslationEditFormProps) {
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
    else setError("Không lưu được bản sửa.");
  };

  return (
    <form className={styles.correctionForm} onSubmit={save}>
      <label htmlFor={`edit-${message.id}`}>Bản dịch bạn cho là đúng</label>
      {/* States what the box is for, because "private" is not something a text
          field can show on its own and the reader would otherwise reasonably
          assume they are correcting the message for everyone. */}
      <p className={styles.correctionHint}>
        Chỉ mình bạn đọc được. Bóng chat vẫn giữ bản dịch của hệ thống.
      </p>
      <textarea
        id={`edit-${message.id}`}
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        placeholder="Nhập bản dịch bạn cho là đúng"
        rows={2}
        autoFocus
      />
      {message.myEdit && (
        <p className={styles.correctionHint}>
          Đã lưu lúc {messageTime(message.myEdit.editedAt)}. Lưu lần nữa sẽ thay bản này.
        </p>
      )}
      {error && <p role="alert">{error}</p>}
      <div>
        <button type="button" onClick={onClose}>Đóng</button>
        <button type="submit" disabled={!draft.trim() || draft.trim() === saved || saving}>
          {saving ? "Đang lưu…" : "Lưu bản sửa"}
        </button>
      </div>
    </form>
  );
}

type MessageClusterProps = {
  messages: ChatMessage[];
  name: string;
  initials: string;
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

const MessageCluster = memo(function MessageCluster({ messages, name, initials, searchQuery, onReply, onRetry, onEdit, onDelete, openMenuId, onToggleMenu, onToggleOriginal, onRate, onSaveEdit, onForward, onDownload, quotes }: MessageClusterProps) {
  const outgoing = messages[0].author === "me";
  // Which bubble has its edit panel open. The pencil is a disclosure
  // toggle, so at most one is open at a time within a cluster.
  const [editingId, setEditingId] = useState<string | null>(null);
  return (
    <MessageGroup direction={outgoing ? "outgoing" : "incoming"} sender={outgoing ? "Bạn" : name} avatarPosition={outgoing ? "cr" : "cl"}>
      {!outgoing && <Avatar name={name} size="sm"><span className={styles.initialsAvatar}>{initials}</span></Avatar>}
      <MessageGroup.Messages>
        {messages.map((message, index) => {
          const indicator = deliveryIndicator(message.delivery);
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
            <Message key={message.id} model={{ message: shown, sender: outgoing ? "Bạn" : name, sentTime: message.time, direction: outgoing ? "outgoing" : "incoming", position }}>
              <Message.Header><time className={styles.messageTimestamp}>{messageTime(message.sentAt)}{message.edited && !message.deleted && <span className={styles.editedMark}>đã sửa</span>}</time></Message.Header>
              <Message.CustomContent>
                <div className={styles.messageBubble}>
                  <div className={styles.messageContent}>
                  {quoted && <blockquote className={styles.replyPreview}>{quoted}</blockquote>}
                  <p className={message.deleted ? styles.deletedMessage : undefined}>{message.deleted ? WITHDRAWN_TEXT : highlight(shown, searchQuery)}</p>
                  {message.file && !message.deleted && <button className={styles.fileCard} type="button" aria-label={`Tải ${message.file.name}`} onClick={() => onDownload(message)}><span>{fileKind(message.file.name)}</span><strong>{message.file.name}<small>{message.file.meta}</small></strong><b aria-hidden="true">↓</b></button>}
                  </div>
                  {!message.deleted && <>
                    <div className={styles.messageQuickActions} aria-label="Thao tác với tin nhắn">
                      <button type="button" aria-label="Mở thao tác với tin nhắn" title="Thao tác" aria-expanded={openMenuId === message.id} aria-haspopup="menu" onClick={() => onToggleMenu(message.id)}>
                        <MoreVertical size={14} strokeWidth={2} aria-hidden="true" />
                      </button>
                    </div>
                    {openMenuId === message.id && <div className={styles.messageMenu} role="menu">
                      <button type="button" role="menuitem" onClick={() => { onReply(message); onToggleMenu(message.id); }}>Trả lời</button>
                      {outgoing && <button type="button" role="menuitem" onClick={() => { onEdit(message); onToggleMenu(message.id); }}>Sửa</button>}
                      <button type="button" role="menuitem" onClick={() => { onForward(message); onToggleMenu(message.id); }}>Chuyển tiếp</button>
                      {/* Withdrawal is the sender's alone (docs/CONTRACT.md §3.6);
                          offering it on someone else's message would only 403. */}
                      {outgoing && <button type="button" role="menuitem" onClick={() => { onDelete(message.id); onToggleMenu(message.id); }}>Gỡ tin nhắn</button>}
                    </div>}
                    {editingId === message.id && (
                      <TranslationEditForm
                        message={message}
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
                      aria-label={ratedUp ? "Bỏ đánh giá bản dịch tốt" : "Bản dịch tốt"}
                      title={ratedUp ? "Bỏ đánh giá" : "Bản dịch tốt"}
                      aria-pressed={ratedUp}
                      className={styles.feedbackButton}
                      onClick={() => onRate(message, RATING_UP)}
                    >
                      <ThumbsUp size={14} strokeWidth={1.75} fill={ratedUp ? "currentColor" : "none"} aria-hidden="true" />
                    </button>
                    <button
                      type="button"
                      aria-label={ratedDown ? "Bỏ đánh giá bản dịch chưa đạt" : "Bản dịch chưa đạt"}
                      title={ratedDown ? "Bỏ đánh giá" : "Bản dịch chưa đạt"}
                      aria-pressed={ratedDown}
                      className={styles.feedbackButton}
                      onClick={() => onRate(message, RATING_DOWN)}
                    >
                      <ThumbsDown size={14} strokeWidth={1.75} fill={ratedDown ? "currentColor" : "none"} aria-hidden="true" />
                    </button>
                    <button
                      type="button"
                      aria-label={edited ? "Xem bản dịch bạn đã sửa" : "Sửa lại bản dịch cho riêng bạn"}
                      title={edited ? "Xem bản sửa của bạn" : "Sửa lại bản dịch cho riêng bạn"}
                      aria-expanded={editingId === message.id}
                      className={styles.feedbackButton}
                      onClick={() => setEditingId((current) => current === message.id ? null : message.id)}
                    >
                      <PencilLine size={14} strokeWidth={1.75} fill={edited ? "currentColor" : "none"} aria-hidden="true" />
                    </button>
                  </span>
                )}
                {message.isFallback && (
                  <span className={styles.deliveryIcon} role="img" aria-label="Bản dịch dự phòng, chất lượng có thể thấp hơn" title="Bản dịch dự phòng, chất lượng có thể thấp hơn">⚠</span>
                )}
                {awaiting && <span className={styles.messageTimestamp}>đang dịch…</span>}
                {message.delivery === "failed" && <button className={styles.retryButton} type="button" onClick={() => onRetry(message.id)}>Không gửi được · Gửi lại</button>}
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
  const router = useRouter();

  // Read once per mount rather than copied into state by an effect: the signed
  // in account cannot change without a navigation.
  const me = useMemo(() => getStoredUser(), []);
  const myId = me?.id ?? "";
  const myLanguage = me?.preferred_language ?? "vi";
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
  const [composerError, setComposerError] = useState("");
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const [conversationItems, setConversationItems] = useState<ConversationItem[]>([]);
  const [messages, setMessages] = useState<Record<string, ChatMessage[]>>({});
  const [loadedThreads, setLoadedThreads] = useState<Record<string, boolean>>({});
  const [notice, setNotice] = useState("");
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
      return { ...item, preview, lastActivityAt: sentAt, lastMessageId: messageId };
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
      return isPreviewed ? { ...item, preview: WITHDRAWN_TEXT } : item;
    }));
  }, []);

  /** Swap a preview for its translation once one arrives for that message. */
  const retranslatePreview = useCallback((conversationId: string, messageId: string, translated: string) => {
    setConversationItems((items) => items.map((item) =>
      item.id === conversationId && item.lastMessageId === messageId
        ? { ...item, preview: translated }
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
        time: clockTime(message.created_at),
        sentAt: message.created_at,
        delivery: "delivered",
      };
      return { ...current, [message.conversation_id]: [...thread, next] };
    });
  }, [settleTranslation, touchConversation]);

  const socket = useWebSocket({
    onMessageCreated: useCallback((clientMessageId: string, message: RealtimeMessage) => {
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

    onError: useCallback((_code: string, message: string) => setNotice(message), []),
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
        setNotice("");
        setActiveId((current) => current || items[0]?.id || "");
      })
      .catch((error: Error) => !cancelled && setNotice(error.message));
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
        setMessages((current) => {
          const fromServer = rows.map((row) => toChatMessage(row, myId, myLanguage, counterpart));
          // Replacing the thread outright would drop anything that appeared
          // while the request was in flight — and the first seconds after a page
          // opens are exactly when someone types. A message sent in that window
          // was added optimistically, then wiped by this response before the
          // socket had even acknowledged it: no bubble, no error, and nothing in
          // the database either, because the send had also been refused by a
          // socket that was still connecting.
          const known = new Set<string>();
          for (const row of rows) {
            known.add(row.id);
            if (row.client_message_id) known.add(row.client_message_id);
          }
          const stillPending = (current[activeId] ?? []).filter((message) =>
            !known.has(message.id)
            && !(message.clientMessageId && known.has(message.clientMessageId)),
          );
          return { ...current, [activeId]: [...fromServer, ...stillPending] };
        });
        // The list endpoint cannot say which message the preview quotes, so the
        // first history load is where that id becomes known.
        const newest = rows.at(-1);
        if (newest) {
          setConversationItems((items) => items.map((item) =>
            item.id === activeId ? { ...item, lastMessageId: newest.id } : item,
          ));
        }
        setLoadedThreads((current) => ({ ...current, [activeId]: true }));
        setNotice("");
      })
      .catch((error: Error) => !cancelled && setNotice(error.message));
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

  const activeMessages = useMemo(() => messages[activeId] ?? [], [activeId, messages]);

  /** What each message shows, so a reply can quote the one it answers. */
  const quotes = useMemo(
    () => Object.fromEntries(activeMessages.map((message) => [
      message.id,
      message.deleted ? WITHDRAWN_TEXT : displayText(message),
    ])),
    [activeMessages],
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
    .filter((item) => `${item.name} ${item.preview}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()))
    // Newest activity first, the order that makes a preview worth showing at
    // all. Conversations nobody has written in sort last rather than first.
    .sort((a, b) => Number(Boolean(b.pinned)) - Number(Boolean(a.pinned))
      || Date.parse(b.lastActivityAt ?? "0") - Date.parse(a.lastActivityAt ?? "0")),
    [conversationItems, filter, query]);

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
        .catch((error: Error) => {
          if (cancelled) return;
          setComposerError(error.message);
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
    subtitle: `${member.email} · đọc ${languageLabel(member.preferred_language)}`,
    initials: initialsOf(member.display_name || member.email),
  }), []);

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
    document.querySelector(".cs-button--attachment")?.setAttribute("aria-label", "Đính kèm tệp");
    document.querySelector(".cs-button--send")?.setAttribute("aria-label", "Gửi tin nhắn");
  }, [activeId, offline]);


  const updateActiveThread = useCallback((updater: (thread: ChatMessage[]) => ChatMessage[]) => {
    setMessages((current) => ({ ...current, [activeId]: updater(current[activeId] ?? []) }));
  }, [activeId]);

  /** Resend a message the socket refused while it was down. */
  const retry = useCallback((id: string) => {
    const thread = messages[activeId] ?? [];
    const failed = thread.find((message) => message.id === id);
    if (!failed) return;
    const clientMessageId = failed.clientMessageId ?? id;
    if (!socket.sendMessage({ clientMessageId, conversationId: activeId, text: failed.originalText })) return;
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
    } catch (error) {
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
      setNotice((error as Error).message);
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
    } catch (error) {
      setNotice((error as Error).message);
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
    } catch (error) {
      setNotice((error as Error).message);
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
    } catch (error) {
      setNotice((error as Error).message);
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
    const accepted = socket.sendMessage({
      clientMessageId,
      conversationId: activeId,
      text: cleanText,
      replyToMessageId: replying?.id ?? null,
    });

    updateActiveThread((thread) => [...thread, {
      id: clientMessageId,
      clientMessageId,
      author: "me",
      senderId: myId,
      originalText: cleanText,
      time: clockTime(now.toISOString()),
      sentAt: now.toISOString(),
      delivery: accepted ? "sending" : "failed",
      reply: replying ? displayText(replying) : undefined,
      replyToMessageId: replying?.id,
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
    const accepted = socket.sendMessage({
      clientMessageId,
      conversationId,
      text: forwarding.originalText,
    });

    setMessages((current) => ({
      ...current,
      [conversationId]: [...(current[conversationId] ?? []), {
        id: clientMessageId,
        clientMessageId,
        author: "me",
        senderId: myId,
        originalText: forwarding.originalText,
        time: clockTime(now.toISOString()),
        sentAt: now.toISOString(),
        delivery: accepted ? "sending" : "failed",
      }],
    }));
    touchConversation(conversationId, clientMessageId, forwarding.originalText, now.toISOString());
    setForwarding(null);
    setNotice(accepted ? "" : "Không chuyển tiếp được khi đang ngoại tuyến.");
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
    } catch (error) {
      setNotice((error as Error).message);
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
    } catch (error) {
      setNotice((error as Error).message);
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
    const accepted = socket.sendMessage({
      clientMessageId,
      conversationId: activeId,
      text: file.name,
      attachmentId: pendingAttachmentId,
    });

    updateActiveThread((thread) => [...thread, {
      id: clientMessageId,
      clientMessageId,
      author: "me",
      senderId: myId,
      originalText: file.name,
      time: clockTime(now.toISOString()),
      sentAt: now.toISOString(),
      delivery: accepted ? "sending" : "failed",
      file: { name: file.name, meta: `${fileKind(file.name)} · ${formatFileSize(file.size)}` },
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
    setComposerError("");
  }, []);

  const startConversation = useCallback(async () => {
    const name = groupName.trim();
    if (!selectedMembers.length) return;
    if (composerMode === "group" && !name) return;
    setComposerError("");

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
    } catch (error) {
      setComposerError((error as Error).message);
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
    setComposerError("");
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
      <nav className={styles.navRail} aria-label="Điều hướng chính">
        <span className={styles.navRailLogo}>
          <Logo size={30} title="LinguaFlow" />
        </span>
        <Link
          className={styles.navRailButton}
          href="/chat"
          aria-current="page"
          aria-label="Tin nhắn"
          title="Tin nhắn"
        >
          <MessagesSquare size={20} strokeWidth={1.8} aria-hidden="true" />
        </Link>
        <Link
          className={styles.navRailButton}
          href="/settings"
          aria-label="Cài đặt"
          title="Cài đặt"
        >
          <Settings size={20} strokeWidth={1.8} aria-hidden="true" />
        </Link>
        <span className={styles.navRailSpacer} />
        <div className={styles.navRailAccount}>
          {showAccountMenu && (
            <div className={styles.accountMenu} role="menu">
              <p className={styles.accountMenuHead}>
                <strong>{accountName}</strong>
                <small>{accountEmail}</small>
              </p>
              <Link className={styles.accountMenuItem} role="menuitem" href="/settings">Cài đặt</Link>
              <button className={styles.accountMenuItem} type="button" role="menuitem" onClick={signOut}>
                Đăng xuất
              </button>
            </div>
          )}
          <button
            type="button"
            className={styles.navRailAvatar}
            aria-label={`Tài khoản ${accountName}`}
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
          <div className={styles.sidebarTools}><div className={styles.sidebarSearchInline}><Search placeholder="Tìm hội thoại" value={query} onChange={setQuery} onClearClick={() => setQuery("")} /></div><button type="button" title="Cuộc trò chuyện mới" aria-label="Cuộc trò chuyện mới" aria-expanded={showComposer} onClick={() => setShowComposer(true)}><UserRoundPlus size={18} strokeWidth={1.8} aria-hidden="true" /></button></div>
          <div className={styles.conversationFilters} aria-label="Lọc hội thoại">
            <button type="button" aria-pressed={filter === "all"} onClick={() => setFilter("all")}>Tất cả</button>
            <button type="button" aria-pressed={filter === "unread"} onClick={() => setFilter("unread")}>Chưa đọc</button>
          </div>
          <div className={styles.listTitle}><span>Hội thoại</span><span>{visibleConversations.length}</span></div>
          <ConversationList className={styles.conversationIndex}>
            {visibleConversations.map((conversation) => (
              <Conversation key={conversation.id} name={conversation.name} info={conversation.preview} unreadCnt={conversation.unread} unreadDot={conversation.mention} active={conversation.id === activeId} role="button" tabIndex={0}
                onClick={() => selectConversation(conversation.id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); selectConversation(conversation.id); } }} lastActivityTime={relativeTime(conversation.lastActivityAt)}>
                {/* No Conversation.Content child: chatscope renders its own
                    from the name/info props and drops the child entirely. */}
                <Avatar name={conversation.name} status={conversation.online ? "available" : "unavailable"}><span className={styles.initialsAvatar}>{conversation.initials}</span></Avatar>
              </Conversation>
            ))}
          </ConversationList>
          {!visibleConversations.length && <div className={styles.noResults}><strong>Không tìm thấy hội thoại</strong><button type="button" onClick={() => { setQuery(""); setFilter("all"); }}>Xóa bộ lọc</button></div>}
        </Sidebar>

        <ChatContainer className={styles.chatWorkspace}>
          <ConversationHeader className={styles.chatHeader}>
            <ConversationHeader.Back><button type="button" aria-label="Quay lại danh sách hội thoại" onClick={() => setMobileView("list")}>←</button></ConversationHeader.Back>
            <Avatar name={active.name} status={active.online ? "available" : "unavailable"}><span className={styles.initialsAvatar}>{active.initials}</span></Avatar>
            <ConversationHeader.Content>
              <button
                className={styles.headerIdentity}
                type="button"
                aria-expanded={showConversationInfo}
                onClick={() => setShowConversationInfo((open) => !open)}
              >
                <strong>{active.name}</strong>
              </button>
            </ConversationHeader.Content>
            <ConversationHeader.Actions>
              <button type="button" aria-label="Thông tin hội thoại" title="Thông tin hội thoại" aria-pressed={showConversationInfo} onClick={() => setShowConversationInfo((open) => !open)}>
                <Info size={18} strokeWidth={1.8} aria-hidden="true" />
              </button>
            </ConversationHeader.Actions>

          </ConversationHeader>

          {/* The shipped typings declare this ref as an HTMLDivElement, but the
              build wraps MessageList in a forwardRef whose useImperativeHandle
              exposes only scrollToBottom. The cast follows the runtime. */}
          <MessageList
            ref={messageListRef as unknown as Ref<HTMLDivElement>}
            typingIndicator={typingHere.length ? <TypingIndicator content={`${active.name} đang nhập`} /> : undefined}
            autoScrollToBottom
            autoScrollToBottomOnMount
            scrollBehavior="smooth"
          >
            {(offline || notice) && <div className={styles.statusBanner} role="status"><strong>{offline ? "Mất kết nối" : "Có lỗi"}</strong><span>{notice || "Đang kết nối lại. Bạn vẫn đọc được các tin nhắn đã tải."}</span></div>}
            {activeMessages.length ? <>
              {grouped.map((cluster, index) => <div key={cluster[0].id} className={styles.messageRow}>{(index === 0 || dayKey(cluster[0].sentAt) !== dayKey(grouped[index - 1][0].sentAt)) && <MessageSeparator content={dateLabel(cluster[0].sentAt)} />}<MessageCluster messages={cluster} name={active.name} initials={active.initials} searchQuery={messageQuery} onReply={beginReply} onRetry={retry} onEdit={beginEdit} onDelete={removeMessage} openMenuId={openMessageMenuId} onToggleMenu={(id) => setOpenMessageMenuId((current) => current === id ? null : id)} onToggleOriginal={toggleOriginal} onRate={rateTranslation} onSaveEdit={saveTranslationEdit} onForward={setForwarding} onDownload={downloadFile} quotes={quotes} /></div>)}
            </> : <div className={styles.emptyState}><span>✦</span><h2>Bắt đầu cuộc trò chuyện</h2><p>Gửi tin nhắn đầu tiên trong không gian riêng của bạn.</p></div>}
          </MessageList>

          {/* Wrapped in an InputToolbox for the same reason the reply bar is:
              ChatContainer keeps only children of its own known types, and a
              bare <div> here was dropped. The file uploaded fine — the panel
              that says so, and the button that actually sends it, never
              rendered, so a chosen file could never leave the browser. */}
          {pendingFile && <InputToolbox className={styles.fileUploadPreview}>
            <span className={styles.fileType}>{fileKind(pendingFile.name)}</span>
            <div><strong>{pendingFile.name}</strong><small>{uploading ? `Đang tải lên · ${uploadProgress}%` : `Sẵn sàng gửi · ${formatFileSize(pendingFile.size)}`}</small>{uploading && <span className={styles.uploadProgress} aria-hidden="true"><span style={{ width: `${uploadProgress}%` }} /></span>}</div>
            {!uploading && <button className={styles.sendFileAction} type="button" onClick={sendFile}>Gửi tệp</button>}
            <button className={styles.cancelAction} type="button" onClick={clearAttachment} aria-label="Hủy tệp đính kèm">×</button>
          </InputToolbox>}

          {(replying || editing) && <InputToolbox className={`${styles.composerToolbox} ${styles.composerToolboxActive}`}>
            <span className={styles.composerContext}><strong>{editing ? "Sửa tin nhắn" : `Trả lời ${active.name}`}</strong><small>{editing ? displayText(editing) : replying ? displayText(replying) : ""}</small></span><button className={styles.cancelAction} type="button" aria-label="Hủy thao tác" onClick={() => { setReplying(null); setEditing(null); }}>×</button>
          </InputToolbox>}
          <InputToolbox className={styles.composerTools}>
            <EmojiPicker disabled={offline} onSelect={(emoji) => setDraft((current) => current + emoji)} />
          </InputToolbox>
          <MessageInput
            className={styles.composerInput}
            value={draft}
            onChange={(_innerHtml, textContent) => { setDraft(textContent); noteTyping(); }}
            onSend={(_, text) => send(text)}
            placeholder={offline ? "Đang ngoại tuyến" : editing ? "Nhập nội dung đã sửa" : replying ? `Trả lời ${active.name}` : `Nhắn cho ${active.name}`}
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
        <aside className={styles.infoPanel} aria-label="Thông tin hội thoại">
          <header>
            <h2>Thông tin hội thoại</h2>
            <button type="button" aria-label="Đóng bảng thông tin" onClick={() => setShowConversationInfo(false)}>
              <X size={18} strokeWidth={1.8} aria-hidden="true" />
            </button>
          </header>
          <p className={styles.infoName}>{active.name}</p>
          <p className={styles.infoHint}>
            Tin nhắn của bạn được dịch sang ngôn ngữ mỗi người dưới đây đang đọc.
          </p>
          <h3 className={styles.infoSectionTitle}>Tìm trong hội thoại</h3>
          <div className={styles.panelSearch}>
            <input
              id="message-search"
              value={messageQuery}
              onChange={(event) => setMessageQuery(event.target.value)}
              placeholder="Nhập nội dung tin nhắn"
              aria-label="Tìm trong cuộc trò chuyện"
            />
            {messageQuery.trim() && (
              <button type="button" aria-label="Xóa tìm kiếm" onClick={() => setMessageQuery("")}>
                <X size={15} strokeWidth={2} aria-hidden="true" />
              </button>
            )}
          </div>
          <p className={styles.infoHint} aria-live="polite">
            {messageQuery.trim() ? `${searchMatches} kết quả` : "Kết quả khớp được tô sáng trong cuộc trò chuyện."}
          </p>

          <h3 className={styles.infoSectionTitle}>Thành viên · {active.members.length}</h3>
          <ul className={styles.memberList}>
            {active.members.map((member) => (
              <li key={member.id} className={styles.memberRow}>
                <span className={styles.memberAvatar} aria-hidden="true">{memberLabel(member).initials}</span>
                <span className={styles.memberCopy}>
                  <strong>{memberLabel(member).name}{member.id === myId && " (bạn)"}</strong>
                  <small>{member.email}</small>
                </span>
                <span className={styles.memberLanguage}>{languageLabel(member.preferred_language)}</span>
              </li>
            ))}
          </ul>
          {!active.members.length && (
            <p className={styles.infoHint}>Chưa tải được danh sách thành viên.</p>
          )}
        </aside>
      )}
      {forwarding && <div className={styles.modalBackdrop} onMouseDown={(event) => { if (event.target === event.currentTarget) setForwarding(null); }}>
        <section className={styles.groupModal} role="dialog" aria-modal="true" aria-labelledby="forward-dialog-title">
          <header>
            <div><span className={styles.groupModalIcon}><Forward size={20} aria-hidden="true" /></span><span><h2 id="forward-dialog-title">Chuyển tiếp tin nhắn</h2><p>Chọn hội thoại nhận tin nhắn này.</p></span></div>
            <button type="button" aria-label="Đóng" onClick={() => setForwarding(null)}><X size={20} aria-hidden="true" /></button>
          </header>
          <div className={styles.forwardBody}>
            {/* The original is what gets sent and re-translated for the new
                audience, so previewing this reader's translation would show
                text nobody there will receive. */}
            <blockquote className={styles.forwardPreview}>{forwarding.originalText}</blockquote>
            <div className={styles.memberResults} role="group" aria-label="Danh sách hội thoại">
              {conversationItems.filter((item) => item.id !== activeId).map((item) => (
                <button key={item.id} type="button" className={styles.forwardTarget} onClick={() => forwardTo(item.id)}>
                  <span className={styles.memberAvatar}>{item.initials}</span>
                  <span><strong>{item.name}</strong><small>{item.subtitle}</small></span>
                </button>
              ))}
              {conversationItems.filter((item) => item.id !== activeId).length === 0 && <p>Chưa có hội thoại nào khác để chuyển tiếp.</p>}
            </div>
          </div>
        </section>
      </div>}
      {showComposer && <div className={styles.modalBackdrop} onMouseDown={(event) => { if (event.target === event.currentTarget) closeComposer(); }}>
        <section className={styles.groupModal} role="dialog" aria-modal="true" aria-labelledby="composer-dialog-title">
          <header><div><span className={styles.groupModalIcon}><UserRoundPlus size={20} aria-hidden="true" /></span><span><h2 id="composer-dialog-title">Cuộc trò chuyện mới</h2><p>Tìm người bằng tên, tên đăng nhập hoặc email.</p></span></div><button type="button" aria-label="Đóng" onClick={closeComposer}><X size={20} aria-hidden="true" /></button></header>
          <div className={styles.composerTabs} role="tablist" aria-label="Kiểu cuộc trò chuyện">
            <button type="button" role="tab" aria-selected={composerMode === "direct"} className={composerMode === "direct" ? styles.composerTabActive : undefined} onClick={() => chooseComposerMode("direct")}>Trò chuyện riêng</button>
            <button type="button" role="tab" aria-selected={composerMode === "group"} className={composerMode === "group" ? styles.composerTabActive : undefined} onClick={() => chooseComposerMode("group")}>Nhóm</button>
          </div>
          <form onSubmit={(event) => { event.preventDefault(); startConversation(); }}>
            {composerMode === "group" && <><label htmlFor="group-name">Tên nhóm</label><input id="group-name" value={groupName} onChange={(event) => setGroupName(event.target.value)} placeholder="Ví dụ: Dự án tháng 8" /></>}
            <label htmlFor="composer-user-search">{composerMode === "direct" ? "Nhắn cho ai" : "Thêm thành viên"}</label><div className={styles.groupUserSearch}><span aria-hidden="true">⌕</span><input id="composer-user-search" value={userQuery} onChange={(event) => setUserQuery(event.target.value)} placeholder="Tên, tên đăng nhập hoặc email" autoFocus autoComplete="off" /></div>
            {selectedMembers.length > 0 && <ul className={styles.composerChosen} aria-label="Đã chọn">{selectedMembers.map((member) => <li key={member.id}><span>{memberLabel(member).name}</span><button type="button" aria-label={`Bỏ chọn ${memberLabel(member).name}`} onClick={() => toggleMember(member)}><X size={12} aria-hidden="true" /></button></li>)}</ul>}
            <div className={styles.memberResults} role="group" aria-label="Kết quả tìm kiếm">{foundUsers.map((member) => { const label = memberLabel(member); return <label key={member.id} className={styles.memberOption}><input type={composerMode === "direct" ? "radio" : "checkbox"} name="composer-member" checked={selectedMembers.some((chosen) => chosen.id === member.id)} onChange={() => toggleMember(member)} /><span className={styles.memberAvatar}>{label.initials}</span><span><strong>{label.name}</strong><small>{label.subtitle}</small></span></label>; })}{!foundUsers.length && <p>{searchNeedle.length < MIN_USER_QUERY_LENGTH ? "Nhập ít nhất 2 ký tự để tìm người." : searchingUsers ? "Đang tìm…" : "Không tìm thấy ai khớp."}</p>}</div>
            {composerError && <p className={styles.formError} role="alert">{composerError}</p>}
            <footer><span>{selectedMembers.length} người được chọn</span><button type="button" onClick={closeComposer}>Hủy</button><button type="submit" disabled={!selectedMembers.length || (composerMode === "group" && !groupName.trim())}>{composerMode === "direct" ? "Bắt đầu trò chuyện" : "Tạo nhóm"}</button></footer>
          </form>
        </section>
      </div>}
    </main>
  );
}
