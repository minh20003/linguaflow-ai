"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import { requestPasswordReset, resetPassword } from "@/lib/api";
import styles from "./AuthForm.module.css";

export default function PasswordRecoveryForm() {
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [complete, setComplete] = useState(false);

  async function requestReset(event: FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await requestPasswordReset(email);
      setMessage("Yêu cầu đã được tiếp nhận. Trong môi trường local, bạn có thể đặt mật khẩu mới ngay bên dưới.");
      if (result.reset_token) setToken(result.reset_token);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể gửi yêu cầu.");
    } finally { setLoading(false); }
  }

  async function submitNewPassword(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (password.length < 8) return setError("Mật khẩu cần có ít nhất 8 ký tự.");
    if (password !== confirmPassword) return setError("Hai mật khẩu chưa khớp.");
    setLoading(true);
    try {
      await resetPassword(token, password);
      setComplete(true);
      setMessage("Mật khẩu đã được cập nhật. Các phiên đăng nhập cũ đã được đăng xuất.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể đặt lại mật khẩu.");
    } finally { setLoading(false); }
  }

  return <form className={styles.form} onSubmit={token ? submitNewPassword : requestReset} noValidate>
    <div className={styles.welcome}><h1 className={styles.loginTitle}>Khôi phục tài khoản</h1><p className={styles.loginDescription}>{token ? "Tạo mật khẩu mới cho tài khoản của bạn." : "Nhập email đã đăng ký để đặt lại mật khẩu."}</p></div>
    {error && <div className={styles.formError} role="alert"><span className={styles.errorMark}>!</span>{error}</div>}
    {message && <div role="status" className={styles.loginDescription}>{message}</div>}
    {!complete && !token && <Input id="recovery-email" type="email" autoComplete="email" label="Email" placeholder="ban@vidu.com" value={email} onChange={(event) => setEmail(event.target.value)} />}
    {!complete && token && <div className={styles.fields}><Input id="new-password" type="password" autoComplete="new-password" label="Mật khẩu mới" placeholder="Ít nhất 8 ký tự" value={password} onChange={(event) => setPassword(event.target.value)} /><Input id="confirm-new-password" type="password" autoComplete="new-password" label="Nhập lại mật khẩu" placeholder="Nhập lại mật khẩu mới" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} /></div>}
    {!complete && <Button type="submit" size="lg" fullWidth loading={loading} className={styles.loginButton}>{token ? "Cập nhật mật khẩu" : "Tiếp tục"}</Button>}
    <p className={styles.footer}><Link href="/login">Quay lại đăng nhập</Link></p>
  </form>;
}
