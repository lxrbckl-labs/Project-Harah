#!/usr/bin/env python3
"""Guard the one invariant every `claude -p` runner in this repo depends on.

A brief is handed to `claude -p` as an ARGV element. `-p/--print` is a boolean
flag, so the brief lands as a positional — and anything starting with `-` is
parsed as an option instead. A brief that still carries its YAML frontmatter
therefore aborts with `error: unknown option`: exit 1, no output, and no
session ever starts, while the listener's log still reads as if it dispatched.

resolve.sh has stripped frontmatter since it first hit this. mentions/scan.py
did not, so every summons died on arg parsing (2026-08-23 drills on
Project-Harah #22 and #31). One runner fixed, its sibling left broken, and
nothing noticed — this file is what notices.

Each runner is exercised through ITS OWN stripping code, never a copy of it,
so a change to either runner is tested rather than shadowed.

    python3 skill/dispatch-selftest.py     # exit 0 = every runner is dispatchable
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FAILURES: list[str] = []


def check(name: str, brief: str) -> None:
    """A brief is dispatchable only if argv can't mistake it for an option."""
    if not brief.strip():
        FAILURES.append(f"{name}: brief is empty")
        return
    if brief.startswith("-"):
        first = brief.splitlines()[0]
        FAILURES.append(
            f"{name}: brief starts with {first!r} — `claude -p` will read it as "
            "an option and abort with `unknown option` (exit 1, no session)"
        )
        return
    print(f"  ok  {name}: {len(brief)} chars, starts {brief.splitlines()[0][:48]!r}")


def _load_scan():
    path = HERE / "mentions" / "scan.py"
    spec = importlib.util.spec_from_file_location("harah_mentions_scan", path)
    mod = importlib.util.module_from_spec(spec)
    sys.argv = ["scan.py", "--dry-run"]      # importing must not dispatch anything
    spec.loader.exec_module(mod)
    return mod


def mentions_brief() -> str:
    """Through scan.py's own loader — not a reimplementation of it."""
    return _load_scan().load_brief()


def mentions_dispatched_brief() -> str:
    """The full artifact actually dispatched — brief plus the fenced comment —
    since that, not prompt.md alone, is what reaches argv."""
    mod = _load_scan()
    return mod.build_brief({
        "repo": "lxrbckl-labs/Project-Harah", "number": "0",
        "author": "lxRbckl", "url": "https://example.invalid/selftest",
        "body": "@project-harah selftest — no real mention.",
    })


def resolver_brief() -> str:
    """Through the awk program resolve.sh actually runs, lifted from the file."""
    sh = (HERE / "resolver" / "resolve.sh").read_text()
    m = re.search(r"""BASE="\$\(awk '(.+?)' "\$PROMPT"\)""", sh, re.DOTALL)
    if not m:
        FAILURES.append(
            "resolver: could not find the frontmatter-stripping awk in resolve.sh — "
            "either it was removed (the bug is back) or it was rewritten (update this test)"
        )
        return ""
    return subprocess.run(
        ["awk", m.group(1), str(HERE / "resolver" / "prompt.md")],
        capture_output=True, text=True, check=True,
    ).stdout


def main() -> int:
    print("dispatch self-test — every `claude -p` brief must be argv-safe")
    check("mentions/prompt.md", mentions_brief())
    check("mentions dispatched brief", mentions_dispatched_brief())
    check("resolver/prompt.md", resolver_brief())
    if FAILURES:
        print("\nFAILED:")
        for f in FAILURES:
            print(f"  ✗ {f}")
        return 1
    print("\nall runners dispatchable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
