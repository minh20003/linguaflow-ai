"use client";

import { useLanguage } from "./LanguageContext";
import { uiText } from "@/shared/lib/ui-text";
import styles from "./AuthRail.module.css";

export default function AuthRail() {
  const { lang } = useLanguage();

  return (
    // The brand name is already in the card header above; repeating it here
    // said the name twice and the product's actual point zero times.
    <aside className={styles.rail} aria-label={uiText(lang, "auth.rail.ariaLabel")}>
      <div className={styles.intro}>
        <h2 className={styles.heading}>{uiText(lang, "auth.rail.heading")}</h2>
        <p className={styles.description}>
          {uiText(lang, "auth.rail.description")}
        </p>
      </div>
    </aside>
  );
}

