/**
 * Bảng nhãn song ngữ — nước đi ký tên của sản phẩm (docs/design.md §7).
 *
 * Nhãn biểu mẫu luôn lấy từ ngôn ngữ giao diện đang chọn.
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
 * Nhãn theo ngôn ngữ. Mọi mã backend hỗ trợ đều phải có đủ nhãn: người dùng đã
 * chọn một ngôn ngữ giao diện thì không nên thấy tiếng Anh như đường đi bình
 * thường. `Record` giữ cam kết này ở mức kiểu khi thêm mã hay nhãn mới.
 */
type LabelTable = Record<LanguageCode, Record<LabelKey, string>>;

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
  id: {
    fullName: "Nama lengkap",
    email: "Email",
    password: "Kata sandi",
    passwordConfirm: "Konfirmasi kata sandi",
    username: "Nama pengguna",
    signIn: "Masuk",
    createAccount: "Buat akun",
    language: "Bahasa Anda",
    show: "Tampilkan",
    hide: "Sembunyikan",
    remember: "Ingat perangkat ini",
    forgot: "Lupa kata sandi?",
    terms: "Ketentuan layanan",
  },
  pt: {
    fullName: "Nome completo",
    email: "E-mail",
    password: "Palavra-passe",
    passwordConfirm: "Confirmar palavra-passe",
    username: "Nome de utilizador",
    signIn: "Entrar",
    createAccount: "Criar conta",
    language: "O seu idioma",
    show: "Mostrar",
    hide: "Ocultar",
    remember: "Lembrar este dispositivo",
    forgot: "Esqueceu-se da palavra-passe?",
    terms: "Termos de serviço",
  },
  ru: {
    fullName: "Полное имя",
    email: "Электронная почта",
    password: "Пароль",
    passwordConfirm: "Подтвердите пароль",
    username: "Имя пользователя",
    signIn: "Войти",
    createAccount: "Создать аккаунт",
    language: "Ваш язык",
    show: "Показать",
    hide: "Скрыть",
    remember: "Запомнить это устройство",
    forgot: "Забыли пароль?",
    terms: "Условия обслуживания",
  },
  ar: {
    fullName: "الاسم الكامل",
    email: "البريد الإلكتروني",
    password: "كلمة المرور",
    passwordConfirm: "تأكيد كلمة المرور",
    username: "اسم المستخدم",
    signIn: "تسجيل الدخول",
    createAccount: "إنشاء حساب",
    language: "لغتك",
    show: "إظهار",
    hide: "إخفاء",
    remember: "تذكر هذا الجهاز",
    forgot: "هل نسيت كلمة المرور؟",
    terms: "شروط الخدمة",
  },
  hi: {
    fullName: "पूरा नाम",
    email: "ईमेल",
    password: "पासवर्ड",
    passwordConfirm: "पासवर्ड की पुष्टि करें",
    username: "उपयोगकर्ता नाम",
    signIn: "साइन इन",
    createAccount: "खाता बनाएँ",
    language: "आपकी भाषा",
    show: "दिखाएँ",
    hide: "छिपाएँ",
    remember: "इस डिवाइस को याद रखें",
    forgot: "पासवर्ड भूल गए?",
    terms: "सेवा की शर्तें",
  },
};

/**
 * Nhãn chính theo ngôn ngữ giao diện đang chọn. Bảng là tổng quát cho toàn bộ
 * allowlist, nên một `LanguageCode` hợp lệ luôn có nhãn tương ứng.
 */
export function mainLabel(key: LabelKey, lang: LanguageCode = UI_LANGUAGE): string {
  return LABELS[lang][key];
}

/**
 * Nhãn phụ ở ngôn ngữ đang chọn. Trả `null` khi ngôn ngữ đích trùng ngôn ngữ
 * giao diện — lúc đó nhãn phụ chỉ lặp lại nhãn chính.
 */
export function altLabel(lang: LanguageCode, key: LabelKey): string | null {
  if (lang === UI_LANGUAGE) return null;
  return LABELS[lang][key];
}
