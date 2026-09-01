"""Fill the interface catalogue's twelve generated languages, via the LLM.

The sibling `build_ui_locales.py` goes one string at a time through the free
secondary translator. That is fine for a handful of new keys and hopeless for a
catalogue: several thousand rows against an unofficial endpoint gets throttled
into mostly-empty results, which the fallback then writes through as English.

This asks the configured model for all twelve languages of a small batch in one
call, so a five-thousand-row fill is about sixty requests. English and
Vietnamese are never touched: they are the authored rows, and everything else is
derived from the Vietnamese, not from the English, so a generated language is
one translation away from the source rather than two.

Usage:
    python scripts/translate_ui_locales.py            # fill what is missing
    python scripts/translate_ui_locales.py --overwrite ko
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
TABLES = ("interactionExtras", "voiceMessageCopy", "voiceRetryCopy")
BATCH = 8
CHAR_BUDGET = 700

PROMPT = """You are localising a chat application's interface.

# Task
Translate each numbered string into every one of these languages: {languages}.
These are buttons, labels, placeholders, headings and short notices.

# Constraints
- Keep each translation as short as the source. A button label is not a sentence.
- Preserve placeholder tokens such as {{name}} and %s exactly.
- Preserve trailing punctuation and ellipses.
- Product names stay as they are: LinguaFlow, Google Calendar, Gemini.
- Output valid JSON ONLY: an object keyed by the number as a string, whose value
  is an object keyed by language code. No markdown fence, no commentary.

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
    for match in re.finditer(r"(\w+):\s*(\{.*?\}),?\n", source[start : index - 1], re.DOTALL):
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


async def translate(chunk: list[str], languages: tuple[str, ...]) -> dict[str, dict[str, str]]:
    from langchain_core.messages import HumanMessage

    from src.config import get_settings
    from src.services.llm import extract_text, get_llm

    numbered = "\n".join(f"{index}. {text}" for index, text in enumerate(chunk))
    # The process ceiling is sized for one chat message; this asks for a batch
    # in twelve languages, and a truncated reply parses as far as the cut and
    # silently drops the rest.
    settings = get_settings().model_copy(update={"llm_max_tokens": 8192})
    response = await get_llm(settings=settings).ainvoke(
        [HumanMessage(content=PROMPT.format(languages=", ".join(languages), numbered=numbered))]
    )
    raw = re.sub(r"^```(?:json)?|```$", "", extract_text(response).strip(), flags=re.MULTILINE)
    parsed = json.loads(raw.strip())
    return {
        text: {
            code: value
            for code, value in (parsed.get(str(index)) or {}).items()
            if isinstance(value, str) and value.strip()
        }
        for index, text in enumerate(chunk)
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", nargs="*", default=[], metavar="LANG")
    args = parser.parse_args()
    overwrite = set(args.overwrite)

    source = CATALOGUE.read_text(encoding="utf-8")
    edits: list[tuple[int, int, str]] = []

    for name in TABLES:
        table, start, end = read_table(source, name)
        vietnamese = table.get("vi", {})
        english = table.get("en", {})
        # A row equal to its English source is a translation that never
        # happened, not one that succeeded; those are retried.
        wanted = [
            key
            for key in english
            if any(
                language in overwrite
                or table.get(language, {}).get(key) in (None, english[key])
                for language in GENERATED
            )
        ]
        print(f"{name}: {len(wanted)} key(s) to translate")
        for number, chunk in enumerate(batches(wanted), start=1):
            # From the Vietnamese where there is one: it is the authored source,
            # and going through English would be two translations deep.
            sources = [vietnamese.get(key) or key for key in chunk]
            try:
                rendered = await translate(sources, GENERATED)
            except Exception as exc:  # noqa: BLE001 - one bad batch must not stop the rest
                print(f"  batch {number}: {type(exc).__name__}")
                continue
            for key, source_text in zip(chunk, sources, strict=True):
                for language, value in rendered.get(source_text, {}).items():
                    if language in GENERATED:
                        table.setdefault(language, {})[key] = value
            print(f"  batch {number}: {len(chunk)} key(s)", flush=True)
        edits.append((start, end, render_table(table)))

    for start, end, rendered in sorted(edits, reverse=True):
        source = source[:start] + rendered + source[end:]
    CATALOGUE.write_text(source, encoding="utf-8", newline="\n")
    print(f"written to {CATALOGUE.name}")


asyncio.run(main())
