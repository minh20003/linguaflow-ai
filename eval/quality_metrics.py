"""Metrics that do not need a model to compute.

Everything in `run_eval.py` rests on a single LLM-as-judge score per sample, and
ADR-17 already records what that costs: one observation each, at temperature
0.3, so two runs of identical code differ by roughly as much as a real change
does. These metrics are the counterweight. They are deterministic, free, and
comparable across runs and providers — a chrF++ that moves is a difference in
the output, never a difference in the judge's mood.

They are a complement, not a replacement. A reference-based score punishes a
correct translation that words things differently from the reference, which is
exactly what the judge is there to forgive. Read them together: the judge for
"is this an acceptable translation", these for "did the output actually change".

Three groups, matching the three things this agent does:

- **Machine translation** — chrF++, BLEU, TER against the reference.
- **Retrieval** — hit rate, recall, MRR and the rank of the line that mattered,
  for the semantic context feature (ADR-27).
- **Generation** — the properties a translation must have whatever it says:
  it is in the language that was asked for, it honours the glossary, it does
  not smuggle in content that only the conversation history knows, and it is
  not a refusal.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Languages written without spaces between words. BLEU and TER count word
# n-grams, so on these they must be told to count characters instead; left on
# the default tokenizer they score near zero for output a reader would call
# perfect. chrF++ needs no such handling, which is the main reason it leads.
SPACELESS_LANGUAGES = frozenset({"ja", "zh", "th", "ko"})


@dataclass(frozen=True, slots=True)
class TranslationScores:
    """Reference-based scores for one translation, all 0-100 except TER.

    TER is an error rate, so lower is better and it is not capped at 100: a
    translation longer than the reference can need more edits than there are
    words to edit.
    """

    chrf: float = 0.0
    bleu: float = 0.0
    ter: float = 0.0


def _tokenizer_for(target_language: str) -> str:
    """The sacrebleu tokenizer this language pair needs."""
    return "char" if target_language in SPACELESS_LANGUAGES else "13a"


def score_translation(
    hypothesis: str, reference: str, *, target_language: str
) -> TranslationScores | None:
    """Score one translation against its reference.

    Returns None when sacrebleu is not installed, so a checkout without the
    dev extras still runs the evaluation it could always run rather than
    failing at import time on a metric that is an addition to it.
    """
    if not hypothesis.strip() or not reference.strip():
        return None
    try:
        from sacrebleu.metrics import BLEU, CHRF, TER
    except ImportError:
        return None

    tokenizer = _tokenizer_for(target_language)
    # word_order=2 is chrF++, which adds word bigrams to the character n-grams.
    # It correlates better with human judgement than chrF on every language in
    # this set, and still needs no tokenizer of its own.
    chrf = CHRF(word_order=2).sentence_score(hypothesis, [reference]).score
    bleu = BLEU(tokenize=tokenizer, effective_order=True).sentence_score(
        hypothesis, [reference]
    ).score
    ter = TER(**({"asian_support": True} if tokenizer == "char" else {})).sentence_score(
        hypothesis, [reference]
    ).score
    return TranslationScores(chrf=chrf, bleu=bleu, ter=ter)


@dataclass(frozen=True, slots=True)
class RetrievalScores:
    """How well retrieval found the lines that were supposed to be found.

    `rank` is 1-based and 0 when nothing relevant came back, which is what
    separates "ranked last" from "not returned at all" — two very different
    failures that a hit rate alone reports identically.
    """

    hit: bool = False
    recall: float = 0.0
    reciprocal_rank: float = 0.0
    rank: int = 0
    returned: int = 0


def score_retrieval(retrieved: list[str], relevant: list[str]) -> RetrievalScores:
    """Compare what retrieval returned against what it should have returned.

    Matching is containment rather than equality: the retrieved lines carry a
    speaker label (`U01: ...`) that the expected text does not.

    Args:
        retrieved: Lines in the order retrieval ranked them, best first.
        relevant: The text of every line that should have been found.
    """
    if not relevant:
        return RetrievalScores(returned=len(retrieved))

    found_ranks = []
    for wanted in relevant:
        for position, line in enumerate(retrieved, start=1):
            if wanted in line:
                found_ranks.append(position)
                break

    if not found_ranks:
        return RetrievalScores(returned=len(retrieved))

    best = min(found_ranks)
    return RetrievalScores(
        hit=True,
        recall=len(found_ranks) / len(relevant),
        reciprocal_rank=1 / best,
        rank=best,
        returned=len(retrieved),
    )


_REFUSAL_MARKERS = (
    "i cannot",
    "i can't",
    "i'm unable",
    "as an ai",
    "tôi không thể",
    "xin lỗi, tôi",
)


def _words(text: str) -> list[str]:
    """Lowercased word-ish tokens, with punctuation and accents left in place."""
    return [token for token in re.split(r"\s+", text.strip().lower()) if token]


def _character_ngrams(text: str, size: int) -> set[str]:
    """Character n-grams of a string with whitespace removed."""
    squeezed = "".join(text.split())
    return {squeezed[i : i + size] for i in range(len(squeezed) - size + 1)}


def _is_spaceless(text: str) -> bool:
    """Whether the text is written without spaces between words.

    Decided from the characters present rather than from a declared language
    code, so the check still works on the mixed-script strings this product
    produces — and so a caller cannot get it wrong by passing the source
    language where the target was meant.
    """
    stripped = "".join(text.split())
    if not stripped:
        return False
    cjk = sum(
        1
        for ch in stripped
        if "぀" <= ch <= "ヿ"  # kana
        or "一" <= ch <= "鿿"  # han
        or "가" <= ch <= "힯"  # hangul
        or "฀" <= ch <= "๿"  # thai
    )
    return cjk / len(stripped) > 0.3


def bleed_score(translation: str, *, source: str, context_lines: list[str]) -> float:
    """How much of the output came from the history rather than the message.

    The system prompt's constraint 6 says the history is read and never written:
    a translation may use it to resolve a pronoun, and may not repeat what it
    says. Nothing measured that until now, and it is not a hypothetical — a
    model under test returned the previous message spliced onto the current one.

    Measured on character n-grams so it works for Japanese as written and for
    Vietnamese as written, without a tokenizer for either. Grams the source
    itself contains are excluded first: a name or a figure appearing in both the
    history and the message belongs to the message.

    The n differs by writing system, and the reason is a miss this metric
    actually had. A model borrowed `先月の請求書` from the history and wrote
    `先ほどの請求書`; at five characters the two share no gram at all, because one
    substituted character breaks every window that spans it, and the score came
    back 0.000 for a leak the sample was built to catch. Japanese packs a word
    into one or two characters, so five of them is a phrase; three is the
    comparable unit. Latin script keeps five, where three would match on
    ordinary syllables and report every translation as partly borrowed.

    Returns:
        The share of the translation's character n-grams that appear in the
        history and not in the source, 0.0 when there is no history. Small
        values are normal — function words recur — so read this as a comparison
        between runs, not as an absolute.
    """
    if not context_lines or not translation.strip():
        return 0.0

    size = 3 if _is_spaceless(translation) else 5
    grams = _character_ngrams(translation, size)
    if not grams:
        return 0.0

    source_grams = _character_ngrams(source, size)
    history_grams: set[str] = set()
    for line in context_lines:
        # The speaker label is ours, not the speaker's; counting it would make
        # every line look partly borrowed.
        history_grams |= _character_ngrams(line.split(":", 1)[-1], size)

    borrowed = (grams & history_grams) - source_grams
    return len(borrowed) / len(grams)


def glossary_adherence(translation: str, terms) -> float | None:
    """The share of required terms the translation actually renders correctly.

    A term is honoured when its target form appears; a `keep_verbatim` term is
    honoured when the source form survives untranslated. Case-insensitive, and
    accent-insensitive for neither — "hạn chót" and "han chot" are different
    words and only one of them is Vietnamese.

    Returns None when the message had no glossary terms, which is different from
    zero: no requirement met none of nothing.
    """
    required = list(terms or [])
    if not required:
        return None

    lowered = translation.lower()
    honoured = sum(
        1
        for term in required
        if (term.source_term if term.keep_verbatim else term.target_term).lower()
        in lowered
    )
    return honoured / len(required)


def looks_like_a_refusal(translation: str) -> bool:
    """Whether the model answered about itself instead of translating.

    Deliberately a short list of openers rather than a classifier. The agent's
    own `guardrails.looks_like_a_refusal` is the one that decides what ships;
    this exists so a run can *count* refusals, and counting wants a rule that
    will read the same in six months.
    """
    head = unicodedata.normalize("NFC", translation.strip().lower())[:80]
    return any(marker in head for marker in _REFUSAL_MARKERS)


def in_target_language(translation: str, target_language: str) -> bool | None:
    """Whether the output reads as the language that was asked for.

    Returns None when the local detector cannot say, which is a real third
    answer on the short messages this product translates — two words carry
    almost no signal, and forcing that into True or False would put noise into
    an aggregate rather than an abstention.
    """
    from src.agents.guardrails import detect_language_code

    detected = detect_language_code(translation)
    if not detected:
        return None
    return detected == target_language
