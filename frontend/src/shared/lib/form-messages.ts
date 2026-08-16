/**
 * Câu thông báo của biểu mẫu, theo ngôn ngữ người dùng đang chọn.
 *
 * Tách khỏi `LABELS` trong `i18n.ts` vì hai bảng gánh hai nghĩa vụ khác nhau.
 * `LABELS` là nhãn cạnh ô nhập và được ghép đôi song ngữ; bảng này là những câu
 * chỉ xuất hiện khi có gì đó sai. Một câu báo lỗi người đọc không hiểu còn tệ
 * hơn không báo, nên nó phải theo ngôn ngữ đang chọn.
 *
 * Chỉ `en` là bắt buộc: `formMessage` lùi về đó cho **từng câu** còn thiếu,
 * đúng quy tắc ở docs/CONTRACT.md §1.2 — thiếu một câu tiếng Thái thì chỉ câu
 * đó ra tiếng Anh, phần còn lại vẫn là tiếng Thái. Năm mã chưa có bảng
 * (id, pt, ru, ar, hi) vì thế vẫn chạy được; dịch nốt là việc của vòng i18n
 * toàn giao diện.
 *
 * CHƯA QUA SOÁT BẢN NGỮ, cùng cảnh báo như `i18n.ts`.
 */

import type { LanguageCode } from "./constants";

export type FormMessageKey =
  | "fullNameRequired"
  | "usernameRequired"
  | "usernameTooShort"
  | "usernameCharset"
  | "example"
  | "emailRequired"
  | "emailInvalid"
  | "passwordRequired"
  | "passwordTooShort"
  | "confirmRequired"
  | "confirmMismatch"
  | "agreeRequired"
  | "registerFailed";

type FormMessageTable = Partial<Record<LanguageCode, Record<FormMessageKey, string>>> & {
  en: Record<FormMessageKey, string>;
};

