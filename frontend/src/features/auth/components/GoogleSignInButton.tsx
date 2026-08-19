"use client";

import { useEffect, useRef, useState } from "react";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (response: { credential?: string }) => void;
          }) => void;
          renderButton: (element: HTMLElement, options: Record<string, unknown>) => void;
        };
      };
    };
  }
}

const GOOGLE_SCRIPT = "https://accounts.google.com/gsi/client";

function loadGoogleScript(): Promise<void> {
  if (window.google?.accounts.id) return Promise.resolve();
  const existing = document.querySelector<HTMLScriptElement>(`script[src="${GOOGLE_SCRIPT}"]`);
  if (existing) {
    return new Promise((resolve, reject) => {
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener("error", () => reject(new Error("Unable to load Google sign-in")), { once: true });
    });
  }
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = GOOGLE_SCRIPT;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Unable to load Google sign-in"));
    document.head.appendChild(script);
  });
}

interface GoogleSignInButtonProps {
  disabled?: boolean;
  onCredential: (credential: string) => void;
  onError: (message: string) => void;
}

/** Google renders the button itself to comply with its branding requirements. */
export function GoogleSignInButton({ disabled = false, onCredential, onError }: GoogleSignInButtonProps) {
  const host = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;

  useEffect(() => {
    if (!clientId) return;
    let cancelled = false;
    void loadGoogleScript()
      .then(() => {
        if (cancelled || !host.current || !window.google) return;
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: ({ credential }) => {
            if (credential) onCredential(credential);
            else onError("Google did not return a sign-in credential.");
          },
        });
        host.current.replaceChildren();
        window.google.accounts.id.renderButton(host.current, {
          type: "standard",
          theme: "outline",
          size: "large",
          text: "continue_with",
          shape: "rectangular",
          width: Math.max(host.current.clientWidth, 280),
        });
        setReady(true);
      })
      .catch(() => onError("Unable to load Google sign-in. Please try again."));
    return () => { cancelled = true; };
  }, [clientId, onCredential, onError]);

  if (!clientId) {
    return <p className="text-xs text-slate-500">Google sign-in is not configured for this deployment.</p>;
  }
  return <div className={disabled || !ready ? "pointer-events-none opacity-60" : ""} ref={host} />;
}
