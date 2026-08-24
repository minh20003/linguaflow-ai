import React, { useState, useRef, useEffect } from 'react';
import {
  Plus,
  Smile,
  SendHorizontal,
  X,
  Image as ImageIcon,
  Paperclip,
  Reply,
  Bot,
} from 'lucide-react';
import { LanguageCode, MessageMention, MessageReply, User } from '../types';
import { interactionText } from '../i18n';

interface MessageComposerProps {
  recipientName: string;
  onSendMessage: (text: string, replyToMessageId?: string, mentions?: MessageMention[]) => void;
  replyTo: MessageReply | null;
  onCancelReply: () => void;
  onSendAttachment?: (file: File) => void;
  onTyping?: (isTyping: boolean) => void;
  mentionCandidates: User[];
  language: LanguageCode;
}

const COMMON_EMOJIS = ['😊', '😂', '👍', '❤️', '🔥', '🎉', '🙌', '✨', '☕', '🍜', '🌍', '👏'];

export const MessageComposer: React.FC<MessageComposerProps> = ({
  recipientName,
  onSendMessage,
  replyTo,
  onCancelReply,
  onSendAttachment,
  onTyping,
  mentionCandidates,
  language,
}) => {
  const [text, setText] = useState('');
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [showAttachMenu, setShowAttachMenu] = useState(false);
  const [activeMention, setActiveMention] = useState(0);
  const [cursorPosition, setCursorPosition] = useState(0);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const scrollHeight = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = `${Math.min(scrollHeight, 130)}px`;
    }
  }, [text]);

  const handleSend = () => {
    if (!text.trim()) return;
    const mentions: MessageMention[] = [];
    for (const user of mentionCandidates) {
      if (new RegExp(`(^|\\s)@${user.username.replace(/[.*+?^${}()|[\\]\\]/g, '\\$&')}(?=\\s|$)`, 'i').test(text)) mentions.push({ type: 'user', userId: user.id });
    }
    if (/(^|\s)@assistant(?=\s|$)/i.test(text)) mentions.push({ type: 'assistant' });
    onSendMessage(text.trim(), replyTo?.id, mentions);
    setText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (mentionOptions.length && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
      e.preventDefault();
      setActiveMention((current) => (current + (e.key === 'ArrowDown' ? 1 : mentionOptions.length - 1)) % mentionOptions.length);
      return;
    }
    if (mentionOptions.length && e.key === 'Tab') {
      e.preventDefault();
      insertMention(mentionOptions[activeMention]);
      return;
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const mentionMatch = text.slice(0, cursorPosition).match(/(^|\s)@([^\s@]*)$/);
  const mentionQuery = mentionMatch?.[2].toLocaleLowerCase() ?? '';
  const mentionOptions = mentionMatch ? [
    ...mentionCandidates.filter((user) => `${user.name} ${user.username}`.toLocaleLowerCase().includes(mentionQuery)).map((user) => ({ type: 'user' as const, user })),
    ...('trợ lý thông minh assistant ai'.includes(mentionQuery) ? [{ type: 'assistant' as const }] : []),
  ] : [];
  const insertMention = (option: typeof mentionOptions[number]) => {
    const cursor = textareaRef.current?.selectionStart ?? text.length;
    const before = text.slice(0, cursor);
    const start = before.lastIndexOf('@');
    const token = option.type === 'assistant' ? '@assistant ' : `@${option.user.username} `;
    setText(`${text.slice(0, start)}${token}${text.slice(cursor)}`);
    setCursorPosition(start + token.length);
    setActiveMention(0);
    requestAnimationFrame(() => textareaRef.current?.focus());
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && onSendAttachment) {
      onSendAttachment(file);
      setShowAttachMenu(false);
    }
  };

  return (
    <div
      id="message-composer-container"
      className="relative w-full px-4 sm:px-6 md:px-8 pb-4 pt-1 flex-shrink-0 transition-colors"
    >
      {/* Reply Banner */}
      {replyTo && (
        <div className="flex items-center justify-between px-4 py-2 mb-2 bg-[#EFF6FF] dark:bg-[#2563EB]/15 border-l-4 border-[#2563EB] rounded-r-xl text-xs">
          <div className="flex items-center gap-2 min-w-0">
            <Reply className="w-3.5 h-3.5 text-[#2563EB] flex-shrink-0" />
            <div className="min-w-0">
              <span className="font-semibold text-[#2563EB] block truncate">
                {interactionText(language, 'Replying to')} {replyTo.senderName}
              </span>
              <span className="text-[#74798C] dark:text-[#9DA3B4] truncate block">
                {replyTo.content}
              </span>
            </div>
          </div>
          <button
            onClick={onCancelReply}
            className="p-1 rounded-lg text-[#74798C] hover:text-[#1E2230] dark:hover:text-white"
            aria-label="Cancel reply"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Main Composer Box */}
      <div
        className={`relative flex items-end gap-2 p-2 sm:p-2.5 bg-white dark:bg-[#1C1F27] border rounded-2xl shadow-sm transition-all ${
          text.trim()
            ? 'border-[#2563EB]/40 shadow-[#2563EB]/5'
            : 'border-[#E8EAF0] dark:border-[#2A2E3D]'
        }`}
      >
        {/* Attachment Button */}
        <div className="relative">
          <button
            id="composer-attach-btn"
            onClick={() => setShowAttachMenu(!showAttachMenu)}
            aria-label="Add attachment"
            className="flex items-center justify-center w-9 h-9 rounded-xl text-[#74798C] dark:text-[#9DA3B4] hover:text-[#2563EB] hover:bg-[#EFF6FF] dark:hover:bg-[#2563EB]/15 transition-colors"
          >
            <Plus className="w-5 h-5" />
          </button>

          {/* Attachment Popup Menu */}
          {showAttachMenu && (
            <div className="absolute bottom-full left-0 mb-2 w-44 bg-white dark:bg-[#232630] border border-[#E8EAF0] dark:border-[#2A2E3D] rounded-xl shadow-xl p-1 z-30 animate-in fade-in zoom-in-95 duration-100">
              <button
                onClick={() => fileInputRef.current?.click()}
                className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-[#1E2230] dark:text-[#E2E5F0] rounded-lg hover:bg-[#F7F8FC] dark:hover:bg-[#2A2E3D] text-left"
              >
                <ImageIcon className="w-4 h-4 text-emerald-500" />
                <span>Photo or Video</span>
              </button>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-[#1E2230] dark:text-[#E2E5F0] rounded-lg hover:bg-[#F7F8FC] dark:hover:bg-[#2A2E3D] text-left"
              >
                <Paperclip className="w-4 h-4 text-blue-500" />
                <span>{interactionText(language, 'Document or File')}</span>
              </button>
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                onChange={handleFileChange}
              />
            </div>
          )}
        </div>

        {/* Text Input Textarea */}
        <div className="flex-1 min-w-0 py-1">
          <textarea
            ref={textareaRef}
            id="message-input-textarea"
            rows={1}
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setActiveMention(0);
              setCursorPosition(e.target.selectionStart);
              onTyping?.(e.target.value.trim().length > 0);
            }}
            onSelect={(event) => setCursorPosition(event.currentTarget.selectionStart)}
            onClick={(event) => setCursorPosition(event.currentTarget.selectionStart)}
            onBlur={() => onTyping?.(false)}
            onKeyDown={handleKeyDown}
            placeholder={`${interactionText(language, 'Message')} ${recipientName}...`}
            className="w-full bg-transparent resize-none text-sm text-[#1E2230] dark:text-[#F5F6FA] placeholder-[#8A8F9E] dark:placeholder-[#74798C] focus:outline-none max-h-32 py-0.5 px-1 leading-relaxed"
          />
          {mentionOptions.length > 0 && (
            <div className="absolute bottom-full left-0 mb-3 w-72 overflow-hidden rounded-xl border border-[#E8EAF0] bg-white p-1 shadow-xl dark:border-[#2A2E3D] dark:bg-[#232630] z-40">
              <p className="px-2.5 py-1.5 text-[11px] font-medium text-[#74798C] dark:text-[#9DA3B4]">Gợi ý tag</p>
              {mentionOptions.map((option, index) => option.type === 'assistant' ? (
                <button key="assistant" type="button" onMouseDown={(event) => event.preventDefault()} onClick={() => insertMention(option)} className={`flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs ${index === activeMention ? 'bg-[#EFF6FF] text-[#2563EB] dark:bg-[#2563EB]/20' : 'hover:bg-[#F7F8FC] dark:hover:bg-[#2A2E3D]'}`}><span className="flex h-7 w-7 items-center justify-center rounded-full bg-violet-100 text-violet-600 dark:bg-violet-500/20 dark:text-violet-300"><Bot className="h-4 w-4" /></span><span><strong className="block text-[#2563EB] dark:text-[#60A5FA]">Trợ lý thông minh</strong><span className="text-[10px] text-[#74798C] dark:text-[#9DA3B4]">Phản hồi ngay trong luồng</span></span></button>
              ) : (
                <button key={option.user.id} type="button" onMouseDown={(event) => event.preventDefault()} onClick={() => insertMention(option)} className={`flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs ${index === activeMention ? 'bg-[#EFF6FF] text-[#2563EB] dark:bg-[#2563EB]/20' : 'hover:bg-[#F7F8FC] dark:hover:bg-[#2A2E3D]'}`}><img src={option.user.avatar} alt="" className="h-7 w-7 rounded-full" /><span><strong className="block text-[#2563EB] dark:text-[#60A5FA]">{option.user.name}</strong><span className="text-[10px] text-[#74798C] dark:text-[#9DA3B4]">@{option.user.username}</span></span></button>
              ))}
            </div>
          )}
        </div>

        {/* Right Action Icons: Emoji and Send */}
        <div className="flex items-center gap-1 sm:gap-1.5 flex-shrink-0">
          {/* Emoji Picker Button */}
          <div className="relative">
            <button
              id="composer-emoji-btn"
              onClick={() => setShowEmojiPicker(!showEmojiPicker)}
              aria-label="Add emoji"
              className="flex items-center justify-center w-9 h-9 rounded-xl text-[#74798C] dark:text-[#9DA3B4] hover:text-[#1E2230] dark:hover:text-white hover:bg-[#F7F8FC] dark:hover:bg-[#232630] transition-colors"
            >
              <Smile className="w-5 h-5" />
            </button>

            {/* Quick Emoji Menu */}
            {showEmojiPicker && (
              <div className="absolute bottom-full right-0 mb-2 w-64 p-2 bg-white dark:bg-[#232630] border border-[#E8EAF0] dark:border-[#2A2E3D] rounded-2xl shadow-xl z-30 grid grid-cols-6 gap-1">
                {COMMON_EMOJIS.map((emoji) => (
                  <button
                    key={emoji}
                    onClick={() => {
                      setText((prev) => prev + emoji);
                      setShowEmojiPicker(false);
                    }}
                    className="w-9 h-9 flex items-center justify-center text-lg hover:scale-125 hover:bg-[#F7F8FC] dark:hover:bg-[#1C1F27] rounded-xl transition-all"
                  >
                    {emoji}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Send Button */}
          <button
            id="composer-send-btn"
            onClick={handleSend}
            disabled={!text.trim()}
            aria-label="Send message"
            className={`flex items-center justify-center w-9 h-9 rounded-xl transition-all ${
              text.trim()
                ? 'bg-[#2563EB] text-white hover:bg-[#1D4ED8] shadow-md shadow-[#2563EB]/20 hover:scale-105 active:scale-95'
                : 'bg-[#F4F5F8] dark:bg-[#232630] text-[#8A8F9E] dark:text-[#74798C] cursor-not-allowed opacity-60'
            }`}
          >
            <SendHorizontal className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
