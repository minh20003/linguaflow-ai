"use client";

import React from "react";
import { usePathname } from "next/navigation";
import styles from "./AuthCardHead.module.css";

/** Mã biểu ở góc thẻ (§10): mỗi biểu mẫu một số hiệu. */
const SERIALS: Record<string, string> = {
  "/login": "01",
  "/register": "02",
};

export default function AuthCardHead() {
  const pathname = usePathname();
  const serial = SERIALS[pathname ?? ""] ?? "01";

  return (
    <header className={styles.head}>
      <span className={styles.brand}>LinguaChat</span>
      <span className={styles.serial}>XÁC THỰC · {serial}</span>
    </header>
  );
}
