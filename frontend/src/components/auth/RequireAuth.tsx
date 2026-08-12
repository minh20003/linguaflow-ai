"use client";

import { useEffect, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";

import { getToken } from "@/lib/auth";

/** localStorage changes only in other tabs; `storage` is the only event for it. */
function subscribe(onChange: () => void): () => void {
  window.addEventListener("storage", onChange);
  return () => window.removeEventListener("storage", onChange);
}

/**
 * Keeps signed-out visitors out of the chat.
 *
 * Renders nothing until the token has been read — without that, the fully
 * populated chat UI flashes before the redirect, which reads as a leak even
 * though no real data has loaded yet.
 *
 * The token is read through `useSyncExternalStore` because localStorage is
 * exactly that: state owned outside React.
 *
 * The server snapshot is `undefined`, not `null`, and the two mean different
 * things: `undefined` is "not known yet", `null` is "definitely signed out".
 * The distinction is load-bearing. React renders the server snapshot once
 * during hydration and runs that render's effects before re-rendering with the
 * client value, so an effect that treated the server snapshot as "signed out"
 * would redirect every signed-in visitor straight back to the login page.
 *
 * Presence is all that is checked here. An expired or forged token is rejected
 * by the backend, and the socket's authentication_failed path sends the user
 * back to login.
 */
export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const token = useSyncExternalStore<string | null | undefined>(
    subscribe,
    getToken,
    () => undefined,
  );

  useEffect(() => {
    if (token === null) router.replace("/login");
  }, [token, router]);

  if (!token) return null;
  return <>{children}</>;
}
