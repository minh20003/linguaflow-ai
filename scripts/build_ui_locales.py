"""Fill the interface catalogue's twelve non-authored languages from English.

`frontend/src/features/chat/i18n.ts` keys its interface copy by the English
string and carries a row per language. Vietnamese and English are written by
hand, because those are the two the team can read. The other twelve are
generated here with the same translation provider the product ships, for the
same reason the pitch deck is built from text rather than edited in PowerPoint:
a generated artefact regenerates after an edit instead of drifting from it.

Hand-writing Thai, Hindi and Arabic for several hundred strings would produce
translations nobody on this team can check, and would have to be redone by hand
every time an English string changes. Generating them makes the pass
reproducible and reviewable, and a reviewer who does read the language can
correct a row in place -- `--keep-existing` (the default) never overwrites one.

Usage:
    python scripts/build_ui_locales.py --check          # report gaps only
    python scripts/build_ui_locales.py                  # fill what is missing
    python scripts/build_ui_locales.py --overwrite ja   # redo one language
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.fallback_translator import (  # noqa: E402
    translate_with_secondary_provider,
)

CATALOGUE = (
    Path(__file__).resolve().parents[1] / "frontend/src/features/chat/i18n.ts"
)
# Written by hand; never generated over.
AUTHORED = ("en", "vi")
LANGUAGES = (
    "en", "vi", "ja", "ko", "zh", "es", "fr",
    "de", "th", "id", "pt", "ru", "ar", "hi",
)
# The tables keyed by the English string. `interactionKeys`/`interactionValues`
# are positional and are left alone: they predate this and are already complete.
TABLES = ("interactionExtras", "voiceMessageCopy", "voiceRetryCopy")


def read_table(source: str, name: str) -> tuple[dict[str, dict[str, str]], int, int]:
    """Parse one `Record<LanguageCode, Record<string, string>>` literal."""
    opening = re.search(
        rf"const {name}: Record<LanguageCode, Record<string, string>> = \{{",
        source,
    )
    if opening is None:
        raise SystemExit(f"{name}: table not found in {CATALOGUE.name}")
    start = opening.end()
    depth = 1
    index = start
    while depth:
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
        index += 1
    body = source[start : index - 1]

    table: dict[str, dict[str, str]] = {}
    for match in re.finditer(r"(\w+):\s*(\{.*?\}),?\n", body, re.DOTALL):
        table[match.group(1)] = json.loads(match.group(2))
    return table, start, index - 1


def render_table(table: dict[str, dict[str, str]]) -> str:
    lines = []
    for language in LANGUAGES:
        rows = table.get(language, {})
        pairs = ",".join(
            f"{json.dumps(key, ensure_ascii=False)}:{json.dumps(value, ensure_ascii=False)}"
            for key, value in rows.items()
        )
        lines.append(f"  {language}: {{{pairs}}},")
    return "\n" + "\n".join(lines) + "\n"


async def fill(
    table: dict[str, dict[str, str]], *, overwrite: set[str], report_only: bool
) -> int:
    english = table.get("en", {})
    filled = 0
    for language in LANGUAGES:
        if language in AUTHORED and language not in overwrite:
            continue
        rows = table.setdefault(language, {})
        for key, source_text in english.items():
            # A row still holding the English text is a translation that failed,
            # not one that succeeded: the provider rate-limits, and the failure
            # path writes the source through so the catalogue degrades rather
            # than breaks. Treating it as done would cement one bad afternoon
            # into the product, so a later run retries it.
            done = key in rows and rows[key] != source_text
            if done and language not in overwrite:
                continue
            filled += 1
            if report_only:
                continue
            # `None` on any failure -- provider off, unreachable, refused. The
            # English string then stands, which `interactionText` already falls
            # back to, so a failed run degrades the catalogue rather than
            # corrupting it.
            rows[key] = (
                await translate_with_secondary_provider(source_text, language, "en")
                or source_text
            )
    return filled


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report gaps, write nothing")
    parser.add_argument(
        "--overwrite",
        nargs="*",
        default=[],
        metavar="LANG",
        help="redo these languages even where a row already exists",
    )
    args = parser.parse_args()

    source = CATALOGUE.read_text(encoding="utf-8")
    total = 0
    # Right to left, so an earlier table's offsets stay valid after a rewrite.
    edits: list[tuple[int, int, str]] = []
    for name in TABLES:
        table, start, end = read_table(source, name)
        missing = await fill(
            table, overwrite=set(args.overwrite), report_only=args.check
        )
        total += missing
        print(f"  {name}: {missing} missing row(s)")
        if not args.check:
            edits.append((start, end, render_table(table)))

    if args.check:
        print(f"{total} row(s) would be filled")
        return
    for start, end, rendered in sorted(edits, reverse=True):
        source = source[:start] + rendered + source[end:]
    CATALOGUE.write_text(source, encoding="utf-8", newline="\n")
    print(f"{total} row(s) filled in {CATALOGUE.name}")


asyncio.run(main())
