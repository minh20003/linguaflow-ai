import type { Metadata } from "next";
import "@chatscope/chat-ui-kit-styles/dist/default/styles.min.css";
import MessagingApp from "@/features/chat/components/MessagingApp";
import RequireAuth from "@/features/auth/components/RequireAuth";

export const metadata: Metadata = {
  title: "Messages — LinguaFlow",
  description: "Real-time chat and translation across languages.",
};

export default function ChatPage() {
  return (
    <RequireAuth>
      <MessagingApp />
    </RequireAuth>
  );
}
