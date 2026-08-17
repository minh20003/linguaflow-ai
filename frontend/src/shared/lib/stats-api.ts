/** Client for the administrator-only translation attempt summary. */

import { getStoredAccessToken } from "./auth-session";
import { API_BASE } from "./constants";

export interface StatsResponse {
  window_days: number | null;
  total_attempts: number;
  outcomes: Record<string, number>;
  fallback_rate: number;
  detect_methods: Record<string, number>;
  fallback_reasons: Record<string, number>;
  models_served: Record<string, number>;
  language_pairs: Record<string, { count: number; p50_ms: number; p95_ms: number }>;
  input_tokens: number;
  output_tokens: number;
  total_ms_p50: number;
  total_ms_p95: number;
}

export async function fetchStats(): Promise<StatsResponse> {
  const token = getStoredAccessToken();
  if (!token) throw new Error("stats_fetch_failed");

  const response = await fetch(`${API_BASE}/api/v1/stats`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (response.status === 403) throw new Error("admin_required");
  if (!response.ok) throw new Error("stats_fetch_failed");
  return response.json() as Promise<StatsResponse>;
}
