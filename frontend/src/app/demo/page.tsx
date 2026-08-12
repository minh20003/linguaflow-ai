import type { Metadata } from "next";
import "@chatscope/chat-ui-kit-styles/dist/default/styles.min.css";
import SideBySideDemo from "@/components/chat/SideBySideDemo";

export const metadata: Metadata = {
  title: "Demo song song — LinguaChat",
  description: "Hai tài khoản, hai ngôn ngữ, cùng một hội thoại.",
};

export default function DemoPage() {
  return <SideBySideDemo />;
}
