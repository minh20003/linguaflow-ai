/**
 * The closed vocabulary of the two glossary scope columns (docs/CONTRACT.md §5
 * note 16).
 *
 * A client-side copy of `GLOSSARY_AUDIENCES` and `GLOSSARY_DOMAINS` in
 * `src/database/models.py`. Two processes, so the duplication is unavoidable;
 * what matters is *why* the list is closed. The lookup compares an entry's
 * scope to the conversation's by equality, so an entry filed under `client` and
 * a conversation profiled as "an external client" never meet — which is how the
 * audience glossary managed to look implemented and do nothing (ADR-24, ADR-26).
 *
 * A value outside the list can still be typed in: the column carries no check
 * constraint, and a team may need a scope this list has not learned about yet.
 * Picking from the list is the default path; typing one is the deliberate
 * exception.
 */

export const GLOSSARY_AUDIENCES = ["internal", "client"] as const;
export const GLOSSARY_DOMAINS = ["engineering", "commercial", "support"] as const;

/** The two scope axes, naming both the option list and the label key prefix. */
export type ScopeKind = "domain" | "audience";

export const SCOPE_OPTIONS: Record<ScopeKind, readonly string[]> = {
  domain: GLOSSARY_DOMAINS,
  audience: GLOSSARY_AUDIENCES,
};
