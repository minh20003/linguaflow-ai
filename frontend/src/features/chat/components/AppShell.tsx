"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { WifiOff } from "lucide-react";
import { clearSession, getAccessToken, getRefreshToken } from "@/features/auth/lib/session";
import { signOut } from "@/features/auth/api/auth-api";
import type { AppSettings, Conversation, Message, SidebarTab, ToastItem, User } from "../types";
import { DEFAULT_CHAT_SETTINGS } from "../constants";
import { createConversation, deleteMessage, getMe, getMessages, listConversations, listUsers, markRead, toChatUser, toConversation, toLanguageCode, toMessage, toMessages, uploadAttachment, type ApiMessage } from "../api/chat-api";
import { newClientMessageId, socketUrl } from "../api/chat-socket";
import { MiniSidebar } from "./MiniSidebar";
import { ConversationPanel } from "./ConversationPanel";
import { ContactsPanel } from "./ContactsPanel";
import { GroupsPanel } from "./GroupsPanel";
import { ChatView } from "./ChatView";
import { NewConversationModal } from "./NewConversationModal";
import { CreateGroupModal } from "./CreateGroupModal";
import { SettingsModal } from "./SettingsModal";
import { CallModal } from "./CallModal";
import { ToastContainer } from "./ToastContainer";

const EMPTY_USER: User = { id: "", email: "", name: "", username: "", avatar: "", nativeLanguage: "en", onlineStatus: "offline" };

function conversationUsers(items: Awaited<ReturnType<typeof listConversations>>): User[] {
  const indexed = new Map<string, User>();
  for (const item of items) for (const member of item.members) indexed.set(member.id, toChatUser(member));
  return [...indexed.values()];
}

