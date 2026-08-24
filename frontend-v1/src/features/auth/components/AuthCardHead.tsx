"use client";

import React from "react";
import { useUiText } from "@/shared/lib/use-ui-text";
import LanguagePicker from "@/shared/ui/LanguagePicker";
import Logo from "@/shared/ui/Logo";
import ThemeToggle from "@/shared/ui/ThemeToggle";
import { useLanguage } from "./LanguageContext";
import styles from "./AuthCardHead.module.css";

export default function AuthCardHead() {
  const { lang, setLang } = useLanguage();
  const t = useUiText();

  return (
    <header className={styles.head}>
      <span className={styles.brand}>
        <Logo size={24} />
        LinguaFlow
      </span>
      <div className={styles.actions}>
        <div className={styles.languagePicker}>
          <LanguagePicker
            id="auth-interface-language"
            value={lang}
            onChange={(code) => setLang(code as typeof lang)}
            label={t("auth.interfaceLanguage")}
          />
        </div>
        <ThemeToggle compact />
      </div>
    </header>
  );
}

