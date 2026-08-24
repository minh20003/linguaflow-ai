/**
 * Client for the glossary and its review queue (administrator only).
 *
 * Shaped after `stats-api.ts`, the other administrator surface: a plain fetch
 * per endpoint, the bearer token read at call time rather than held, and a 403
 * turned into `admin_required` so the page can say who a screen is for instead
 * of showing a generic failure.
 *
 * A proposal carries counts and anonymised fragments and nothing else — no
 * author, no conversation, no message id. That is not an omission this client
 * makes: the server's DTO has nowhere to put them, because an administrator is
 * barred from reading conversation content (docs/CONTRACT.md §3.12).
 */

import { getStoredAccessToken } from "./auth-session";
import { API_BASE } from "./constants";

/** One anonymised fragment showing a proposed term in use. */
export interface GlossaryCitation {
  anonymized_snippet: string;
  observed_at: string;
}

export interface GlossaryProposal {
  id: string;
  source_term: string;
  target_term: string;
  source_language: string;
  target_language: string;
  domain: string;
  audience: string;
  keep_verbatim: boolean;
  status: string;
  /** How many corrections the miner grouped together. */
  occurrence_count: number;
  /** How many different people made them — the number a reviewer judges on. */
  distinct_user_count: number;
  rationale: string;
  reject_reason: string;
  created_at: string;
  citations: GlossaryCitation[];
  /** Entries the glossary already holds for this source term. */
  similar_entries: GlossarySimilarEntry[];
  /**
   * True when one of them is live with a different rendering — the machine is
   * already translating this term correctly by the glossary's current lights,
   * and the proposal is asking to overturn that rather than to fill a gap.
   */
  conflicts_with_active: boolean;
}

/** An entry already in the glossary covering the same source term. */
export interface GlossarySimilarEntry {
  id: string;
  source_term: string;
  target_term: string;
  domain: string;
  audience: string;
  status: string;
}

export interface GlossaryEntry {
  id: string;
  source_term: string;
  target_term: string;
  source_language: string;
  target_language: string;
  domain: string;
  audience: string;
  keep_verbatim: boolean;
  status: string;
  created_at: string;
  updated_at: string;
}

/** The corrections an administrator may make while approving. */
export interface GlossaryApproval {
  source_term?: string;
  target_term?: string;
  domain?: string;
  audience?: string;
  keep_verbatim?: boolean;
}

/** The fields an edit may change. The language pair is deliberately not one. */
export interface GlossaryEntryPatch {
  source_term?: string;
  target_term?: string;
  domain?: string;
  audience?: string;
  keep_verbatim?: boolean;
}

export interface GlossaryEntryDraft {
  source_term: string;
  target_term: string;
  source_language: string;
  target_language: string;
  domain?: string;
  audience?: string;
  keep_verbatim?: boolean;
}

export type ProposalStatus = "pending" | "approved" | "rejected";

/**
 * One request, with the failures this screen distinguishes between.
 *
 * `glossary_conflict` is its own code rather than a generic failure because it
 * is the only one where retrying is wrong: it means somebody else already
 * decided this proposal, or the entry already exists. The screen has to reload
 * rather than resend.
 */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getStoredAccessToken();
  if (!token) throw new Error("glossary_request_failed");

  const response = await fetch(`${API_BASE}/api/v1${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
    cache: "no-store",
  });

  if (response.status === 403) throw new Error("admin_required");
  if (response.status === 404) throw new Error("glossary_missing");
  if (response.status === 409) throw new Error("glossary_conflict");
  if (!response.ok) throw new Error("glossary_request_failed");
  return response.json() as Promise<T>;
}

export function fetchGlossaryProposals(
  status: ProposalStatus = "pending",
  limit = 50,
): Promise<GlossaryProposal[]> {
  return request(`/admin/glossary/proposals?status=${status}&limit=${limit}`);
}

/**
 * Accept a proposal, optionally correcting it on the way through.
 *
 * Every field of `changes` is optional and overrides what the miner suggested.
 * Making a reviewer reject and re-add a nearly-right term is the fastest way
 * for a queue to stop being worked (docs/CONTRACT.md §3.12).
 */
export function approveGlossaryProposal(
  proposalId: string,
  changes: GlossaryApproval = {},
): Promise<GlossaryEntry> {
  return request(`/admin/glossary/proposals/${encodeURIComponent(proposalId)}/approve`, {
    method: "POST",
    body: JSON.stringify(changes),
  });
}

/** Refuse a proposal. The reason is required and is kept as rejection memory. */
export function rejectGlossaryProposal(
  proposalId: string,
  reason: string,
): Promise<GlossaryProposal> {
  return request(`/admin/glossary/proposals/${encodeURIComponent(proposalId)}/reject`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export function fetchGlossaryEntries(
  includeRetired = false,
  limit = 100,
): Promise<GlossaryEntry[]> {
  return request(`/admin/glossary?include_retired=${includeRetired}&limit=${limit}`);
}

export function createGlossaryEntry(draft: GlossaryEntryDraft): Promise<GlossaryEntry> {
  return request("/admin/glossary", { method: "POST", body: JSON.stringify(draft) });
}

/**
 * Correct an entry that is already in force.
 *
 * Only the fields sent are changed. The language pair is not among them: an
 * entry with the wrong pair is a different entry rather than a mistyped one,
 * and both the embedding and the uniqueness rule are scoped to the pair.
 */
export function updateGlossaryEntry(
  entryId: string,
  changes: GlossaryEntryPatch,
): Promise<GlossaryEntry> {
  return request(`/admin/glossary/${encodeURIComponent(entryId)}`, {
    method: "PATCH",
    body: JSON.stringify(changes),
  });
}

/**
 * Take an entry out of use.
 *
 * The verb is DELETE and the effect is retirement: a translation delivered last
 * month was shaped by this term, and removing the row would erase the only
 * explanation for the wording somebody is still reading.
 */
export function retireGlossaryEntry(entryId: string): Promise<GlossaryEntry> {
  return request(`/admin/glossary/${encodeURIComponent(entryId)}`, { method: "DELETE" });
}

/**
 * Put a retired entry back into use.
 *
 * The counterpart of `retireGlossaryEntry`, and possible only because nothing
 * was deleted: the entry keeps its id, its embedding and the date it was first
 * approved instead of coming back as a second row.
 */
export function restoreGlossaryEntry(entryId: string): Promise<GlossaryEntry> {
  return request(`/admin/glossary/${encodeURIComponent(entryId)}/restore`, {
    method: "POST",
  });
}

/**
 * Remove a retired entry from the glossary for good.
 *
 * The one thing `retireGlossaryEntry` cannot do, and deliberately narrow: the
 * server refuses this for an active entry with a 409, because an entry in use
 * has shaped translations people may still be reading and the row is the only
 * explanation for their wording. What is left is the case retirement reads
 * wrong for — a term typed in by mistake, which explains nothing because it
 * never shaped anything anybody saw, and whose scope stays taken by the
 * uniqueness rule until the row is gone.
 */
export function deleteGlossaryEntry(entryId: string): Promise<GlossaryEntry> {
  return request(`/admin/glossary/${encodeURIComponent(entryId)}/permanent`, {
    method: "DELETE",
  });
}
