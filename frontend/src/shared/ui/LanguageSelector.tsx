"use client";

import React from "react";
import {
  SUPPORTED_LANGUAGES,
  getLanguage,
  type LanguageCode,
} from "@/shared/lib/constants";
import styles from "./LanguageSelector.module.css";

interface LanguageSelectorProps {
  value: LanguageCode;
  onChange: (code: LanguageCode) => void;
  /** Tên của nhóm cho screen reader. */
  label: string;
  /** `name` của nhóm radio — phải khác nhau nếu có hai nhóm trên một trang. */
  name?: string;
}

/**
 * Dải mã ngôn ngữ: ô vuông hairline chứa mã hai chữ, không emoji cờ (§7.4).
 *
 * Dùng `input[type=radio]` thật thay vì `button role="radio"`: mũi tên di
 * chuyển trong nhóm và cả nhóm chỉ chiếm một điểm tab — hành vi mà bản cũ
 * dựng bằng button không có.
 */
export default function LanguageSelector({
  value,
  onChange,
  label,
  name = "language",
}: LanguageSelectorProps) {
  const current = getLanguage(value);

  return (
    <div className={styles.wrapper}>
      <div className={styles.grid} role="radiogroup" aria-label={label}>
        {SUPPORTED_LANGUAGES.map((lang) => (
          <label key={lang.code} className={styles.chip}>
            <input
              type="radio"
              name={name}
              value={lang.code}
              checked={value === lang.code}
              onChange={() => onChange(lang.code)}
              className={styles.radio}
            />
            <span className="sr-only">{lang.name}</span>
            <span className={styles.face} aria-hidden="true">
              {lang.display}
            </span>
          </label>
        ))}
      </div>

      {/* Tên bản địa hiện một lần cho mục đang chọn — chip chỉ mang mã. */}
      <p className={styles.current} lang={current.code}>
        {current.name}
      </p>
    </div>
  );
}
