import type { Metadata } from "next";
import RequireAuth from "@/features/auth/components/RequireAuth";
import SettingsPage from "@/features/settings/components/SettingsPage";

export const metadata: Metadata = {
  title: "Settings — LinguaFlow",
  description: "Choose your reading language and customize appearance.",
};

export default function Settings() {
  return (
    <RequireAuth>
      <SettingsPage />
    </RequireAuth>
  );
}
