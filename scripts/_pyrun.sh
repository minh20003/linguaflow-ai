#!/usr/bin/env bash
# Cross-platform Python launcher for AI log hooks.
# Order: repo .venv → python3 → python → py -3 → common Windows install dirs.
# Every candidate is *probed* (`-c pass`) before use, because on Windows
# `python3` is often the Microsoft Store redirector stub, which is on PATH,
# prints "Python was not found" and exits 0 — silently swallowing every log.
# The repo venv comes first so submit_log.py can import python-dotenv.
# Designed to be called as: bash scripts/_pyrun.sh <script> [args...]
#
# Exits 0 silently if no Python is found — hooks must never block the AI tool.
set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"

# Usable = runs a trivial program successfully. Filters out Store stubs.
# Args stay quoted so interpreter paths containing spaces (e.g. "Program
# Files") work.
_usable() {
  [ -n "${1:-}" ] || return 1
  if [ -n "${2:-}" ]; then
    "$1" "$2" -c pass >/dev/null 2>&1
  else
    "$1" -c pass >/dev/null 2>&1
  fi
}

PY=""
PY_ARG=""
for cand in \
  "$REPO_ROOT/.venv/Scripts/python.exe" \
  "$REPO_ROOT/.venv/bin/python" \
  python3 \
  python \
  py; do
  # `py` is the Windows launcher: it needs an explicit -3.
  arg=""
  [ "$cand" = "py" ] && arg="-3"
  case "$cand" in
    /*|[A-Za-z]:*) [ -x "$cand" ] || continue ;;
    *) command -v "$cand" >/dev/null 2>&1 || continue ;;
  esac
  if _usable "$cand" "$arg"; then PY="$cand"; PY_ARG="$arg"; break; fi
done

if [ -z "$PY" ]; then
  # PATH lookup failed — probe standard Windows install locations.
  shopt -s nullglob 2>/dev/null || true
  for cand in \
    /c/Users/*/AppData/Local/Programs/Python/Python*/python.exe \
    "/c/Program Files/Python"*/python.exe \
    "/c/Program Files (x86)/Python"*/python.exe \
    /c/Python*/python.exe; do
    if [ -x "$cand" ] && _usable "$cand"; then PY="$cand"; break; fi
  done
  shopt -u nullglob 2>/dev/null || true
  [ -n "$PY" ] || exit 0
fi

if [ -n "$PY_ARG" ]; then
  exec "$PY" "$PY_ARG" "$@"
else
  exec "$PY" "$@"
fi
