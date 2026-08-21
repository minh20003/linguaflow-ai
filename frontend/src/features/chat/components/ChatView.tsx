import React, { useState } from 'react';
import { Conversation, Message, User, MessageReply, MessageAttachment } from '../types';
import { ChatHeader } from './ChatHeader';
import { MessageList } from './MessageList';
import { MessageComposer } from './MessageComposer';
import { ConversationDetailsDrawer } from './ConversationDetailsDrawer';
import { MessageSquare, Sparkles, Plus, Globe } from 'lucide-react';

interface ChatViewProps {
  conversation: Conversation | null;
  messages: Message[];
  currentUser: User;
  onBack?: () => void;
  onSendMessage: (text: string, replyToMessageId?: string) => void;
  onSendAttachment?: (file: File) => void;
  onTyping?: (isTyping: boolean) => void;
  onReact: (messageId: string, emoji: string) => void;
  onCopy: (text: string) => void;
  onToggleOriginal: (messageId: string) => void;
  onRetryTranslation: (messageId: string) => void;
  onRateTranslation: (messageId: string, translationId: string, rating: 1 | 5) => void;
  onEditTranslation: (messageId: string, translationId: string, editedText: string) => void;
  onForward: (message: Message) => void;
  onDeleteMessage?: (messageId: string) => void;
  onToggleMute: (conversationId: string) => void;
  onOpenNewChat: () => void;
  onStartCall: (type: 'voice' | 'video') => void;
  language: User['nativeLanguage'];
  attachments: MessageAttachment[];
  onDownloadAttachment: (attachment: MessageAttachment) => void;
  onLoadAttachmentPreview: (attachment: MessageAttachment) => Promise<string>;
}

export const ChatView: React.FC<ChatViewProps> = ({
  conversation,
  messages,
  currentUser,
  onBack,
  onSendMessage,
  onSendAttachment,
  onTyping,
  onReact,
  onCopy,
  onToggleOriginal,
  onRetryTranslation,
  onRateTranslation,
  onEditTranslation,
  onForward,
  onDeleteMessage,
  onToggleMute,
  onOpenNewChat,
  onStartCall,
  language,
  attachments,
  onDownloadAttachment,
  onLoadAttachmentPreview,
}) => {
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);
  const [replyTo, setReplyTo] = useState<MessageReply | null>(null);

  // If no conversation is active, render the clean centered empty state
  if (!conversation) {
    return (
      <div
        id="empty-chat-state"
        className="flex-1 flex flex-col items-center justify-center h-screen bg-[#F7F8FC] dark:bg-[#14161C] px-6 text-center select-none"
      >
        <div className="flex items-center justify-center w-16 h-16 rounded-3xl bg-gradient-to-tr from-[#2563EB] to-[#60A5FA] text-white shadow-lg shadow-[#2563EB]/20 mb-4">
          <MessageSquare className="w-8 h-8" />
        </div>

        <h2 className="text-xl font-bold text-[#1E2230] dark:text-[#F5F6FA] mb-1.5">
          Your conversations live here
        </h2>
        <p className="text-sm text-[#74798C] dark:text-[#9DA3B4] max-w-sm mb-6 leading-relaxed">
          Chat naturally across languages with AI-assisted instant translation and real-time smart suggestions.
        </p>

        <button
          onClick={onOpenNewChat}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#2563EB] text-white font-semibold text-sm hover:bg-[#1D4ED8] shadow-md shadow-[#2563EB]/25 hover:scale-105 active:scale-95 transition-all"
        >
          <Plus className="w-4 h-4" />
          <span>Start a conversation</span>
        </button>
      </div>
    );
  }

  const handleReply = (message: Message) => {
    setReplyTo({
      id: message.id,
      senderName: message.senderName || 'Sender',
      content: message.senderId === currentUser.id || message.translation?.showOriginal
        ? message.content
        : message.translation?.translatedText || message.content,
    });
  };

  return (
    <div className="flex-1 flex h-screen min-w-0 overflow-hidden bg-[#F7F8FC] dark:bg-[#14161C]">
      {/* Main Active Chat Column - Stretches to fill entire available width */}
      <main
        id="active-chat-panel"
        className="flex-1 flex flex-col h-screen min-w-0 bg-[#F7F8FC] dark:bg-[#14161C] transition-colors"
      >
        {/* Full-width Chat Header */}
        <ChatHeader
          conversation={conversation}
          onBack={onBack}
          onToggleDetails={() => setIsDetailsOpen(!isDetailsOpen)}
          isDetailsOpen={isDetailsOpen}
          onStartCall={onStartCall}
          onSearchInChat={() => {}}
          language={language}
        />

        {/* Full-width Messages Container */}
        <MessageList
          messages={messages}
          currentUser={currentUser}
          conversation={conversation}
          onReact={onReact}
          onReply={handleReply}
          onCopy={onCopy}
          onToggleOriginal={onToggleOriginal}
          onRetryTranslation={onRetryTranslation}
          onRateTranslation={onRateTranslation}
          onEditTranslation={onEditTranslation}
          onForward={onForward}
          onDeleteMessage={onDeleteMessage}
          onDownloadAttachment={onDownloadAttachment}
          onLoadAttachmentPreview={onLoadAttachmentPreview}
          language={language}
        />

        {/* Full-width Composer */}
        <MessageComposer
          recipientName={conversation.name}
          onSendMessage={onSendMessage}
          replyTo={replyTo}
          onCancelReply={() => setReplyTo(null)}
          onSendAttachment={onSendAttachment}
          onTyping={onTyping}
          language={language}
        />
      </main>

      {/* Temporary Conversation Details Drawer */}
      <ConversationDetailsDrawer
        conversation={conversation}
        isOpen={isDetailsOpen}
        onClose={() => setIsDetailsOpen(false)}
        onToggleMute={onToggleMute}
        language={language}
        attachments={attachments}
        onDownloadAttachment={onDownloadAttachment}
      />
    </div>
  );
};
