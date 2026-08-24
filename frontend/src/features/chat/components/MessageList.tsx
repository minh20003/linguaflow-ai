import React, { useEffect, useRef } from 'react';
import { Languages } from 'lucide-react';
import { Message, User, Conversation, LanguageCode, MessageAttachment } from '../types';
import { interactionText } from '../i18n';
import { MessageBubble } from './MessageBubble';

interface MessageListProps {
  messages: Message[];
  currentUser: User;
  conversation: Conversation;
  onReact: (messageId: string, emoji: string) => void;
  onReply: (message: Message) => void;
  onCopy: (text: string) => void;
  onToggleOriginal: (messageId: string) => void;
  onRetryTranslation: (messageId: string) => void;
  onRateTranslation: (messageId: string, translationId: string, rating: 1 | 5) => void;
  onEditTranslation: (messageId: string, translationId: string, editedText: string) => void;
  onForward: (message: Message) => void;
  onSaveMessage: (messageId: string) => void;
  onDeleteMessage?: (messageId: string) => void;
  onDownloadAttachment: (attachment: MessageAttachment) => void;
  onLoadAttachmentPreview: (attachment: MessageAttachment) => Promise<string>;
  onStartDirectChat?: (userId: string) => void;
  language: LanguageCode;
}

export const MessageList: React.FC<MessageListProps> = ({
  messages,
  currentUser,
  conversation,
  onReact,
  onReply,
  onCopy,
  onToggleOriginal,
  onRetryTranslation,
  onRateTranslation,
  onEditTranslation,
  onForward,
  onSaveMessage,
  onDeleteMessage,
  onDownloadAttachment,
  onLoadAttachmentPreview,
  onStartDirectChat,
  language,
}) => {
  const bottomRef = useRef<HTMLDivElement>(null);
  const isGroup = conversation.type === 'group';

  const dateKey = (value?: string) => value ? new Date(value).toLocaleDateString('en-CA') : undefined;
  const dateLabel = (value?: string) => {
    if (!value) return undefined;
    const date = new Date(value);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(today.getDate() - 1);
    if (dateKey(value) === dateKey(today.toISOString())) return language === 'vi' ? 'Hôm nay' : 'Today';
    if (dateKey(value) === dateKey(yesterday.toISOString())) return language === 'vi' ? 'Hôm qua' : 'Yesterday';
    return new Intl.DateTimeFormat(language === 'vi' ? 'vi-VN' : 'en-US', {
      weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
    }).format(date);
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, conversation.isTyping]);

  return (
    <div
      id="chat-messages-container"
      className="flex-1 overflow-y-auto w-full px-4 sm:px-6 md:px-8 lg:px-10 py-6 space-y-1.5 transition-colors"
      role="log"
      aria-label="Chat messages"
    >
      {/* Encryption & Security Greeting Banner */}
      <div className="flex justify-center my-3">
        <div className="px-3.5 py-1.5 rounded-full text-[11px] font-medium text-[#74798C] dark:text-[#9DA3B4] bg-[#F4F5F8] dark:bg-[#232630] border border-[#E8EAF0] dark:border-[#2A2E3D] text-center max-w-md">
          <Languages className="mr-1 inline-block h-3.5 w-3.5 text-[#2563EB]" aria-hidden="true" />
          {interactionText(language, 'Messages are translated in real-time. Speak your native language freely.')}
        </div>
      </div>

      {messages.map((message, index) => {
        const isOutgoing = message.senderId === currentUser.id && !message.isAssistant;
        const prevMessage = index > 0 ? messages[index - 1] : null;
        const nextMessage = index < messages.length - 1 ? messages[index + 1] : null;

        // Determine if consecutive message from same sender
        const isSameSenderAsPrev = prevMessage?.senderId === message.senderId && prevMessage?.isAssistant === message.isAssistant;
        const isSameSenderAsNext = nextMessage?.senderId === message.senderId && nextMessage?.isAssistant === message.isAssistant;

        // Show avatar only for the last message in a consecutive cluster (for incoming)
        const showAvatar = !isOutgoing && !isSameSenderAsNext;
        // Show sender name on first message of cluster (for incoming group chats)
        const showSenderName = !isOutgoing && !isSameSenderAsPrev;
        const divider = message.dateDivider ?? (dateKey(message.createdAt) !== dateKey(prevMessage?.createdAt)
          ? dateLabel(message.createdAt)
          : undefined);

        return (
          <React.Fragment key={message.id}>
            {/* Time / Date Separator */}
            {divider && (
              <div className="flex items-center justify-center my-6">
                <div className="flex items-center w-full max-w-sm gap-3">
                  <div className="flex-1 h-[1px] bg-[#E8EAF0] dark:bg-[#2A2E3D]" />
                  <span className="text-[11px] font-bold tracking-wider text-[#8A8F9E] dark:text-[#74798C] uppercase select-none px-1">
                    {divider}
                  </span>
                  <div className="flex-1 h-[1px] bg-[#E8EAF0] dark:bg-[#2A2E3D]" />
                </div>
              </div>
            )}

            {/* Bubble */}
            <MessageBubble
              message={message}
              currentUser={currentUser}
              isGroup={isGroup}
              showAvatar={showAvatar}
              showSenderName={showSenderName}
              onReact={onReact}
              onReply={onReply}
              onCopy={onCopy}
              onToggleOriginal={onToggleOriginal}
              onRetryTranslation={onRetryTranslation}
              onRateTranslation={onRateTranslation}
              onEditTranslation={onEditTranslation}
              onForward={onForward}
              onSaveMessage={onSaveMessage}
              onDeleteMessage={onDeleteMessage}
              onDownloadAttachment={onDownloadAttachment}
              onLoadAttachmentPreview={onLoadAttachmentPreview}
              onStartDirectChat={onStartDirectChat}
              language={language}
            />
          </React.Fragment>
        );
      })}

      {/* Typing Indicator */}
      {conversation.isTyping && (
        <div className="flex items-center gap-2.5 my-2 animate-in fade-in duration-200">
          <img
            src={conversation.avatar}
            alt={conversation.name}
            className="w-7 h-7 rounded-full object-cover ring-1 ring-[#E8EAF0] dark:ring-[#2A2E3D]"
            referrerPolicy="no-referrer"
          />
          <div className="flex items-center gap-2 px-3.5 py-2 rounded-2xl rounded-bl-sm bg-white dark:bg-[#232630] border border-[#E8EAF0] dark:border-[#2E3342] shadow-sm">
            <span className="text-xs text-[#2563EB] font-medium">
              {conversation.typingUser || conversation.name} is typing
            </span>
            <div className="flex gap-1 items-center">
              <span className="w-1.5 h-1.5 rounded-full bg-[#2563EB] animate-bounce" />
              <span className="w-1.5 h-1.5 rounded-full bg-[#2563EB] animate-bounce [animation-delay:0.2s]" />
              <span className="w-1.5 h-1.5 rounded-full bg-[#2563EB] animate-bounce [animation-delay:0.4s]" />
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
};
