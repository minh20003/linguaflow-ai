"use client";

import React from "react";
import Logo from "@/shared/ui/Logo";
import ThemeToggle from "@/shared/ui/ThemeToggle";
import styles from "./AuthCardHead.module.css";

export default function AuthCardHead() {
  return (
    <header className={styles.head}>
      <span className={styles.brand}>
        <Logo size={24} />
        LinguaFlow
      </span>
      <ThemeToggle compact />
    </header>
  );
}

