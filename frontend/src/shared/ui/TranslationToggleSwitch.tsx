"use client";

import styles from "./TranslationToggleSwitch.module.css";

interface TranslationToggleSwitchProps {
  showOriginal: boolean;
  onToggle: () => void;
  className?: string;
}

/**
 * Flips one message between its translation and its original text (F-04).
 *
 * The control carries no visible text, so the accessible name is the only thing
 * that says what it does — it must stay in step with `showOriginal`.
 */
export default function TranslationToggleSwitch({
  showOriginal,
  onToggle,
  className = "",
}: TranslationToggleSwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={showOriginal}
      aria-label={showOriginal ? "Đang hiện bản gốc, bấm để xem bản dịch" : "Đang hiện bản dịch, bấm để xem bản gốc"}
      title={showOriginal ? "Chuyển sang xem bản dịch" : "Chuyển sang xem bản gốc"}
      className={`${styles.switch} ${showOriginal ? styles.isOriginal : ""} ${className}`}
      onClick={onToggle}
    >
      <span className={styles.knob} aria-hidden="true" />
    </button>
  );
}
