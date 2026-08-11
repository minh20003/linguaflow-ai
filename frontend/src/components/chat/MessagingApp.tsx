"use client";

import { memo, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
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
  TypingIndicator,
} from "@chatscope/chat-ui-kit-react";
import styles from "./MessagingApp.module.css";

type Delivery = "sending" | "delivered" | "read" | "failed";
type ChatMessage = {
  id: number;
  author: "me" | "them";
  text: string;
  time: string;
  sentAt?: string;
  delivery?: Delivery;
  edited?: boolean;
  deleted?: boolean;
  reply?: string;
  file?: { name: string; meta: string };
  reaction?: string;
};

type ConversationItem = {
  id: string;
  name: string;
  initials: string;
  subtitle: string;
  preview: string;
  time: string;
  unread?: number;
  mention?: boolean;
  muted?: boolean;
  pinned?: boolean;
  online?: boolean;
};

function timestamp(daysAgo: number, time: string) {
  const [hours, minutes] = time.split(":").map(Number);
  const date = new Date();
  date.setDate(date.getDate() - daysAgo);
  date.setHours(hours, minutes, 0, 0);
  return date.toISOString();
}

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

function messageTime(value?: string) {
  const date = value ? new Date(value) : new Date();
  const today = new Date();
  const clock = new Intl.DateTimeFormat("vi-VN", { hour: "2-digit", minute: "2-digit" }).format(date);
  if (dayKey(date.toISOString()) === dayKey(today.toISOString())) return clock;
  const dateOptions: Intl.DateTimeFormatOptions = date.getFullYear() === today.getFullYear()
    ? { day: "2-digit", month: "2-digit" }
    : { day: "2-digit", month: "2-digit", year: "numeric" };
  return `${new Intl.DateTimeFormat("vi-VN", dateOptions).format(date)} · ${clock}`;
}

function deliveryIndicator(delivery?: Delivery) {
  if (delivery === "sending") return { symbol: "◷", label: "Đang gửi", className: "sending" };
  if (delivery === "delivered") return { symbol: "✓", label: "Đã gửi", className: "delivered" };
  if (delivery === "read") return { symbol: "✓✓", label: "Đã xem", className: "read" };
  return null;
}

function highlight(text: string, query: string): ReactNode {
  const cleaned = query.trim();
  if (!cleaned) return text;
  const index = text.toLocaleLowerCase().indexOf(cleaned.toLocaleLowerCase());
  if (index < 0) return text;
  return <>{text.slice(0, index)}<mark className={styles.match}>{text.slice(index, index + cleaned.length)}</mark>{text.slice(index + cleaned.length)}</>;
}

const initialConversations: ConversationItem[] = [
  { id: "aiko", name: "Aiko Tanaka", initials: "AT", subtitle: "Product design · đang trực tuyến", preview: "Hẹn gặp bạn lúc 18:30 nhé", time: "09:42", unread: 2, mention: true, online: true, pinned: true },
  { id: "minh", name: "Minh Anh", initials: "MA", subtitle: "Kỹ sư nền tảng", preview: "Mình đã gửi tài liệu rồi", time: "08:15", unread: 1, online: true },
  { id: "sofia", name: "Sofía Rodríguez", initials: "SR", subtitle: "Nghiên cứu người dùng", preview: "Cảm ơn bạn rất nhiều!", time: "T.2", muted: true },
  { id: "chen", name: "Chen Wei", initials: "CW", subtitle: "Đối tác vận hành", preview: "See you at the station", time: "T.7", online: true },
  { id: "notes", name: "Ghi chú của tôi", initials: "TN", subtitle: "Không gian riêng tư", preview: "Chưa có tin nhắn", time: "" },
];

