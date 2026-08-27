import type { Metadata } from "next";
import { Suspense } from "react";
import { ResetPasswordScreen } from "@/features/auth/screens/ResetPasswordScreen";

export const metadata: Metadata = {
  title: "Set a new password — LinguaChat",
  description: "Set a new password for your LinguaChat account.",
};

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="min-h-80" aria-busy="true" />}>
      <ResetPasswordScreen />
    </Suspense>
  );
}
