import type { Metadata } from "next";
import LoginForm from "@/features/auth/components/LoginForm";

export const metadata: Metadata = {
  title: "Sign in — LinguaFlow",
  description:
    "Sign in to LinguaFlow: write in your language, they read in theirs.",
};

export default function LoginPage() {
  return <LoginForm />;
}
