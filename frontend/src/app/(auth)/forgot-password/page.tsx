import type { Metadata } from "next";
import PasswordRecoveryForm from "@/features/auth/components/PasswordRecoveryForm";

export const metadata: Metadata = {
  title: "Account recovery — LinguaFlow",
  description: "Reset your LinguaFlow account password.",
};

export default function ForgotPasswordPage() {
  return <PasswordRecoveryForm />;
}
