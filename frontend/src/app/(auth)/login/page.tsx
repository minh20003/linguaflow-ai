import type { Metadata } from "next";
import { LoginScreen } from "@/features/auth/screens/LoginScreen";

export const metadata: Metadata = {
  title: "Đăng nhập — LinguaChat",
  description:
    "Đăng nhập LinguaChat: viết bằng tiếng của bạn, người kia đọc bằng tiếng của họ.",
};

export default function LoginPage() {
  return <LoginScreen />;
}
