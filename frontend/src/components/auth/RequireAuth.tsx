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
 * exactly that: state owned outside React. The server snapshot is null, so the
 * markup rendered on the server matches the signed-out client and hydration
 * cannot mismatch.
 *
 * Presence is all that is checked here. An expired or forged token is rejected
 * by the backend, and the socket's authentication_failed path sends the user
 * back to login.
 */
export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const token = useSyncExternalStore(subscribe, getToken, () => null);

  useEffect(() => {
    if (token === null) router.replace("/login");
  }, [token, router]);

  if (token === null) return null;
  return <>{children}</>;
}
