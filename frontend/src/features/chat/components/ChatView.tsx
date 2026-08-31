import React, { useState } from 'react';
import { Conversation, Message, User, MessageMention, MessageReply, MessageAttachment } from '../types';
import { ChatHeader } from './ChatHeader';
import { MessageList } from './MessageList';
import { MessageComposer } from './MessageComposer';
import { ConversationDetailsDrawer } from './ConversationDetailsDrawer';
import { MessageSearchPanel, type ConversationSearchResult } from './MessageSearchPanel';
import { MessageSquare, Sparkles, Plus, Globe } from 'lucide-react';
import { emptyChatText } from '../i18n';
import type { VoiceRecorderStage } from '../voice-recorder';
import type { ApiActionProposal } from '../api/chat-api';

interface ChatViewProps {
  conversation: Conversation | null;
  messages: Message[];
  currentUser: User;
  onBack?: () => void;
  onSendMessage: (text: string, replyToMessageId?: string, mentions?: MessageMention[]) => void;
  onSendAttachment?: (file: File) => void;
  onSendVoice?: (
    file: File,
    replyToMessageId: string | undefined,
    onStage: (stage: Extract<VoiceRecorderStage, 'uploading' | 'sending'>) => void,
  ) => Promise<void>;
  onTyping?: (isTyping: boolean) => void;
  onReact: (messageId: string, emoji: string) => void;
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
  onToggleMute: (conversationId: string) => void;
  onTogglePin: (conversationId: string) => void;
  onBlockContact: (conversationId: string) => void;
  onSearchMessages: (query: string) => Promise<ConversationSearchResult[]>;
  onOpenNewChat: () => void;
  /** Proposals the assistant raised in this conversation.
   *
   *  Decided ones stay in the list: the card is a turn in the conversation, so
   *  the answer to it belongs in the transcript too. */
  proposals?: ApiActionProposal[];
  proposalBusyId?: string | null;
  onApproveProposal?: (proposal: ApiActionProposal, corrections: Record<string, unknown>) => void;
  onRejectProposal?: (proposal: ApiActionProposal) => void;
  onStartCall: (type: 'voice' | 'video') => void;
  language: User['nativeLanguage'];
  attachments: MessageAttachment[];
  onDownloadAttachment: (attachment: MessageAttachment) => void;
  onLoadAttachmentPreview: (attachment: MessageAttachment) => Promise<string>;
  onLeaveGroup?: (conversationId: string) => void;
  onDeleteGroup?: (conversationId: string) => void;
  availableUsers: User[];
  onAddMembers?: (conversationId: string, userIds: string[]) => void;
  onRemoveMember?: (conversationId: string, userId: string) => void;
  onChangeMemberRole?: (conversationId: string, userId: string, role: 'admin' | 'member') => void;
  onSearchUsers?: (query: string) => void;
  onTransferOwnership?: (conversationId: string, userId: string) => void;
  onUpdateGroup?: (conversationId: string, title: string, description: string) => void;
  onStartDirectChat?: (userId: string) => void;
  assistantMode?: boolean;
}

