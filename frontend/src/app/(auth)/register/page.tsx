import type { Metadata } from "next";
import RegisterForm from "@/features/auth/components/RegisterForm";

export const metadata: Metadata = {
  title: "Create account — LinguaFlow",
  description:
    "Create a LinguaFlow account and start messaging across 14 languages.",
};

export default function RegisterPage() {
  return <RegisterForm />;
}
