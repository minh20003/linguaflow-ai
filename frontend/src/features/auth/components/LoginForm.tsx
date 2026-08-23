"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Button from "@/shared/ui/Button";
import Input from "@/shared/ui/Input";
import { googleLogin, login } from "@/shared/lib/api";
import { saveSession } from "@/shared/lib/auth-session";
import { getGisLocale, loadGis } from "@/shared/lib/google-gis";
import type { LanguageCode } from "@/shared/lib/constants";
import { formMessage } from "@/shared/lib/form-messages";
import { mainLabel } from "@/shared/lib/i18n";
import { uiText } from "@/shared/lib/ui-text";
import { useDocumentMetadata } from "@/shared/lib/use-ui-text";
import { useLanguage } from "./LanguageContext";
import styles from "./AuthForm.module.css";

const EMAIL_RE = /\S+@\S+\.\S+/;

type ErrorState = { lang: LanguageCode; message: string };
type FieldErrors = { email?: string; password?: string };
type FieldErrorState = { lang: LanguageCode; fields: FieldErrors };

export default function LoginForm() {
  useDocumentMetadata("meta.title.login", "meta.desc.login");
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
  const [googleLoadError, setGoogleLoadError] = useState(false);
  const googleButtonRef = useRef<HTMLDivElement>(null);
  const visibleError = error?.lang === lang ? error.message : "";
  const visibleErrors = errors?.lang === lang ? errors.fields : {};

  // Load GIS and render the Google Sign-In button once on mount or lang change
  useEffect(() => {
    const clientId = process.env.NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID;
    if (!clientId) return;

    let cancelled = false;
    const container = googleButtonRef.current;

    loadGis()
      .then(() => {
        if (cancelled || !window.google?.accounts?.id || !container) return;

        // Clear container before rendering to prevent duplicate buttons
        container.innerHTML = "";

        // Initialize GIS with callback that handles the credential
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: async (response: { credential?: string; error?: string }) => {
            if (cancelled) return;
            if (!response.credential) return; // User dismissed

            setError(null);
            try {
              const result = await googleLogin(response.credential);
              saveSession(result, true);
              router.replace("/chat");
            } catch {
              setError({ lang, message: formMessage(lang, "googleLoginFailed") });
            }
          },
          auto_select: false,
        });

        // Render the Google Sign-In button in the user's locale
        window.google.accounts.id.renderButton(container, {
          type: "standard",
          theme: "outline",
          size: "large",
          text: "signin_with",
          shape: "rectangular",
          width: container.offsetWidth || 280,
          locale: getGisLocale(lang),
        });
      })
      .catch(() => {
        if (!cancelled) {
          setGoogleLoadError(true);
        }
      });

    return () => {
      cancelled = true;
      if (container) {
        container.innerHTML = "";
      }
    };
  }, [lang, router]);

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

  const hasGoogleClientId = Boolean(process.env.NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID);

  return (
    <form className={styles.form} onSubmit={handleSubmit} noValidate>
      <div className={styles.welcome}>
        <h1 className={styles.loginTitle}>{uiText(lang, "auth.welcomeBack")}</h1>
        <p className={styles.loginDescription}>{uiText(lang, "auth.signInDescription")}</p>
      </div>

      {visibleError && (
        <div className={styles.formError} role="alert">
          <span className={styles.errorMark} aria-hidden="true">
            !
          </span>
          {visibleError}
        </div>
      )}

      <div className={styles.fields}>
        <Input
          id="login-email"
          type="email"
          autoComplete="email"
          inputMode="email"
          placeholder={uiText(lang, "auth.emailPlaceholder")}
          label={mainLabel("email", lang)}
          value={email}
          onChange={(event) => {
            setEmail(event.target.value);
            setErrors((previous) =>
              previous?.lang === lang
                ? { ...previous, fields: { ...previous.fields, email: undefined } }
                : previous,
            );
          }}
          error={visibleErrors.email}
        />
        <Input
          id="login-password"
          type="password"
          autoComplete="current-password"
          placeholder={uiText(lang, "auth.passwordPlaceholder")}
          label={mainLabel("password", lang)}
          showText={mainLabel("show", lang)}
          hideText={mainLabel("hide", lang)}
          value={password}
          onChange={(event) => {
            setPassword(event.target.value);
            setErrors((previous) =>
              previous?.lang === lang
                ? { ...previous, fields: { ...previous.fields, password: undefined } }
                : previous,
            );
          }}
          error={visibleErrors.password}
        />
      </div>

      <div className={styles.row}>
        <label className={styles.check}>
          <input
            type="checkbox"
            checked={remember}
            onChange={(event) => setRemember(event.target.checked)}
          />
          <span>{mainLabel("remember", lang)}</span>
        </label>
        <Link href="/forgot-password" className={styles.quiet}>
          {mainLabel("forgot", lang)}
        </Link>
      </div>

      <Button
        type="submit"
        size="lg"
        fullWidth
        loading={loading}
        className={styles.loginButton}
      >
        <span className={styles.actionMain}>{mainLabel("signIn", lang)}</span>
      </Button>

      {hasGoogleClientId && (
        <>
          <div className={styles.orDivider}>
            <span className={styles.orLine} />
            <span className={styles.orText}>{uiText(lang, "auth.or")}</span>
            <span className={styles.orLine} />
          </div>
          {googleLoadError ? (
            <p className={styles.formError} role="status">
              {formMessage(lang, "googleLoginFailed")}
            </p>
          ) : (
            /* Google renders its own button inside this div via renderButton() */
            <div
              ref={googleButtonRef}
              className={styles.googleButton}
              aria-label={uiText(lang, "auth.google.signInWithGoogle")}
            />
          )}
        </>
      )}

      <p className={styles.footer}>
        {uiText(lang, "auth.newToProduct")}{" "}
        <Link href="/register">{uiText(lang, "auth.createFreeAccount")}</Link>
      </p>
    </form>
  );
}
