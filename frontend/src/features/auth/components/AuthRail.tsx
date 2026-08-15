"use client";

import React from "react";
import styles from "./AuthRail.module.css";

export default function AuthRail() {
  return (
    // The brand name is already in the card header above; repeating it here
    // said the name twice and the product's actual point zero times.
    <aside className={styles.rail} aria-label="Giới thiệu LinguaFlow">
      <div className={styles.intro}>
        <h2 className={styles.heading}>Bạn viết tiếng của mình. Họ đọc tiếng của họ.</h2>
        <p className={styles.description}>
          Mỗi tin nhắn được dịch theo ngữ cảnh của cuộc trò chuyện, nên cách xưng hô
          và thuật ngữ giữ đúng ý bạn muốn nói.
        </p>
      </div>
    </aside>
  );
}
