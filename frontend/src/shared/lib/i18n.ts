/**
 * Bảng nhãn song ngữ — nước đi ký tên của sản phẩm (docs/design.md §7).
 *
 * Nhãn chính trên form luôn lấy từ `LABELS.vi`; nhãn phụ lấy từ ngôn ngữ đang
 * chọn. Trang đăng nhập vì thế chứng minh việc sản phẩm làm trước khi người
 * dùng phải tin.
 *
 * CHƯA QUA SOÁT BẢN NGỮ. Nhãn sai ở một sản phẩm dịch thuật là lỗi đắt hơn bình
 * thường — ưu tiên soát ja, ko, th.
 */

import { UI_LANGUAGE, type LanguageCode } from "./constants";

export type LabelKey =
  | "fullName"
  | "email"
  | "password"
  | "passwordConfirm"
  | "username"
  | "signIn"
  | "createAccount"
  | "language"
  | "show"
  | "hide"
  | "remember"
  | "forgot"
  | "terms";

/**
 * Nhãn theo ngôn ngữ. Không bắt buộc đủ mọi mã backend hỗ trợ: `altLabel` đã
 * lùi về tiếng Anh khi thiếu (§7.3), nên thêm một ngôn ngữ vào allowlist không
 * kéo theo nghĩa vụ dịch nhãn ngay. Riêng `vi` và `en` bắt buộc có — một là
 * ngôn ngữ giao diện, một là ngôn ngữ lùi về.
 */
type LabelTable = Partial<Record<LanguageCode, Record<LabelKey, string>>> & {
  vi: Record<LabelKey, string>;
  en: Record<LabelKey, string>;
};

export const LABELS: LabelTable = {
  vi: {
    fullName: "Họ và tên",
    email: "Email",
    password: "Mật khẩu",
    passwordConfirm: "Nhập lại mật khẩu",
    username: "Tên đăng nhập",
    signIn: "Đăng nhập",
    createAccount: "Tạo tài khoản",
    language: "Ngôn ngữ của bạn",
    show: "Hiện",
    hide: "Ẩn",
    remember: "Ghi nhớ tài khoản",
    forgot: "Quên mật khẩu?",
    terms: "Điều khoản dịch vụ",
  },
  en: {
    fullName: "Full name",
    email: "Email",
    password: "Password",
    passwordConfirm: "Confirm password",
    username: "Username",
    signIn: "Sign in",
    createAccount: "Create account",
    language: "Your language",
    show: "Show",
    hide: "Hide",
    remember: "Remember this device",
    forgot: "Forgot password?",
    terms: "Terms of service",
  },
  zh: {
    fullName: "姓名",
    email: "邮箱",
    password: "密码",
    passwordConfirm: "确认密码",
    username: "用户名",
    signIn: "登录",
    createAccount: "创建账户",
    language: "你的语言",
    show: "显示",
    hide: "隐藏",
    remember: "记住此设备",
    forgot: "忘记密码？",
    terms: "服务条款",
  },
  ja: {
    fullName: "氏名",
    email: "メール",
    password: "パスワード",
    passwordConfirm: "パスワードの確認",
    username: "ユーザー名",
    signIn: "ログイン",
    createAccount: "アカウント作成",
    language: "あなたの言語",
    show: "表示",
    hide: "非表示",
    remember: "この端末を記憶する",
    forgot: "パスワードをお忘れですか？",
    terms: "利用規約",
  },
  ko: {
    fullName: "이름",
    email: "이메일",
    password: "비밀번호",
    passwordConfirm: "비밀번호 확인",
    username: "사용자 이름",
    signIn: "로그인",
    createAccount: "계정 만들기",
    language: "사용 언어",
    show: "표시",
    hide: "숨기기",
    remember: "이 기기 기억하기",
    forgot: "비밀번호를 잊으셨나요?",
    terms: "이용약관",
  },
  fr: {
    fullName: "Nom complet",
    email: "E-mail",
    password: "Mot de passe",
    passwordConfirm: "Confirmer le mot de passe",
    username: "Nom d’utilisateur",
    signIn: "Se connecter",
    createAccount: "Créer un compte",
    language: "Votre langue",
    show: "Afficher",
    hide: "Masquer",
    remember: "Se souvenir de cet appareil",
    forgot: "Mot de passe oublié ?",
    terms: "Conditions d’utilisation",
  },
  de: {
    fullName: "Vollständiger Name",
    email: "E-Mail",
    password: "Passwort",
    passwordConfirm: "Passwort bestätigen",
    username: "Benutzername",
    signIn: "Anmelden",
    createAccount: "Konto erstellen",
    language: "Ihre Sprache",
    show: "Anzeigen",
    hide: "Verbergen",
    remember: "Dieses Gerät merken",
    forgot: "Passwort vergessen?",
    terms: "Nutzungsbedingungen",
  },
  es: {
    fullName: "Nombre completo",
    email: "Correo electrónico",
    password: "Contraseña",
    passwordConfirm: "Confirmar contraseña",
    username: "Nombre de usuario",
    signIn: "Iniciar sesión",
    createAccount: "Crear cuenta",
    language: "Tu idioma",
    show: "Mostrar",
    hide: "Ocultar",
    remember: "Recordar este dispositivo",
    forgot: "¿Olvidaste tu contraseña?",
    terms: "Términos del servicio",
  },
  th: {
    fullName: "ชื่อ-นามสกุล",
    email: "อีเมล",
    password: "รหัสผ่าน",
    passwordConfirm: "ยืนยันรหัสผ่าน",
    username: "ชื่อผู้ใช้",
    signIn: "เข้าสู่ระบบ",
    createAccount: "สร้างบัญชี",
    language: "ภาษาของคุณ",
    show: "แสดง",
    hide: "ซ่อน",
    remember: "จดจำอุปกรณ์นี้",
    forgot: "ลืมรหัสผ่าน?",
    terms: "ข้อกำหนดการให้บริการ",
  },
};

/**
 * Nhãn chính, theo ngôn ngữ giao diện đang chọn.
 *
 * Trước đây hàm này luôn trả tiếng Việt (`LABELS[UI_LANGUAGE]`), nên trang đăng
 * nhập và đăng ký hiện tiếng Việt kể cả khi người dùng vừa chọn 中文 ngay trên
 * chính trang đó. Nay nó nhận ngôn ngữ và lùi về `en` cho từng nhãn còn thiếu,
 * đúng quy tắc docs/CONTRACT.md §1.2.
 */
export function mainLabel(key: LabelKey, lang: LanguageCode = UI_LANGUAGE): string {
  return LABELS[lang]?.[key] ?? LABELS.en[key];
}

/**
 * Nhãn phụ ở ngôn ngữ đang chọn. Trả `null` khi ngôn ngữ đích trùng ngôn ngữ
 * giao diện — lúc đó nhãn phụ chỉ lặp lại nhãn chính. Thiếu ngôn ngữ thì lùi về
 * tiếng Anh, không để trống (§7.3).
 */
export function altLabel(lang: LanguageCode, key: LabelKey): string | null {
  if (lang === UI_LANGUAGE) return null;
  return LABELS[lang]?.[key] ?? LABELS.en[key];
}
