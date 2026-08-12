"use client";

import { useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { restoreSession } from "@/lib/auth-session";

export default function RequireAuth({ children }: { children: ReactNode }) {
  const router = useRouter();
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
    return <main aria-busy="true" aria-label="Đang kiểm tra phiên đăng nhập" style={{ minHeight: "100vh", background: "#f4f8fc" }} />;
  }
  return children;
}
