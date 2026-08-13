"use client";

import { memo, useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent, type ReactNode } from "react";
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
  TypingIndicator,
} from "@chatscope/chat-ui-kit-react";
import { UserRoundPlus, X } from "lucide-react";
import { logoutSession } from "@/shared/lib/api";
import { clearSession, getStoredRefreshToken, getStoredUser } from "@/shared/lib/auth-session";
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

function dayKey(value?: string) {
  return value?.slice(0, 10) ?? "";
}

// Demo messages must be deterministic: rendering `new Date()` or locale based
// formatting during SSR creates different markup from the browser at midnight
// or across time zones, which causes a React hydration mismatch.
const DEMO_TODAY = "2026-08-11";

function dateLabel(value?: string) {
  const key = dayKey(value);
  if (key === DEMO_TODAY) return "Hôm nay";
  if (key === "2026-08-10") return "Thứ hai, 10/08";
  return key;
}

function messageTime(value?: string) {
  if (!value) return "";
  const key = dayKey(value);
  const clock = value.slice(11, 16);
  if (key === DEMO_TODAY) return clock;
  return `${key.slice(8, 10)}-${key.slice(5, 7)} · ${clock}`;
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
    { id: 3, author: "them", text: "Cảm ơn bạn. Chúng ta gặp ở quán cà phê gần ga nhé.", time: "09:03" },
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

seedMessages.aiko.forEach((message, index) => {
  const date = index < 3 ? "2026-08-10" : DEMO_TODAY;
  message.sentAt = `${date}T${message.time}:00.000Z`;
});
Object.entries(seedMessages).forEach(([id, thread]) => {
  if (id !== "aiko") thread.forEach((message) => { message.sentAt = `2026-08-09T${message.time}:00.000Z`; });
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
  openMenuId: number | null;
  onToggleMenu: (id: number) => void;
};

const MessageCluster = memo(function MessageCluster({ messages, name, initials, searchQuery, onReply, onRetry, onEdit, onDelete, openMenuId, onToggleMenu }: MessageClusterProps) {
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
                    {openMenuId === message.id && <div className={styles.messageMenu} role="menu"><button type="button" role="menuitem" onClick={() => { onReply(message); onToggleMenu(message.id); }}>Trả lời</button>{outgoing && <button type="button" role="menuitem" onClick={() => { onEdit(message); onToggleMenu(message.id); }}>Sửa</button>}{outgoing && <button type="button" role="menuitem" onClick={() => { onDelete(message.id); onToggleMenu(message.id); }}>Xóa</button>}</div>}
                  </>}
                </div>
              </Message.CustomContent>
              <Message.Footer>
                {message.delivery === "failed" && <button className={styles.retryButton} type="button" onClick={() => onRetry(message.id)}>Không gửi được · Gửi lại</button>}
                {indicator && <span className={`${styles.deliveryIcon} ${styles[indicator.className]}`} role="img" aria-label={indicator.label} title={indicator.label}>{indicator.symbol}</span>}
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
  const [activeId, setActiveId] = useState("aiko");
  const [mobileView, setMobileView] = useState<"list" | "chat">("chat");
  const [query, setQuery] = useState("");
  const [showGroupCreator, setShowGroupCreator] = useState(false);
  const [groupName, setGroupName] = useState("");
  const [groupMembers, setGroupMembers] = useState<string[]>([]);
  const [groupUserQuery, setGroupUserQuery] = useState("");
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
  const [uploadProgress, setUploadProgress] = useState(0);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [openMessageMenuId, setOpenMessageMenuId] = useState<number | null>(null);
  const [showAccountMenu, setShowAccountMenu] = useState(false);
  const [accountName, setAccountName] = useState("Phạm Đức Thiện");
  const [accountEmail, setAccountEmail] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const active = conversationItems.find((item) => item.id === activeId) ?? conversationItems[0];
  const activeMessages = useMemo(() => messages[activeId] ?? [], [activeId, messages]);

  const visibleConversations = useMemo(() => conversationItems
    .filter((item) => filter === "all" || Boolean(item.unread))
    .filter((item) => `${item.name} ${item.preview}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()))
    .sort((a, b) => Number(Boolean(b.pinned)) - Number(Boolean(a.pinned))), [conversationItems, filter, query]);

  const groupCandidates = useMemo(() => initialConversations
    .filter((item) => item.id !== "notes")
    .filter((item) => `${item.name} ${item.subtitle}`.toLocaleLowerCase().includes(groupUserQuery.trim().toLocaleLowerCase())), [groupUserQuery]);

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
    const user = getStoredUser();
    if (user) {
      setAccountName(user.display_name || user.username || user.email.split("@")[0]);
      setAccountEmail(user.email);
    }
  }, []);

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
    updateActiveThread((thread) => thread.map((message) => message.id === id ? { ...message, deleted: true, text: "", reply: undefined, file: undefined } : message));
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

  const clearAttachment = useCallback(() => {
    setPendingFile(null);
    setUploading(false);
    setUploadProgress(0);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, []);

  const uploadFile = useCallback((file: File) => {
    setPendingFile(file);
    setUploading(true);
    setUploadProgress(0);
    const timer = window.setInterval(() => {
      setUploadProgress((current) => {
        const next = Math.min(100, current + 20);
        if (next === 100) {
          window.clearInterval(timer);
          setUploading(false);
        }
        return next;
      });
    }, 160);
  }, []);

  const chooseFile = useCallback(() => {
    if (!offline && !uploading) fileInputRef.current?.click();
  }, [offline, uploading]);

  const handleFileSelection = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) uploadFile(file);
  }, [uploadFile]);

  const sendFile = useCallback(() => {
    if (!pendingFile || uploading || offline) return;
    const now = new Date();
    const file = pendingFile;
    updateActiveThread((thread) => [...thread, {
      id: Date.now(), author: "me", text: "Đã gửi một tệp",
      time: new Intl.DateTimeFormat("vi", { hour: "2-digit", minute: "2-digit" }).format(now),
      sentAt: now.toISOString(), delivery: "sending",
      file: { name: file.name, meta: `${fileKind(file.name)} · ${formatFileSize(file.size)}` },
    }]);
    clearAttachment();
  }, [clearAttachment, offline, pendingFile, updateActiveThread, uploading]);

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
    if (!name || !groupMembers.length) return;
    const id = `group-${Date.now()}`;
    const memberCount = groupMembers.length + 1;
    setConversationItems((items) => [...items, { id, name, initials: "#", subtitle: `Nhóm · ${memberCount} thành viên`, preview: "Nhóm mới đã được tạo", time: "", online: true }]);
    setMessages((current) => ({ ...current, [id]: [] }));
    setGroupName("");
    setGroupMembers([]);
    setGroupUserQuery("");
    setShowGroupCreator(false);
    selectConversation(id);
  }, [groupMembers, groupName, selectConversation]);

  const closeGroupCreator = useCallback(() => {
    setShowGroupCreator(false);
    setGroupName("");
    setGroupMembers([]);
    setGroupUserQuery("");
  }, []);

  const toggleGroupMember = useCallback((id: string) => {
    setGroupMembers((current) => current.includes(id) ? current.filter((memberId) => memberId !== id) : [...current, id]);
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

  useEffect(() => {
    if (!showGroupCreator) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeGroupCreator();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [closeGroupCreator, showGroupCreator]);

  return (
    <main className={`${styles.appShell} ${mobileView === "chat" ? styles.mobileChat : styles.mobileList}`}>
      <MainContainer>
        <Sidebar position="left" scrollable={false} className={styles.chatSidebar}>
          <div className={styles.workspaceTop}><div><span className={styles.productMark}>LC</span><span><strong>LinguaChat</strong><small>Web nhắn tin trực tuyến</small></span></div></div>
          <div className={styles.sidebarTools}><div className={styles.sidebarSearchInline}><Search placeholder="Tìm hội thoại" value={query} onChange={setQuery} onClearClick={() => setQuery("")} /></div><button type="button" title="Tạo nhóm trò chuyện" aria-label="Tạo nhóm trò chuyện" aria-expanded={showGroupCreator} onClick={() => setShowGroupCreator(true)}><UserRoundPlus size={18} strokeWidth={1.8} aria-hidden="true" /></button></div>
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
          <div className={styles.accountArea}><Avatar name={accountName} status="available" size="sm"><span className={styles.initialsAvatar}>{accountName.split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase()}</span></Avatar><span><strong>{accountName}</strong><small>{accountEmail || "Đang kết nối"}</small></span><button type="button" className={styles.accountMenuButton} aria-label="Mở tùy chọn tài khoản" title="Tùy chọn tài khoản" aria-expanded={showAccountMenu} onClick={() => setShowAccountMenu((current) => !current)}>•••</button>{showAccountMenu && <div className={styles.accountMenu} role="menu"><button type="button" role="menuitem" onClick={signOut}>Đăng xuất</button></div>}</div>
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
              {grouped.map((cluster, index) => <div key={cluster[0].id}>{(index === 0 || dayKey(cluster[0].sentAt) !== dayKey(grouped[index - 1][0].sentAt)) && <MessageSeparator content={dateLabel(cluster[0].sentAt)} />}<MessageCluster messages={cluster} name={active.name} initials={active.initials} searchQuery={messageQuery} onReply={beginReply} onRetry={retry} onEdit={beginEdit} onDelete={removeMessage} openMenuId={openMessageMenuId} onToggleMenu={(id) => setOpenMessageMenuId((current) => current === id ? null : id)} /></div>)}
            </> : <div className={styles.emptyState}><span>✦</span><h2>Bắt đầu cuộc trò chuyện</h2><p>Gửi tin nhắn đầu tiên trong không gian riêng của bạn.</p></div>}
          </MessageList>

          {pendingFile && <div className={styles.fileUploadPreview} role="status">
            <span className={styles.fileType}>{fileKind(pendingFile.name)}</span>
            <div><strong>{pendingFile.name}</strong><small>{uploading ? `Đang tải lên · ${uploadProgress}%` : `Sẵn sàng gửi · ${formatFileSize(pendingFile.size)}`}</small>{uploading && <span className={styles.uploadProgress} aria-hidden="true"><span style={{ width: `${uploadProgress}%` }} /></span>}</div>
            {!uploading && <button className={styles.sendFileAction} type="button" onClick={sendFile}>Gửi tệp</button>}
            <button className={styles.cancelAction} type="button" onClick={clearAttachment} aria-label="Hủy tệp đính kèm">×</button>
          </div>}

          <input ref={fileInputRef} className={styles.fileInput} type="file" onChange={handleFileSelection} tabIndex={-1} aria-hidden="true" />
          {(replying || editing) && <InputToolbox className={`${styles.composerToolbox} ${styles.composerToolboxActive}`}>
            <span className={styles.composerContext}><strong>{editing ? "Sửa tin nhắn" : `Trả lời ${active.name}`}</strong><small>{editing?.text ?? replying?.text}</small></span><button className={styles.cancelAction} type="button" aria-label="Hủy thao tác" onClick={() => { setReplying(null); setEditing(null); }}>×</button>
          </InputToolbox>}
          <MessageInput onSend={(_, text) => send(text)} onAttachClick={chooseFile} placeholder={offline ? "Đang ngoại tuyến" : editing ? "Nhập nội dung đã sửa" : replying ? `Trả lời ${active.name}` : `Nhắn cho ${active.name}`} disabled={offline || uploading} sendButton attachButton attachDisabled={offline || uploading} />
        </ChatContainer>
      </MainContainer>
      {showGroupCreator && <div className={styles.modalBackdrop} onMouseDown={(event) => { if (event.target === event.currentTarget) closeGroupCreator(); }}>
        <section className={styles.groupModal} role="dialog" aria-modal="true" aria-labelledby="group-dialog-title">
          <header><div><span className={styles.groupModalIcon}><UserRoundPlus size={20} aria-hidden="true" /></span><span><h2 id="group-dialog-title">Tạo nhóm trò chuyện</h2><p>Chọn những người bạn muốn thêm vào nhóm.</p></span></div><button type="button" aria-label="Đóng" onClick={closeGroupCreator}><X size={20} aria-hidden="true" /></button></header>
          <form onSubmit={(event) => { event.preventDefault(); createGroup(); }}>
            <label htmlFor="group-name">Tên nhóm</label><input id="group-name" value={groupName} onChange={(event) => setGroupName(event.target.value)} placeholder="Ví dụ: Dự án tháng 8" autoFocus />
            <label htmlFor="group-user-search">Thêm thành viên</label><div className={styles.groupUserSearch}><span aria-hidden="true">⌕</span><input id="group-user-search" value={groupUserQuery} onChange={(event) => setGroupUserQuery(event.target.value)} placeholder="Tìm theo tên hoặc vai trò" /></div>
            <div className={styles.memberResults} role="group" aria-label="Danh sách người dùng">{groupCandidates.map((candidate) => <label key={candidate.id} className={styles.memberOption}><input type="checkbox" checked={groupMembers.includes(candidate.id)} onChange={() => toggleGroupMember(candidate.id)} /><span className={styles.memberAvatar}>{candidate.initials}</span><span><strong>{candidate.name}</strong><small>{candidate.subtitle}</small></span></label>)}{!groupCandidates.length && <p>Không tìm thấy người dùng phù hợp.</p>}</div>
            <footer><span>{groupMembers.length} người được chọn</span><button type="button" onClick={closeGroupCreator}>Hủy</button><button type="submit" disabled={!groupName.trim() || !groupMembers.length}>Tạo nhóm</button></footer>
          </form>
        </section>
      </div>}
    </main>
  );
}
