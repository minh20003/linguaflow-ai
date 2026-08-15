"use client";

import React from "react";
import { Laptop, Moon, Sun } from "lucide-react";
import { type ThemeMode, useTheme } from "@/shared/lib/ThemeContext";
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

  const options: Array<{ mode: ThemeMode; label: string; icon: React.ReactNode }> = [
    {
      mode: "light",
      label: "Sáng",
      icon: <Sun className={styles.icon} aria-hidden="true" />,
    },
    {
      mode: "dark",
      label: "Tối",
      icon: <Moon className={styles.icon} aria-hidden="true" />,
    },
    {
      mode: "system",
      label: "Tự động",
      icon: <Laptop className={styles.icon} aria-hidden="true" />,
    },
  ];

  return (
    <div
      className={`${styles.toggleContainer} ${compact ? styles.compact : ""} ${className}`}
      role="radiogroup"
      aria-label="Chọn giao diện hiển thị"
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
            title={`Giao diện: ${opt.label}`}
          >
            {opt.icon}
            <span className={styles.label}>{opt.label}</span>
          </button>
        );
      })}
    </div>
  );
}