const seedMessages: Record<string, ChatMessage[]> = {
  aiko: [
    { id: 1, author: "them", text: "Chào buổi sáng! Cuộc họp hôm nay bắt đầu lúc 15 giờ có ổn không?", time: "08:52" },
    { id: 2, author: "me", text: "Ổn nhé. Mình sẽ gửi bản nháp trước giờ họp.", time: "08:55", delivery: "read" },
    { id: 3, author: "them", text: "Cảm ơn bạn. Chúng ta gặp ở quán cà phê gần ga nhé.", time: "09:03", reaction: "👍 1" },
    { id: 4, author: "them", text: "Mình gửi thêm tài liệu tham khảo.", time: "09:04", file: { name: "meeting-notes.pdf", meta: "PDF · 1,8 MB" } },
    { id: 5, author: "me", text: "Được, mình biết quán đó. Hẹn gặp bạn lúc 18:30 nhé.", time: "09:10", delivery: "delivered", edited: true, reply: "Chúng ta gặp ở quán cà phê gần ga nhé." },
    { id: 6, author: "me", text: "Tin nhắn thử khi mạng yếu", time: "09:12", delivery: "failed" },
    { id: 7, author: "them", text: "Tin nhắn đã được thu hồi", time: "09:31", deleted: true },
    { id: 8, author: "them", text: "Vậy hẹn gặp lại sau nhé!", time: "09:42" },
  ],
  minh: [{ id: 21, author: "them", text: "Mình đã gửi tài liệu rồi, bạn xem giúp nhé.", time: "08:15" }],
  sofia: [{ id: 31, author: "them", text: "Cảm ơn bạn rất nhiều vì đã giúp đỡ!", time: "10:20" }],
  chen: [{ id: 41, author: "them", text: "Chúng ta gặp nhau ở nhà ga nhé.", time: "10:20" }],
  notes: [],
};

seedMessages.aiko.forEach((message, index) => { message.sentAt = timestamp(index < 3 ? 1 : 0, message.time); });
Object.entries(seedMessages).forEach(([id, thread]) => {
  if (id !== "aiko") thread.forEach((message) => { message.sentAt = timestamp(2, message.time); });
});

type MessageClusterProps = {
  messages: ChatMessage[];
  name: string;
  initials: string;
  searchQuery: string;
  onReply: (message: ChatMessage) => void;
  onRetry: (id: number) => void;
  onEdit: (message: ChatMessage) => void;
  onDelete: (id: number) => void;
  onReact: (id: number, emoji?: string) => void;
  openMenuId: number | null;
  onToggleMenu: (id: number) => void;
};