export const FORM_MESSAGES: FormMessageTable = {
  vi: {
    fullNameRequired: "Chưa nhập họ và tên.",
    usernameRequired: "Chưa nhập tên đăng nhập.",
    usernameTooShort: "Tên đăng nhập cần ít nhất {n} ký tự.",
    usernameCharset: "Tên đăng nhập chỉ gồm chữ, số, dấu gạch ngang và gạch dưới — không có dấu cách.",
    example: "Ví dụ: {s}",
    emailRequired: "Chưa nhập email.",
    emailInvalid: "Email này thiếu dấu @ hoặc phần tên miền.",
    passwordRequired: "Chưa nhập mật khẩu.",
    passwordTooShort: "Mật khẩu cần ít nhất {n} ký tự.",
    confirmRequired: "Chưa nhập lại mật khẩu.",
    confirmMismatch: "Hai lần nhập không khớp nhau.",
    agreeRequired: "Cần đồng ý điều khoản để tạo tài khoản.",
    registerFailed: "Không tạo được tài khoản.",
  },
  en: {
    fullNameRequired: "Enter your full name.",
    usernameRequired: "Enter a username.",
    usernameTooShort: "A username needs at least {n} characters.",
    usernameCharset: "A username may only contain letters, numbers, hyphens and underscores — no spaces.",
    example: "For example: {s}",
    emailRequired: "Enter your email.",
    emailInvalid: "This email is missing the @ sign or the domain.",
    passwordRequired: "Enter a password.",
    passwordTooShort: "A password needs at least {n} characters.",
    confirmRequired: "Repeat your password.",
    confirmMismatch: "The two entries do not match.",
    agreeRequired: "Accept the terms to create an account.",
    registerFailed: "The account could not be created.",
  },
  zh: {
    fullNameRequired: "请填写姓名。",
    usernameRequired: "请填写用户名。",
    usernameTooShort: "用户名至少需要 {n} 个字符。",
    usernameCharset: "用户名只能包含字母、数字、连字符和下划线，不能有空格。",
    example: "例如：{s}",
    emailRequired: "请填写邮箱。",
    emailInvalid: "该邮箱缺少 @ 或域名部分。",
    passwordRequired: "请填写密码。",
    passwordTooShort: "密码至少需要 {n} 个字符。",
    confirmRequired: "请再次输入密码。",
    confirmMismatch: "两次输入不一致。",
    agreeRequired: "需同意条款才能创建账户。",
    registerFailed: "无法创建账户。",
  },
  ja: {
    fullNameRequired: "氏名を入力してください。",
    usernameRequired: "ユーザー名を入力してください。",
    usernameTooShort: "ユーザー名は {n} 文字以上必要です。",
    usernameCharset: "ユーザー名に使えるのは文字、数字、ハイフン、アンダースコアだけです。スペースは使えません。",
    example: "例: {s}",
    emailRequired: "メールアドレスを入力してください。",
    emailInvalid: "このメールアドレスには @ かドメインがありません。",
    passwordRequired: "パスワードを入力してください。",
    passwordTooShort: "パスワードは {n} 文字以上必要です。",
    confirmRequired: "パスワードをもう一度入力してください。",
    confirmMismatch: "入力した二つが一致しません。",
    agreeRequired: "アカウント作成には規約への同意が必要です。",
    registerFailed: "アカウントを作成できませんでした。",
  },
  ko: {
    fullNameRequired: "이름을 입력하세요.",
    usernameRequired: "아이디를 입력하세요.",
    usernameTooShort: "아이디는 {n}자 이상이어야 합니다.",
    usernameCharset: "아이디에는 문자, 숫자, 하이픈, 밑줄만 쓸 수 있습니다. 공백은 안 됩니다.",
    example: "예: {s}",
    emailRequired: "이메일을 입력하세요.",
    emailInvalid: "이 이메일에는 @ 또는 도메인이 없습니다.",
    passwordRequired: "비밀번호를 입력하세요.",
    passwordTooShort: "비밀번호는 {n}자 이상이어야 합니다.",
    confirmRequired: "비밀번호를 다시 입력하세요.",
    confirmMismatch: "두 번 입력한 값이 다릅니다.",
    agreeRequired: "계정을 만들려면 약관에 동의해야 합니다.",
    registerFailed: "계정을 만들지 못했습니다.",
  },
  fr: {
    fullNameRequired: "Saisissez votre nom complet.",
    usernameRequired: "Saisissez un nom d’utilisateur.",
    usernameTooShort: "Un nom d’utilisateur doit compter au moins {n} caractères.",
    usernameCharset: "Un nom d’utilisateur ne peut contenir que des lettres, des chiffres, des tirets et des traits de soulignement — sans espace.",
    example: "Par exemple : {s}",
    emailRequired: "Saisissez votre e-mail.",
    emailInvalid: "Cet e-mail n’a pas de @ ou de domaine.",
    passwordRequired: "Saisissez un mot de passe.",
    passwordTooShort: "Un mot de passe doit compter au moins {n} caractères.",
    confirmRequired: "Saisissez à nouveau le mot de passe.",
    confirmMismatch: "Les deux saisies ne correspondent pas.",
    agreeRequired: "Acceptez les conditions pour créer un compte.",
    registerFailed: "Impossible de créer le compte.",
  },
  de: {
    fullNameRequired: "Geben Sie Ihren vollständigen Namen ein.",
    usernameRequired: "Geben Sie einen Benutzernamen ein.",
    usernameTooShort: "Ein Benutzername braucht mindestens {n} Zeichen.",
    usernameCharset: "Ein Benutzername darf nur Buchstaben, Ziffern, Bindestriche und Unterstriche enthalten — keine Leerzeichen.",
    example: "Zum Beispiel: {s}",
    emailRequired: "Geben Sie Ihre E-Mail-Adresse ein.",
    emailInvalid: "Dieser E-Mail-Adresse fehlt das @ oder die Domain.",
    passwordRequired: "Geben Sie ein Passwort ein.",
    passwordTooShort: "Ein Passwort braucht mindestens {n} Zeichen.",
    confirmRequired: "Geben Sie das Passwort erneut ein.",
    confirmMismatch: "Die beiden Eingaben stimmen nicht überein.",
    agreeRequired: "Stimmen Sie den Bedingungen zu, um ein Konto zu erstellen.",
    registerFailed: "Das Konto konnte nicht erstellt werden.",
  },
  es: {
    fullNameRequired: "Escribe tu nombre completo.",
    usernameRequired: "Escribe un nombre de usuario.",
    usernameTooShort: "Un nombre de usuario necesita al menos {n} caracteres.",
    usernameCharset: "Un nombre de usuario solo puede llevar letras, números, guiones y guiones bajos — sin espacios.",
    example: "Por ejemplo: {s}",
    emailRequired: "Escribe tu correo.",
    emailInvalid: "A este correo le falta la @ o el dominio.",
    passwordRequired: "Escribe una contraseña.",
    passwordTooShort: "Una contraseña necesita al menos {n} caracteres.",
    confirmRequired: "Vuelve a escribir la contraseña.",
    confirmMismatch: "Las dos entradas no coinciden.",
    agreeRequired: "Acepta los términos para crear una cuenta.",
    registerFailed: "No se pudo crear la cuenta.",
  },
  th: {
    fullNameRequired: "กรุณากรอกชื่อ-นามสกุล",
    usernameRequired: "กรุณากรอกชื่อผู้ใช้",
    usernameTooShort: "ชื่อผู้ใช้ต้องมีอย่างน้อย {n} ตัวอักษร",
    usernameCharset: "ชื่อผู้ใช้ใช้ได้เฉพาะตัวอักษร ตัวเลข ขีดกลาง และขีดล่าง ห้ามมีช่องว่าง",
    example: "ตัวอย่าง: {s}",
    emailRequired: "กรุณากรอกอีเมล",
    emailInvalid: "อีเมลนี้ขาดเครื่องหมาย @ หรือส่วนโดเมน",
    passwordRequired: "กรุณากรอกรหัสผ่าน",
    passwordTooShort: "รหัสผ่านต้องมีอย่างน้อย {n} ตัวอักษร",
    confirmRequired: "กรุณากรอกรหัสผ่านอีกครั้ง",
    confirmMismatch: "ทั้งสองครั้งไม่ตรงกัน",
    agreeRequired: "ต้องยอมรับข้อกำหนดจึงจะสร้างบัญชีได้",
    registerFailed: "สร้างบัญชีไม่สำเร็จ",
  },
};

