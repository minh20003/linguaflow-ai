/**
 * Câu thông báo của biểu mẫu, theo ngôn ngữ người dùng đang chọn.
 *
 * Tách khỏi `LABELS` trong `i18n.ts` vì hai bảng gánh hai nghĩa vụ khác nhau.
 * `LABELS` là nhãn cạnh ô nhập và được ghép đôi song ngữ; bảng này là những câu
 * chỉ xuất hiện khi có gì đó sai. Một câu báo lỗi người đọc không hiểu còn tệ
 * hơn không báo, nên nó phải theo ngôn ngữ đang chọn.
 *
 * Mọi mã backend hỗ trợ đều có đủ thông báo. Một người đã chọn ngôn ngữ giao
 * diện không nên nhận lỗi biểu mẫu bằng tiếng Anh như đường đi bình thường.
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
  | "registerFailed"
  | "loginFailed"
  | "resetTokenRequired"
  | "resetRequestFailed"
  | "resetPasswordFailed"
  | "otpRequired"
  | "otpInvalidFormat"
  | "otpInvalid"
  | "otpExpired"
  | "otpMaxAttempts"
  | "otpRateLimit"
  | "emailDeliveryFailed"
  | "duplicateAccount";

type FormMessageTable = Record<LanguageCode, Record<FormMessageKey, string>>;

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
    loginFailed: "Chưa thể đăng nhập. Vui lòng thử lại.",
    resetTokenRequired: "Nhập mã đặt lại bạn nhận được.",
    resetRequestFailed: "Không thể gửi yêu cầu đặt lại mật khẩu.",
    resetPasswordFailed: "Không thể đặt lại mật khẩu.",
    otpRequired: "Vui lòng nhập mã xác thực 6 chữ số.",
    otpInvalidFormat: "Mã xác thực phải gồm đúng 6 chữ số.",
    otpInvalid: "Mã xác thực không đúng. Vui lòng thử lại.",
    otpExpired: "Mã xác thực đã hết hạn. Vui lòng gửi lại mã mới.",
    otpMaxAttempts: "Đã nhập sai quá số lần cho phép. Vui lòng gửi lại mã mới.",
    otpRateLimit: "Yêu cầu quá nhiều lần. Vui lòng thử lại sau.",
    emailDeliveryFailed: "Không thể gửi email xác thực. Vui lòng thử lại sau.",
    duplicateAccount: "Email hoặc tên đăng nhập này đã được đăng ký.",
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
    loginFailed: "Could not sign in. Please try again.",
    resetTokenRequired: "Enter the reset code you received.",
    resetRequestFailed: "Could not send the password reset request.",
    resetPasswordFailed: "Could not reset the password.",
    otpRequired: "Enter the 6-digit verification code.",
    otpInvalidFormat: "Verification code must be exactly 6 digits.",
    otpInvalid: "Invalid verification code. Please try again.",
    otpExpired: "Verification code has expired. Please request a new code.",
    otpMaxAttempts: "Maximum attempts exceeded. Please request a new code.",
    otpRateLimit: "Too many requests. Please try again later.",
    emailDeliveryFailed: "Could not send the verification email. Please try again later.",
    duplicateAccount: "This email or username is already registered.",
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
    loginFailed: "暂时无法登录，请重试。",
    resetTokenRequired: "请输入您收到的重置代码。",
    resetRequestFailed: "无法发送重置密码请求。",
    resetPasswordFailed: "无法重置密码。",
    otpRequired: "请输入 6 位验证码。",
    otpInvalidFormat: "验证码必须为 6 位数字。",
    otpInvalid: "验证码不正确，请重试。",
    otpExpired: "验证码已过期，请重新获取。",
    otpMaxAttempts: "超出最大尝试次数，请重新获取验证码。",
    otpRateLimit: "请求过于频繁，请稍后重试。",
    emailDeliveryFailed: "无法发送验证邮件，请稍后再试。",
    duplicateAccount: "该邮箱或用户名已被注册。",
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
    loginFailed: "ログインできませんでした。もう一度お試しください。",
    resetTokenRequired: "受け取ったリセットコードを入力してください。",
    resetRequestFailed: "パスワード再設定のリクエストを送信できませんでした。",
    resetPasswordFailed: "パスワードを再設定できませんでした。",
    otpRequired: "6桁の認証コードを入力してください。",
    otpInvalidFormat: "認証コードは6桁の数字である必要があります。",
    otpInvalid: "認証コードが無効です。もう一度お試しください。",
    otpExpired: "認証コードの有効期限が切れました。再取得してください。",
    otpMaxAttempts: "試行回数の上限に達しました。新しいコードをリクエストしてください。",
    otpRateLimit: "リクエストが多すぎます。しばらくしてから再試行してください。",
    emailDeliveryFailed: "確認メールを送信できませんでした。しばらくしてからもう一度お試しください。",
    duplicateAccount: "このメールアドレスまたはユーザー名は既に登録されています。",
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
    loginFailed: "로그인할 수 없습니다. 다시 시도해 주세요.",
    resetTokenRequired: "받은 재설정 코드를 입력해 주세요.",
    resetRequestFailed: "비밀번호 재설정 요청을 보낼 수 없습니다.",
    resetPasswordFailed: "비밀번호를 재설정할 수 없습니다.",
    otpRequired: "6자리 인증 코드를 입력하세요.",
    otpInvalidFormat: "인증 코드는 6자리 숫자여야 합니다.",
    otpInvalid: "잘못된 인증 코드입니다. 다시 시도해 주세요.",
    otpExpired: "인증 코드가 만료되었습니다. 새 코드를 요청하세요.",
    otpMaxAttempts: "최대 시도 횟수를 초과했습니다. 새 코드를 요청하세요.",
    otpRateLimit: "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
    emailDeliveryFailed: "인증 이메일을 보낼 수 없습니다. 나중에 다시 시도해 주세요.",
    duplicateAccount: "이미 등록된 이메일 또는 아이디입니다.",
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
    loginFailed: "Impossible de vous connecter. Veuillez réessayer.",
    resetTokenRequired: "Saisissez le code de réinitialisation reçu.",
    resetRequestFailed: "Impossible d’envoyer la demande de réinitialisation du mot de passe.",
    resetPasswordFailed: "Impossible de réinitialiser le mot de passe.",
    otpRequired: "Saisissez le code de vérification à 6 chiffres.",
    otpInvalidFormat: "Le code de vérification doit comporter 6 chiffres.",
    otpInvalid: "Code de vérification non valide. Veuillez réessayer.",
    otpExpired: "Le code de vérification a expiré. Veuillez en demander un nouveau.",
    otpMaxAttempts: "Nombre maximal de tentatives dépassé. Veuillez demander un nouveau code.",
    otpRateLimit: "Trop de requêtes. Veuillez réessayer plus tard.",
    emailDeliveryFailed: "Impossible d'envoyer l'e-mail de vérification. Veuillez réessayer plus tard.",
    duplicateAccount: "Cet e-mail ou ce nom d'utilisateur est déjà enregistré.",
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
    loginFailed: "Anmeldung nicht möglich. Bitte versuchen Sie es erneut.",
    resetTokenRequired: "Geben Sie den erhaltenen Zurücksetzungscode ein.",
    resetRequestFailed: "Die Anfrage zum Zurücksetzen des Passworts konnte nicht gesendet werden.",
    resetPasswordFailed: "Das Passwort konnte nicht zurückgesetzt werden.",
    otpRequired: "Geben Sie den 6-stelligen Bestätigungscode ein.",
    otpInvalidFormat: "Der Bestätigungscode muss genau 6 Ziffern lang sein.",
    otpInvalid: "Ungültiger Bestätigungscode. Bitte versuchen Sie es erneut.",
    otpExpired: "Der Bestätigungscode ist abgelaufen. Bitte fordern Sie einen neuen an.",
    otpMaxAttempts: "Maximale Anzahl an Versuchen überschritten. Bitte fordern Sie einen neuen Code an.",
    otpRateLimit: "Zu viele Anfragen. Bitte versuchen Sie es später erneut.",
    emailDeliveryFailed: "Die Bestätigungs-E-Mail konnte nicht gesendet werden. Bitte versuchen Sie es später erneut.",
    duplicateAccount: "Diese E-Mail-Adresse oder dieser Benutzername ist bereits registriert.",
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
    loginFailed: "No se pudo iniciar sesión. Inténtalo de nuevo.",
    resetTokenRequired: "Introduce el código de restablecimiento que recibiste.",
    resetRequestFailed: "No se pudo enviar la solicitud de restablecimiento de contraseña.",
    resetPasswordFailed: "No se pudo restablecer la contraseña.",
    otpRequired: "Introduce el código de verificación de 6 dígitos.",
    otpInvalidFormat: "El código de verificación debe tener 6 dígitos.",
    otpInvalid: "Código de verificación no válido. Inténtalo de nuevo.",
    otpExpired: "El código de verificación ha caducado. Solicita uno nuevo.",
    otpMaxAttempts: "Has superado el límite de intentos. Solicita un código nuevo.",
    otpRateLimit: "Demasiadas solicitudes. Inténtalo de nuevo más tarde.",
    emailDeliveryFailed: "No se pudo enviar el correo de verificación. Inténtelo más tarde.",
    duplicateAccount: "Este correo o nombre de usuario ya está registrado.",
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
    loginFailed: "ไม่สามารถเข้าสู่ระบบได้ โปรดลองอีกครั้ง",
    resetTokenRequired: "กรอกรหัสรีเซ็ตที่คุณได้รับ",
    resetRequestFailed: "ไม่สามารถส่งคำขอรีเซ็ตรหัสผ่านได้",
    resetPasswordFailed: "ไม่สามารถรีเซ็ตรหัสผ่านได้",
    otpRequired: "กรุณากรอกรหัสยืนยัน 6 หลัก",
    otpInvalidFormat: "รหัสยืนยันต้องเป็นตัวเลข 6 หลัก",
    otpInvalid: "รหัสยืนยันไม่ถูกต้อง โปรดลองอีกครั้ง",
    otpExpired: "รหัสยืนยันหมดอายุแล้ว โปรดขอรหัสใหม่",
    otpMaxAttempts: "ป้อนรหัสผิดเกินจำนวนครั้งที่กำหนด โปรดขอรหัสใหม่",
    otpRateLimit: "มีคำขอมากเกินไป โปรดลองอีกครั้งในภายหลัง",
    emailDeliveryFailed: "ไม่สามารถส่งอีเมลยืนยันได้ โปรดลองอีกครั้งในภายหลัง",
    duplicateAccount: "อีเมลหรือชื่อผู้ใช้นี้ถูกลงทะเบียนแล้ว",
  },
  id: {
    fullNameRequired: "Masukkan nama lengkap Anda.",
    usernameRequired: "Masukkan nama pengguna.",
    usernameTooShort: "Nama pengguna harus memiliki setidaknya {n} karakter.",
    usernameCharset: "Nama pengguna hanya boleh berisi huruf, angka, tanda hubung, dan garis bawah — tanpa spasi.",
    example: "Contoh: {s}",
    emailRequired: "Masukkan email Anda.",
    emailInvalid: "Email ini tidak memiliki tanda @ atau domain.",
    passwordRequired: "Masukkan kata sandi.",
    passwordTooShort: "Kata sandi harus memiliki setidaknya {n} karakter.",
    confirmRequired: "Ulangi kata sandi Anda.",
    confirmMismatch: "Kedua entri tidak cocok.",
    agreeRequired: "Setujui ketentuan untuk membuat akun.",
    registerFailed: "Akun tidak dapat dibuat.",
    loginFailed: "Tidak dapat masuk. Silakan coba lagi.",
    resetTokenRequired: "Masukkan kode pengaturan ulang yang Anda terima.",
    resetRequestFailed: "Tidak dapat mengirim permintaan pengaturan ulang kata sandi.",
    resetPasswordFailed: "Tidak dapat mengatur ulang kata sandi.",
    otpRequired: "Masukkan 6 digit kode verifikasi.",
    otpInvalidFormat: "Kode verifikasi harus berupa 6 digit angka.",
    otpInvalid: "Kode verifikasi tidak valid. Silakan coba lagi.",
    otpExpired: "Kode verifikasi telah kedaluwarsa. Silakan minta kode baru.",
    otpMaxAttempts: "Batas percobaan terlampaui. Silakan minta kode baru.",
    otpRateLimit: "Terlalu banyak permintaan. Silakan coba lagi nanti.",
    emailDeliveryFailed: "Tidak dapat mengirim email verifikasi. Silakan coba lagi nanti.",
    duplicateAccount: "Email atau nama pengguna ini sudah terdaftar.",
  },
  pt: {
    fullNameRequired: "Introduza o seu nome completo.",
    usernameRequired: "Introduza um nome de utilizador.",
    usernameTooShort: "Um nome de utilizador precisa de pelo menos {n} caracteres.",
    usernameCharset: "Um nome de utilizador só pode conter letras, números, hífenes e sublinhados — sem espaços.",
    example: "Por exemplo: {s}",
    emailRequired: "Introduza o seu e-mail.",
    emailInvalid: "Falta o @ ou o domínio neste e-mail.",
    passwordRequired: "Introduza uma palavra-passe.",
    passwordTooShort: "Uma palavra-passe precisa de pelo menos {n} caracteres.",
    confirmRequired: "Repita a sua palavra-passe.",
    confirmMismatch: "As duas entradas não coincidem.",
    agreeRequired: "Aceite os termos para criar uma conta.",
    registerFailed: "Não foi possível criar a conta.",
    loginFailed: "Não foi possível iniciar sessão. Tente novamente.",
    resetTokenRequired: "Introduza o código de reposição que recebeu.",
    resetRequestFailed: "Não foi possível enviar o pedido de reposição da palavra-passe.",
    resetPasswordFailed: "Não foi possível repor a palavra-passe.",
    otpRequired: "Introduza o código de verificação de 6 dígitos.",
    otpInvalidFormat: "O código de verificação deve ter 6 dígitos.",
    otpInvalid: "Código de verificação inválido. Tente novamente.",
    otpExpired: "O código de verificação expirou. Peça um novo código.",
    otpMaxAttempts: "Limite de tentativas excedido. Peça um novo código.",
    otpRateLimit: "Demasiados pedidos. Tente novamente mais tarde.",
    emailDeliveryFailed: "Não foi possível enviar o e-mail de verificação. Tente novamente mais tarde.",
    duplicateAccount: "Este e-mail ou nome de utilizador já está registado.",
  },
  ru: {
    fullNameRequired: "Введите полное имя.",
    usernameRequired: "Введите имя пользователя.",
    usernameTooShort: "Имя пользователя должно содержать не менее {n} символов.",
    usernameCharset: "Имя пользователя может содержать только буквы, цифры, дефисы и подчёркивания — без пробелов.",
    example: "Например: {s}",
    emailRequired: "Введите адрес электронной почты.",
    emailInvalid: "В этом адресе нет символа @ или домена.",
    passwordRequired: "Введите пароль.",
    passwordTooShort: "Пароль должен содержать не менее {n} символов.",
    confirmRequired: "Повторите пароль.",
    confirmMismatch: "Введённые значения не совпадают.",
    agreeRequired: "Примите условия, чтобы создать аккаунт.",
    registerFailed: "Не удалось создать аккаунт.",
    loginFailed: "Не удалось войти. Попробуйте ещё раз.",
    resetTokenRequired: "Введите полученный код сброса.",
    resetRequestFailed: "Не удалось отправить запрос на сброс пароля.",
    resetPasswordFailed: "Не удалось сбросить пароль.",
    otpRequired: "Введите 6-значный код подтверждения.",
    otpInvalidFormat: "Код подтверждения должен состоять из 6 цифр.",
    otpInvalid: "Неверный код подтверждения. Попробуйте ещё раз.",
    otpExpired: "Срок действия кода подтверждения истёк. Запросите новый код.",
    otpMaxAttempts: "Превышено максимальное число попыток. Запросите новый код.",
    otpRateLimit: "Слишком много запросов. Попробуйте позже.",
    emailDeliveryFailed: "Не удалось отправить письмо с подтверждением. Пожалуйста, попробуйте позже.",
    duplicateAccount: "Этот адрес электронной почты или имя пользователя уже зарегистрированы.",
  },
  ar: {
    fullNameRequired: "أدخل اسمك الكامل.",
    usernameRequired: "أدخل اسم المستخدم.",
    usernameTooShort: "يجب أن يتكون اسم المستخدم من {n} أحرف على الأقل.",
    usernameCharset: "يمكن أن يحتوي اسم المستخدم على أحرف وأرقام وشرطات وشرطات سفلية فقط — دون مسافات.",
    example: "مثال: {s}",
    emailRequired: "أدخل بريدك الإلكتروني.",
    emailInvalid: "ينقص هذا البريد الإلكتروني الرمز @ أو اسم النطاق.",
    passwordRequired: "أدخل كلمة المرور.",
    passwordTooShort: "يجب أن تتكون كلمة المرور من {n} أحرف على الأقل.",
    confirmRequired: "أعد إدخال كلمة المرور.",
    confirmMismatch: "الإدخالان غير متطابقين.",
    agreeRequired: "وافق على الشروط لإنشاء حساب.",
    registerFailed: "تعذر إنشاء الحساب.",
    loginFailed: "تعذر تسجيل الدخول. يرجى المحاولة مرة أخرى.",
    resetTokenRequired: "أدخل رمز إعادة التعيين الذي تلقيته.",
    resetRequestFailed: "تعذر إرسال طلب إعادة تعيين كلمة المرور.",
    resetPasswordFailed: "تعذر إعادة تعيين كلمة المرور.",
    otpRequired: "أدخل رمز التحقق المكون من 6 أرقام.",
    otpInvalidFormat: "يجب أن يتكون رمز التحقق من 6 أرقام.",
    otpInvalid: "رمز التحقق غير صالح. يرجى المحاولة مرة أخرى.",
    otpExpired: "انتهت صلاحية رمز التحقق. يرجى طلب رمز جديد.",
    otpMaxAttempts: "تم تجاوز الحد الأقصى للمحاولات. يرجى طلب رمز جديد.",
    otpRateLimit: "طلبات كثيرة جدًا. يرجى المحاولة مرة أخرى لاحقًا.",
    emailDeliveryFailed: "تعذر إرسال بريد التحقق الإلكتروني. يرجى المحاولة مرة أخرى لاحقًا.",
    duplicateAccount: "هذا البريد الإلكتروني أو اسم المستخدم مسجل بالفعل.",
  },
  hi: {
    fullNameRequired: "अपना पूरा नाम दर्ज करें।",
    usernameRequired: "उपयोगकर्ता नाम दर्ज करें।",
    usernameTooShort: "उपयोगकर्ता नाम में कम से कम {n} वर्ण होने चाहिए।",
    usernameCharset: "उपयोगकर्ता नाम में केवल अक्षर, अंक, हाइफ़न और अंडरस्कोर हो सकते हैं — रिक्त स्थान नहीं।",
    example: "उदाहरण: {s}",
    emailRequired: "अपना ईमेल दर्ज करें।",
    emailInvalid: "इस ईमेल में @ चिह्न या डोमेन नहीं है।",
    passwordRequired: "पासवर्ड दर्ज करें।",
    passwordTooShort: "पासवर्ड में कम से कम {n} वर्ण होने चाहिए।",
    confirmRequired: "अपना पासवर्ड फिर से दर्ज करें।",
    confirmMismatch: "दोनों प्रविष्टियाँ मेल नहीं खातीं।",
    agreeRequired: "खाता बनाने के लिए शर्तों को स्वीकार करें।",
    registerFailed: "खाता नहीं बनाया जा सका।",
    loginFailed: "साइन इन नहीं हो सका। कृपया फिर से प्रयास करें।",
    resetTokenRequired: "आपको मिला रीसेट कोड दर्ज करें।",
    resetRequestFailed: "पासवर्ड रीसेट का अनुरोध भेजा नहीं जा सका।",
    resetPasswordFailed: "पासवर्ड रीसेट नहीं किया जा सका।",
    otpRequired: "6 अंकों का सत्यापन कोड दर्ज करें।",
    otpInvalidFormat: "सत्यापन कोड 6 अंकों का होना चाहिए।",
    otpInvalid: "अमान्य सत्यापन कोड। कृपया पुनः प्रयास करें।",
    otpExpired: "सत्यापन कोड समाप्त हो गया है। कृपया नया कोड मांगें।",
    otpMaxAttempts: "अधिकतम प्रयास पार हो गए हैं। कृपया नया कोड मांगें।",
    otpRateLimit: "बहुत अधिक अनुरोध। कृपया बाद में प्रयास करें।",
    emailDeliveryFailed: "सत्यापन ईमेल नहीं भेजा जा सका। कृपया बाद में पुनः प्रयास करें।",
    duplicateAccount: "यह ईमेल या उपयोगकर्ता नाम पहले से पंजीकृत है।",
  },
};

/** A message in the chosen language, with `{n}` and `{s}` filled in. */
export function formMessage(
  lang: LanguageCode,
  key: FormMessageKey,
  values?: { n?: number; s?: string },
): string {
  const template = FORM_MESSAGES[lang][key];
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
