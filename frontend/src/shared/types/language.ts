export type LanguageCode =
  | "en"
  | "vi"
  | "ja"
  | "ko"
  | "zh"
  | "es"
  | "fr"
  | "de"
  | "th"
  | "id";

export interface LanguageOption {
  code: LanguageCode;
  name: string;
  nativeName: string;
  flag: string;
}
