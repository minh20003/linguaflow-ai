import React, { useState } from 'react';
import { Message, User, LanguageCode } from '../types';
import { interactionText } from '../i18n';
import {
  Check,
  CheckCheck,
  Languages,
  RotateCw,
  Sparkles,
  Smile,
  Reply,
  Copy,
  MoreHorizontal,
  Bookmark,
  Trash2,
  Eye,
  EyeOff,
  AlertCircle,
  ThumbsDown,
  ThumbsUp,
  Pencil,
  X
} from 'lucide-react';

interface MessageBubbleProps {
  message: Message;
  currentUser: User;
  isGroup: boolean;
  showAvatar: boolean;
  showSenderName: boolean;
  onReact: (messageId: string, emoji: string) => void;
  onReply: (message: Message) => void;
  onCopy: (text: string) => void;
  onToggleOriginal: (messageId: string) => void;
  onRetryTranslation: (messageId: string) => void;
  onRateTranslation: (messageId: string, translationId: string, rating: 1 | 5) => void;
  onEditTranslation: (messageId: string, translationId: string, editedText: string) => void;
  onForward: (message: Message) => void;
  onDeleteMessage?: (messageId: string) => void;
  language: LanguageCode;
}

const QUICK_EMOJIS = ['❤️', '👍', '🔥', '😂', '🎉', '👏'];

