"use client";

import { memo, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import {
  Avatar,
  ChatContainer,
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
import { getUser, type AuthUser } from "@/shared/lib/auth";
import {
  createConversation,
  getMessages,
  listConversations,
  lookupUserByEmail,
  type Conversation as ApiConversation,
  type HistoryMessage,
} from "@/shared/lib/chat-api";
import { languageLabel } from "@/shared/lib/constants";
import { useWebSocket, type RealtimeMessage, type TranslationCompleted } from "@/shared/lib/use-websocket";
import styles from "./DemoMessagingApp.module.css";

/**
 * Editing, deleting, reactions and attachments are UI-only today — there is no
 * endpoint behind any of them, so a reload silently reverts whatever the user
 * did. They stay hidden until F-05 and file upload land, rather than being
 * demonstrated as if they worked.
 */
const SHOW_UNIMPLEMENTED = false;

/**
 * How long to keep showing "đang dịch…" for a message that just arrived.
 *
 * The server sends nothing at all when a message is already in the reader's
 * language, so the client cannot distinguish "translating" from "no translation
 * is coming" — it can only stop waiting (ADR-16).
 */
const TRANSLATION_WAIT_MS = 8000;

type Delivery = "sending" | "delivered" | "failed";

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
  /** F-04: per-message override of the default view. */
  showOriginal?: boolean;
  /** Set once no translation can still be expected for this reader. */
  translationSettled?: boolean;
  time: string;
  sentAt?: string;
  delivery?: Delivery;
};

type ConversationItem = {
  id: string;
  name: string;
  initials: string;
  subtitle: string;
  preview: string;
  time: string;
};

function dayKey(value?: string) {
  const date = value ? new Date(value) : new Date();
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
}

function dateLabel(value?: string) {
  const date = value ? new Date(value) : new Date();
  const today = new Date();
  if (dayKey(date.toISOString()) === dayKey(today.toISOString())) return "Hôm nay";
  return new Intl.DateTimeFormat("vi-VN", date.getFullYear() === today.getFullYear()
    ? { weekday: "long", day: "2-digit", month: "2-digit" }
    : { weekday: "long", day: "2-digit", month: "2-digit", year: "numeric" }).format(date);
}

function clockTime(value?: string) {
  const date = value ? new Date(value) : new Date();
  return new Intl.DateTimeFormat("vi-VN", { hour: "2-digit", minute: "2-digit" }).format(date);
}

function messageTime(value?: string) {
  const date = value ? new Date(value) : new Date();
  const today = new Date();
  const clock = clockTime(value);
  if (dayKey(date.toISOString()) === dayKey(today.toISOString())) return clock;
  const dateOptions: Intl.DateTimeFormatOptions = date.getFullYear() === today.getFullYear()
    ? { day: "2-digit", month: "2-digit" }
    : { day: "2-digit", month: "2-digit", year: "numeric" };
  return `${new Intl.DateTimeFormat("vi-VN", dateOptions).format(date)} · ${clock}`;
}

function deliveryIndicator(delivery?: Delivery) {
  if (delivery === "sending") return { symbol: "◷", label: "Đang gửi", className: "sending" };
  if (delivery === "delivered") return { symbol: "✓", label: "Đã gửi", className: "delivered" };
  return null;
}

function initialsOf(value: string) {
  const name = value.split("@")[0];
  const parts = name.split(/[.\s_-]+/).filter(Boolean);
  const letters = parts.length >= 2 ? parts[0][0] + parts[1][0] : name.slice(0, 2);
  return letters.toUpperCase();
}

/** What the bubble shows: the translation by default, the original on request. */
function displayText(message: ChatMessage) {
  if (message.showOriginal || !message.translatedText) return message.originalText;
  return message.translatedText;
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
    || others.map((member) => member.email.split("@")[0]).join(", ")
    || "Ghi chú của tôi";
  const languages = [...new Set(conversation.members.map((m) => m.preferred_language))];
  return {
    id: conversation.id,
    name,
    initials: initialsOf(name),
    subtitle: conversation.type === "group"
      ? `Nhóm · ${conversation.members.length} thành viên · ${languages.map(languageLabel).join(", ")}`
      : others.map((member) => languageLabel(member.preferred_language)).join(", "),
    preview: "",
    time: "",
  };
}

/** Turn a history row into a bubble, picking the translation this account reads. */
function toChatMessage(row: HistoryMessage, myId: string, myLanguage: string): ChatMessage {
  const mine = row.translations.find((t) => t.target_language === myLanguage);
  return {
    id: row.id,
    clientMessageId: row.client_message_id,
    author: row.sender_id === myId ? "me" : "them",
    senderId: row.sender_id,
    originalText: row.original_text,
    translatedText: mine?.translated_text,
    translationId: mine?.translation_id,
    isFallback: mine?.is_fallback,
    sourceLanguage: row.source_language,
    time: clockTime(row.created_at),
    sentAt: row.created_at,
    delivery: "delivered",
    // History is complete: whatever translations exist are already attached.
    translationSettled: true,
  };
}

type MessageClusterProps = {
  messages: ChatMessage[];
  name: string;
  initials: string;
  searchQuery: string;
  myLanguage: string;
  onToggleOriginal: (id: string) => void;
};

const MessageCluster = memo(function MessageCluster({ messages, name, initials, searchQuery, myLanguage, onToggleOriginal }: MessageClusterProps) {
  const outgoing = messages[0].author === "me";
  return (
    <MessageGroup direction={outgoing ? "outgoing" : "incoming"} sender={outgoing ? "Bạn" : name} avatarPosition={outgoing ? "cr" : "cl"}>
      {!outgoing && <Avatar name={name} size="sm"><span className={styles.initialsAvatar}>{initials}</span></Avatar>}
      <MessageGroup.Messages>
        {messages.map((message, index) => {
          const indicator = deliveryIndicator(message.delivery);
          const position = messages.length === 1 ? "single" : index === 0 ? "first" : index === messages.length - 1 ? "last" : "normal";
          const shown = displayText(message);
          const hasTranslation = Boolean(message.translatedText);
          // Nothing is coming when the message is already in this reader's
          // language: the server sends no event for that case at all.
          const awaiting =
            !hasTranslation
            && !message.translationSettled
            && message.sourceLanguage !== myLanguage
            && message.delivery === "delivered";
          return (
            <Message key={message.id} model={{ message: shown, sender: outgoing ? "Bạn" : name, sentTime: message.time, direction: outgoing ? "outgoing" : "incoming", position }}>
              <Message.Header><time className={styles.messageTimestamp}>{messageTime(message.sentAt)}</time></Message.Header>
              <Message.CustomContent>
                <div className={styles.messageBubble}>
                  <div className={styles.messageContent}>
                    <p>{highlight(shown, searchQuery)}</p>
                  </div>
                </div>
              </Message.CustomContent>
              <Message.Footer>
                {hasTranslation && (
                  <button className={styles.retryButton} type="button" onClick={() => onToggleOriginal(message.id)}>
                    {message.showOriginal ? "Xem bản dịch" : "Xem bản gốc"}
                  </button>
                )}
                {message.isFallback && (
                  <span className={styles.deliveryIcon} role="img" aria-label="Bản dịch dự phòng, chất lượng có thể thấp hơn" title="Bản dịch dự phòng, chất lượng có thể thấp hơn">⚠</span>
                )}
                {awaiting && <span className={styles.messageTimestamp}>đang dịch…</span>}
                {indicator && <span className={`${styles.deliveryIcon} ${styles[indicator.className]}`} role="img" aria-label={indicator.label} title={indicator.label}>{indicator.symbol}</span>}
              </Message.Footer>
            </Message>
          );
        })}
      </MessageGroup.Messages>
    </MessageGroup>
  );
});

/**
 * @param session Account to run as. Omitted, it uses the stored session, which
 *   is what the real app does. The side-by-side demo passes one explicitly so a
 *   single tab can hold two accounts — localStorage has room for exactly one.
 * @param compact Hides the sidebar for the demo's two-pane layout.
 */
export default function MessagingApp({
  session,
  compact = false,
}: { session?: { token: string; user: AuthUser }; compact?: boolean } = {}) {
  const router = useRouter();
  const stored = useMemo(() => getUser(), []);
  const me = session?.user ?? stored;
  const token = session?.token;
  const myId = me?.id ?? "";
  const myLanguage = me?.preferred_language ?? "en";

  const [activeId, setActiveId] = useState("");
  const [mobileView, setMobileView] = useState<"list" | "chat">("chat");
  const [query, setQuery] = useState("");
  const [showGroupCreator, setShowGroupCreator] = useState(false);
  const [groupName, setGroupName] = useState("");
  const [groupMembers, setGroupMembers] = useState("");
  const [groupError, setGroupError] = useState("");
  const [conversationItems, setConversationItems] = useState<ConversationItem[]>([]);
  const [messages, setMessages] = useState<Record<string, ChatMessage[]>>({});
  const [loadedThreads, setLoadedThreads] = useState<Record<string, boolean>>({});
  const [notice, setNotice] = useState("");
  const [showMessageSearch, setShowMessageSearch] = useState(false);
  const [messageQuery, setMessageQuery] = useState("");

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

  const applyIncoming = useCallback((message: RealtimeMessage, author: "me" | "them") => {
    window.setTimeout(
      () => settleTranslation(message.conversation_id, message.id),
      TRANSLATION_WAIT_MS,
    );
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
  }, [settleTranslation]);

  const socket = useWebSocket({
    onMessageCreated: useCallback((clientMessageId: string, message: RealtimeMessage) => {
      // The sender waits for a translation too — they may read a different
      // language than the one they typed in. Same deadline as an incoming
      // message, after which nothing more is expected.
      window.setTimeout(
        () => settleTranslation(message.conversation_id, message.id),
        TRANSLATION_WAIT_MS,
      );
      // Replace the optimistic bubble with the server's row, keyed by the id
      // the client minted for exactly this purpose.
      setMessages((current) => {
        const thread = current[message.conversation_id] ?? [];
        const known = thread.some((existing) => existing.clientMessageId === clientMessageId);
        if (!known) return current;
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
      // The server only sends this to readers of that language, so anything
      // arriving here is meant for this account.
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
                  isFallback: event.is_fallback,
                  sourceLanguage: event.source_language,
                }
              : existing,
          ),
        };
      });
    }, []),

    onError: useCallback((_code: string, message: string) => setNotice(message), []),

    onAuthFailure: useCallback(() => {
      if (!session) router.replace("/login");
    }, [router, session]),
  }, token);

  // Load the conversation list once.
  useEffect(() => {
    let cancelled = false;
    listConversations(token)
      .then((conversations) => {
        if (cancelled) return;
        const items = conversations.map((conversation) => toConversationItem(conversation, myId));
        setConversationItems(items);
        setActiveId((current) => current || items[0]?.id || "");
      })
      .catch((error: Error) => !cancelled && setNotice(error.message));
    return () => { cancelled = true; };
  }, [myId, token]);

  // Load a thread's history the first time it is opened.
  useEffect(() => {
    if (!activeId || loadedThreads[activeId]) return;
    let cancelled = false;
    getMessages(activeId, 50, token)
      .then((rows) => {
        if (cancelled) return;
        setMessages((current) => ({
          ...current,
          [activeId]: rows.map((row) => toChatMessage(row, myId, myLanguage)),
        }));
        setLoadedThreads((current) => ({ ...current, [activeId]: true }));
      })
      .catch((error: Error) => !cancelled && setNotice(error.message));
    return () => { cancelled = true; };
  }, [activeId, loadedThreads, myId, myLanguage, token]);

  const active = conversationItems.find((item) => item.id === activeId);
  const activeMessages = useMemo(() => messages[activeId] ?? [], [activeId, messages]);

  const visibleConversations = useMemo(
    () => conversationItems.filter((item) => item.name.toLocaleLowerCase().includes(query.toLocaleLowerCase())),
    [conversationItems, query],
  );

  const grouped = useMemo(() => activeMessages.reduce<ChatMessage[][]>((groups, message) => {
    const previous = groups.at(-1)?.[0];
    if (!previous || previous.author !== message.author || dayKey(previous.sentAt) !== dayKey(message.sentAt)) groups.push([message]);
    else groups.at(-1)?.push(message);
    return groups;
  }, []), [activeMessages]);

  const searchMatches = useMemo(() => messageQuery.trim()
    ? activeMessages.filter((message) => displayText(message).toLocaleLowerCase().includes(messageQuery.trim().toLocaleLowerCase())).length
    : 0, [activeMessages, messageQuery]);

  const toggleOriginal = useCallback((id: string) => {
    setMessages((current) => ({
      ...current,
      [activeId]: (current[activeId] ?? []).map((message) =>
        message.id === id ? { ...message, showOriginal: !message.showOriginal } : message,
      ),
    }));
  }, [activeId]);

  const send = useCallback((text: string) => {
    const cleanText = text.trim();
    if (!cleanText || !activeId) return;

    const clientMessageId = crypto.randomUUID();
    const now = new Date();
    const optimistic: ChatMessage = {
      id: clientMessageId,
      clientMessageId,
      author: "me",
      senderId: myId,
      originalText: cleanText,
      time: clockTime(now.toISOString()),
      sentAt: now.toISOString(),
      delivery: "sending",
    };
    setMessages((current) => ({ ...current, [activeId]: [...(current[activeId] ?? []), optimistic] }));

    const accepted = socket.sendMessage({ clientMessageId, conversationId: activeId, text: cleanText });
    if (!accepted) {
      setMessages((current) => ({
        ...current,
        [activeId]: (current[activeId] ?? []).map((message) =>
          message.clientMessageId === clientMessageId ? { ...message, delivery: "failed" } : message,
        ),
      }));
    }
  }, [activeId, myId, socket]);

  const selectConversation = useCallback((id: string) => {
    setActiveId(id);
    setMessageQuery("");
    setMobileView("chat");
  }, []);

  const createGroup = useCallback(async () => {
    const name = groupName.trim();
    const emails = groupMembers.split(",").map((value) => value.trim()).filter(Boolean);
    if (!name || !emails.length) {
      setGroupError("Cần tên nhóm và ít nhất một email.");
      return;
    }

    setGroupError("");
    try {
      // The form collects emails while the endpoint wants ids, so every address
      // is resolved first — which also catches a typo while it is still on screen.
      const resolved = await Promise.all(emails.map((email) => lookupUserByEmail(email, token)));
      const missing = emails.filter((_, index) => resolved[index] === null);
      if (missing.length) {
        setGroupError(`Không tìm thấy tài khoản: ${missing.join(", ")}`);
        return;
      }

      const conversation = await createConversation({
        type: "group",
        title: name,
        member_ids: resolved.map((member) => member!.id),
      }, token);

      setConversationItems((items) => [toConversationItem(conversation, myId), ...items]);
      setMessages((current) => ({ ...current, [conversation.id]: [] }));
      setLoadedThreads((current) => ({ ...current, [conversation.id]: true }));
      setGroupName("");
      setGroupMembers("");
      setShowGroupCreator(false);
      selectConversation(conversation.id);
    } catch (error) {
      setGroupError((error as Error).message);
    }
  }, [groupMembers, groupName, myId, selectConversation, token]);

  return (
    <main className={`${styles.appShell} ${compact ? styles.embedded : ""} ${mobileView === "chat" ? styles.mobileChat : styles.mobileList}`}>
      <MainContainer>
        {!compact && <Sidebar position="left" scrollable={false} className={styles.chatSidebar}>
          <div className={styles.workspaceTop}><div><span className={styles.productMark}>LC</span><span><strong>LinguaChat</strong><small>Web nhắn tin trực tuyến</small></span></div></div>
          <div className={styles.sidebarTools}>
            <div className={styles.sidebarSearchInline}><Search placeholder="Tìm hội thoại" value={query} onChange={setQuery} onClearClick={() => setQuery("")} /></div>
            <button type="button" title="Tạo nhóm trò chuyện" aria-label="Tạo nhóm trò chuyện" aria-expanded={showGroupCreator} onClick={() => setShowGroupCreator((value) => !value)}>♧</button>
          </div>
          {showGroupCreator && (
            <form className={styles.groupCreator} onSubmit={(event) => { event.preventDefault(); void createGroup(); }}>
              <label htmlFor="group-name">Tên nhóm</label>
              <input id="group-name" value={groupName} onChange={(event) => setGroupName(event.target.value)} placeholder="Ví dụ: Dự án tháng 8" autoFocus />
              <label htmlFor="group-members">Thành viên</label>
              <input id="group-members" value={groupMembers} onChange={(event) => setGroupMembers(event.target.value)} placeholder="Email, ngăn cách bằng dấu phẩy" />
              {groupError && <small role="alert">{groupError}</small>}
              <button type="submit">Tạo nhóm</button>
            </form>
          )}
          <div className={styles.listTitle}><span>Hội thoại</span><span>{visibleConversations.length}</span></div>
          <ConversationList className={styles.conversationIndex}>
            {visibleConversations.map((conversation) => (
              <Conversation key={conversation.id} name={conversation.name} info={conversation.subtitle} active={conversation.id === activeId} role="button" tabIndex={0}
                onClick={() => selectConversation(conversation.id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); selectConversation(conversation.id); } }}>
                <Avatar name={conversation.name}><span className={styles.initialsAvatar}>{conversation.initials}</span></Avatar>
                <Conversation.Content name={conversation.name} info={conversation.subtitle} />
              </Conversation>
            ))}
          </ConversationList>
          {!visibleConversations.length && <div className={styles.noResults}><strong>Chưa có hội thoại</strong><button type="button" onClick={() => setShowGroupCreator(true)}>Tạo nhóm</button></div>}
          <div className={styles.accountArea}>
            <Avatar name={me?.email ?? ""} status={socket.connected ? "available" : "unavailable"} size="sm"><span className={styles.initialsAvatar}>{initialsOf(me?.email ?? "?")}</span></Avatar>
            <span><strong>{me?.display_name ?? "Tài khoản"}</strong><small>{socket.connected ? `Đang đọc ${languageLabel(myLanguage)}` : "Mất kết nối"}</small></span>
          </div>
        </Sidebar>}

        <ChatContainer className={styles.chatWorkspace}>
          <ConversationHeader className={styles.chatHeader}>
            <ConversationHeader.Back><button type="button" aria-label="Quay lại danh sách hội thoại" onClick={() => setMobileView("list")}>←</button></ConversationHeader.Back>
            <Avatar name={active?.name ?? ""}><span className={styles.initialsAvatar}>{active?.initials ?? "–"}</span></Avatar>
            <ConversationHeader.Content
              userName={`${me?.display_name ?? "Tài khoản"} · đọc ${languageLabel(myLanguage)}`}
              info={active ? `${active.name} — ${active.subtitle}` : "Chưa chọn hội thoại"}
            />
            <ConversationHeader.Actions>
              <button type="button" aria-label="Tìm trong hội thoại" aria-pressed={showMessageSearch} onClick={() => { setShowMessageSearch((value) => !value); setMessageQuery(""); }}>⌕</button>
            </ConversationHeader.Actions>
          </ConversationHeader>

          <MessageList className={styles.messageTimeline} autoScrollToBottom autoScrollToBottomOnMount scrollBehavior="smooth">
            {!socket.connected && <div className={styles.statusBanner} role="status"><strong>Đang kết nối lại…</strong><span>Bạn vẫn có thể đọc các tin nhắn đã tải.</span></div>}
            {notice && <div className={styles.statusBanner} role="status"><strong>{notice}</strong><span><button type="button" onClick={() => setNotice("")}>Đóng</button></span></div>}
            {showMessageSearch && <div className={styles.messageSearch}><label htmlFor="message-search">Tìm trong cuộc trò chuyện</label><input id="message-search" autoFocus value={messageQuery} onChange={(event) => setMessageQuery(event.target.value)} placeholder="Nhập nội dung tin nhắn" /><span aria-live="polite">{messageQuery.trim() ? `${searchMatches} kết quả` : ""}</span><button type="button" onClick={() => { setShowMessageSearch(false); setMessageQuery(""); }} aria-label="Đóng tìm kiếm">×</button></div>}
            {activeMessages.length ? grouped.map((cluster, index) => (
              <div key={cluster[0].id}>
                {(index === 0 || dayKey(cluster[0].sentAt) !== dayKey(grouped[index - 1][0].sentAt)) && <MessageSeparator content={dateLabel(cluster[0].sentAt)} />}
                <MessageCluster messages={cluster} name={active?.name ?? ""} initials={active?.initials ?? ""} searchQuery={messageQuery} myLanguage={myLanguage} onToggleOriginal={toggleOriginal} />
              </div>
            )) : <div className={styles.emptyState}><span>✦</span><h2>Bắt đầu cuộc trò chuyện</h2><p>Gửi tin nhắn đầu tiên — bản dịch sẽ tới ngay sau đó.</p></div>}
          </MessageList>

          {SHOW_UNIMPLEMENTED && <InputToolbox className={styles.composerToolbox} />}
          <MessageInput
            onSend={(_, text) => send(text)}
            placeholder={active ? `Nhắn cho ${active.name}` : "Chọn một hội thoại"}
            disabled={!activeId || !socket.connected}
            sendButton
            attachButton={false}
          />
        </ChatContainer>
      </MainContainer>
    </main>
  );
}
