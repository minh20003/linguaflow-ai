"use client";

/** The reader's interface language, readable from anywhere without a prop.
 *
 *  `interactionText(language, "…")` needs the language, and until now every
 *  component that wanted a translated word had to be handed one through props.
 *  That was fine while sixteen strings were translated; it does not survive
 *  several hundred spread over thirty-odd components, several of which are five
 *  levels below the shell and have no other reason to know about language.
 *
 *  The existing `language` props stay exactly as they are. This is additive: a
 *  component already holding one keeps using it, and a component that does not
 *  reads the context instead of growing a prop chain to reach it. Two ways in,
 *  one source of truth -- the provider is fed from the same
 *  `settings.interfaceLanguage` the props are.
 *
 *  Defaults to English rather than Vietnamese when there is no provider above,
 *  for the reason the catalogue does: no provider means nothing is known about
 *  the reader, and Vietnamese is a guess about them in a way English is not.
 */

import React, { createContext, useContext, useMemo } from "react";

import { interactionText } from "./i18n";
import type { LanguageCode } from "./types";

const LanguageContext = createContext<LanguageCode>("en");

export const LanguageProvider: React.FC<{
  language: LanguageCode;
  children: React.ReactNode;
}> = ({ language, children }) => (
  <LanguageContext.Provider value={language}>{children}</LanguageContext.Provider>
);

/** The current interface language. */
export function useLanguage(): LanguageCode {
  return useContext(LanguageContext);
}

/** Translate by English source string: `const t = useT(); t("Save message")`.
 *
 *  Memoised on the language so a component re-rendering for another reason does
 *  not hand its children a new function identity and invalidate their memos.
 */
export function useT(): (value: string) => string {
  const language = useLanguage();
  return useMemo(() => (value: string) => interactionText(language, value), [language]);
}

/** Translate against an explicit language rather than the ambient one.
 *
 *  For a subtree whose words do not belong to the interface. The proposal card
 *  in the message thread is the case this exists for: it sits among translated
 *  messages, so everything it shows — its buttons as much as its sentences —
 *  follows the reader's translation language, and taking that from context
 *  would give it the interface language instead.
 *
 *  Memoised on the language for the same reason `useT` is.
 */
export function useTFor(language: LanguageCode): (value: string) => string {
  return useMemo(() => (value: string) => interactionText(language, value), [language]);
}
