"use client";

import React, { useId, useState } from "react";
import styles from "./Input.module.css";

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  /** Nhãn chính — tiếng Việt, mono in hoa. */
  label: string;
  /** Nhãn phụ ở ngôn ngữ đang chọn. `null` khi trùng ngôn ngữ giao diện. */
  altLabel?: string | null;
  /** `lang` của nhãn phụ — screen reader cần để phát âm đúng giọng. */
  altLang?: string;
  error?: string;
  /** Chữ trên nút hiện/ẩn mật khẩu, ở ngôn ngữ giao diện. */
  showText?: string;
  hideText?: string;
}

export default function Input({
  label,
  altLabel,
  altLang,
  error,
  showText = "Hiện",
  hideText = "Ẩn",
  type = "text",
  className = "",
  id,
  ...props
}: InputProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const errorId = `${inputId}-error`;

  const [revealed, setRevealed] = useState(false);
  const isPassword = type === "password";
  const inputType = isPassword && revealed ? "text" : type;

  return (
    <div className={[styles.field, className].filter(Boolean).join(" ")}>
      <div className={styles.labelRow}>
        <label htmlFor={inputId} className={styles.label}>
          {label}
        </label>
        {/* Nhãn phụ là bản dịch của nhãn chính — đọc lại thành nhiễu, nên ẩn
            khỏi screen reader. Ô nhập đã lấy tên từ nhãn chính qua htmlFor. */}
        {altLabel && (
          <span className={styles.altLabel} lang={altLang} aria-hidden="true">
            {altLabel}
          </span>
        )}
        {isPassword && (
          <button
            type="button"
            className={styles.reveal}
            onClick={() => setRevealed((v) => !v)}
            aria-pressed={revealed}
            aria-controls={inputId}
          >
            {revealed ? hideText : showText}
          </button>
        )}
      </div>

      <input
        id={inputId}
        type={inputType}
        className={styles.input}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        {...props}
      />

      {/* Lỗi luôn kèm dấu + chữ, không bao giờ chỉ dựa vào màu. */}
      {error && (
        <p id={errorId} className={styles.error} role="alert">
          <span className={styles.errorMark} aria-hidden="true">
            !
          </span>
          {error}
        </p>
      )}
    </div>
  );
}
