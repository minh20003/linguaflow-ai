"use client";

import React, { createContext, useContext, useState } from "react";
import { DEFAULT_LANGUAGE, type LanguageCode } from "@/shared/lib/constants";

interface LanguageContextValue {
  lang: LanguageCode;
  setLang: (code: LanguageCode) => void;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

/**
 * Ngôn ngữ đích đang chọn ở dải bên trái. Dải chọn và các form là anh em trong
 * cây, nên state phải nằm ở layout — đổi ngôn ngữ đổi ngay mọi nhãn phụ, không
 * reload (docs/design.md §7.1).
 */
export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLang] = useState<LanguageCode>(DEFAULT_LANGUAGE);
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