export const ChatView: React.FC<ChatViewProps> = ({
  conversation,
  messages,
  currentUser,
  onBack,
  onSendMessage,
  onSendAttachment,
  onSendVoice,
  onTyping,
  onReact,
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
  onToggleMute,
  onTogglePin,
  onBlockContact,
  onSearchMessages,
  onOpenNewChat,
  proposals = [],
  proposalBusyId = null,
  onApproveProposal,
  onRejectProposal,
  onStartCall,
  language,
  attachments,
  onDownloadAttachment,
  onLoadAttachmentPreview,
  onLeaveGroup,
  onDeleteGroup,
  availableUsers,
  onAddMembers,
  onRemoveMember,
  onChangeMemberRole,
  onSearchUsers,
  onTransferOwnership,
  onUpdateGroup,
  onStartDirectChat,
  assistantMode = false,
}) => {
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [replyTo, setReplyTo] = useState<MessageReply | null>(null);

  // If no conversation is active, render the clean centered empty state
  if (!conversation) {
    const [emptyTitle, emptyDescription, startConversation] = emptyChatText(language);
    return (
      <div
        id="empty-chat-state"
        className="flex-1 flex flex-col items-center justify-center h-screen bg-[#F7F8FC] dark:bg-[#14161C] px-6 text-center select-none"
      >
        <div className="flex items-center justify-center w-16 h-16 rounded-3xl bg-gradient-to-tr from-[#2563EB] to-[#60A5FA] text-white shadow-lg shadow-[#2563EB]/20 mb-4">
          <MessageSquare className="w-8 h-8" />
        </div>

        <h2 className="text-xl font-bold text-[#1E2230] dark:text-[#F5F6FA] mb-1.5">
          {emptyTitle}
        </h2>
        <p className="text-sm text-[#74798C] dark:text-[#9DA3B4] max-w-sm mb-6 leading-relaxed">
          {emptyDescription}
        </p>

        <button
          onClick={onOpenNewChat}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#2563EB] text-white font-semibold text-sm hover:bg-[#1D4ED8] shadow-md shadow-[#2563EB]/25 hover:scale-105 active:scale-95 transition-all"
        >
          <Plus className="w-4 h-4" />
          <span>{startConversation}</span>
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
        className="relative flex-1 flex flex-col h-screen min-w-0 bg-[#F7F8FC] dark:bg-[#14161C] transition-colors"
      >
        {/* Full-width Chat Header */}
        <ChatHeader
          conversation={conversation}
          onBack={onBack}
          onToggleDetails={() => setIsDetailsOpen(!isDetailsOpen)}
          isDetailsOpen={isDetailsOpen}
          onStartCall={onStartCall}
          onSearchInChat={() => setIsSearchOpen(true)}
          language={language}
          assistantMode={assistantMode}
        />

        {isSearchOpen && (
          <MessageSearchPanel
            onClose={() => setIsSearchOpen(false)}
            onSearch={onSearchMessages}
            onSelect={(messageId) => {
              document.getElementById(`message-${messageId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
              setIsSearchOpen(false);
            }}
          />
        )}

        {/* Full-width Messages Container. Proposals go in here rather than
            above the composer: deciding on one belongs next to the message that
            prompted it, and it should scroll away with that message. */}
        <MessageList
          messages={messages}
          currentUser={currentUser}
          conversation={conversation}
          onReact={onReact}
          onReply={handleReply}
          onCopy={onCopy}
          onToggleOriginal={onToggleOriginal}
          onRetryTranslation={onRetryTranslation}
          onRetryTranscription={onRetryTranscription}
          retryingTranscriptionIds={retryingTranscriptionIds}
          onRateTranslation={onRateTranslation}
          onEditTranslation={onEditTranslation}
          onForward={onForward}
          onSaveMessage={onSaveMessage}
          onDeleteMessage={onDeleteMessage}
          onDownloadAttachment={onDownloadAttachment}
          onLoadAttachmentPreview={onLoadAttachmentPreview}
          onStartDirectChat={onStartDirectChat}
          proposals={proposals}
          proposalBusyId={proposalBusyId}
          onApproveProposal={onApproveProposal}
          onRejectProposal={onRejectProposal}
          language={language}
        />

        {/* Full-width Composer */}
        <MessageComposer
          recipientName={conversation.name}
          onSendMessage={onSendMessage}
          replyTo={replyTo}
          onCancelReply={() => setReplyTo(null)}
          onSendAttachment={onSendAttachment}
          onSendVoice={onSendVoice}
          onTyping={onTyping}
          mentionCandidates={assistantMode ? [] : conversation.type === 'group'
            ? (conversation.members || []).filter((member) => member.id !== currentUser.id)
            : (conversation.recipient ? [conversation.recipient] : [])}
          language={language}
        />
      </main>

      {/* Temporary Conversation Details Drawer */}
      {!assistantMode && <ConversationDetailsDrawer
        conversation={conversation}
        isOpen={isDetailsOpen}
        onClose={() => setIsDetailsOpen(false)}
        onToggleMute={onToggleMute}
        onTogglePin={onTogglePin}
        onLeaveGroup={onLeaveGroup}
        onBlockContact={onBlockContact}
        language={language}
        attachments={attachments}
        onDownloadAttachment={onDownloadAttachment}
        onDeleteGroup={onDeleteGroup}
        currentUserId={currentUser.id}
        availableUsers={availableUsers}
        onAddMembers={onAddMembers}
        onRemoveMember={onRemoveMember}
        onChangeMemberRole={onChangeMemberRole}
        onSearchUsers={onSearchUsers}
        onTransferOwnership={onTransferOwnership}
        onUpdateGroup={onUpdateGroup}
        onStartDirectChat={onStartDirectChat}
      />}
    </div>
  );
};
