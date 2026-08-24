/** Client for the administrator-only translation attempt summary. */

import { getStoredAccessToken } from "./auth-session";
import { API_BASE } from "./constants";

/** One model's traffic and, when `src/services/llm_pricing.py` has an entry
    for it, the $/1M rates that entry holds and the rough cost they imply.
    `cost_usd` (and the two prices) are `null` — not `0` — for a model with no
    price on file: those mean different things. */
export interface ModelUsage {
  count: number;
  input_tokens: number;
  output_tokens: number;
  input_price_per_million_usd: number | null;
  output_price_per_million_usd: number | null;
  cost_usd: number | null;
}

export interface StatsResponse {
  window_days: number | null;
  total_attempts: number;
  outcomes: Record<string, number>;
  fallback_rate: number;
  detect_methods: Record<string, number>;
  fallback_reasons: Record<string, number>;
  models_served: Record<string, number>;
  model_usage: Record<string, ModelUsage>;
  /** Sum of every priced model's `cost_usd`. Read alongside
      `cost_usd_partial`: when that is true, this total leaves out whatever
      models had no price on file, and is a floor, not the whole bill. */
  total_cost_usd: number;
  cost_usd_partial: boolean;
  language_pairs: Record<string, { count: number; p50_ms: number; p95_ms: number }>;
  input_tokens: number;
  output_tokens: number;
  /** The arithmetic mean — distinct from `total_ms_p50`, the median. See
      `stats.summaryHint` for why both are shown. */
  total_ms_mean: number;
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
