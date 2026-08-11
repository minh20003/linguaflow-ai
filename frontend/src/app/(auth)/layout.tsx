import React from "react";
import AuthCardHead from "@/components/auth/AuthCardHead";
import AuthRail from "@/components/auth/AuthRail";
import { LanguageProvider } from "@/components/auth/LanguageContext";
import styles from "./auth.module.css";

/**
 * Thẻ nhãn 620px, bên trong chia hai cột không đều — cấu trúc mặt sau một
 * nhãn sản phẩm: cột thông số hẹp, cột nội dung rộng (docs/design.md §10).
 */
export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <main className={styles.stage}>
      <LanguageProvider>
        <div className={styles.card}>
          <AuthCardHead />
          <div className={styles.body}>
            <AuthRail />
            <div className={styles.panel}>{children}</div>
          </div>
        </div>
      </LanguageProvider>
    </main>
  );
}
