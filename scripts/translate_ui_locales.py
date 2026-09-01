"""Fill the interface catalogue's twelve generated languages, via the LLM.

The sibling `build_ui_locales.py` goes one string at a time through the free
secondary translator. That is fine for a handful of new keys and hopeless for a
catalogue: several thousand rows against an unofficial endpoint gets throttled
into mostly-empty results, which the fallback then writes through as English.

**One language per request, a batch of strings inside it.** A first version
asked for all twelve languages of a batch in one call and the model simply
stopped answering -- two strings took longer than five minutes and then failed.
A flat "translate these into Vietnamese" reply is a shape it produces reliably;
a nested object keyed by twelve language codes is not, and the difference is
worth more than the request count.

English and Vietnamese are never written: they are the authored rows. Everything
else derives from the **Vietnamese**, not the English, so a generated language is
one translation from the source rather than two.

Resumable, because it will be interrupted. A row still equal to its English
source counts as never translated and is retried on the next run. See
`outstanding` for what that costs: `--check` never reaches zero, because a few
dozen words are simply the same in both languages.

Usage:
    python scripts/translate_ui_locales.py --check
    python scripts/translate_ui_locales.py                # everything missing
    python scripts/translate_ui_locales.py --only ja ko   # just these
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CATALOGUE = Path(__file__).resolve().parents[1] / "frontend/src/features/chat/i18n.ts"
AUTHORED = ("en", "vi")
LANGUAGES = (
    "en", "vi", "ja", "ko", "zh", "es", "fr",
    "de", "th", "id", "pt", "ru", "ar", "hi",
)
GENERATED = tuple(code for code in LANGUAGES if code not in AUTHORED)
NAMES = {
    "ja": "Japanese", "ko": "Korean", "zh": "Simplified Chinese",
    "es": "Spanish", "fr": "French", "de": "German", "th": "Thai",
    "id": "Indonesian", "pt": "Portuguese", "ru": "Russian",
    "ar": "Arabic", "hi": "Hindi",
}
TABLES = ("interactionExtras", "voiceMessageCopy", "voiceRetryCopy")
BATCH = 20
CHAR_BUDGET = 1200

PROMPT = """You are localising a chat application's interface into {name}.

# Task
Translate each numbered string into natural {name} of the same register and
length. These are buttons, labels, placeholders, headings and short notices.

# Constraints
- Keep each translation as short as the source. A button label is not a sentence.
- Preserve placeholder tokens such as {{name}} and %s exactly.
- Preserve trailing punctuation and ellipses.
- Product names stay as they are: LinguaFlow, Google Calendar, Gemini.
- Output valid JSON ONLY: an object mapping the number, as a string, to the
  translated text. No markdown fence, no commentary.

