"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import { login } from "@/lib/api";
import { setSession } from "@/lib/auth";
import { mainLabel } from "@/lib/i18n";
import styles from "./AuthForm.module.css";

const EMAIL_RE = /\S+@\S+\.\S+/;

export default function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});

  function validate(): boolean {
    const nextErrors: typeof errors = {};
    if (!email) nextErrors.email = "Bạn chưa nhập email.";
    else if (!EMAIL_RE.test(email)) nextErrors.email = "Email chưa đúng định dạng. Ví dụ: ban@vidu.com";
    if (!password) nextErrors.password = "Bạn chưa nhập mật khẩu.";
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    if (!validate()) return;
    setLoading(true);
    try {
      const result = await login(email, password);
      setSession(result.access_token, result.user);
      router.push("/chat");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Chưa thể đăng nhập. Bạn vui lòng thử lại nhé.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit} noValidate>
      <div className={styles.welcome}>
        <span className={styles.welcomeMark} aria-hidden="true">◌</span>
        <p className={styles.eyebrow}>Rất vui được gặp lại bạn</p>
        <h1 className={styles.loginTitle}>Chào mừng trở lại</h1>
        <p className={styles.loginDescription}>Đăng nhập để tiếp tục những cuộc trò chuyện của bạn.</p>
      </div>

      {error && <div className={styles.formError} role="alert"><span className={styles.errorMark} aria-hidden="true">!</span>{error}</div>}

      <div className={styles.fields}>
        <Input id="login-email" type="email" autoComplete="email" inputMode="email" placeholder="ban@vidu.com" label={mainLabel("email")} value={email} onChange={(event) => { setEmail(event.target.value); setErrors((previous) => ({ ...previous, email: undefined })); }} error={errors.email} />
        <Input id="login-password" type="password" autoComplete="current-password" placeholder="Nhập mật khẩu của bạn" label={mainLabel("password")} showText={mainLabel("show")} hideText={mainLabel("hide")} value={password} onChange={(event) => { setPassword(event.target.value); setErrors((previous) => ({ ...previous, password: undefined })); }} error={errors.password} />
      </div>

      <div className={styles.row}>
        <label className={styles.check}>
          <input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} />
          <span>{mainLabel("remember")}</span>
        </label>
        <a href="#" className={styles.quiet}>{mainLabel("forgot")}</a>
      </div>

      <Button type="submit" size="lg" fullWidth loading={loading} className={styles.loginButton}>
        <span className={styles.actionMain}>{mainLabel("signIn")}</span>
      </Button>

      <p className={styles.footer}>Bạn mới đến LinguaChat? <Link href="/register">Tạo tài khoản miễn phí</Link></p>
    </form>
  );
}