export const AppShell: React.FC = () => {
  const router = useRouter();
  const socket = useRef<WebSocket | null>(null);
  const token = useRef<string | null>(null);
  const [currentUser, setCurrentUser] = useState<User>(EMPTY_USER);
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_CHAT_SETTINGS);
  const [users, setUsers] = useState<User[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [messagesMap, setMessagesMap] = useState<Record<string, Message[]>>({});
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<SidebarTab>("chats");
  const [mobileView, setMobileView] = useState<"list" | "chat">("list");
  const [isNewChatOpen, setIsNewChatOpen] = useState(false);
  const [isCreateGroupOpen, setIsCreateGroupOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [callState, setCallState] = useState<{ isOpen: boolean; type: "voice" | "video" }>({ isOpen: false, type: "voice" });

  const addToast = useCallback((title: string, message?: string, type: ToastItem["type"] = "info") => {
    const id = `toast_${Date.now()}`;
    setToasts((items) => [...items, { id, title, message, type }]);
    window.setTimeout(() => setToasts((items) => items.filter((item) => item.id !== id)), 3500);
  }, []);

  const handleLogout = useCallback(async () => {
    if (isLoggingOut) return;
    setIsLoggingOut(true);
    const refreshToken = getRefreshToken();

    try {
      if (refreshToken) await signOut(refreshToken);
    } catch {
      // Local logout must still complete when the network is unavailable.
    } finally {
      socket.current?.close();
      socket.current = null;
      token.current = null;
      clearSession();
      router.replace("/login");
    }
  }, [isLoggingOut, router]);

  const selectedConversation = conversations.find((item) => item.id === selectedConversationId) ?? null;
  const currentMessages = selectedConversationId ? messagesMap[selectedConversationId] ?? [] : [];
  const usersById = useMemo(() => new Map([currentUser, ...users].filter((user) => user.id).map((user) => [user.id, user])), [currentUser, users]);

  const loadConversationMessages = useCallback(async (conversationId: string) => {
    if (!token.current) return;
    const history = await getMessages(token.current, conversationId);
    setMessagesMap((previous) => ({ ...previous, [conversationId]: toMessages(history, usersById, settings.preferredLanguage) }));
  }, [settings.preferredLanguage, usersById]);

  const refreshConversations = useCallback(async () => {
    if (!token.current || !currentUser.id) return;
    const result = await listConversations(token.current);
    setConversations(result.map((item) => toConversation(item, currentUser.id)));
    setUsers(conversationUsers(result).filter((user) => user.id !== currentUser.id));
  }, [currentUser.id]);

  useEffect(() => {
    const accessToken = getAccessToken();
    if (!accessToken) { router.replace("/login"); return; }
    token.current = accessToken;
    let active = true;
    getMe(accessToken).then(async (profile) => {
      const user = toChatUser(profile);
      const list = await listConversations(accessToken);
      if (!active) return;
      const contacts = conversationUsers(list).filter((contact) => contact.id !== user.id);
      setCurrentUser(user);
      setUsers(contacts);
      setSettings((value) => ({ ...value, preferredLanguage: user.nativeLanguage }));
      setConversations(list.map((item) => toConversation(item, user.id)));
      if (list[0]) {
        const members = new Map([user, ...contacts].map((contact) => [contact.id, contact]));
        const history = await getMessages(accessToken, list[0].id);
        if (!active) return;
        setMessagesMap({ [list[0].id]: toMessages(history, members, user.nativeLanguage) });
        setSelectedConversationId(list[0].id);
      }
    }).catch(() => { clearSession(); router.replace("/login"); });
    return () => { active = false; };
  }, [router]);

  useEffect(() => {
    if (!currentUser.id || !token.current) return;
    let disposed = false;
    let retry: number | undefined;
    const connect = () => {
      const ws = new WebSocket(socketUrl());
      socket.current = ws;
      ws.onopen = () => ws.send(JSON.stringify({ type: "auth", token: token.current }));
      ws.onmessage = (event) => {
        const payload = JSON.parse(event.data) as Record<string, unknown>;
        const eventType = payload.type as string;
        if (eventType === "message_created" || eventType === "message_received") {
          const realtime = payload.message as Record<string, unknown>;
          const clientMessageId = payload.client_message_id as string | undefined;
          const message: ApiMessage = { id: realtime.id as string, client_message_id: clientMessageId || realtime.id as string, conversation_id: realtime.conversation_id as string, sender_id: realtime.sender_id as string, original_text: realtime.original_text as string, source_language: settings.preferredLanguage, translations: [], created_at: realtime.created_at as string, deleted_at: null, reply_to_message_id: realtime.reply_to_message_id as string | null };
          const mapped = toMessage(message, usersById, settings.preferredLanguage);
          setMessagesMap((previous) => {
            const messages = previous[mapped.conversationId] ?? [];
            const withoutOptimistic = clientMessageId ? messages.filter((item) => item.id !== clientMessageId) : messages;
            const repliedMessage = mapped.replyTo ? withoutOptimistic.find((item) => item.id === mapped.replyTo?.id) : undefined;
            const replyContent = repliedMessage
              ? (
                repliedMessage.senderId === currentUser.id || repliedMessage.translation?.showOriginal
                  ? repliedMessage.content
                  : repliedMessage.translation?.translatedText || repliedMessage.content
              )
              : undefined;
            const messageWithReply = repliedMessage && mapped.replyTo ? {
              ...mapped,
              replyTo: { id: repliedMessage.id, senderName: repliedMessage.senderName || "Message", content: replyContent || repliedMessage.content },
            } : mapped;
            return { ...previous, [mapped.conversationId]: withoutOptimistic.some((item) => item.id === mapped.id) ? withoutOptimistic : [...withoutOptimistic, messageWithReply] };
          });
          void refreshConversations();
        }
        // This is the authoritative result produced by the LangGraph translation
        // agent. The server persists it before publishing, so REST history also
        // restores it after a reconnect.
        if (eventType === "translation_completed" || eventType === "translation.completed") {
          const messageId = payload.message_id as string;
          const targetLanguage = String(payload.target_language || settings.preferredLanguage);
          if (targetLanguage !== settings.preferredLanguage) return;
          const translatedText = String(payload.translated_text ?? payload.content ?? "");
          const sourceLanguage = toLanguageCode(String(payload.source_language || "en"));
          const status = payload.status === "failed" || !translatedText ? "failed" : "success";
          setMessagesMap((previous) => Object.fromEntries(Object.entries(previous).map(([conversationId, messages]) => [conversationId, messages.map((item) => item.id === messageId ? { ...item, translation: { originalText: item.content, originalLanguage: sourceLanguage, translatedText, targetLanguage: toLanguageCode(targetLanguage), status } } : item)])));
        }
        if (eventType === "typing") setConversations((items) => items.map((item) => item.id === payload.conversation_id ? { ...item, isTyping: Boolean(payload.is_typing) } : item));
        if (eventType === "message_updated" || eventType === "message_deleted") {
          const messageId = payload.message_id as string;
          setMessagesMap((previous) => Object.fromEntries(Object.entries(previous).map(([conversationId, messages]) => [conversationId, messages.map((item) => item.id === messageId ? { ...item, content: eventType === "message_deleted" ? "This message was deleted" : payload.original_text as string, translation: undefined } : item)])));
        }
        if (eventType === "error") addToast("Chat error", payload.message as string, "warning");
      };
      ws.onclose = () => { if (!disposed) retry = window.setTimeout(connect, 1500); };
    };
    connect();
    return () => { disposed = true; if (retry) window.clearTimeout(retry); socket.current?.close(); };
  }, [addToast, currentUser.id, refreshConversations, settings.preferredLanguage, usersById]);

  useEffect(() => { document.documentElement.classList.toggle("dark", settings.theme === "dark"); }, [settings.theme]);

  const selectConversation = async (conversation: Conversation) => {
    setSelectedConversationId(conversation.id); setMobileView("chat");
    try {
      await Promise.all([loadConversationMessages(conversation.id), markRead(token.current!, conversation.id)]);
      setConversations((items) => items.map((item) => item.id === conversation.id ? { ...item, unreadCount: 0 } : item));
    } catch (error) { addToast("Could not load messages", error instanceof Error ? error.message : undefined, "warning"); }
  };

  const send = (text: string, replyToMessageId?: string, attachmentId?: string) => {
    if (!selectedConversationId || socket.current?.readyState !== WebSocket.OPEN) { addToast("Reconnecting", "Your message will send when realtime reconnects.", "warning"); return; }
    const clientMessageId = newClientMessageId();
    const repliedMessage = replyToMessageId ? currentMessages.find((message) => message.id === replyToMessageId) : undefined;
    const optimistic: Message = { id: clientMessageId, senderId: currentUser.id, senderName: currentUser.name, senderAvatar: currentUser.avatar, conversationId: selectedConversationId, content: text, timestamp: "Now", status: "sending", replyTo: repliedMessage ? { id: repliedMessage.id, senderName: repliedMessage.senderName || "Message", content: repliedMessage.content } : undefined };
    setMessagesMap((previous) => ({ ...previous, [selectedConversationId]: [...(previous[selectedConversationId] ?? []), optimistic] }));
    socket.current.send(JSON.stringify({ type: "send_message", client_message_id: clientMessageId, conversation_id: selectedConversationId, text, reply_to_message_id: replyToMessageId, attachment_id: attachmentId }));
  };

  const startConversation = async (user: User) => {
    try {
      const item = await createConversation(token.current!, "direct", [user.id]);
      const conversation = toConversation(item, currentUser.id);
      setUsers((items) => [...items.filter((item) => item.id !== user.id), user]);
      setConversations((items) => [conversation, ...items.filter((value) => value.id !== conversation.id)]);
      await selectConversation(conversation); setActiveTab("chats");
    } catch (error) { addToast("Could not start conversation", error instanceof Error ? error.message : undefined, "warning"); }
  };

  const createGroup = async (name: string, memberIds: string[]) => {
    try {
      const item = await createConversation(token.current!, "group", memberIds, name);
      const conversation = toConversation(item, currentUser.id);
      setConversations((items) => [conversation, ...items]); await selectConversation(conversation); setActiveTab("chats"); addToast("Group created", name, "success");
    } catch (error) { addToast("Could not create group", error instanceof Error ? error.message : undefined, "warning"); }
  };

  const attach = async (file: File) => {
    if (!selectedConversationId || !token.current) return;
    try { const attachment = await uploadAttachment(token.current, selectedConversationId, file); send(`Shared ${file.name}`, undefined, attachment.id); }
    catch (error) { addToast("Could not upload attachment", error instanceof Error ? error.message : undefined, "warning"); }
  };

  const searchUsers = async (query: string) => {
    if (!token.current || query.trim().length < 2) return;
    try { setUsers((await listUsers(token.current, query.trim())).map(toChatUser)); }
    catch (error) { addToast("Could not search contacts", error instanceof Error ? error.message : undefined, "warning"); }
  };
  const unreadChatsCount = conversations.reduce((total, item) => total + item.unreadCount, 0);
  if (!currentUser.id) return <div className="h-screen bg-[#F7F8FC]" />;

  return <div id="linguachat-app-shell" className="flex w-screen h-screen overflow-hidden bg-[#F7F8FC] dark:bg-[#14161C] select-none">
    {settings.offlineModeSimulation && <div className="absolute top-0 inset-x-0 z-50 flex items-center justify-center gap-2 py-1 px-4 bg-amber-500 text-white text-xs font-semibold"><WifiOff className="w-3.5 h-3.5" />You&apos;re offline. Messages will send automatically when you reconnect.</div>}
    <div className={mobileView === "chat" ? "hidden md:flex" : "flex"}><MiniSidebar activeTab={activeTab} onTabChange={(tab) => tab === "settings" ? setIsSettingsOpen(true) : setActiveTab(tab)} currentUser={currentUser} settings={settings} onOpenSettings={() => setIsSettingsOpen(true)} onToggleTheme={() => setSettings((value) => ({ ...value, theme: value.theme === "dark" ? "light" : "dark" }))} onLogout={handleLogout} isLoggingOut={isLoggingOut} unreadChatsCount={unreadChatsCount} /></div>
    <div className={`h-screen flex-shrink-0 ${mobileView === "chat" ? "hidden md:flex" : "flex w-full md:w-[340px]"}`}>
      {activeTab === "chats" && <ConversationPanel conversations={conversations} selectedConversationId={selectedConversationId} onSelectConversation={selectConversation} onOpenNewChat={() => setIsNewChatOpen(true)} onMarkAllAsRead={() => conversations.forEach((item) => void markRead(token.current!, item.id))} />}
      {activeTab === "contacts" && <ContactsPanel users={users} onSearchUsers={searchUsers} onStartChatWithUser={startConversation} onOpenNewChat={() => setIsNewChatOpen(true)} />}
      {activeTab === "groups" && <GroupsPanel conversations={conversations} selectedConversationId={selectedConversationId} onSelectConversation={selectConversation} onCreateGroupClick={() => setIsCreateGroupOpen(true)} />}
    </div>
    <div className={`flex-1 flex min-w-0 h-screen overflow-hidden ${mobileView === "list" ? "hidden md:flex" : "flex w-full"}`}><ChatView conversation={selectedConversation} messages={currentMessages} currentUser={currentUser} onBack={() => setMobileView("list")} onSendMessage={send} onSendAttachment={attach} onTyping={(isTyping) => selectedConversationId && socket.current?.readyState === WebSocket.OPEN && socket.current.send(JSON.stringify({ type: "typing", conversation_id: selectedConversationId, is_typing: isTyping }))} onReact={() => addToast("Not available", "Reactions are not supported by the backend yet.", "info")} onCopy={(text) => void navigator.clipboard.writeText(text)} onToggleOriginal={(id) => setMessagesMap((items) => ({ ...items, [selectedConversationId!]: (items[selectedConversationId!] ?? []).map((message) => message.id === id && message.translation ? { ...message, translation: { ...message.translation, showOriginal: !message.translation.showOriginal } } : message) }))} onRetryTranslation={() => addToast("Translation", "Translations are generated automatically by the backend.", "info")} onDeleteMessage={(id) => selectedConversationId && void deleteMessage(token.current!, selectedConversationId, id).catch((error) => addToast("Could not delete message", error.message, "warning"))} onToggleMute={() => addToast("Not available", "Notification settings are not exposed by the backend yet.", "info")} onOpenNewChat={() => setIsNewChatOpen(true)} onStartCall={(type) => setCallState({ isOpen: true, type })} /></div>
    <NewConversationModal isOpen={isNewChatOpen} onClose={() => setIsNewChatOpen(false)} onSelectUser={startConversation} onCreateGroupClick={() => setIsCreateGroupOpen(true)} users={users} onSearchUsers={searchUsers} />
    <CreateGroupModal isOpen={isCreateGroupOpen} onClose={() => setIsCreateGroupOpen(false)} onCreateGroup={createGroup} users={users} onSearchUsers={searchUsers} />
    <SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} settings={settings} onUpdateSettings={(value) => setSettings((previous) => ({ ...previous, ...value }))} currentUser={currentUser} onUpdateUser={(value) => setCurrentUser((previous) => ({ ...previous, ...value }))} />
    {selectedConversation && <CallModal isOpen={callState.isOpen} type={callState.type} conversation={selectedConversation} onEndCall={() => setCallState({ isOpen: false, type: "voice" })} />}
    <ToastContainer toasts={toasts} onDismiss={(id) => setToasts((items) => items.filter((item) => item.id !== id))} />
  </div>;
};
