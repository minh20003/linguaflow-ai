import type { LanguageCode } from "@/shared/types/language";

export type { LanguageCode, LanguageOption } from "@/shared/types/language";

export interface User {
  id: string;
  email: string;
  name: string;
  username: string;
  avatar: string;
  nativeLanguage: LanguageCode;
  onlineStatus: 'online' | 'offline' | 'away' | 'busy';
  lastSeen?: string;
  bio?: string;
  role?: string;
}

export interface TranslationData {
  translationId: string;
  originalText: string;
  originalLanguage: LanguageCode;
  translatedText: string;
  targetLanguage: LanguageCode;
  status: 'idle' | 'pending' | 'success' | 'failed';
  showOriginal?: boolean;
  rating?: 1 | 5;
  correction?: string;
  editedText?: string;
}

export interface MessageReaction {
  emoji: string;
  count: number;
  users: string[]; // user IDs
}

export interface MessageReply {
  id: string;
  senderName: string;
  content: string;
}

export interface MessageAttachment {
  id: string;
  type: 'image' | 'file';
  url: string;
  name: string;
  size?: string;
  contentType?: string;
  createdAt?: string;
}

export interface MessageMention {
  type: 'user' | 'assistant';
  userId?: string;
}

export interface Message {
  id: string;
  senderId: string;
  senderName?: string;
  senderAvatar?: string;
  conversationId: string;
  content: string;
  translation?: TranslationData;
  timestamp: string;
  createdAt?: string;
  status: 'sending' | 'sent' | 'delivered' | 'read';
  replyTo?: MessageReply;
  forwardedFromMessageId?: string;
  reactions?: MessageReaction[];
  isSaved?: boolean;
  attachments?: MessageAttachment[];
  mentions?: MessageMention[];
  isAssistant?: boolean;
  dateDivider?: string;
}

export interface Conversation {
  id: string;
  type: 'direct' | 'group';
  name: string;
  avatar: string;
  isOnline?: boolean;
  memberCount?: number;
  members?: User[];
  recipient?: User;
  lastMessage: string;
  lastMessageTime: string;
  unreadCount: number;
  isTyping?: boolean;
  typingUser?: string;
  isMuted?: boolean;
  isPinned?: boolean;
  pinnedAt?: string | null;
  createdAt?: string | null;
  description?: string;
  createdBy?: string;
  currentUserRole?: 'owner' | 'admin' | 'member';
}

export interface AppSettings {
  preferredLanguage: LanguageCode;
  interfaceLanguage: LanguageCode;
  autoTranslate: boolean;
  showOriginalByDefault: boolean;
  translationTone: 'natural' | 'formal' | 'casual' | 'friendly';
  theme: 'light' | 'dark';
  soundEnabled: boolean;
  readReceipts: boolean;
  aiSmartAssistance: boolean;
  offlineModeSimulation: boolean;
}

export interface ToastItem {
  id: string;
  title: string;
  message?: string;
  type?: 'info' | 'success' | 'warning' | 'translation';
  timestamp?: number;
}

export type SidebarTab = 'chats' | 'contacts' | 'groups' | 'calendar' | 'settings';
