"use client";

import React from "react";
import LanguageSelector from "@/components/ui/LanguageSelector";
import { mainLabel } from "@/lib/i18n";
import { useLanguage } from "./LanguageContext";
import styles from "./AuthRail.module.css";

export default function AuthRail() {
  const { lang, setLang } = useLanguage();
  return (
    <aside className={styles.rail}>
      <p className={styles.heading}>{mainLabel("language")}</p>
      <p className={styles.description}>Chúng mình sẽ dùng lựa chọn này để hiển thị giao diện phù hợp với bạn.</p>
      <LanguageSelector value={lang} onChange={setLang} label={mainLabel("language")} name="target-language" />
      <p className={styles.spec}>Của bạn<br />Có thể đổi bất kỳ lúc nào</p>
    </aside>
  );
}
