import type { Metadata } from "next";
import LoginForm from "@/components/auth/LoginForm";

export const metadata: Metadata = {
  title: "Đăng nhập — LinguaChat",
  description:
    "Đăng nhập LinguaChat: viết bằng tiếng của bạn, người kia đọc bằng tiếng của họ.",
};

export default function LoginPage() {
  return <LoginForm />;
}
