import React, { useEffect, useRef } from 'react';
import { Message, User, Conversation } from '../types';
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
  onDeleteMessage?: (messageId: string) => void;
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
  onDeleteMessage,
}) => {
  const bottomRef = useRef<HTMLDivElement>(null);
  const isGroup = conversation.type === 'group';

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
          ✨ Messages are translated in real-time. Speak your native language freely.
        </div>
      </div>

      {messages.map((message, index) => {
        const isOutgoing = message.senderId === currentUser.id;
        const prevMessage = index > 0 ? messages[index - 1] : null;
        const nextMessage = index < messages.length - 1 ? messages[index + 1] : null;

        // Determine if consecutive message from same sender
        const isSameSenderAsPrev = prevMessage?.senderId === message.senderId;
        const isSameSenderAsNext = nextMessage?.senderId === message.senderId;

        // Show avatar only for the last message in a consecutive cluster (for incoming)
        const showAvatar = !isOutgoing && !isSameSenderAsNext;
        // Show sender name on first message of cluster (for incoming group chats)
        const showSenderName = !isOutgoing && !isSameSenderAsPrev;

        return (
          <React.Fragment key={message.id}>
            {/* Time / Date Separator */}
            {message.dateDivider && (
              <div className="flex items-center justify-center my-6">
                <div className="flex items-center w-full max-w-sm gap-3">
                  <div className="flex-1 h-[1px] bg-[#E8EAF0] dark:bg-[#2A2E3D]" />
                  <span className="text-[11px] font-bold tracking-wider text-[#8A8F9E] dark:text-[#74798C] uppercase select-none px-1">
                    {message.dateDivider}
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
              onDeleteMessage={onDeleteMessage}
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
