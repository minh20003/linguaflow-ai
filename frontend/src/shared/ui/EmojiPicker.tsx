"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Smile } from "lucide-react";
import styles from "./EmojiPicker.module.css";

/**
 * A fixed set rather than a full emoji library.
 *
 * Every emoji package worth using ships a megabyte or more of metadata for a
 * feature that, in a chat whose point is translation, is a garnish. These are
 * the ones people actually reach for in a work conversation.
 */
const EMOJI = [
  "😀", "😁", "😂", "🙂", "😉", "😊", "😍", "🤔",
  "😅", "😭", "😮", "😴", "🙃", "😎", "🥳", "😇",
  "👍", "👎", "👏", "🙏", "💪", "🤝", "👋", "✌️",
  "❤️", "🔥", "✨", "🎉", "💡", "✅", "❌", "⚠️",
  "📌", "📎", "📷", "🗓️", "⏰", "🚀", "☕", "🌍",
];

interface EmojiPickerProps {
  /** Called with the chosen character; the caller appends it to the draft. */
  onSelect: (emoji: string) => void;
  disabled?: boolean;
}

export default function EmojiPicker({ onSelect, disabled = false }: EmojiPickerProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (event: Event) => {
      if (event instanceof KeyboardEvent && event.key !== "Escape") return;
      if (event.type === "pointerdown" && rootRef.current?.contains(event.target as Node)) return;
      setOpen(false);
    };
    document.addEventListener("keydown", close);
    document.addEventListener("pointerdown", close);
    return () => {
      document.removeEventListener("keydown", close);
      document.removeEventListener("pointerdown", close);
    };
  }, [open]);

  const choose = useCallback((emoji: string) => {
    onSelect(emoji);
    setOpen(false);
  }, [onSelect]);

  return (
    <div className={styles.root} ref={rootRef}>
      {open && (
        <div className={styles.panel} role="dialog" aria-label="Chọn biểu tượng cảm xúc">
          <div className={styles.grid}>
            {EMOJI.map((emoji) => (
              <button
                key={emoji}
                type="button"
                className={styles.emoji}
                aria-label={`Chèn ${emoji}`}
                onClick={() => choose(emoji)}
              >
                {emoji}
              </button>
            ))}
          </div>
        </div>
      )}
      <button
        type="button"
        className={styles.trigger}
        aria-label="Biểu tượng cảm xúc"
        title="Biểu tượng cảm xúc"
        aria-expanded={open}
        aria-haspopup="dialog"
        disabled={disabled}
        onClick={() => setOpen((value) => !value)}
      >
        <Smile size={18} strokeWidth={1.8} aria-hidden="true" />
      </button>
    </div>
  );
}
