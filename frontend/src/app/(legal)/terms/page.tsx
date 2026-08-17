"use client";

import Link from "next/link";
import { TERMS_CONTENT } from "@/shared/lib/legal-content";
import { useDocumentMetadata, useInterfaceLanguage } from "@/shared/lib/use-ui-text";
import Logo from "@/shared/ui/Logo";
import styles from "../legal.module.css";

export default function TermsPage() {
  useDocumentMetadata("meta.title.terms", "meta.desc.terms");
  const lang = useInterfaceLanguage();
  const c = TERMS_CONTENT[lang] ?? TERMS_CONTENT.en;

  return (
    <main className={styles.page}>
      <article className={styles.sheet}>
        <Link className={styles.brand} href="/login">
          <Logo size={24} />
          LinguaFlow
        </Link>

        <h1>{c.title}</h1>
        <p className={styles.updated}>{c.updated}</p>

        <p className={styles.callout}>
          {c.calloutLead}
          <strong>{c.calloutBold}</strong>
          {c.calloutTail}
        </p>

        <h2>{c.serviceTitle}</h2>
        <p>{c.serviceDesc}</p>

        <h2>{c.qualityTitle}</h2>
        <p>
          {c.qualityP1Lead}
          <strong>{c.qualityP1Bold}</strong>
          {c.qualityP1Tail}
        </p>
        <p>{c.qualityP2}</p>

        <h2>{c.responsibilitiesTitle}</h2>
        <ul>
          <li>{c.responsibilitiesItem1}</li>
          <li>
            {c.responsibilitiesItem2Prefix}
            <Link href="/privacy">{c.responsibilitiesItem2Link}</Link>
            {c.responsibilitiesItem2Suffix}
          </li>
          <li>{c.responsibilitiesItem3}</li>
        </ul>

        <h2>{c.accountsTitle}</h2>
        <p>{c.accountsDesc}</p>

        <Link className={styles.back} href="/register">
          {c.backToRegister}
        </Link>
      </article>
    </main>
  );
}
