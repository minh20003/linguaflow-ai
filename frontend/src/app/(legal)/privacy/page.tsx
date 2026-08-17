"use client";

import Link from "next/link";
import { PRIVACY_CONTENT } from "@/shared/lib/legal-content";
import { useDocumentMetadata, useInterfaceLanguage } from "@/shared/lib/use-ui-text";
import Logo from "@/shared/ui/Logo";
import styles from "../legal.module.css";

/**
 * Written from `ARCHITECTURE.md` section 6, not from a template.
 *
 * The point of the page is section 6.4: translating a message means sending it
 * to a third party, and the person typing it deserves to know that before they
 * type. A privacy page that omitted this would be worse than no page.
 */
export default function PrivacyPage() {
  useDocumentMetadata("meta.title.privacy", "meta.desc.privacy");
  const lang = useInterfaceLanguage();
  const c = PRIVACY_CONTENT[lang] ?? PRIVACY_CONTENT.en;

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

        <h2>{c.storedTitle}</h2>
        <p>{c.storedP1}</p>
        <p>{c.storedP2}</p>

        <h2>{c.accessTitle}</h2>
        <ul>
          {c.accessItems.map((item, index) => (
            <li key={index}>{item}</li>
          ))}
        </ul>

        <h2>{c.thirdPartyTitle}</h2>
        <p>{c.thirdPartyDesc}</p>
        <table className={styles.table}>
          <thead>
            <tr>
              {c.tableHeaders.map((header, index) => (
                <th key={index}>{header}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>{c.tableRows[0][0]}</td>
              <td>{c.tableRows[0][1]}</td>
              <td>{c.tableRows[0][2] as string}</td>
            </tr>
            <tr>
              <td>{c.tableRows[1][0]}</td>
              <td>{c.tableRows[1][1]}</td>
              <td>
                {(c.tableRows[1][2] as { before: string; bold: string; after: string }).before}
                <strong>
                  {(c.tableRows[1][2] as { before: string; bold: string; after: string }).bold}
                </strong>
                {(c.tableRows[1][2] as { before: string; bold: string; after: string }).after}
              </td>
            </tr>
            <tr>
              <td>{c.tableRows[2][0]}</td>
              <td>{c.tableRows[2][1]}</td>
              <td>{c.tableRows[2][2] as string}</td>
            </tr>
          </tbody>
        </table>

        <h2>{c.deletionTitle}</h2>
        <p>{c.deletionDesc}</p>

        <Link className={styles.back} href="/register">
          {c.backToRegister}
        </Link>
      </article>
    </main>
  );
}
