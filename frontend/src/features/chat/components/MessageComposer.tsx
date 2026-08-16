import React, { useState, useRef, useEffect } from 'react';
import {
  Plus,
  Smile,
  SendHorizontal,
  X,
  Image as ImageIcon,
  Paperclip,
  Reply
} from 'lucide-react';
import { MessageReply } from '../types';

interface MessageComposerProps {
  recipientName: string;
  onSendMessage: (text: string, replyToMessageId?: string) => void;
  replyTo: MessageReply | null;
  onCancelReply: () => void;
  onSendAttachment?: (file: File) => void;
  onTyping?: (isTyping: boolean) => void;
}

const COMMON_EMOJIS = ['😊', '😂', '👍', '❤️', '🔥', '🎉', '🙌', '✨', '☕', '🍜', '🌍', '👏'];

export const MessageComposer: React.FC<MessageComposerProps> = ({
  recipientName,
  onSendMessage,
  replyTo,
  onCancelReply,
  onSendAttachment,
  onTyping,
}) => {
  const [text, setText] = useState('');
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [showAttachMenu, setShowAttachMenu] = useState(false);

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
    onSendMessage(text.trim(), replyTo?.id);
    setText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
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
                Replying to {replyTo.senderName}
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
                <span>Document or File</span>
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
              onTyping?.(e.target.value.trim().length > 0);
            }}
            onBlur={() => onTyping?.(false)}
            onKeyDown={handleKeyDown}
            placeholder={`Message ${recipientName}...`}
            className="w-full bg-transparent resize-none text-sm text-[#1E2230] dark:text-[#F5F6FA] placeholder-[#8A8F9E] dark:placeholder-[#74798C] focus:outline-none max-h-32 py-0.5 px-1 leading-relaxed"
          />
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
