"use client";

import React from "react";
import styles from "./AuthRail.module.css";

export default function AuthRail() {
  return (
    <aside className={styles.rail} aria-label="Giới thiệu LinguaChat">
      <p className={styles.eyebrow}>LinguaChat</p>
      <div className={styles.intro}>
        <h2 className={styles.heading}>Trò chuyện rõ ràng, gần gũi hơn.</h2>
        <p className={styles.description}>
          Giữ kết nối với mọi người qua những cuộc trò chuyện đơn giản, riêng tư và dễ theo dõi.
        </p>
      </div>
    </aside>
  );
}
