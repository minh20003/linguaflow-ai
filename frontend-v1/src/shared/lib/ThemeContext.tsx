"use client";

import {
  createContext,
  useContext,
  useEffect,
  useSyncExternalStore,
  type ReactNode,
} from "react";

export type ThemeMode = "light" | "dark" | "system";

interface ThemeContextValue {
  theme: ThemeMode;
  resolvedTheme: "light" | "dark";
  setTheme: (theme: ThemeMode) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

const STORAGE_KEY = "lingua_theme_mode";

/**
 * The saved preference is state owned outside React — localStorage — so it is
 * read through `useSyncExternalStore` rather than copied into React state by an
 * effect.
 *
 * The server snapshot is `null`, meaning "not known yet", and the distinction
 * from `"system"` is load-bearing. React runs the hydration render's effects
 * before re-rendering with the client value, so an effect that treated the
 * server snapshot as a real preference would remove the `data-theme` attribute
 * the blocking script in `layout.tsx` had just written, letting the OS
 * preference drive the page for a paint before the saved choice corrected it.
 */
const listeners = new Set<() => void>();
let cachedTheme: ThemeMode | null = null;

function readStoredTheme(): ThemeMode {
  if (cachedTheme === null) {
    const saved = localStorage.getItem(STORAGE_KEY);
    cachedTheme = saved === "light" || saved === "dark" ? saved : "system";
  }
  return cachedTheme;
}

function subscribeToStoredTheme(onStoreChange: () => void): () => void {
  listeners.add(onStoreChange);

  // localStorage only raises `storage` in *other* tabs, so a change made here
  // notifies the listeners directly.
  const onStorage = (event: StorageEvent) => {
    if (event.key !== STORAGE_KEY) return;
    cachedTheme = null;
    listeners.forEach((notify) => notify());
  };
  window.addEventListener("storage", onStorage);

  return () => {
    listeners.delete(onStoreChange);
    window.removeEventListener("storage", onStorage);
  };
}

function writeStoredTheme(mode: ThemeMode): void {
  cachedTheme = mode;
  localStorage.setItem(STORAGE_KEY, mode);
  listeners.forEach((notify) => notify());
}

function readSystemTheme(): "light" | "dark" {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function subscribeToSystemTheme(onStoreChange: () => void): () => void {
  const query = window.matchMedia("(prefers-color-scheme: dark)");
  query.addEventListener("change", onStoreChange);
  return () => query.removeEventListener("change", onStoreChange);
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const stored = useSyncExternalStore<ThemeMode | null>(
    subscribeToStoredTheme,
    readStoredTheme,
    () => null,
  );
  const systemTheme = useSyncExternalStore<"light" | "dark">(
    subscribeToSystemTheme,
    readSystemTheme,
    () => "light",
  );

  const theme = stored ?? "system";
  const resolvedTheme = theme === "system" ? systemTheme : theme;

  useEffect(() => {
    // Until the stored value is known, leave the attribute the blocking script
    // wrote exactly as it is.
    if (stored === null) return;

    if (stored === "system") {
      document.documentElement.removeAttribute("data-theme");
    } else {
      document.documentElement.setAttribute("data-theme", stored);
    }
  }, [stored]);

  return (
    <ThemeContext.Provider value={{ theme, resolvedTheme, setTheme: writeStoredTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used within a <ThemeProvider>");
  }
  return ctx;
}