const MessageCluster = memo(function MessageCluster({ messages, name, initials, searchQuery, onReply, onRetry, onEdit, onDelete, onReact, openMenuId, onToggleMenu }: MessageClusterProps) {
  const outgoing = messages[0].author === "me";
  return (
    <MessageGroup direction={outgoing ? "outgoing" : "incoming"} sender={outgoing ? "Bạn" : name} avatarPosition={outgoing ? "cr" : "cl"}>
      {!outgoing && <Avatar name={name} size="sm"><span className={styles.initialsAvatar}>{initials}</span></Avatar>}
      <MessageGroup.Messages>
        {messages.map((message, index) => {
          const indicator = deliveryIndicator(message.delivery);
          const position = messages.length === 1 ? "single" : index === 0 ? "first" : index === messages.length - 1 ? "last" : "normal";
          return (
            <Message key={message.id} model={{ message: message.text, sender: outgoing ? "Bạn" : name, sentTime: message.time, direction: outgoing ? "outgoing" : "incoming", position }}>
              <Message.Header><time className={styles.messageTimestamp}>{messageTime(message.sentAt)}{message.edited && !message.deleted && <span className={styles.editedMark}>đã sửa</span>}</time></Message.Header>
              <Message.CustomContent>
                <div className={styles.messageBubble}>
                  <div className={styles.messageContent}>
                  {message.reply && <blockquote className={styles.replyPreview}>{message.reply}</blockquote>}
                  <p className={message.deleted ? styles.deletedMessage : undefined}>{message.deleted ? "Tin nhắn đã được thu hồi" : highlight(message.text, searchQuery)}</p>
                  {message.file && <button className={styles.fileCard} type="button" aria-label={`Tải ${message.file.name}`}><span>PDF</span><strong>{message.file.name}<small>{message.file.meta}</small></strong><b aria-hidden="true">↓</b></button>}
                  </div>
                  {!message.deleted && <>
                    <div className={styles.messageQuickActions} aria-label="Thao tác nhanh">
                      {outgoing && <button type="button" aria-label="Sửa tin nhắn" onClick={() => onEdit(message)}>✎</button>}
                      <button type="button" aria-label="Mở thêm thao tác" aria-expanded={openMenuId === message.id} onClick={() => onToggleMenu(message.id)}>•••</button>
                    </div>
                    <div className={styles.reactionTray} aria-label="Thả cảm xúc">
                      {["👍", "❤️", "😂", "🎉", "👀"].map((emoji) => <button key={emoji} type="button" aria-label={`Thả ${emoji}`} onClick={() => onReact(message.id, emoji)}>{emoji}</button>)}
                    </div>
                    {openMenuId === message.id && <div className={styles.messageMenu} role="menu"><button type="button" role="menuitem" onClick={() => { onReply(message); onToggleMenu(message.id); }}>Trả lời</button>{outgoing && <button type="button" role="menuitem" onClick={() => { onEdit(message); onToggleMenu(message.id); }}>Sửa</button>}{outgoing && <button type="button" role="menuitem" onClick={() => { onDelete(message.id); onToggleMenu(message.id); }}>Xóa</button>}</div>}
                  </>}
                </div>
              </Message.CustomContent>
              <Message.Footer>
                {message.delivery === "failed" && <button className={styles.retryButton} type="button" onClick={() => onRetry(message.id)}>Không gửi được · Gửi lại</button>}
                {indicator && <span className={`${styles.deliveryIcon} ${styles[indicator.className]}`} role="img" aria-label={indicator.label} title={indicator.label}>{indicator.symbol}</span>}
                {message.reaction && <button className={styles.reaction} type="button" aria-label="Bỏ cảm xúc" onClick={() => onReact(message.id)}>{message.reaction}</button>}
              </Message.Footer>
            </Message>
          );
        })}
      </MessageGroup.Messages>
    </MessageGroup>
  );
});

