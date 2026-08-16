"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import Button from "@/shared/ui/Button";
import Input from "@/shared/ui/Input";
import { listLanguages, register } from "@/shared/lib/api";
import { saveSession } from "@/shared/lib/auth-session";
import { mainLabel } from "@/shared/lib/i18n";
import {
  MIN_PASSWORD_LENGTH,
  MIN_USERNAME_LENGTH,
  formMessage,
  isValidUsername,
  suggestUsername,
} from "@/shared/lib/form-messages";
import LanguagePicker from "@/shared/ui/LanguagePicker";
import { useLanguage } from "./LanguageContext";
import styles from "./AuthForm.module.css";

const EMAIL_RE = /\S+@\S+\.\S+/;

type Strength = "weak" | "medium" | "strong";

const STRENGTH_TEXT: Record<Strength, string> = {
  weak: "Yếu",
  medium: "Trung bình",
  strong: "Mạnh",
};

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
  /* Ngôn ngữ lấy từ dải bên trái — nó chính là preferred_language, nên form
     không dựng thêm bảng chọn thứ hai. */
  const { lang, setLang } = useLanguage();
  // The allowlist belongs to the backend (CONTRACT section 1). It also supplies
  // the count in the headline, which was hardcoded as "Mười" and had been wrong
  // ever since a language was added.
  const [codes, setCodes] = useState<string[]>([]);

  useEffect(() => {
    let cancelled = false;
    listLanguages()
      .then((list) => !cancelled && setCodes(list))
      .catch(() => undefined);
    return () => { cancelled = true; };
  }, []);

  const [fullName, setFullName] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [agree, setAgree] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [errors, setErrors] = useState<Record<string, string | undefined>>({});

  const strength = getPasswordStrength(password);

  function validate(): boolean {
    const e: Record<string, string> = {};

    const normalizedFullName = fullName.trim();
    const normalizedUsername = username.trim();

    if (!normalizedFullName) e.fullName = formMessage(lang, "fullNameRequired");

    if (!normalizedUsername) {
      e.username = formMessage(lang, "usernameRequired");
    } else if (normalizedUsername.length < MIN_USERNAME_LENGTH) {
      e.username = formMessage(lang, "usernameTooShort", { n: MIN_USERNAME_LENGTH });
    } else if (!isValidUsername(normalizedUsername)) {
      // The rule first, then something they can actually type. A name with a
      // space is the ordinary case here, and the server's own message for it
      // arrives in English inside a 422 body.
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

    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleSubmit(ev: React.FormEvent) {
    ev.preventDefault();
    setError("");
    if (!validate()) return;

    setLoading(true);
    try {
      const result = await register({
        username: username.trim(),
        // The name people are called by, kept apart from the handle they sign
        // in with — one has spaces and diacritics, the other cannot.
        display_name: fullName.trim(),
        email,
        password,
        preferred_language: lang,
      });
      saveSession(result, true);
      window.location.href = "/chat";
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : formMessage(lang, "registerFailed"));
    } finally {
      setLoading(false);
    }
  }

  const clearError = (field: string) =>
    setErrors((p) => ({ ...p, [field]: undefined }));

  return (
    <form className={styles.form} onSubmit={handleSubmit} noValidate>
      <h1 className={styles.lede}>
        <span>Một tài khoản.</span>
        <span>{codes.length ? `${codes.length} ngôn ngữ` : "Nhiều ngôn ngữ"} đọc được.</span>
      </h1>

      <hr className={styles.divider} />

      {error && (
        <div className={styles.formError} role="alert">
          <span className={styles.errorMark} aria-hidden="true">
            !
          </span>
          {error}
        </div>
      )}

      <div className={styles.fields}>
        <Input
          id="register-full-name"
          autoComplete="name"
          placeholder="Nguyễn Văn An"
          label={mainLabel("fullName", lang)}
          value={fullName}
          required
          maxLength={100}
          onChange={(e) => {
            setFullName(e.target.value);
            clearError("fullName");
          }}
          onBlur={() => setFullName((value) => value.trim())}
          error={errors.fullName}
        />

        <Input
          id="register-username"
          autoComplete="username"
          placeholder="thuan"
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
          error={errors.username}
        />

        <Input
          id="register-email"
          type="email"
          autoComplete="email"
          placeholder="ban@vidu.com"
          label={mainLabel("email", lang)}
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            clearError("email");
          }}
          error={errors.email}
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
          error={errors.password}
        />

        {strength && (
          <div className={styles.strength}>
            <span className={styles.strengthTrack}>
              <span className={`${styles.strengthFill} ${styles[strength]}`} />
            </span>
            <span className={styles.strengthLabel}>
              {STRENGTH_TEXT[strength]}
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
          error={errors.confirmPassword}
        />
      </div>

      <div className={styles.languageField}>
        <label htmlFor="register-language">Ngôn ngữ</label>
        <LanguagePicker
          id="register-language"
          value={lang}
          onChange={(code) => setLang(code as typeof lang)}
          label="Ngôn ngữ bạn muốn đọc"
          codes={codes}
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
            aria-invalid={errors.agree ? true : undefined}
            aria-describedby={errors.agree ? "register-agree-error" : undefined}
          />
          <span>
            Tôi đồng ý với <Link href="/terms" target="_blank">{mainLabel("terms", lang)}</Link> và{" "}
            <Link href="/privacy" target="_blank">Chính sách riêng tư</Link>
          </span>
        </label>
        {errors.agree && (
          <p
            id="register-agree-error"
            className={styles.formError}
            role="alert"
          >
            <span className={styles.errorMark} aria-hidden="true">
              !
            </span>
            {errors.agree}
          </p>
        )}
      </div>

      <Button type="submit" size="lg" fullWidth loading={loading}>
        <span className={styles.actionMain}>Tạo tài khoản</span>
      </Button>

      <p className={styles.footer}>
        Đã có tài khoản? <Link href="/login">Đăng nhập</Link>
      </p>
    </form>
  );
}
