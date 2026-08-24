"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import Button from "@/shared/ui/Button";
import Input from "@/shared/ui/Input";
import { requestPasswordReset, resetPassword } from "@/shared/lib/api";
import type { LanguageCode } from "@/shared/lib/constants";
import { MIN_PASSWORD_LENGTH, formMessage } from "@/shared/lib/form-messages";
import { mainLabel } from "@/shared/lib/i18n";
import { uiText } from "@/shared/lib/ui-text";
import { useDocumentMetadata } from "@/shared/lib/use-ui-text";
import { useLanguage } from "./LanguageContext";
import styles from "./AuthForm.module.css";

type RecoveryMessageKey =
  | "auth.recovery.requestAcceptedLocal"
  | "auth.recovery.requestAcceptedRemote"
  | "auth.recovery.passwordUpdated";

type ErrorState = { lang: LanguageCode; message: string };

/**
 * Password recovery, in two steps on one screen.
 *
 * The server only hands the reset token back in the response when it runs in
 * development; a deployed one writes it to its log for an administrator to read
 * out, because the project has no mail provider yet (docs/CONTRACT.md §3.9). So
 * the second step has to work either way: with the token already filled in, or
 * with a field for the person to type the one they were given.
 */
export default function PasswordRecoveryForm() {
  useDocumentMetadata("meta.title.forgotPassword", "meta.desc.forgotPassword");
  const { lang } = useLanguage();
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [tokenFromServer, setTokenFromServer] = useState(false);
  const [requested, setRequested] = useState(false);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ErrorState | null>(null);
  const [messageKey, setMessageKey] = useState<RecoveryMessageKey | null>(null);
  const [complete, setComplete] = useState(false);

  const visibleError = error?.lang === lang ? error.message : "";

  async function requestReset(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await requestPasswordReset(email);
      setRequested(true);
      if (result.reset_token) {
        setToken(result.reset_token);
        setTokenFromServer(true);
        setMessageKey("auth.recovery.requestAcceptedLocal");
      } else {
        setMessageKey("auth.recovery.requestAcceptedRemote");
      }
    } catch {
      setError({ lang, message: formMessage(lang, "resetRequestFailed") });
    } finally {
      setLoading(false);
    }
  }

  async function submitNewPassword(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!token.trim()) {
      setError({ lang, message: formMessage(lang, "resetTokenRequired") });
      return;
    }
    if (password.length < MIN_PASSWORD_LENGTH) {
      setError({ lang, message: formMessage(lang, "passwordTooShort", { n: MIN_PASSWORD_LENGTH }) });
      return;
    }
    if (password !== confirmPassword) {
      setError({ lang, message: formMessage(lang, "confirmMismatch") });
      return;
    }
    setLoading(true);
    try {
      await resetPassword(token, password);
      setComplete(true);
      setMessageKey("auth.recovery.passwordUpdated");
    } catch {
      setError({ lang, message: formMessage(lang, "resetPasswordFailed") });
    } finally {
      setLoading(false);
    }
  }

  return (
    <form
      className={styles.form}
      onSubmit={requested ? submitNewPassword : requestReset}
      noValidate
    >
      <div className={styles.welcome}>
        <h1 className={styles.loginTitle}>{uiText(lang, "auth.recovery.title")}</h1>
        <p className={styles.loginDescription}>
          {requested
            ? uiText(lang, "auth.recovery.newPasswordDescription")
            : uiText(lang, "auth.recovery.requestDescription")}
        </p>
      </div>

      {visibleError && (
        <div className={styles.formError} role="alert">
          <span className={styles.errorMark} aria-hidden="true">!</span>
          {visibleError}
        </div>
      )}
      {messageKey && (
        <div role="status" className={styles.loginDescription}>
          {uiText(lang, messageKey)}
        </div>
      )}

      {!complete && !requested && (
        <Input
          id="recovery-email"
          type="email"
          autoComplete="email"
          label={mainLabel("email", lang)}
          placeholder={uiText(lang, "auth.emailPlaceholder")}
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      )}

      {!complete && requested && (
        <div className={styles.fields}>
          {!tokenFromServer && (
            <Input
              id="reset-token"
              type="text"
              autoComplete="one-time-code"
              label={uiText(lang, "auth.recovery.resetToken")}
              placeholder={uiText(lang, "auth.recovery.tokenPlaceholder")}
              value={token}
              onChange={(event) => setToken(event.target.value)}
            />
          )}
          <Input
            id="new-password"
            type="password"
            autoComplete="new-password"
            label={uiText(lang, "auth.recovery.newPassword")}
            placeholder={uiText(lang, "auth.recovery.newPasswordPlaceholder")}
            showText={mainLabel("show", lang)}
            hideText={mainLabel("hide", lang)}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <Input
            id="confirm-new-password"
            type="password"
            autoComplete="new-password"
            label={uiText(lang, "auth.recovery.confirmNewPassword")}
            placeholder={uiText(lang, "auth.recovery.confirmNewPasswordPlaceholder")}
            showText={mainLabel("show", lang)}
            hideText={mainLabel("hide", lang)}
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
          />
        </div>
      )}

      {!complete && (
        <Button type="submit" size="lg" fullWidth loading={loading} className={styles.loginButton}>
          {requested
            ? uiText(lang, "auth.recovery.updatePassword")
            : uiText(lang, "auth.recovery.continue")}
        </Button>
      )}
      <p className={styles.footer}>
        <Link href="/login">{uiText(lang, "auth.recovery.backToLogin")}</Link>
      </p>
    </form>
  );
}
