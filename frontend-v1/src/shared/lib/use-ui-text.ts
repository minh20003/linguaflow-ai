"use client";

import { useCallback, useEffect, useSyncExternalStore } from "react";

import type { LanguageCode } from "./constants";
import { readInterfaceLanguage, subscribeToInterfaceLanguage } from "./ui-language";
import { uiText, type UiTextKey } from "./ui-text";

/**
 * The interface-language lookup, bound to whatever language is in effect now.
 *
 * A hook rather than a bare `uiText(lang, key)` call at each site so a screen
 * repaints when the setting changes — including when it changes in another tab,
 * which the store's `storage` listener covers.
 *
 * The server snapshot is `en`: it is what a first render with no stored choice
 * shows, so the markup React hydrates against matches what the server sent.
 */
export function useInterfaceLanguage(): LanguageCode {
  return useSyncExternalStore(
    subscribeToInterfaceLanguage,
    readInterfaceLanguage,
    () => "en" as const,
  );
}

export function useUiText(): (key: UiTextKey) => string {
  const lang = useInterfaceLanguage();
  return useCallback((key: UiTextKey) => uiText(lang, key), [lang]);
}

/**
 * Synchronizes client document.title and meta description to the active interface language.
 */
export function useDocumentMetadata(titleKey: UiTextKey, descKey?: UiTextKey): void {
  const t = useUiText();
  const lang = useInterfaceLanguage();

  useEffect(() => {
    const title = t(titleKey);
    if (title && document.title !== title) {
      document.title = title;
    }
    if (descKey) {
      const desc = t(descKey);
      if (desc) {
        let meta = document.querySelector('meta[name="description"]');
        if (!meta) {
          meta = document.createElement("meta");
          meta.setAttribute("name", "description");
          document.head.appendChild(meta);
        }
        if (meta.getAttribute("content") !== desc) {
          meta.setAttribute("content", desc);
        }
      }
    }
  }, [t, lang, titleKey, descKey]);
}


