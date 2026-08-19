"use client";

import React, { createContext, useCallback, useContext, useSyncExternalStore } from "react";
import { type LanguageCode } from "@/shared/lib/constants";
import {
  readInterfaceLanguage,
  setInterfaceLanguage,
  subscribeToInterfaceLanguage,
} from "@/shared/lib/ui-language";

interface LanguageContextValue {
  lang: LanguageCode;
  setLang: (code: LanguageCode) => void;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

/**
 * Ngôn ngữ đang chọn ở màn hình chưa đăng nhập.
 *
 * Không còn giữ trong `useState`: lựa chọn ở đây **là** ngôn ngữ giao diện
 * trước khi có tài khoản, nên nó đọc và ghi thẳng vào store dùng chung
 * (`ui-language.ts`). Nhờ vậy nó sống qua lần tải trang sau, và khi đăng nhập
 * xong thì `saveSession` ghi đè bằng giá trị của tài khoản — đúng ba bước ở
 * docs/CONTRACT.md §1.3.
 *
 * Provider vẫn giữ nguyên để không phải sửa mọi nơi đang gọi `useLanguage`.
 */
export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const lang = useSyncExternalStore(
    subscribeToInterfaceLanguage,
    readInterfaceLanguage,
    () => "en" as const,
  );
  const setLang = useCallback((code: LanguageCode) => setInterfaceLanguage(code), []);
  return (
    <LanguageContext.Provider value={{ lang, setLang }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage(): LanguageContextValue {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useLanguage phải nằm trong <LanguageProvider>");
  return ctx;
}
