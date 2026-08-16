/**
 * Ngôn ngữ giao diện đang có hiệu lực, và cách các màn hình theo dõi nó.
 *
 * Không dùng React context vì hai lý do. Giá trị này sống ngoài React — nó đến
 * từ `localStorage` trước khi có phiên đăng nhập, rồi từ `UserDTO` sau đó — nên
 * `useSyncExternalStore` mô tả đúng bản chất hơn là một state được một effect
 * chép vào. Và các trang ở đây là những cây client riêng biệt của app router,
 * nên một provider sẽ phải gắn vào layout gốc chỉ để phục vụ chuyện này.
 *
 * Thứ tự lấy giá trị bám theo docs/CONTRACT.md §1.3:
 *
 * 1. Chưa từng chọn gì → `en`. Đây là ngôn ngữ duy nhất chắc chắn đủ nhãn.
 * 2. Đã chọn lúc chưa đăng nhập → giá trị trong `localStorage`.
 * 3. Đăng nhập xong → `interface_language` của tài khoản, do `saveSession` ghi
 *    đè vào `localStorage`, nên lần render đầu sau khi mở lại trình duyệt đã
 *    đúng ngôn ngữ chứ không loé tiếng Anh rồi mới đổi.
 */

import { DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, type LanguageCode } from "./constants";

const STORAGE_KEY = "interface_language";

const listeners = new Set<() => void>();

function isSupported(code: string | null): code is LanguageCode {
  return Boolean(code) && SUPPORTED_LANGUAGES.some((language) => language.code === code);
}

/** The language the interface should be drawn in right now. */
export function readInterfaceLanguage(): LanguageCode {
  if (typeof window === "undefined") return DEFAULT_LANGUAGE;
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return isSupported(stored) ? stored : DEFAULT_LANGUAGE;
}

/**
 * Record the interface language and repaint every screen listening for it.
 *
 * Called both by the settings page after the server confirms, and by
 * `saveSession` when an account's own value arrives with the login response.
 */
export function setInterfaceLanguage(code: string): void {
  if (typeof window === "undefined") return;
  if (!isSupported(code)) return;
  if (window.localStorage.getItem(STORAGE_KEY) === code) return;
  window.localStorage.setItem(STORAGE_KEY, code);
  for (const notify of listeners) notify();
}

/** Forget the choice, so the next visitor starts from English again. */
export function clearInterfaceLanguage(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(STORAGE_KEY);
  for (const notify of listeners) notify();
}

export function subscribeToInterfaceLanguage(onStoreChange: () => void): () => void {
  listeners.add(onStoreChange);
  // Another tab of the same account changing the setting counts too.
  window.addEventListener("storage", onStoreChange);
  return () => {
    listeners.delete(onStoreChange);
    window.removeEventListener("storage", onStoreChange);
  };
}
