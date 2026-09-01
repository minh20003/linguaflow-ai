"""Find interface strings that are looked up but not in the catalogue.

A missing key is invisible: `interactionText` falls back to the key itself, so
the screen renders the English source and looks perfectly correct *in English*.
Every other language silently shows English, and nothing anywhere reports it.
That is how `ui("Approved")` shipped with no catalogue row at all.

Run it in CI, or before a release:

    python scripts/check_ui_keys.py          # non-zero exit if anything is missing
    python scripts/check_ui_keys.py --add    # add what is missing to en, for translating
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend/src"
CATALOGUE = FRONTEND / "features/chat/i18n.ts"
# `ui("…")`, and the two-argument form components still use directly.
CALLS = (
    re.compile(r'\bui\("((?:[^"\\]|\\.)*)"\)'),
    re.compile(r'\binteractionText\(\s*\w+\s*,\s*"((?:[^"\\]|\\.)*)"\s*\)'),
)
TABLES = ("interactionExtras", "voiceMessageCopy", "voiceRetryCopy")


def catalogue_keys(source: str) -> set[str]:
    keys: set[str] = set()
    for name in TABLES:
        opening = re.search(
            rf"const {name}: Record<LanguageCode, Record<string, string>> = \{{", source
        )
        if opening is None:
            continue
        start = opening.end()
        depth, index = 1, start
        while depth:
            depth += {"{": 1, "}": -1}.get(source[index], 0)
            index += 1
        match = re.search(r"\n  en: (\{.*?\}),\n", source[start : index - 1], re.DOTALL)
        if match:
            keys |= set(json.loads(match.group(1)))
    # The positional table, whose keys are its English values.
    positional = re.search(r"const interactionKeys = (\[.*?\]);", source, re.DOTALL)
    if positional:
        keys |= set(json.loads(positional.group(1)))
    return keys


def used_keys() -> dict[str, set[str]]:
    """Every looked-up string, and which files ask for it."""
    found: dict[str, set[str]] = {}
    for path in list(FRONTEND.rglob("*.tsx")) + list(FRONTEND.rglob("*.ts")):
        if path == CATALOGUE or ".test." in path.name:
            continue
        # Comment and docstring lines are dropped first: a `ui("…")` written as
        # an example in a comment is not a lookup, and reporting it teaches the
        # reader to ignore this tool's output.
        text = "\n".join(
            line
            for line in path.read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith(("//", "*", "/*"))
        )
        for pattern in CALLS:
            for match in pattern.finditer(text):
                # Unescaped, because the key at runtime is what JavaScript makes
                # of the literal: `ui("Click \"+ Add\" …")` looks up a string
                # containing plain quotes. Comparing the raw source text instead
                # reports a key that is in fact present.
                key = json.loads(f'"{match.group(1)}"')
                found.setdefault(key, set()).add(path.relative_to(FRONTEND).as_posix())
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--add", action="store_true", help="add missing keys to the English row")
    args = parser.parse_args()

    source = CATALOGUE.read_text(encoding="utf-8")
    known = catalogue_keys(source)
    used = used_keys()
    missing = {key: files for key, files in used.items() if key not in known}

    print(f"{len(used)} key(s) looked up, {len(known)} in the catalogue")
    if not missing:
        print("nothing missing")
        return
    print(f"{len(missing)} missing:")
    for key, files in sorted(missing.items()):
        print(f"  {key!r}  <- {', '.join(sorted(files))}")

    if not args.add:
        sys.exit(1)

    start = source.index("const interactionExtras")
    match = re.search(r"\n  en: (\{.*?\}),\n", source[start:], re.DOTALL)
    english = json.loads(match.group(1))
    for key in missing:
        english[key] = key
    rendered = (
        "{"
        + ",".join(
            f"{json.dumps(k, ensure_ascii=False)}:{json.dumps(v, ensure_ascii=False)}"
            for k, v in english.items()
        )
        + "}"
    )
    source = source[: start + match.start(1)] + rendered + source[start + match.end(1) :]
    CATALOGUE.write_text(source, encoding="utf-8", newline="\n")
    print(f"{len(missing)} key(s) added to the English row; translate them next")


main()
