"use client";

import React from "react";
import { Laptop, Moon, Sun } from "lucide-react";
import { type ThemeMode, useTheme } from "@/shared/lib/ThemeContext";
import { useUiText } from "@/shared/lib/use-ui-text";
import styles from "./ThemeToggle.module.css";

interface ThemeToggleProps {
  compact?: boolean;
  className?: string;
}

export default function ThemeToggle({
  compact = false,
  className = "",
}: ThemeToggleProps) {
  const { theme, setTheme } = useTheme();
  const t = useUiText();

  const options: Array<{ mode: ThemeMode; label: string; icon: React.ReactNode }> = [
    {
      mode: "light",
      label: t("theme.light"),
      icon: <Sun className={styles.icon} aria-hidden="true" />,
    },
    {
      mode: "dark",
      label: t("theme.dark"),
      icon: <Moon className={styles.icon} aria-hidden="true" />,
    },
    {
      mode: "system",
      label: t("theme.system"),
      icon: <Laptop className={styles.icon} aria-hidden="true" />,
    },
  ];

  return (
    <div
      className={`${styles.toggleContainer} ${compact ? styles.compact : ""} ${className}`}
      role="radiogroup"
      aria-label={t("theme.group")}
    >
      {options.map((opt) => {
        const isSelected = theme === opt.mode;
        return (
          <button
            key={opt.mode}
            type="button"
            role="radio"
            aria-checked={isSelected}
            className={`${styles.optionBtn} ${isSelected ? styles.active : ""}`}
            onClick={() => setTheme(opt.mode)}
            title={`${t("settings.theme.title")}: ${opt.label}`}
          >
            {opt.icon}
            <span className={styles.label}>{opt.label}</span>
          </button>
        );
      })}
    </div>
  );
}
