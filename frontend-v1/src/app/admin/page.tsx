"use client";

import RequireAuth from "@/features/auth/components/RequireAuth";
import AdminPage from "@/features/admin/components/AdminPage";

export default function Admin() {
  return <RequireAuth><AdminPage /></RequireAuth>;
}
