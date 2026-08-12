"use client";

import React from "react";
import styles from "./AuthCardHead.module.css";

export default function AuthCardHead() {
  return (
    <header className={styles.head}>
      <span className={styles.brand}>LinguaChat</span>
    </header>
  );
}
