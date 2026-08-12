import type { Metadata } from "next";
import RegisterForm from "@/components/auth/RegisterForm";

export const metadata: Metadata = {
  title: "Tạo tài khoản — LinguaChat",
  description:
    "Tạo tài khoản LinguaChat và bắt đầu nhắn tin xuyên mười ngôn ngữ.",
};

export default function RegisterPage() {
  return <RegisterForm />;
}
