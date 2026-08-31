import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ArrowDown, Languages } from 'lucide-react';
import { Message, User, Conversation, LanguageCode, MessageAttachment } from '../types';
import { interactionText } from '../i18n';
import { MessageBubble } from './MessageBubble';
import { InlineProposalCard } from './InlineProposalCard';
import type { ApiActionProposal } from '../api/chat-api';

interface MessageListProps {
  messages: Message[];
  currentUser: User;
  conversation: Conversation;
  onReact: (messageId: string, emoji: string) => void;
  onReply: (message: Message) => void;
  onCopy: (text: string) => void;
  onToggleOriginal: (messageId: string) => void;
  onRetryTranslation: (messageId: string) => void;
  onRetryTranscription: (messageId: string) => void;
  retryingTranscriptionIds: ReadonlySet<string>;
  onRateTranslation: (messageId: string, translationId: string, rating: 1 | 5) => void;
  onEditTranslation: (messageId: string, translationId: string, editedText: string) => void;
  onForward: (message: Message) => void;
  onSaveMessage: (messageId: string) => void;
  onDeleteMessage?: (messageId: string) => void;
  onDownloadAttachment: (attachment: MessageAttachment) => void;
  onLoadAttachmentPreview: (attachment: MessageAttachment) => Promise<string>;
  onStartDirectChat?: (userId: string) => void;
  /** Proposals the assistant raised in this conversation, decided or not. */
  proposals?: ApiActionProposal[];
  proposalBusyId?: string | null;
  onApproveProposal?: (proposal: ApiActionProposal, corrections: Record<string, unknown>) => void;
  onRejectProposal?: (proposal: ApiActionProposal) => void;
  language: LanguageCode;
}

/** How close to the foot of the thread still counts as "reading the latest". */
const NEAR_BOTTOM_PX = 120;

/** How far up the thread the reader has to be before the arrow is worth
 *  offering. Wider than `NEAR_BOTTOM_PX` on purpose: a nudge of the wheel
 *  should stop the list following, but it should not put a button on screen. */
const FAR_FROM_BOTTOM_PX = 400;

