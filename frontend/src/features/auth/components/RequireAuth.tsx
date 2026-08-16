"use client";

import { useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { restoreSession } from "@/shared/lib/auth-session";
import { useUiText } from "@/shared/lib/use-ui-text";

export default function RequireAuth({ children }: { children: ReactNode }) {
  const router = useRouter();
  const t = useUiText();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let active = true;
    restoreSession().then((session) => {
      if (!active) return;
      if (!session) router.replace("/login");
      else setReady(true);
    });
    return () => { active = false; };
  }, [router]);

  if (!ready) {
    return <main aria-busy="true" aria-label={t("auth.loading")} style={{ minHeight: "100vh", background: "#f4f8fc" }} />;
  }
  return children;
}
