import type { Metadata } from "next";
import PasswordRecoveryForm from "@/components/auth/PasswordRecoveryForm";

export const metadata: Metadata = {
  title: "Khôi phục tài khoản — LinguaChat",
  description: "Đặt lại mật khẩu tài khoản LinguaChat.",
};

export default function ForgotPasswordPage() {
  return <PasswordRecoveryForm />;
}
