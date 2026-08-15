import type { Metadata } from "next";
import RegisterForm from "@/features/auth/components/RegisterForm";

export const metadata: Metadata = {
  title: "Tạo tài khoản — LinguaFlow",
  description:
    "Tạo tài khoản LinguaFlow và bắt đầu nhắn tin xuyên mười ngôn ngữ.",
};

export default function RegisterPage() {
  return <RegisterForm />;
}
