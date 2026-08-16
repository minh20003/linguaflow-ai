export type LanguageCode =
  | 'en'
  | 'vi'
  | 'ja'
  | 'ko'
  | 'zh'
  | 'es'
  | 'fr'
  | 'de'
  | 'th'
  | 'id';

export interface LanguageOption {
  code: LanguageCode;
  name: string;
  nativeName: string;
  flag: string;
}

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
  originalText: string;
  originalLanguage: LanguageCode;
  translatedText: string;
  targetLanguage: LanguageCode;
  status: 'idle' | 'pending' | 'success' | 'failed';
  showOriginal?: boolean;
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
  status: 'sending' | 'sent' | 'delivered' | 'read';
  replyTo?: MessageReply;
  reactions?: MessageReaction[];
  attachments?: MessageAttachment[];
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
  description?: string;
}

export interface AppSettings {
  preferredLanguage: LanguageCode;
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

export type SidebarTab = 'chats' | 'contacts' | 'groups' | 'settings';
