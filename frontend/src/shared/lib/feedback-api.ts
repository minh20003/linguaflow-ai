/**
 * Client for the administrator's view of reader feedback (administrator only).
 *
 * Shaped after `stats-api.ts` and `glossary-api.ts`: one plain fetch, the
 * bearer token read at call time rather than held, and a 403 turned into
 * `admin_required` so the screen can say who it is for instead of showing a
 * generic failure.
 *
 * What comes back is counts, plus the anonymised fragment the correction
 * recorder prepared at edit time. No author, no conversation, no message id —
 * an administrator is barred from reading conversation content
 * (docs/CONTRACT.md §3.12), so the server's DTO has nowhere to put them.
 */

import { getStoredAccessToken } from "./auth-session";
import { API_BASE } from "./constants";

/**
 * How readers rated the translations they were shown.
 *
 * Two named buckets, not three: the interface offers a thumb up and a thumb
 * down and nothing between them, so a `neutral` count was always zero and read
 * on the screen as a third opinion nobody was holding.
 */
export interface FeedbackVoteSummary {
  up: number;
  down: number;
  total: number;
  /** Share of votes that were positive, 0 when nobody has voted. */
  up_rate: number;
  /** The raw 1-to-5 histogram, kept so a rating outside the two named buckets
      stays visible instead of vanishing — that is the signal that the
      interface sending ratings has changed. */
  ratings: Record<string, number>;
}

/**
 * One correction a reader allowed to be used for the shared glossary.
 *
 * Two anonymised fragments, not one: `original_snippet` previews the
 * sender's own wording in `source_language`, and `anonymized_snippet` is the
 * window around the corrected phrase in the machine's rendering, in
 * `target_language`. Neither is the reader's own wording of a message they
 * did not consent to share.
 */
export interface SharedCorrection {
  source_phrase: string;
  corrected_target: string;
  source_language: string;
  target_language: string;
  domain: string;
  audience: string;
  original_snippet: string;
  anonymized_snippet: string;
  observed_at: string;
}

export interface FeedbackOverview {
  votes: FeedbackVoteSummary;
  shared_corrections: SharedCorrection[];
  /** Every consented correction, which is not the length of the list once the
      request's limit bites. */
  shared_total: number;
  /** Corrections whose author did not consent: a count and nothing else. */
  withheld_total: number;
}

export async function fetchFeedbackOverview(limit = 50): Promise<FeedbackOverview> {
  const token = getStoredAccessToken();
  if (!token) throw new Error("feedback_fetch_failed");

  const response = await fetch(`${API_BASE}/api/v1/admin/feedback?limit=${limit}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (response.status === 403) throw new Error("admin_required");
  if (!response.ok) throw new Error("feedback_fetch_failed");
  return response.json() as Promise<FeedbackOverview>;
}
