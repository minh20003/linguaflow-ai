export type AuthScreen = 'signin' | 'signup' | 'forgot-password' | 'language-onboarding';

export interface LanguageOption {
  id: string;
  name: string;
  nativeName: string;
  flag: string;
  code: string;
  sampleGreeting: string;
}

export interface UserProfile {
  name: string;
  email: string;
  preferredLanguage: string; // language id
  avatar?: string;
}