export default function MessagingApp() {
  const [activeId, setActiveId] = useState("aiko");
  const [mobileView, setMobileView] = useState<"list" | "chat">("chat");
  const [query, setQuery] = useState("");
  const [showGroupCreator, setShowGroupCreator] = useState(false);
  const [groupName, setGroupName] = useState("");
  const [groupMembers, setGroupMembers] = useState("");
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const [conversationItems, setConversationItems] = useState(initialConversations);
  const [messages, setMessages] = useState(seedMessages);
  const [offline, setOffline] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);
  const [replying, setReplying] = useState<ChatMessage | null>(null);
  const [editing, setEditing] = useState<ChatMessage | null>(null);
  const [showMessageSearch, setShowMessageSearch] = useState(false);
  const [messageQuery, setMessageQuery] = useState("");
  const [uploading, setUploading] = useState(false);
  const [openMessageMenuId, setOpenMessageMenuId] = useState<number | null>(null);

  const active = conversationItems.find((item) => item.id === activeId) ?? conversationItems[0];
  const activeMessages = useMemo(() => messages[activeId] ?? [], [activeId, messages]);

  const visibleConversations = useMemo(() => conversationItems
    .filter((item) => filter === "all" || Boolean(item.unread))
    .filter((item) => `${item.name} ${item.preview}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()))
    .sort((a, b) => Number(Boolean(b.pinned)) - Number(Boolean(a.pinned))), [conversationItems, filter, query]);

  const grouped = useMemo(() => activeMessages.reduce<ChatMessage[][]>((groups, message) => {
    const previous = groups.at(-1)?.[0];
    if (!previous || previous.author !== message.author || dayKey(previous.sentAt) !== dayKey(message.sentAt)) groups.push([message]);
    else groups.at(-1)?.push(message);
    return groups;
  }, []), [activeMessages]);

  const searchMatches = useMemo(() => messageQuery.trim()
    ? activeMessages.filter((message) => !message.deleted && message.text.toLocaleLowerCase().includes(messageQuery.trim().toLocaleLowerCase())).length
    : 0, [activeMessages, messageQuery]);

  useEffect(() => {
    document.querySelector(".cs-button--attachment")?.setAttribute("aria-label", "Đính kèm tệp");
    document.querySelector(".cs-button--send")?.setAttribute("aria-label", "Gửi tin nhắn");
  }, [activeId, offline]);

  useEffect(() => {
    const goOffline = () => setOffline(true);
    const goOnline = () => {
      setOffline(false);
      setReconnecting(true);
      window.setTimeout(() => setReconnecting(false), 900);
    };
    window.addEventListener("offline", goOffline);
    window.addEventListener("online", goOnline);
    return () => { window.removeEventListener("offline", goOffline); window.removeEventListener("online", goOnline); };
  }, []);

  const updateActiveThread = useCallback((updater: (thread: ChatMessage[]) => ChatMessage[]) => {
    setMessages((current) => ({ ...current, [activeId]: updater(current[activeId] ?? []) }));
  }, [activeId]);

  const retry = useCallback((id: number) => {
    updateActiveThread((thread) => thread.map((message) => message.id === id ? { ...message, delivery: "sending" } : message));
    window.setTimeout(() => updateActiveThread((thread) => thread.map((message) => message.id === id ? { ...message, delivery: "delivered" } : message)), 650);
  }, [updateActiveThread]);

  const removeMessage = useCallback((id: number) => {
    updateActiveThread((thread) => thread.map((message) => message.id === id ? { ...message, deleted: true, text: "", reply: undefined, file: undefined, reaction: undefined } : message));
  }, [updateActiveThread]);

  const reactToMessage = useCallback((id: number, emoji?: string) => {
    updateActiveThread((thread) => thread.map((message) => message.id === id ? { ...message, reaction: emoji ? `${emoji} 1` : undefined } : message));
  }, [updateActiveThread]);

  const beginReply = useCallback((message: ChatMessage) => { setEditing(null); setReplying(message); }, []);
  const beginEdit = useCallback((message: ChatMessage) => { setReplying(null); setEditing(message); }, []);

  const send = useCallback((text: string) => {
    const cleanText = text.trim();
    if (!cleanText || offline) return;
    if (editing) {
      updateActiveThread((thread) => thread.map((message) => message.id === editing.id ? { ...message, text: cleanText, edited: true } : message));
      setEditing(null);
      return;
    }
    const id = Date.now();
    const now = new Date();
    const next: ChatMessage = { id, author: "me", text: cleanText, time: new Intl.DateTimeFormat("vi", { hour: "2-digit", minute: "2-digit" }).format(now), sentAt: now.toISOString(), delivery: "sending", reply: replying?.text };
    updateActiveThread((thread) => [...thread, next]);
    setReplying(null);
    window.setTimeout(() => updateActiveThread((thread) => thread.map((message) => message.id === id ? { ...message, delivery: "delivered" } : message)), 650);
  }, [editing, offline, replying, updateActiveThread]);

  const attachFile = useCallback(() => {
    if (offline || uploading) return;
    setUploading(true);
    window.setTimeout(() => {
      const now = new Date();
      updateActiveThread((thread) => [...thread, { id: Date.now(), author: "me", text: "Đã gửi một tệp", time: new Intl.DateTimeFormat("vi", { hour: "2-digit", minute: "2-digit" }).format(now), sentAt: now.toISOString(), delivery: "delivered", file: { name: "tai-lieu-du-an.pdf", meta: "PDF · 2,4 MB" } }]);
      setUploading(false);
    }, 900);
  }, [offline, updateActiveThread, uploading]);

  const selectConversation = useCallback((id: string) => {
    setActiveId(id);
    setReplying(null);
    setEditing(null);
    setOpenMessageMenuId(null);
    setMessageQuery("");
    setMobileView("chat");
    setConversationItems((items) => items.map((item) => item.id === id ? { ...item, unread: undefined, mention: false } : item));
  }, []);

  const createGroup = useCallback(() => {
    const name = groupName.trim();
    if (!name) return;
    const id = `group-${Date.now()}`;
    const memberCount = groupMembers.split(",").filter(Boolean).length + 1;
    setConversationItems((items) => [...items, { id, name, initials: "#", subtitle: `Nhóm · ${memberCount} thành viên`, preview: "Nhóm mới đã được tạo", time: "", online: true }]);
    setMessages((current) => ({ ...current, [id]: [] }));
    setGroupName("");
    setGroupMembers("");
    setShowGroupCreator(false);
    selectConversation(id);
  }, [groupMembers, groupName, selectConversation]);

  return (
    <main className={`${styles.appShell} ${mobileView === "chat" ? styles.mobileChat : styles.mobileList}`}>
      <MainContainer>
        <Sidebar position="left" scrollable={false} className={styles.chatSidebar}>
          <div className={styles.workspaceTop}><div><span className={styles.productMark}>LC</span><span><strong>LinguaChat</strong><small>Web nhắn tin trực tuyến</small></span></div></div>
          <div className={styles.sidebarTools}><div className={styles.sidebarSearchInline}><Search placeholder="Tìm hội thoại" value={query} onChange={setQuery} onClearClick={() => setQuery("")} /></div><button type="button" title="Tạo nhóm trò chuyện" aria-label="Tạo nhóm trò chuyện" aria-expanded={showGroupCreator} onClick={() => setShowGroupCreator((value) => !value)}>♧</button></div>
          {showGroupCreator && <form className={styles.groupCreator} onSubmit={(event) => { event.preventDefault(); createGroup(); }}><label htmlFor="group-name">Tên nhóm</label><input id="group-name" value={groupName} onChange={(event) => setGroupName(event.target.value)} placeholder="Ví dụ: Dự án tháng 8" autoFocus /><label htmlFor="group-members">Thành viên</label><input id="group-members" value={groupMembers} onChange={(event) => setGroupMembers(event.target.value)} placeholder="Tên, email (ngăn cách dấu phẩy)" /><button type="submit">Tạo nhóm</button></form>}
          <div className={styles.conversationFilters} aria-label="Lọc hội thoại">
            <button type="button" aria-pressed={filter === "all"} onClick={() => setFilter("all")}>Tất cả</button>
            <button type="button" aria-pressed={filter === "unread"} onClick={() => setFilter("unread")}>Chưa đọc</button>
          </div>
          <div className={styles.listTitle}><span>Hội thoại</span><span>{visibleConversations.length}</span></div>
          <ConversationList className={styles.conversationIndex}>
            {visibleConversations.map((conversation) => (
              <Conversation key={conversation.id} name={conversation.name} info={conversation.preview} lastActivityTime={conversation.time} unreadCnt={conversation.unread} unreadDot={conversation.mention} active={conversation.id === activeId} role="button" tabIndex={0}
                onClick={() => selectConversation(conversation.id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); selectConversation(conversation.id); } }}>
                <Avatar name={conversation.name} status={conversation.online ? "available" : "unavailable"}><span className={styles.initialsAvatar}>{conversation.initials}</span></Avatar>
                <Conversation.Content name={conversation.name} info={conversation.preview} />
              </Conversation>
            ))}
          </ConversationList>
          {!visibleConversations.length && <div className={styles.noResults}><strong>Không tìm thấy hội thoại</strong><button type="button" onClick={() => { setQuery(""); setFilter("all"); }}>Xóa bộ lọc</button></div>}
          <div className={styles.accountArea}><Avatar name="Phạm Đức Thiện" status="available" size="sm"><span className={styles.initialsAvatar}>PT</span></Avatar><span><strong>Phạm Đức Thiện</strong><small>Đang kết nối</small></span></div>
        </Sidebar>

        <ChatContainer className={styles.chatWorkspace}>
          <ConversationHeader className={styles.chatHeader}>
            <ConversationHeader.Back><button type="button" aria-label="Quay lại danh sách hội thoại" onClick={() => setMobileView("list")}>←</button></ConversationHeader.Back>
            <Avatar name={active.name} status={active.online ? "available" : "unavailable"}><span className={styles.initialsAvatar}>{active.initials}</span></Avatar>
            <ConversationHeader.Content userName={active.name} info={active.subtitle} />
            <ConversationHeader.Actions><button type="button" aria-label="Tìm trong hội thoại" aria-pressed={showMessageSearch} onClick={() => { setShowMessageSearch((value) => !value); setMessageQuery(""); }}>⌕</button><button type="button" aria-label="Thêm tùy chọn">•••</button></ConversationHeader.Actions>
          </ConversationHeader>

          <MessageList className={styles.messageTimeline} typingIndicator={activeId === "aiko" ? <TypingIndicator content="Aiko đang nhập" /> : undefined} autoScrollToBottom autoScrollToBottomOnMount scrollBehavior="smooth">
            {(offline || reconnecting) && <div className={styles.statusBanner} role="status"><strong>{offline ? "Ngoại tuyến" : "Đang kết nối lại…"}</strong><span>{offline ? "Bạn vẫn có thể đọc các tin nhắn đã tải." : "Đồng bộ tin nhắn mới."}</span></div>}
            {showMessageSearch && <div className={styles.messageSearch}><label htmlFor="message-search">Tìm trong cuộc trò chuyện</label><input id="message-search" autoFocus value={messageQuery} onChange={(event) => setMessageQuery(event.target.value)} placeholder="Nhập nội dung tin nhắn" /><span aria-live="polite">{messageQuery.trim() ? `${searchMatches} kết quả` : ""}</span><button type="button" onClick={() => { setShowMessageSearch(false); setMessageQuery(""); }} aria-label="Đóng tìm kiếm">×</button></div>}
            {activeMessages.length ? <>
              {grouped.map((cluster, index) => <div key={cluster[0].id}>{(index === 0 || dayKey(cluster[0].sentAt) !== dayKey(grouped[index - 1][0].sentAt)) && <MessageSeparator content={dateLabel(cluster[0].sentAt)} />}<MessageCluster messages={cluster} name={active.name} initials={active.initials} searchQuery={messageQuery} onReply={beginReply} onRetry={retry} onEdit={beginEdit} onDelete={removeMessage} onReact={reactToMessage} openMenuId={openMessageMenuId} onToggleMenu={(id) => setOpenMessageMenuId((current) => current === id ? null : id)} /></div>)}
            </> : <div className={styles.emptyState}><span>✦</span><h2>Bắt đầu cuộc trò chuyện</h2><p>Gửi tin nhắn đầu tiên trong không gian riêng của bạn.</p></div>}
          </MessageList>

          <InputToolbox className={`${styles.composerToolbox} ${replying || editing || uploading ? styles.composerToolboxActive : ""}`}>
            <button className={styles.attachAction} type="button" disabled={offline || uploading} onClick={attachFile} aria-label="Đính kèm tệp">📎 <span>Đính kèm</span></button>
            {(replying || editing || uploading) && <><span className={styles.composerContext}><strong>{uploading ? "Đang tải tệp…" : editing ? "Sửa tin nhắn" : `Trả lời ${active.name}`}</strong><small>{uploading ? "tai-lieu-du-an.pdf" : editing?.text ?? replying?.text}</small></span>{!uploading && <button className={styles.cancelAction} type="button" aria-label="Hủy thao tác" onClick={() => { setReplying(null); setEditing(null); }}>×</button>}</>}
          </InputToolbox>
          <MessageInput onSend={(_, text) => send(text)} placeholder={offline ? "Đang ngoại tuyến" : editing ? "Nhập nội dung đã sửa" : replying ? `Trả lời ${active.name}` : `Nhắn cho ${active.name}`} disabled={offline || uploading} sendButton attachButton={false} />
        </ChatContainer>
      </MainContainer>
    </main>
  );
}
