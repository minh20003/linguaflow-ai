import type { Metadata } from "next";
import PasswordRecoveryForm from "@/features/auth/components/PasswordRecoveryForm";

export const metadata: Metadata = {
  title: "Khôi phục tài khoản — LinguaFlow",
  description: "Đặt lại mật khẩu tài khoản LinguaFlow.",
};

export default function ForgotPasswordPage() {
  return <PasswordRecoveryForm />;
}
