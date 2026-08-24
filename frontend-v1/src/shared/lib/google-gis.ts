/**
 * Google Identity Services (GIS) loader and credential fetcher.
 *
 * Loads the GIS library dynamically and exposes typed helpers for rendering
 * GIS buttons and requesting credentials.
 *
 * Docs: https://developers.google.com/identity/gsi/web/guides/overview
 */

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: IdConfiguration) => void;
          requestIdToken?: (callback: (response: CallbackResponse) => void) => void;
          renderButton: (
            element: HTMLElement,
            config: GsiButtonConfiguration,
          ) => void;
          prompt: (momentListener?: (notification: PromptMomentNotification) => void) => void;
          cancel?: () => void;
        };
      };
    };
  }
}

export interface PromptMomentNotification {
  isDisplayMoment: () => boolean;
  isDisplayed: () => boolean;
  isNotDisplayed: () => boolean;
  getNotDisplayedReason: () => string;
  isSkippedMoment: () => boolean;
  getSkippedReason: () => string;
  isDismissedMoment: () => boolean;
  getDismissedReason: () => string;
  getMomentType: () => string;
}

export interface IdConfiguration {
  client_id: string;
  callback: (response: CallbackResponse) => void;
  auto_select?: boolean;
  cancel_on_tap_outside?: boolean;
  prompt_parent_id?: string;
  context?: "signin" | "signup" | "use";
}

export interface GsiButtonConfiguration {
  type?: "standard" | "icon";
  theme?: "outline" | "filled_blue" | "filled_black";
  size?: "small" | "medium" | "large";
  text?: "signin_with" | "signup_with" | "continue_with" | "signin";
  shape?: "rectangular" | "pill" | "circle" | "square";
  logo_alignment?: "left" | "center";
  width?: number;
  locale?: string;
}

export interface CallbackResponse {
  credential?: string;
  select_by?:
    | "user"
    | "user_1tap"
    | "user_3tap"
    | "btn"
    | "btn_confirm"
    | "add_session"
    | "iframe"
    | "auto";
  error?: string;
}

const GIS_URL = "https://accounts.google.com/gsi/client";
const GIS_LOAD_TIMEOUT_MS = 10000;

let _gisPromise: Promise<void> | null = null;

/**
 * Map application language code to a supported Google Identity Services locale tag.
 */
export function getGisLocale(lang: string): string {
  const map: Record<string, string> = {
    zh: "zh-CN",
    vi: "vi",
    en: "en",
    ja: "ja",
    ko: "ko",
    fr: "fr",
    de: "de",
    es: "es",
    th: "th",
    id: "id",
    pt: "pt-BR",
    ru: "ru",
    ar: "ar",
    hi: "hi",
  };
  return map[lang] || lang;
}

/**
 * Dynamically load the Google Identity Services script.
 *
 * Guarantees:
 * - Immediate resolution if GIS is already loaded.
 * - Single in-flight Promise for concurrent callers.
 * - Bounded 10s timeout.
 * - Cleans up and rejects on error/timeout so subsequent calls can retry.
 */
export function loadGis(): Promise<void> {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("GIS can only be loaded in browser environment"));
  }

  if (window.google?.accounts?.id) {
    return Promise.resolve();
  }

  if (_gisPromise) {
    return _gisPromise;
  }

  _gisPromise = new Promise<void>((resolve, reject) => {
    let timer: NodeJS.Timeout | null = null;

    const cleanup = () => {
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
    };

    const onLoad = () => {
      cleanup();
      if (window.google?.accounts?.id) {
        resolve();
      } else {
        _gisPromise = null;
        reject(new Error("GIS script loaded but window.google.accounts.id is unavailable"));
      }
    };

    const onError = (err?: unknown) => {
      cleanup();
      _gisPromise = null;
      reject(err instanceof Error ? err : new Error("GIS script failed to load"));
    };

    timer = setTimeout(() => {
      _gisPromise = null;
      const script = document.querySelector(`script[src="${GIS_URL}"]`);
      if (script && !window.google?.accounts?.id) {
        script.remove();
      }
      reject(new Error("GIS script load timed out"));
    }, GIS_LOAD_TIMEOUT_MS);

    const existing = document.querySelector(`script[src="${GIS_URL}"]`) as HTMLScriptElement | null;
    if (existing) {
      if (window.google?.accounts?.id) {
        cleanup();
        resolve();
        return;
      }
      existing.addEventListener("load", onLoad, { once: true });
      existing.addEventListener(
        "error",
        () => {
          existing.remove();
          onError();
        },
        { once: true },
      );
      return;
    }

    const script = document.createElement("script");
    script.src = GIS_URL;
    script.async = true;
    script.defer = true;
    script.onload = onLoad;
    script.onerror = () => {
      script.remove();
      onError();
    };
    document.head.appendChild(script);
  }).catch((err) => {
    _gisPromise = null;
    throw err;
  });

  return _gisPromise;
}

/**
 * Request a Google ID token via prompt with bounded timeout.
 *
 * Guarantees:
 * - auto_select is strictly false.
 * - Handles dismissal/skipped/not-displayed events.
 * - Bounded timeout (defaults to 15s) so the Promise always settles.
 */
export function requestGoogleToken(clientId: string, timeoutMs = 15000): Promise<string | null> {
  return new Promise<string | null>((resolve) => {
    if (!window.google?.accounts?.id) {
      resolve(null);
      return;
    }

    let settled = false;
    let timer: NodeJS.Timeout | null = null;

    const finish = (result: string | null) => {
      if (settled) return;
      settled = true;
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
      resolve(result);
    };

    timer = setTimeout(() => {
      finish(null);
    }, timeoutMs);

    window.google.accounts.id.initialize({
      client_id: clientId,
      callback: (response: CallbackResponse) => {
        if (response.credential) {
          finish(response.credential);
        } else {
          finish(null);
        }
      },
      auto_select: false,
      cancel_on_tap_outside: true,
    });

    window.google.accounts.id.prompt((notification: PromptMomentNotification) => {
      if (
        notification.isNotDisplayed() ||
        notification.isSkippedMoment() ||
        notification.isDismissedMoment()
      ) {
        finish(null);
      }
    });
  });
}

/** True when the GIS script has been injected and is ready. */
export function isGisLoaded(): boolean {
  return Boolean(window.google?.accounts?.id);
}
