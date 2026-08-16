import type { Metadata } from "next";
import { ForgotPasswordScreen } from "@/features/auth/screens/ForgotPasswordScreen";

export const metadata: Metadata = {
  title: "Reset password — LinguaChat",
  description: "Request password reset instructions for your LinguaChat account.",
};

export default function ForgotPasswordPage() {
  return <ForgotPasswordScreen />;
}
