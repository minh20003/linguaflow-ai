"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Button from "@/shared/ui/Button";
import Input from "@/shared/ui/Input";
import { login } from "@/shared/lib/api";
import { saveSession } from "@/shared/lib/auth-session";
import type { LanguageCode } from "@/shared/lib/constants";
import { formMessage } from "@/shared/lib/form-messages";
import { mainLabel } from "@/shared/lib/i18n";
import { uiText } from "@/shared/lib/ui-text";
import { useLanguage } from "./LanguageContext";
import styles from "./AuthForm.module.css";

const EMAIL_RE = /\S+@\S+\.\S+/;

type ErrorState = { lang: LanguageCode; message: string };
type FieldErrors = { email?: string; password?: string };
type FieldErrorState = { lang: LanguageCode; fields: FieldErrors };

export default function LoginForm() {
  const router = useRouter();
  /* The rail's choice drives the labels here too, not just the sub-labels —
     otherwise picking 中文 leaves the form in Vietnamese (§1.3). */
  const { lang } = useLanguage();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ErrorState | null>(null);
  const [errors, setErrors] = useState<FieldErrorState | null>(null);
  const visibleError = error?.lang === lang ? error.message : "";
  const visibleErrors = errors?.lang === lang ? errors.fields : {};

  function validate(): boolean {
    const nextErrors: FieldErrors = {};
    if (!email) nextErrors.email = formMessage(lang, "emailRequired");
    else if (!EMAIL_RE.test(email)) nextErrors.email = formMessage(lang, "emailInvalid");
    if (!password) nextErrors.password = formMessage(lang, "passwordRequired");
    setErrors({ lang, fields: nextErrors });
    return Object.keys(nextErrors).length === 0;
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    if (!validate()) return;
    setLoading(true);
    try {
      const result = await login(email, password, remember);
      saveSession(result, remember);
      router.replace("/chat");
    } catch {
      setError({ lang, message: formMessage(lang, "loginFailed") });
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit} noValidate>
      <div className={styles.welcome}>
        <h1 className={styles.loginTitle}>{uiText(lang, "auth.welcomeBack")}</h1>
        <p className={styles.loginDescription}>{uiText(lang, "auth.signInDescription")}</p>
      </div>

      {visibleError && <div className={styles.formError} role="alert"><span className={styles.errorMark} aria-hidden="true">!</span>{visibleError}</div>}

      <div className={styles.fields}>
        <Input id="login-email" type="email" autoComplete="email" inputMode="email" placeholder={uiText(lang, "auth.emailPlaceholder")} label={mainLabel("email", lang)} value={email} onChange={(event) => { setEmail(event.target.value); setErrors((previous) => previous?.lang === lang ? { ...previous, fields: { ...previous.fields, email: undefined } } : previous); }} error={visibleErrors.email} />
        <Input id="login-password" type="password" autoComplete="current-password" placeholder={uiText(lang, "auth.passwordPlaceholder")} label={mainLabel("password", lang)} showText={mainLabel("show", lang)} hideText={mainLabel("hide", lang)} value={password} onChange={(event) => { setPassword(event.target.value); setErrors((previous) => previous?.lang === lang ? { ...previous, fields: { ...previous.fields, password: undefined } } : previous); }} error={visibleErrors.password} />
      </div>

      <div className={styles.row}>
        <label className={styles.check}>
          <input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} />
          <span>{mainLabel("remember", lang)}</span>
        </label>
        <Link href="/forgot-password" className={styles.quiet}>{mainLabel("forgot", lang)}</Link>
      </div>

      <Button type="submit" size="lg" fullWidth loading={loading} className={styles.loginButton}>
        <span className={styles.actionMain}>{mainLabel("signIn", lang)}</span>
      </Button>

      <p className={styles.footer}>{uiText(lang, "auth.newToProduct")} <Link href="/register">{uiText(lang, "auth.createFreeAccount")}</Link></p>
    </form>
  );
}
