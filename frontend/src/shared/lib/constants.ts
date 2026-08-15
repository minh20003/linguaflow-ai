/**
 * Shared constants for the frontend.
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Nhãn hiển thị cho từng mã ngôn ngữ.
 *
 * Danh sách mã hợp lệ do backend sở hữu (`GET /api/v1/languages`, hằng
 * `SUPPORTED_LANGUAGES` trong `src/schemas/auth.py`) — CONTRACT §1 cấm nhân bản
 * danh sách đó. Bảng dưới đây chỉ giữ phần backend không có việc gì phải biết:
 * tên hiển thị. Mã nào chưa có nhãn thì hiện bằng chính mã viết hoa.
 *
 * `display` là mã hai chữ in hoa dùng cho chip chọn ngôn ngữ — KHÔNG dùng emoji
 * cờ: Windows không có glyph cờ quốc gia nên `🇻🇳` hiện thành hai chữ `VN`, và
 * cờ không tương ứng một-một với ngôn ngữ. Xem docs/design.md §7.4.
 */
export const SUPPORTED_LANGUAGES = [
  { code: "vi", display: "VI", name: "Tiếng Việt" },
  { code: "en", display: "EN", name: "English" },
  { code: "zh", display: "ZH", name: "中文" },
  { code: "ja", display: "JA", name: "日本語" },
  { code: "ko", display: "KO", name: "한국어" },
  { code: "fr", display: "FR", name: "Français" },
  { code: "de", display: "DE", name: "Deutsch" },
  { code: "es", display: "ES", name: "Español" },
  { code: "th", display: "TH", name: "ไทย" },
  { code: "id", display: "ID", name: "Bahasa Indonesia" },
  { code: "pt", display: "PT", name: "Português" },
  { code: "ru", display: "RU", name: "Русский" },
  { code: "ar", display: "AR", name: "العربية" },
  { code: "hi", display: "HI", name: "हिन्दी" },
] as const;

export type LanguageCode = (typeof SUPPORTED_LANGUAGES)[number]["code"];

/**
 * Ngôn ngữ giao diện — nhãn chính luôn ở ngôn ngữ này.
 *
 * Cố ý không chú kiểu `LanguageCode`: giữ kiểu literal `"vi"` cho phép bảng
 * nhãn ở `i18n.ts` bảo đảm ở mức kiểu rằng ngôn ngữ này luôn có nhãn.
 */
export const UI_LANGUAGE = "vi";

/**
 * Ngôn ngữ đích mặc định. Cố tình KHÔNG phải `vi`: nhãn phụ song ngữ (§7) chỉ
 * nói được điều gì khi ngôn ngữ đích khác ngôn ngữ giao diện.
 */
export const DEFAULT_LANGUAGE: LanguageCode = "en";

/**
 * Mô tả hiển thị cho một mã ngôn ngữ.
 *
 * Mã lạ sinh ra một mục ngay tại chỗ thay vì rơi về phần tử đầu bảng — trả về
 * tiếng Việt cho một mã không nhận ra sẽ dựng ra hai ô "VI" cạnh nhau trong bộ
 * chọn, và mục thứ hai lại lưu một giá trị hoàn toàn khác khi được chọn.
 */
export function getLanguage(code: string) {
  return (
    SUPPORTED_LANGUAGES.find((l) => l.code === code)
    ?? { code, display: code.toUpperCase(), name: code.toUpperCase() }
  );
}

/** Nhãn cho một mã bất kỳ, kể cả mã backend hỗ trợ mà bảng trên chưa có. */
export function languageLabel(code: string): string {
  return (
    SUPPORTED_LANGUAGES.find((l) => l.code === code)?.name ?? code.toUpperCase()
  );
}