export const MessageBubble: React.FC<MessageBubbleProps> = ({
  message,
  currentUser,
  isGroup,
  showAvatar,
  showSenderName,
  onReact,
  onReply,
  onCopy,
  onToggleOriginal,
  onRetryTranslation,
  onRateTranslation,
  onEditTranslation,
  onForward,
  onDeleteMessage,
  language,
}) => {
  const [showActions, setShowActions] = useState(false);
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [showMoreMenu, setShowMoreMenu] = useState(false);
  const [isEditingTranslation, setIsEditingTranslation] = useState(false);
  const [editedTranslation, setEditedTranslation] = useState("");

  const isOutgoing = message.senderId === currentUser.id;
  const hasTranslation = !!message.translation;
  // A sender always reads their original wording. Do not surface historical
  // self-translations while the backend stops creating new ones for them.
  const isTranslated = !isOutgoing && hasTranslation && message.translation?.status === 'success';
  const isTranslating = !isOutgoing && hasTranslation && message.translation?.status === 'pending';
  const isTranslationFailed = !isOutgoing && hasTranslation && message.translation?.status === 'failed';
  const isShowingOriginal = message.translation?.showOriginal;
  const showTranslatedAsPrimary = isTranslated && !isShowingOriginal;
  const showTranslationPreview = isTranslated && isShowingOriginal;
  const canReviewTranslation = Boolean(
    message.translation?.translationId && message.translation.status === 'success',
  );

  const beginTranslationEdit = () => {
    setEditedTranslation(message.translation?.editedText || message.translation?.translatedText || '');
    setIsEditingTranslation(true);
  };

  const saveTranslationEdit = () => {
    const text = editedTranslation.trim();
    if (!text || !message.translation?.translationId) return;
    onEditTranslation(message.id, message.translation.translationId, text);
    setIsEditingTranslation(false);
  };

  // Language display name helper
  const getLanguageName = (code?: string) => {
    switch (code) {
      case 'vi': return 'Vietnamese';
      case 'ja': return 'Japanese';
      case 'ko': return 'Korean';
      case 'zh': return 'Chinese';
      case 'es': return 'Spanish';
      case 'fr': return 'French';
      case 'de': return 'German';
      case 'th': return 'Thai';
      case 'id': return 'Indonesian';
      default: return 'English';
    }
  };

  return (
    <div
      id={`message-${message.id}`}
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => {
        setShowActions(false);
        setShowEmojiPicker(false);
        setShowMoreMenu(false);
      }}
      className={`group relative flex gap-2.5 my-1 transition-all ${
        isOutgoing ? 'justify-end' : 'justify-start'
      }`}
    >
      {/* Incoming Avatar */}
      {!isOutgoing && (
        <div className="w-8 flex-shrink-0 flex items-end">
          {showAvatar && message.senderAvatar ? (
            <img
              src={message.senderAvatar}
              alt={message.senderName || 'Sender'}
              className="w-8 h-8 rounded-full object-cover ring-1 ring-[#E8EAF0] dark:ring-[#2A2E3D]"
              referrerPolicy="no-referrer"
            />
          ) : showAvatar ? (
            <div className="flex items-center justify-center w-8 h-8 rounded-full bg-[#EFF6FF] dark:bg-[#2563EB]/20 text-[10px] font-semibold text-[#2563EB] ring-1 ring-[#E8EAF0] dark:ring-[#2A2E3D]">
              {(message.senderName || "?").slice(0, 2).toUpperCase()}
            </div>
          ) : (
            <div className="w-8" />
          )}
        </div>
      )}

      {/* Message Container */}
      <div
        className={`relative flex flex-col max-w-[85%] sm:max-w-[72%] md:max-w-[62%] ${
          isOutgoing ? 'items-end' : 'items-start'
        }`}
      >
        {/* Sender Name for Group Chats */}
        {isGroup && !isOutgoing && showSenderName && (
          <span className="text-[11px] font-bold text-[#2563EB] dark:text-[#60A5FA] ml-2 mb-1">
            {message.senderName}
          </span>
        )}

        {/* Reply Quote Preview */}
        {message.forwardedFromMessageId && (
          <span className="mb-1 ml-2 inline-flex items-center gap-1 text-[11px] font-medium text-[#74798C] dark:text-[#9DA3B4]">
            <RotateCw className="h-3 w-3" /> {interactionText(language, 'Forwarded')}
          </span>
        )}
        {message.replyTo && (
          <div
            className={`flex items-start gap-1.5 px-3 py-1.5 mb-1 rounded-xl text-xs max-w-full border-l-2 ${
              isOutgoing
                ? 'bg-[#1D4ED8]/45 border-white/70 text-white/75'
                : 'bg-[#F4F5F8] dark:bg-[#232630] border-[#2563EB] text-[#74798C] dark:text-[#9DA3B4] opacity-80'
            }`}
          >
            <Reply className="w-3 h-3 flex-shrink-0 mt-0.5" />
            <div className="min-w-0">
              <span className="font-semibold block truncate opacity-90">
                {message.replyTo.senderName}
              </span>
              <span className="truncate block opacity-75">
                {message.replyTo.content}
              </span>
            </div>
          </div>
        )}

        {/* Message Bubble Box */}
        <div
          className={`relative px-4 py-2.5 rounded-2xl text-sm leading-relaxed transition-colors select-text ${
            isOutgoing
              ? 'bg-[#2563EB] text-white rounded-br-sm shadow-sm'
              : 'bg-white dark:bg-[#232630] text-[#1E2230] dark:text-[#F5F6FA] border border-[#E8EAF0] dark:border-[#2E3342] rounded-bl-sm shadow-sm'
          }`}
        >
          {/* Main message text */}
          <div className="space-y-1">
            {showTranslatedAsPrimary ? (
              isEditingTranslation ? (
                <div className="space-y-1.5">
                  <textarea
                    aria-label="Edit translated text"
                    autoFocus
                    rows={2}
                    value={editedTranslation}
                    onChange={(event) => setEditedTranslation(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Escape') setIsEditingTranslation(false);
                      if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
                        event.preventDefault();
                        saveTranslationEdit();
                      }
                    }}
                    className="w-full resize-none rounded-md border border-[#2563EB]/60 bg-white/70 px-2 py-1 text-sm leading-relaxed text-[#1E2230] outline-none focus:border-[#2563EB] dark:bg-[#1C1F27] dark:text-[#F5F6FA]"
                  />
                  <div className="flex justify-end gap-1">
                    <button type="button" aria-label="Cancel edit" title="Cancel" onClick={() => setIsEditingTranslation(false)} className="rounded p-1 text-[#74798C] hover:bg-[#F4F5F8] dark:hover:bg-[#2E3342]"><X className="h-3.5 w-3.5" /></button>
                    <button type="button" aria-label="Save translation edit" title="Save" onClick={saveTranslationEdit} className="rounded p-1 text-[#2563EB] hover:bg-[#EFF6FF] dark:text-[#60A5FA] dark:hover:bg-[#2563EB]/20"><Check className="h-3.5 w-3.5" /></button>
                  </div>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={canReviewTranslation ? beginTranslationEdit : undefined}
                  title={canReviewTranslation ? 'Click to edit translation' : undefined}
                  className={`block w-full whitespace-pre-wrap break-words text-left font-normal ${canReviewTranslation ? 'cursor-text rounded -mx-1 px-1 hover:bg-black/[0.03] dark:hover:bg-white/[0.04]' : ''}`}
                >
                  {message.translation?.editedText || message.translation?.translatedText}
                </button>
              )
            ) : (
              <p className="whitespace-pre-wrap break-words font-normal">
                {message.content}
              </p>
            )}

            {/* Revealed Original (when toggle is active) */}
            {showTranslationPreview && (
              <div className="mt-2 pt-2 border-t border-dashed border-[#E8EAF0] dark:border-[#383E50] text-xs">
                <span className="text-[10px] font-bold uppercase tracking-wider text-[#74798C] dark:text-[#9DA3B4] block mb-0.5">
                  {isOutgoing ? 'Translation preview:' : 'Translated Version:'}
                </span>
                {isEditingTranslation ? (
                  <div className="space-y-1.5">
                    <textarea
                      aria-label="Edit translated text"
                      autoFocus
                      rows={2}
                      value={editedTranslation}
                      onChange={(event) => setEditedTranslation(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === 'Escape') setIsEditingTranslation(false);
                        if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
                          event.preventDefault();
                          saveTranslationEdit();
                        }
                      }}
                      className="w-full resize-none rounded-md border border-[#2563EB]/60 bg-white/70 px-2 py-1 text-sm leading-relaxed text-[#1E2230] outline-none focus:border-[#2563EB] dark:bg-[#1C1F27] dark:text-[#F5F6FA]"
                    />
                    <div className="flex justify-end gap-1">
                      <button type="button" aria-label="Cancel edit" title="Cancel" onClick={() => setIsEditingTranslation(false)} className="rounded p-1 text-[#74798C] hover:bg-[#F4F5F8] dark:hover:bg-[#2E3342]"><X className="h-3.5 w-3.5" /></button>
                      <button type="button" aria-label="Save translation edit" title="Save" onClick={saveTranslationEdit} className="rounded p-1 text-[#2563EB] hover:bg-[#EFF6FF] dark:text-[#60A5FA] dark:hover:bg-[#2563EB]/20"><Check className="h-3.5 w-3.5" /></button>
                    </div>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={canReviewTranslation ? beginTranslationEdit : undefined}
                    title={canReviewTranslation ? 'Click to edit translation' : undefined}
                    className={`block w-full rounded px-1 -mx-1 text-left text-[#1E2230] dark:text-[#F5F6FA] ${canReviewTranslation ? 'cursor-text hover:bg-black/[0.03] dark:hover:bg-white/[0.04]' : ''}`}
                  >
                    {message.translation?.editedText || message.translation?.translatedText}
                  </button>
                )}
              </div>
            )}

            {/* Translating Pending State */}
            {isTranslating && (
              <div className="flex items-center gap-1.5 py-1 text-xs text-[#74798C] dark:text-[#9DA3B4]">
                <div className="flex gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#2563EB] animate-bounce" />
                  <span className="w-1.5 h-1.5 rounded-full bg-[#2563EB] animate-bounce [animation-delay:0.2s]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-[#2563EB] animate-bounce [animation-delay:0.4s]" />
                </div>
                <span className="italic">Translating…</span>
              </div>
            )}

            {/* Translation Failure State */}
            {isTranslationFailed && (
              <div className="flex items-center gap-2 pt-1 text-xs text-amber-600 dark:text-amber-400">
                <AlertCircle className="w-3.5 h-3.5" />
                <span>Translation unavailable</span>
                <button
                  onClick={() => onRetryTranslation(message.id)}
                  className="underline font-semibold hover:text-amber-700"
                >
                  Retry
                </button>
              </div>
            )}
          </div>

          {/* Translation Footer Metadata */}
          {isTranslated && (
            <div
              className={`flex items-center justify-between gap-3 mt-1.5 pt-1.5 border-t text-[11px] select-none ${
                isOutgoing
                  ? 'border-white/20 text-white/80'
                  : 'border-[#E8EAF0] dark:border-[#2E3342] text-[#74798C] dark:text-[#9DA3B4]'
              }`}
            >
              <div className="flex items-center gap-1">
                <Languages className="w-3 h-3 text-[#2563EB]" />
                <span>
                  {isOutgoing
                    ? `Translated for ${getLanguageName(message.translation?.targetLanguage)}`
                    : `Translated from ${getLanguageName(message.translation?.originalLanguage)}`}
                </span>
              </div>

              <button
                onClick={() => onToggleOriginal(message.id)}
                className="font-medium hover:underline flex items-center gap-0.5 text-[#2563EB] dark:text-[#60A5FA]"
              >
                {isShowingOriginal ? (
                  <>
                    <EyeOff className="w-2.5 h-2.5" />
                    <span>{interactionText(language, isOutgoing ? 'Hide translation' : 'Hide original')}</span>
                  </>
                ) : (
                  <>
                    <Eye className="w-2.5 h-2.5" />
                    <span>{interactionText(language, isOutgoing ? 'Show translation' : 'Show original')}</span>
                  </>
                )}
              </button>
            </div>
          )}

          {canReviewTranslation && message.translation && (
            <div className="mt-1.5 flex items-center gap-0.5 text-[#74798C] dark:text-[#9DA3B4]">
                <button
                  type="button"
                  aria-label="Like translation"
                  title="Like translation"
                  aria-pressed={message.translation.rating === 5}
                  onClick={() => onRateTranslation(message.id, message.translation!.translationId, 5)}
                  className={`inline-flex rounded-md p-1 transition-colors ${message.translation.rating === 5 ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300' : 'hover:bg-[#F4F5F8] dark:hover:bg-[#2E3342]'}`}
                >
                  <ThumbsUp className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  aria-label="Dislike translation"
                  title="Dislike translation"
                  aria-pressed={message.translation.rating === 1}
                  onClick={() => onRateTranslation(message.id, message.translation!.translationId, 1)}
                  className={`inline-flex rounded-md p-1 transition-colors ${message.translation.rating === 1 ? 'bg-rose-100 text-rose-700 dark:bg-rose-500/20 dark:text-rose-300' : 'hover:bg-[#F4F5F8] dark:hover:bg-[#2E3342]'}`}
                >
                  <ThumbsDown className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  aria-label="Edit translation"
                  title="Edit translation"
                  onClick={beginTranslationEdit}
                  className="inline-flex rounded-md p-1 text-[#2563EB] hover:bg-[#EFF6FF] dark:text-[#60A5FA] dark:hover:bg-[#2563EB]/20"
                >
                  <Pencil className="w-3.5 h-3.5" />
                </button>
            </div>
          )}
        </div>

        {/* Timestamp & Status info */}
        <div
          className={`flex items-center gap-1.5 mt-1 px-1 text-[11px] text-[#8A8F9E] dark:text-[#74798C] select-none ${
            isOutgoing ? 'justify-end' : 'justify-start'
          }`}
        >
          <span>{message.timestamp}</span>

          {isOutgoing && (
            <span className="flex items-center">
              {message.status === 'sending' && (
                <span className="italic text-[10px]">Sending...</span>
              )}
              {message.status === 'sent' && <Check className="w-3.5 h-3.5" />}
              {message.status === 'delivered' && (
                <CheckCheck className="w-3.5 h-3.5 text-[#8A8F9E]" />
              )}
              {message.status === 'read' && (
                <CheckCheck className="w-3.5 h-3.5 text-[#2563EB]" />
              )}
            </span>
          )}
        </div>

        {/* Reaction Badges */}
        {message.reactions && message.reactions.length > 0 && (
          <div
            className={`flex flex-wrap gap-1 mt-0.5 ${
              isOutgoing ? 'justify-end' : 'justify-start'
            }`}
          >
            {message.reactions.map((reaction, idx) => {
              const hasReacted = reaction.users.includes(currentUser.id);
              return (
                <button
                  key={idx}
                  onClick={() => onReact(message.id, reaction.emoji)}
                  className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs transition-all ${
                    hasReacted
                      ? 'bg-[#EFF6FF] dark:bg-[#2563EB]/25 text-[#2563EB] border border-[#2563EB]/30 font-semibold scale-105'
                      : 'bg-white dark:bg-[#232630] text-[#1E2230] dark:text-[#E2E5F0] border border-[#E8EAF0] dark:border-[#2E3342] hover:bg-[#F7F8FC]'
                  } shadow-2xs`}
                >
                  <span>{reaction.emoji}</span>
                  <span className="text-[10px] font-medium">{reaction.count}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Floating Hover Action Toolbar */}
      {showActions && (
        <div
          className={`absolute top-0 flex items-center gap-0.5 p-1 bg-white dark:bg-[#232630] border border-[#E8EAF0] dark:border-[#2E3342] rounded-xl shadow-lg z-20 transition-all ${
            isOutgoing ? 'right-0 -top-8' : 'left-8 -top-8'
          }`}
        >
          {/* Reaction Picker Button */}
          <div className="relative">
            <button
              onClick={() => setShowEmojiPicker(!showEmojiPicker)}
              aria-label="Add reaction"
              className="p-1 rounded-lg text-[#74798C] hover:text-[#1E2230] dark:hover:text-white hover:bg-[#F7F8FC] dark:hover:bg-[#2A2E3D] transition-colors"
            >
              <Smile className="w-3.5 h-3.5" />
            </button>

            {/* Quick Emoji Bar */}
            {showEmojiPicker && (
              <div className="absolute left-0 bottom-full mb-1 flex items-center gap-1 p-1 bg-white dark:bg-[#232630] border border-[#E8EAF0] dark:border-[#2E3342] rounded-full shadow-xl z-30">
                {QUICK_EMOJIS.map((emoji) => (
                  <button
                    key={emoji}
                    onClick={() => {
                      onReact(message.id, emoji);
                      setShowEmojiPicker(false);
                    }}
                    className="w-7 h-7 flex items-center justify-center hover:scale-125 text-base transition-transform"
                  >
                    {emoji}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Reply Button */}
          <button
            onClick={() => onReply(message)}
            aria-label="Reply"
            className="p-1 rounded-lg text-[#74798C] hover:text-[#1E2230] dark:hover:text-white hover:bg-[#F7F8FC] dark:hover:bg-[#2A2E3D] transition-colors"
          >
            <Reply className="w-3.5 h-3.5" />
          </button>

          {/* Copy Button */}
          <button
            onClick={() =>
              onCopy(
                isOutgoing || message.translation?.showOriginal
                  ? message.content
                  : message.translation?.translatedText || message.content
              )
            }
            aria-label="Copy text"
            className="p-1 rounded-lg text-[#74798C] hover:text-[#1E2230] dark:hover:text-white hover:bg-[#F7F8FC] dark:hover:bg-[#2A2E3D] transition-colors"
          >
            <Copy className="w-3.5 h-3.5" />
          </button>

          {/* More Menu Dropdown */}
          <div className="relative">
            <button
              onClick={() => setShowMoreMenu(!showMoreMenu)}
              aria-label="More actions"
              className="p-1 rounded-lg text-[#74798C] hover:text-[#1E2230] dark:hover:text-white hover:bg-[#F7F8FC] dark:hover:bg-[#2A2E3D] transition-colors"
            >
              <MoreHorizontal className="w-3.5 h-3.5" />
            </button>

            {showMoreMenu && (
              <div className="absolute right-0 top-full mt-1 w-36 bg-white dark:bg-[#232630] border border-[#E8EAF0] dark:border-[#2E3342] rounded-xl shadow-xl p-1 z-30 text-xs">
                <button
                  onClick={() => { onForward(message); setShowMoreMenu(false); }}
                  className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-[#1E2230] dark:text-[#E2E5F0] hover:bg-[#F7F8FC] dark:hover:bg-[#2A2E3D] text-left"
                >
                  <RotateCw className="w-3 h-3 text-[#2563EB]" />
                  <span>{interactionText(language, 'Forward')}</span>
                </button>
                <button
                  onClick={() => {
                    onRetryTranslation(message.id);
                    setShowMoreMenu(false);
                  }}
                  className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-[#1E2230] dark:text-[#E2E5F0] hover:bg-[#F7F8FC] dark:hover:bg-[#2A2E3D] text-left"
                >
                  <RotateCw className="w-3 h-3 text-[#2563EB]" />
                  <span>{interactionText(language, 'Translate again')}</span>
                </button>

                <button
                  onClick={() => setShowMoreMenu(false)}
                  className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-[#1E2230] dark:text-[#E2E5F0] hover:bg-[#F7F8FC] dark:hover:bg-[#2A2E3D] text-left"
                >
                  <Bookmark className="w-3 h-3 text-[#74798C]" />
                  <span>{interactionText(language, 'Save message')}</span>
                </button>

                {onDeleteMessage && (
                  <button
                    onClick={() => {
                      onDeleteMessage(message.id);
                      setShowMoreMenu(false);
                    }}
                    className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/30 text-left"
                  >
                    <Trash2 className="w-3 h-3" />
                    <span>{interactionText(language, 'Delete')}</span>
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
