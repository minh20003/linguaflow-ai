"use client";

import { useUiText } from "@/shared/lib/use-ui-text";
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
  const t = useUiText();
  const label = t(showOriginal ? "toggle.original" : "toggle.translated");

  return (
    <button
      type="button"
      role="switch"
      aria-checked={showOriginal}
      aria-label={label}
      title={label}
      className={`${styles.switch} ${showOriginal ? styles.isOriginal : ""} ${className}`}
      onClick={onToggle}
    >
      <span className={styles.knob} aria-hidden="true" />
    </button>
  );
}
