"use client";

import React, { useState } from "react";
import Link from "next/link";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import { register } from "@/lib/api";
import { saveSession } from "@/lib/auth-session";
import { mainLabel } from "@/lib/i18n";
import { SUPPORTED_LANGUAGES } from "@/lib/constants";
import { useLanguage } from "./LanguageContext";
import styles from "./AuthForm.module.css";

const EMAIL_RE = /\S+@\S+\.\S+/;
const MIN_PASSWORD = 8;
const MIN_USERNAME = 3;

type Strength = "weak" | "medium" | "strong";

const STRENGTH_TEXT: Record<Strength, string> = {
  weak: "Yếu",
  medium: "Trung bình",
  strong: "Mạnh",
};

function getPasswordStrength(pw: string): Strength | null {
  if (!pw) return null;
  let score = 0;
  if (pw.length >= MIN_PASSWORD) score++;
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

    const normalizedUsername = username.trim();

    if (!normalizedUsername) {
      e.username = "Chưa nhập tên đăng nhập.";
    } else if (normalizedUsername.length < MIN_USERNAME) {
      e.username = `Còn thiếu ${MIN_USERNAME - normalizedUsername.length} ký tự.`;
    }

    if (!email) {
      e.email = "Chưa nhập email.";
    } else if (!EMAIL_RE.test(email)) {
      e.email = "Email này thiếu dấu @ hoặc phần tên miền.";
    }

    if (!password) {
      e.password = "Chưa nhập mật khẩu.";
    } else if (password.length < MIN_PASSWORD) {
      e.password = `Còn thiếu ${MIN_PASSWORD - password.length} ký tự.`;
    }

    if (!confirmPassword) {
      e.confirmPassword = "Chưa nhập lại mật khẩu.";
    } else if (password !== confirmPassword) {
      e.confirmPassword = "Hai lần nhập không khớp nhau.";
    }

    if (!agree) e.agree = "Cần đồng ý điều khoản để tạo tài khoản.";

    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleSubmit(ev: React.FormEvent) {
    ev.preventDefault();
    setError("");
    if (!validate()) return;

    setLoading(true);
    try {
      const registeredUsername = username.trim();
      const result = await register({
        username: registeredUsername,
        display_name: registeredUsername,
        email,
        password,
        preferred_language: lang,
      });
      saveSession(result, true);
      window.location.href = "/chat";
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Không tạo được tài khoản.");
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
        <span>Mười ngôn ngữ đọc được.</span>
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
          id="register-username"
          autoComplete="username"
          placeholder="thuan"
          label={mainLabel("username")}
          value={username}
          required
          minLength={MIN_USERNAME}
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
          label={mainLabel("email")}
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
          label={mainLabel("password")}
          showText={mainLabel("show")}
          hideText={mainLabel("hide")}
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
          label={mainLabel("passwordConfirm")}
          showText={mainLabel("show")}
          hideText={mainLabel("hide")}
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
        <select id="register-language" value={lang} onChange={(event) => setLang(event.target.value as typeof lang)}>
          {SUPPORTED_LANGUAGES.map((language) => <option key={language.code} value={language.code}>{language.name}</option>)}
        </select>
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
            Tôi đồng ý với <a href="#">{mainLabel("terms")}</a> và{" "}
            <a href="#">Chính sách riêng tư</a>
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