/** A message in the chosen language, with `{n}` and `{s}` filled in. */
export function formMessage(
  lang: LanguageCode,
  key: FormMessageKey,
  values?: { n?: number; s?: string },
): string {
  const template = FORM_MESSAGES[lang]?.[key] ?? FORM_MESSAGES.en[key];
  return template
    .replace("{n}", String(values?.n ?? ""))
    .replace("{s}", values?.s ?? "");
}

/**
 * Số ký tự tối thiểu, giữ đúng ràng buộc server ở `src/schemas/auth.py`.
 *
 * Để cạnh nhau ở đây vì luật client mà lỏng hơn server thì người dùng lãnh một
 * lỗi 422 bằng tiếng Anh — đúng thứ đang xảy ra trước khi có tệp này.
 */
export const MIN_USERNAME_LENGTH = 3;
export const MIN_PASSWORD_LENGTH = 8;

/**
 * Tên đăng nhập có hợp lệ không, soi gương đúng validator của server.
 *
 * Server dùng `value.replace("_","").replace("-","").isalnum()` của Python, mà
 * `isalnum()` **chấp nhận chữ có dấu và chữ Hán/Nhật/Hàn** — "nguyễn" hợp lệ,
 * "Nguyen An" thì không vì có dấu cách. Vì vậy luật ở đây dùng `\p{L}` và
 * `\p{N}` chứ không phải `[a-z0-9]`: chặt hơn server sẽ từ chối những cái tên
 * mà server sẵn sàng nhận, và người Việt là nhóm chịu thiệt đầu tiên.
 */
export function isValidUsername(value: string): boolean {
  const withoutSeparators = value.replaceAll("_", "").replaceAll("-", "");
  return withoutSeparators.length > 0 && /^[\p{L}\p{N}]+$/u.test(withoutSeparators);
}

/**
 * Gợi ý một tên đăng nhập hợp lệ dựng từ thứ người dùng vừa gõ.
 *
 * Gợi ý chứ không tự sửa: đổi ngầm tên đăng nhập của một người là thứ họ chỉ
 * phát hiện ra vào lần đăng nhập sau.
 */
export function suggestUsername(value: string): string {
  const suggestion = value
    .trim()
    .toLocaleLowerCase()
    .replace(/\s+/gu, "-")
    .replace(/[^\p{L}\p{N}_-]/gu, "")
    .replace(/-{2,}/gu, "-")
    .replace(/^-+|-+$/gu, "");
  return suggestion.slice(0, 50);
}
