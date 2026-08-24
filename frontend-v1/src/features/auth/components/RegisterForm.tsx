"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Button from "@/shared/ui/Button";
import Input from "@/shared/ui/Input";
import { register, resendRegisterOtp, verifyRegisterOtp } from "@/shared/lib/api";
import { saveSession } from "@/shared/lib/auth-session";
import { SUPPORTED_LANGUAGES, type LanguageCode } from "@/shared/lib/constants";
import { mainLabel } from "@/shared/lib/i18n";
import { formatUiText, uiText } from "@/shared/lib/ui-text";
import {
  MIN_PASSWORD_LENGTH,
  MIN_USERNAME_LENGTH,
  formMessage,
  isValidUsername,
  suggestUsername,
} from "@/shared/lib/form-messages";
import { useDocumentMetadata } from "@/shared/lib/use-ui-text";
import { useLanguage } from "./LanguageContext";
import styles from "./AuthForm.module.css";

const EMAIL_RE = /\S+@\S+\.\S+/;

type Strength = "weak" | "medium" | "strong";
type ErrorState = { lang: LanguageCode; message: string };
type FieldErrors = Record<string, string | undefined>;
type FieldErrorState = { lang: LanguageCode; fields: FieldErrors };

function getPasswordStrength(pw: string): Strength | null {
  if (!pw) return null;
  let score = 0;
  if (pw.length >= MIN_PASSWORD_LENGTH) score++;
  if (pw.length >= 12) score++;
  if (/[A-Z]/.test(pw)) score++;
  if (/[0-9]/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;
  if (score <= 2) return "weak";
  if (score <= 3) return "medium";
  return "strong";
}

export default function RegisterForm() {
  const router = useRouter();
  useDocumentMetadata("meta.title.register", "meta.desc.register");
  /* The shared AuthCardHead picker controls the interface. Registration uses
     that one first-run selection to initialize the separate reading preference,
     so this form deliberately has no second language control. */
  const { lang } = useLanguage();

  const [step, setStep] = useState<"form" | "otp">("form");
  const [pendingId, setPendingId] = useState("");
  const [registeredEmail, setRegisteredEmail] = useState("");
  const [cooldownSeconds, setCooldownSeconds] = useState(60);
  const [otp, setOtp] = useState("");
  const [resending, setResending] = useState(false);
  const [successNotice, setSuccessNotice] = useState<string | null>(null);

  const [fullName, setFullName] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [agree, setAgree] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ErrorState | null>(null);
  const [errors, setErrors] = useState<FieldErrorState | null>(null);
  const visibleError = error?.lang === lang ? error.message : "";
  const visibleErrors = errors?.lang === lang ? errors.fields : {};

  const strength = getPasswordStrength(password);

  useEffect(() => {
    if (step !== "otp" || cooldownSeconds <= 0) return;
    const timer = setInterval(() => {
      setCooldownSeconds((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [step, cooldownSeconds]);

  function validate(): boolean {
    const e: FieldErrors = {};

    const normalizedFullName = fullName.trim();
    const normalizedUsername = username.trim();

    if (!normalizedFullName) e.fullName = formMessage(lang, "fullNameRequired");

    if (!normalizedUsername) {
      e.username = formMessage(lang, "usernameRequired");
    } else if (normalizedUsername.length < MIN_USERNAME_LENGTH) {
      e.username = formMessage(lang, "usernameTooShort", { n: MIN_USERNAME_LENGTH });
    } else if (!isValidUsername(normalizedUsername)) {
      const suggestion = suggestUsername(normalizedUsername) || suggestUsername(normalizedFullName);
      e.username = suggestion
        ? `${formMessage(lang, "usernameCharset")} ${formMessage(lang, "example", { s: suggestion })}`
        : formMessage(lang, "usernameCharset");
    }

    if (!email) {
      e.email = formMessage(lang, "emailRequired");
    } else if (!EMAIL_RE.test(email)) {
      e.email = formMessage(lang, "emailInvalid");
    }

    if (!password) {
      e.password = formMessage(lang, "passwordRequired");
    } else if (password.length < MIN_PASSWORD_LENGTH) {
      e.password = formMessage(lang, "passwordTooShort", { n: MIN_PASSWORD_LENGTH });
    }

    if (!confirmPassword) {
      e.confirmPassword = formMessage(lang, "confirmRequired");
    } else if (password !== confirmPassword) {
      e.confirmPassword = formMessage(lang, "confirmMismatch");
    }

    if (!agree) e.agree = formMessage(lang, "agreeRequired");

    setErrors({ lang, fields: e });
    return Object.keys(e).length === 0;
  }

  async function handleRegisterSubmit(ev: React.FormEvent) {
    ev.preventDefault();
    setError(null);
    setSuccessNotice(null);
    if (!validate()) return;

    setLoading(true);
    try {
      const result = await register({
        username: username.trim(),
        display_name: fullName.trim(),
        email: email.trim(),
        password,
        preferred_language: lang,
      });
      setPendingId(result.pending_id);
      setRegisteredEmail(result.email || email.trim());
      setPassword("");
      setConfirmPassword("");
      setCooldownSeconds(result.cooldown_seconds || 60);
      setOtp("");
      setStep("otp");
    } catch (err) {
      const code = (err as Error)?.message;
      if (code === "duplicate_account") {
        setError({ lang, message: formMessage(lang, "duplicateAccount") });
      } else if (code === "rate_limit_exceeded") {
        setError({ lang, message: formMessage(lang, "otpRateLimit") });
      } else if (code === "email_delivery_failed") {
        setError({ lang, message: formMessage(lang, "emailDeliveryFailed") });
      } else {
        setError({ lang, message: formMessage(lang, "registerFailed") });
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleVerifySubmit(ev: React.FormEvent) {
    ev.preventDefault();
    setError(null);
    setSuccessNotice(null);
    const cleanOtp = otp.trim();
    if (!cleanOtp) {
      setError({ lang, message: formMessage(lang, "otpRequired") });
      return;
    }
    if (!/^\d{6}$/.test(cleanOtp)) {
      setError({ lang, message: formMessage(lang, "otpInvalidFormat") });
      return;
    }

    setLoading(true);
    try {
      const result = await verifyRegisterOtp(pendingId, cleanOtp);
      saveSession(result, true);
      router.push("/chat");
    } catch (err) {
      const code = (err as Error)?.message;
      if (code === "otp_expired") {
        setError({ lang, message: formMessage(lang, "otpExpired") });
      } else if (code === "otp_max_attempts") {
        setError({ lang, message: formMessage(lang, "otpMaxAttempts") });
      } else if (code === "otp_invalid") {
        setError({ lang, message: formMessage(lang, "otpInvalid") });
      } else if (code === "duplicate_account") {
        setError({ lang, message: formMessage(lang, "duplicateAccount") });
      } else {
        setError({ lang, message: formMessage(lang, "registerFailed") });
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleResend() {
    if (cooldownSeconds > 0 || resending) return;
    setResending(true);
    setError(null);
    setSuccessNotice(null);
    try {
      const res = await resendRegisterOtp(pendingId);
      setCooldownSeconds(res.cooldown_seconds || 60);
      setOtp("");
      setSuccessNotice(uiText(lang, "auth.otp.resent"));
    } catch (err) {
      const code = (err as Error)?.message;
      if (code === "rate_limit_exceeded") {
        setError({ lang, message: formMessage(lang, "otpRateLimit") });
      } else if (code === "email_delivery_failed") {
        setError({ lang, message: formMessage(lang, "emailDeliveryFailed") });
      } else {
        setError({ lang, message: formMessage(lang, "registerFailed") });
      }
    } finally {
      setResending(false);
    }
  }

  const clearError = (field: string) =>
    setErrors((previous) => previous?.lang === lang
      ? { ...previous, fields: { ...previous.fields, [field]: undefined } }
      : previous);

  if (step === "otp") {
    return (
      <form className={styles.form} onSubmit={handleVerifySubmit} noValidate>
        <div className={styles.welcome}>
          <h1 className={styles.loginTitle}>{uiText(lang, "auth.otp.title")}</h1>
          <p className={styles.loginDescription}>
            {formatUiText(lang, "auth.otp.description", { email: registeredEmail, minutes: 5 })}
          </p>
        </div>

        <hr className={styles.divider} />

        {visibleError && (
          <div className={styles.formError} role="alert">
            <span className={styles.errorMark} aria-hidden="true">
              !
            </span>
            {visibleError}
          </div>
        )}

        {successNotice && (
          <div style={{ color: "var(--success)", fontSize: "var(--fs-small)" }} role="status">
            {successNotice}
          </div>
        )}

        <div className={styles.fields}>
          <Input
            id="register-otp"
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            label={uiText(lang, "auth.otp.label")}
            placeholder="000000"
            value={otp}
            maxLength={6}
            onChange={(e) => {
              const digits = e.target.value.replace(/\D/g, "").slice(0, 6);
              setOtp(digits);
              setError(null);
            }}
          />
        </div>

        <Button type="submit" size="lg" fullWidth loading={loading} disabled={otp.length !== 6}>
          <span className={styles.actionMain}>{uiText(lang, "auth.otp.verify")}</span>
        </Button>

        <div className={styles.row}>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={handleResend}
            disabled={cooldownSeconds > 0 || resending}
            loading={resending}
          >
            {cooldownSeconds > 0
              ? formatUiText(lang, "auth.otp.resendWait", { s: cooldownSeconds })
              : uiText(lang, "auth.otp.resend")}
          </Button>
        </div>

        <p className={styles.footer}>
          {uiText(lang, "auth.alreadyHaveAccount")} <Link href="/login">{mainLabel("signIn", lang)}</Link>
        </p>
      </form>
    );
  }

  return (
    <form className={styles.form} onSubmit={handleRegisterSubmit} noValidate>
      <h1 className={styles.lede}>
        <span>{uiText(lang, "auth.register.oneAccount")}</span>
        <span>{formatUiText(lang, "auth.register.languagesReadable", { count: SUPPORTED_LANGUAGES.length })}</span>
      </h1>

      <hr className={styles.divider} />

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
          id="register-full-name"
          autoComplete="name"
          placeholder={uiText(lang, "auth.fullNamePlaceholder")}
          label={mainLabel("fullName", lang)}
          value={fullName}
          required
          maxLength={100}
          onChange={(e) => {
            setFullName(e.target.value);
            clearError("fullName");
          }}
          onBlur={() => setFullName((value) => value.trim())}
          error={visibleErrors.fullName}
        />

        <Input
          id="register-username"
          autoComplete="username"
          placeholder={uiText(lang, "auth.usernamePlaceholder")}
          label={mainLabel("username", lang)}
          value={username}
          required
          minLength={MIN_USERNAME_LENGTH}
          maxLength={50}
          onChange={(e) => {
            setUsername(e.target.value);
            clearError("username");
          }}
          onBlur={() => setUsername((value) => value.trim())}
          error={visibleErrors.username}
        />

        <Input
          id="register-email"
          type="email"
          autoComplete="email"
          placeholder={uiText(lang, "auth.emailPlaceholder")}
          label={mainLabel("email", lang)}
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            clearError("email");
          }}
          error={visibleErrors.email}
        />

        <Input
          id="register-password"
          type="password"
          autoComplete="new-password"
          placeholder="••••••••••"
          label={mainLabel("password", lang)}
          showText={mainLabel("show", lang)}
          hideText={mainLabel("hide", lang)}
          value={password}
          onChange={(e) => {
            setPassword(e.target.value);
            clearError("password");
          }}
          error={visibleErrors.password}
        />

        {strength && (
          <div className={styles.strength}>
            <span className={styles.strengthTrack}>
              <span className={`${styles.strengthFill} ${styles[strength]}`} />
            </span>
            <span className={styles.strengthLabel}>
              {uiText(lang, `auth.strength.${strength}`)}
            </span>
          </div>
        )}

        <Input
          id="register-confirm"
          type="password"
          autoComplete="new-password"
          placeholder="••••••••••"
          label={mainLabel("passwordConfirm", lang)}
          showText={mainLabel("show", lang)}
          hideText={mainLabel("hide", lang)}
          value={confirmPassword}
          onChange={(e) => {
            setConfirmPassword(e.target.value);
            clearError("confirmPassword");
          }}
          error={visibleErrors.confirmPassword}
        />
      </div>

      <div className={styles.termsBlock}>
        <label className={styles.terms}>
          <input
            type="checkbox"
            checked={agree}
            onChange={(e) => {
              setAgree(e.target.checked);
              clearError("agree");
            }}
            aria-invalid={visibleErrors.agree ? true : undefined}
            aria-describedby={visibleErrors.agree ? "register-agree-error" : undefined}
          />
          <span>
            {uiText(lang, "auth.agreePrefix")}{" "}
            <Link href="/terms" target="_blank">{mainLabel("terms", lang)}</Link>{" "}
            {uiText(lang, "auth.and")}{" "}
            <Link href="/privacy" target="_blank">{uiText(lang, "auth.privacyPolicy")}</Link>
          </span>
        </label>
        {visibleErrors.agree && (
          <p
            id="register-agree-error"
            className={styles.formError}
            role="alert"
          >
            <span className={styles.errorMark} aria-hidden="true">
              !
            </span>
            {visibleErrors.agree}
          </p>
        )}
      </div>

      <Button type="submit" size="lg" fullWidth loading={loading}>
        <span className={styles.actionMain}>{mainLabel("createAccount", lang)}</span>
      </Button>

      <p className={styles.footer}>
        {uiText(lang, "auth.alreadyHaveAccount")} <Link href="/login">{mainLabel("signIn", lang)}</Link>
      </p>
    </form>
  );
}
