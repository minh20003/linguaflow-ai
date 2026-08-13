"use client";

import { useCallback, useState } from "react";

import { login } from "@/shared/lib/api";
import type { AuthUser } from "@/shared/lib/auth";
import { createConversation, listConversations, lookupUserByEmail } from "@/shared/lib/chat-api";
import { languageLabel } from "@/shared/lib/constants";
import DemoMessagingApp from "./DemoMessagingApp";
import styles from "./SideBySideDemo.module.css";

/**
 * Two accounts, two reading languages, one conversation — side by side.
 *
 * A demo surface, not a product screen. It exists because the translation is
 * only legible when both ends are visible at once: watching one window shows a
 * message being sent, not a message arriving in another language.
 *
 * The accounts are the ones `scripts/seed_dev_users.py` creates, whose whole
 * point is that they read different languages. Their sessions are held in React
 * state rather than localStorage, which has room for exactly one.
 */

const ACCOUNTS = [
  { email: "member@test.com", password: "testpass123" },
  { email: "admin@test.com", password: "adminpass123" },
];

const CONVERSATION_TITLE = "Demo song ngữ";

type Session = { token: string; user: AuthUser };

export default function SideBySideDemo() {
  const [sessions, setSessions] = useState<Session[] | null>(null);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  // Started by a click rather than on mount. Signing two accounts in is a side
  // effect worth putting behind an explicit action, and it gives whoever is
  // presenting a moment to explain the screen before it fills.
  const start = useCallback(async () => {
    setBusy(true);
    setStatus("Đang đăng nhập hai tài khoản demo…");
    try {
      const results = await Promise.all(
        ACCOUNTS.map((account) => login(account.email, account.password)),
      );
      const pair: Session[] = results.map((result) => ({
        token: result.access_token,
        user: result.user,
      }));

      if (pair[0].user.preferred_language === pair[1].user.preferred_language) {
        setStatus(
          `Cả hai tài khoản cùng đọc ${languageLabel(pair[0].user.preferred_language)}, `
          + "nên sẽ không có bản dịch nào. Chạy `make reset-db` để seed lại với hai ngôn ngữ khác nhau.",
        );
        setBusy(false);
        return;
      }

      setStatus("Đang chuẩn bị hội thoại chung…");
      const existing = await listConversations(pair[0].token);
      const shared = existing.find((conversation) => conversation.title === CONVERSATION_TITLE);
      if (!shared) {
        const other = await lookupUserByEmail(ACCOUNTS[1].email, pair[0].token);
        if (!other) throw new Error(`Không tìm thấy tài khoản ${ACCOUNTS[1].email}.`);
        await createConversation(
          { type: "group", title: CONVERSATION_TITLE, member_ids: [pair[0].user.id, other.id] },
          pair[0].token,
        );
      }

      setSessions(pair);
    } catch (error) {
      setStatus(
        `${(error as Error).message} — kiểm tra backend đã chạy và đã seed tài khoản `
        + "(`make reset-db`).",
      );
      setBusy(false);
    }
  }, []);

  if (!sessions) {
    return (
      <main className={styles.loading}>
        <h1>Demo song ngữ</h1>
        <p>
          Mở hai tài khoản seed cạnh nhau — mỗi bên đọc một ngôn ngữ khác nhau —
          trong cùng một hội thoại. Gõ ở một bên, bản dịch hiện ở bên kia.
        </p>
        {status && <p role="status">{status}</p>}
        <button type="button" disabled={busy} onClick={() => void start()}>
          {busy ? "Đang chuẩn bị…" : "Bắt đầu demo"}
        </button>
      </main>
    );
  }

  return (
    <main className={styles.shell}>
      <header className={styles.banner}>
        <strong>Demo song ngữ</strong>
        <span>
          Gõ ở một bên, bản dịch hiện ở bên kia theo ngôn ngữ tài khoản đó đã cài.
          Mỗi tin nhắn có nút chuyển giữa bản dịch và bản gốc.
        </span>
      </header>
      <div className={styles.panes}>
        {sessions.map((session) => (
          <section key={session.user.id} className={styles.pane}>
            <div className={styles.paneHead}>
              <strong>{session.user.email}</strong>
              <span>đọc {languageLabel(session.user.preferred_language)}</span>
            </div>
            <div className={styles.paneBody}>
              <DemoMessagingApp session={session} compact />
            </div>
          </section>
        ))}
      </div>
    </main>
  );
}