export const MessageList: React.FC<MessageListProps> = ({
  messages,
  currentUser,
  conversation,
  onReact,
  onReply,
  onCopy,
  onToggleOriginal,
  onRetryTranslation,
  onRetryTranscription,
  retryingTranscriptionIds,
  onRateTranslation,
  onEditTranslation,
  onForward,
  onSaveMessage,
  onDeleteMessage,
  onDownloadAttachment,
  onLoadAttachmentPreview,
  onStartDirectChat,
  proposals = [],
  proposalBusyId = null,
  onApproveProposal,
  onRejectProposal,
  language,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  // Mirrored in a ref as well as in state: the arrival effect has to read the
  // position at the instant a message lands, and a state value captured when
  // that effect was created would still say "at the foot" long after the person
  // had scrolled away.
  const atBottomRef = useRef(true);
  const [isFarFromBottom, setIsFarFromBottom] = useState(false);
  const [hasNewBelow, setHasNewBelow] = useState(false);
  const isGroup = conversation.type === 'group';

  const showProposals = Boolean(onApproveProposal && onRejectProposal);
  /** Proposals grouped under the message each one was extracted from. */
  const proposalsByMessage = useMemo(() => {
    const grouped = new Map<string, ApiActionProposal[]>();
    if (!showProposals) return grouped;
    for (const proposal of proposals) {
      const anchor = proposal.source_message_id;
      grouped.set(anchor, [...(grouped.get(anchor) ?? []), proposal]);
    }
    return grouped;
  }, [proposals, showProposals]);
  // A proposal whose source message is not on screen — an older page of the
  // thread, or one raised somewhere this list cannot see — still has to be
  // answerable, so it goes at the foot of the thread rather than nowhere.
  const orphanProposals = useMemo(() => {
    if (!showProposals) return [] as ApiActionProposal[];
    const known = new Set(messages.map((message) => message.id));
    return proposals.filter((proposal) => !known.has(proposal.source_message_id));
  }, [messages, proposals, showProposals]);

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

  const jumpToLatest = useCallback((behavior: ScrollBehavior = 'smooth') => {
    bottomRef.current?.scrollIntoView({ behavior, block: 'end' });
    atBottomRef.current = true;
    setIsFarFromBottom(false);
    setHasNewBelow(false);
  }, []);

  const handleScroll = useCallback(() => {
    const element = scrollRef.current;
    if (!element) return;
    const distance = element.scrollHeight - element.scrollTop - element.clientHeight;
    const near = distance <= NEAR_BOTTOM_PX;
    atBottomRef.current = near;
    setIsFarFromBottom(distance > FAR_FROM_BOTTOM_PX);
    if (near) setHasNewBelow(false);
  }, []);

  // Opening a thread starts at its foot, with no animation to sit through.
  useEffect(() => {
    atBottomRef.current = true;
    setIsFarFromBottom(false);
    setHasNewBelow(false);
    const frame = window.requestAnimationFrame(() => {
      bottomRef.current?.scrollIntoView({ block: 'end' });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [conversation.id]);

  // What counts as something arriving, as opposed to a message already in the
  // thread being rewritten in place.
  //
  // The list used to follow the foot of the thread on any change to `messages`,
  // and a reaction, a "show original" toggle or a translation landing all
  // replace that array — so reading back through the history threw the person
  // to the newest message the moment they touched anything. Only an arrival
  // moves the viewport now, and only when they were already at the foot;
  // otherwise the arrow below offers the trip instead of taking it for them.
  const arrivalKey = [messages.length, messages.at(-1)?.id ?? '', proposals.length].join(':');
  const lastArrivalKey = useRef(arrivalKey);

  useEffect(() => {
    if (lastArrivalKey.current === arrivalKey) return;
    lastArrivalKey.current = arrivalKey;
    if (atBottomRef.current) jumpToLatest('smooth');
    else setHasNewBelow(true);
  }, [arrivalKey, jumpToLatest]);

  useEffect(() => {
    if (conversation.isTyping && atBottomRef.current) jumpToLatest('smooth');
  }, [conversation.isTyping, jumpToLatest]);

  const renderProposals = (anchored: ApiActionProposal[] | undefined) =>
    (anchored ?? []).map((proposal) => (
      <InlineProposalCard
        key={proposal.id}
        proposal={proposal}
        busy={proposalBusyId === proposal.id}
        onApprove={onApproveProposal!}
        onReject={onRejectProposal!}
      />
    ));

  return (
    <div className="relative flex min-h-0 flex-1 flex-col">
      <div
        id="chat-messages-container"
        ref={scrollRef}
        onScroll={handleScroll}
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
                onRetryTranscription={onRetryTranscription}
                isRetryingTranscription={retryingTranscriptionIds.has(message.id)}
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

              {/* The assistant answering the message right above it, where the
                  proposal was raised — it scrolls away with that message like
                  any other turn in the conversation. */}
              {renderProposals(proposalsByMessage.get(message.id))}
            </React.Fragment>
          );
        })}

        {renderProposals(orphanProposals)}

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

      {/* The trip back to the newest message, offered rather than taken.
          Also offered when something arrived while the reader was away, however
          far up they happen to be. */}
      {(isFarFromBottom || hasNewBelow) && (
        <button
          type="button"
          onClick={() => jumpToLatest('smooth')}
          aria-label={language === 'vi' ? 'Đến tin nhắn mới nhất' : 'Jump to the latest message'}
          title={language === 'vi' ? 'Đến tin nhắn mới nhất' : 'Jump to the latest message'}
          className="absolute bottom-4 right-4 z-10 flex h-10 w-10 items-center justify-center rounded-full border border-[#E8EAF0] bg-white text-[#4E5568] shadow-lg transition-all hover:scale-105 hover:text-[#2563EB] active:scale-95 dark:border-[#2E3342] dark:bg-[#232630] dark:text-[#C6CAD6]"
        >
          <ArrowDown className="h-5 w-5" />
          {hasNewBelow && (
            <span className="absolute -top-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-white bg-[#2563EB] dark:border-[#232630]" />
          )}
        </button>
      )}
    </div>
  );
};