# Strings
{numbered}
"""


def read_table(source: str, name: str) -> tuple[dict[str, dict[str, str]], int, int]:
    opening = re.search(
        rf"const {name}: Record<LanguageCode, Record<string, string>> = \{{", source
    )
    if opening is None:
        raise SystemExit(f"{name}: table not found")
    start = opening.end()
    depth, index = 1, start
    while depth:
        depth += {"{": 1, "}": -1}.get(source[index], 0)
        index += 1
    table: dict[str, dict[str, str]] = {}
    for match in re.finditer(
        r"(\w+):\s*(\{.*?\}),?\n", source[start : index - 1], re.DOTALL
    ):
        table[match.group(1)] = json.loads(match.group(2))
    return table, start, index - 1


def render_table(table: dict[str, dict[str, str]]) -> str:
    rows = []
    for language in LANGUAGES:
        pairs = ",".join(
            f"{json.dumps(k, ensure_ascii=False)}:{json.dumps(v, ensure_ascii=False)}"
            for k, v in table.get(language, {}).items()
        )
        rows.append(f"  {language}: {{{pairs}}},")
    return "\n" + "\n".join(rows) + "\n"


def batches(items: list[str]) -> list[list[str]]:
    out: list[list[str]] = []
    current: list[str] = []
    budget = 0
    for text in items:
        if current and (len(current) >= BATCH or budget + len(text) > CHAR_BUDGET):
            out.append(current)
            current, budget = [], 0
        current.append(text)
        budget += len(text)
    if current:
        out.append(current)
    return out


async def translate(chunk: list[str], language: str) -> dict[str, str]:
    from langchain_core.messages import HumanMessage

    from src.config import get_settings
    from src.services.llm import extract_text, get_llm

    numbered = "\n".join(f"{index}. {text}" for index, text in enumerate(chunk))
    # The process ceiling is sized for one chat message; a batch needs more.
    settings = get_settings().model_copy(update={"llm_max_tokens": 4096})
    response = await get_llm(settings=settings).ainvoke(
        [HumanMessage(content=PROMPT.format(name=NAMES[language], numbered=numbered))]
    )
    raw = re.sub(
        r"^```(?:json)?|```$", "", extract_text(response).strip(), flags=re.MULTILINE
    ).strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Salvage the complete pairs from a truncated object rather than losing
        # the batch for its last line.
        parsed = {
            m.group(1): json.loads(f'"{m.group(2)}"')
            for m in re.finditer(r'"(\d+)"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
        }
        if not parsed:
            raise
    return {
        text: parsed[str(index)].strip()
        for index, text in enumerate(chunk)
        if isinstance(parsed.get(str(index)), str) and parsed[str(index)].strip()
    }


def outstanding(table: dict[str, dict[str, str]], language: str) -> list[str]:
    """Keys this language still needs.

    A row equal to its English source counts as never translated, which is what
    makes the script resumable after the provider drops a batch. The cost is
    that it cannot tell that apart from a word which is simply the same in both
    languages -- "Original" in French, "Color" in Spanish, "Actions" -- so a few
    dozen rows are re-requested on every run and never settle. `--check` will
    therefore never print zero; a couple of dozen outstanding is the floor, not
    a gap.
    """
    english = table.get("en", {})
    rows = table.get(language, {})
    return [key for key in english if rows.get(key) in (None, english[key])]


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report gaps, write nothing")
    parser.add_argument("--only", nargs="*", default=[], metavar="LANG")
    args = parser.parse_args()
    targets = tuple(args.only) if args.only else GENERATED

    source = CATALOGUE.read_text(encoding="utf-8")
    edits: list[tuple[int, int, str]] = []
    total = 0

    for name in TABLES:
        table, start, end = read_table(source, name)
        vietnamese = table.get("vi", {})
        for language in targets:
            wanted = outstanding(table, language)
            total += len(wanted)
            if args.check:
                if wanted:
                    print(f"{name} {language}: {len(wanted)} missing", flush=True)
                continue
            if not wanted:
                continue
            print(f"{name} {language}: {len(wanted)} to translate", flush=True)
            for number, chunk in enumerate(batches(wanted), start=1):
                # From the Vietnamese: it is the authored source, and going via
                # English would be two translations deep.
                sources = [vietnamese.get(key) or key for key in chunk]
                try:
                    rendered = await translate(sources, language)
                except Exception as exc:  # noqa: BLE001 - one batch must not stop the rest
                    print(f"  {language} batch {number}: {type(exc).__name__}", flush=True)
                    continue
                for key, source_text in zip(chunk, sources, strict=True):
                    value = rendered.get(source_text)
                    if value:
                        table.setdefault(language, {})[key] = value
                print(f"  {language} batch {number}/{len(batches(wanted))}", flush=True)
            # Written after each language, so an interrupted run keeps its work.
            edits = [(start, end, render_table(table))]
            rebuilt = source[:start] + edits[0][2] + source[end:]
            CATALOGUE.write_text(rebuilt, encoding="utf-8", newline="\n")
            source = CATALOGUE.read_text(encoding="utf-8")
            table, start, end = read_table(source, name)
            vietnamese = table.get("vi", {})

    if args.check:
        print(f"{total} row(s) outstanding")


asyncio.run(main())
