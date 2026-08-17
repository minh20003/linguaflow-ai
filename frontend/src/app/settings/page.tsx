import type { Metadata } from "next";
import RequireAuth from "@/features/auth/components/RequireAuth";
import SettingsPage from "@/features/settings/components/SettingsPage";

export const metadata: Metadata = {
  title: "Cài đặt — LinguaFlow",
  description: "Chọn ngôn ngữ bạn muốn đọc tin nhắn và tuỳ chỉnh giao diện.",
};

export default function Settings() {
  return <RequireAuth><SettingsPage /></RequireAuth>;
}
