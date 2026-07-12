#!/usr/bin/env python3
"""
caddy-ensure-logging.py — guarantee every Caddy site block is instrumented for
access logging, so newly-added subdomains can't become monitoring blind spots.

Caddy enables access logging PER SITE (there is no global "log everything"
switch). ServerManager's pattern is an `(accesslog)` snippet imported into every
site block. This guard parses the Caddyfile and finds any site block that lacks
that logging, so coverage never silently drifts as you add channels/subdomains.

    ./caddy-ensure-logging.py                 # check ~/caddyfile, list gaps, exit 1 if any
    ./caddy-ensure-logging.py --caddyfile P   # check a specific file
    ./caddy-ensure-logging.py --fix           # inject `import accesslog` into gaps (backs up first)
    ./caddy-ensure-logging.py --json          # machine-readable report

A "site block" is any top-level `name { ... }` whose name is a real address —
NOT the global options block (`{ ... }`) and NOT a snippet definition
(`(name) { ... }`). A block counts as covered if it contains `import accesslog`
or a `log` directive of its own.

Exit codes: 0 = all covered (or --fix succeeded), 1 = gaps found (check mode),
2 = usage/IO error.
"""
import argparse
import json
import os
import re
import shutil
import sys
import time


SNIPPET = "accesslog"


def strip_comment(line):
    """Remove an unquoted trailing # comment. Good enough for Caddyfiles."""
    out, in_str = [], False
    i = 0
    while i < len(line):
        c = line[i]
        if c == '"':
            in_str = not in_str
        elif c == "#" and not in_str:
            break
        out.append(c)
        i += 1
    return "".join(out)


def parse_blocks(lines):
    """
    Return top-level blocks as dicts:
      {kind: 'global'|'snippet'|'site', header, open_idx, close_idx, covered}
    kind is based on the block header; `covered` is only meaningful for sites.
    Uses brace-depth tracking on comment-stripped lines.
    """
    blocks = []
    depth = 0
    cur = None
    for i, raw in enumerate(lines):
        code = strip_comment(raw)
        stripped = code.strip()

        if depth == 0 and cur is None and stripped.endswith("{"):
            header = stripped[:-1].strip()
            if header == "":
                kind = "global"
            elif header.startswith("("):
                kind = "snippet"
            else:
                kind = "site"
            cur = {"kind": kind, "header": header, "open_idx": i,
                   "close_idx": None, "covered": False}

        # count braces on this line to track depth
        opens = code.count("{")
        closes = code.count("}")
        depth += opens - closes

        if cur is not None:
            # inspect body lines for logging directives
            if i > cur["open_idx"]:
                s = stripped
                if s == f"import {SNIPPET}" or s.startswith("import ") and SNIPPET in s.split():
                    cur["covered"] = True
                elif s == "log" or s.startswith("log ") or s.startswith("log{") or s == "log {":
                    cur["covered"] = True
            if depth == 0:
                cur["close_idx"] = i
                blocks.append(cur)
                cur = None
    return blocks


def snippet_defined(blocks):
    return any(b["kind"] == "snippet" and b["header"].strip("() ") == SNIPPET
              for b in blocks)


def indent_of(line):
    return line[:len(line) - len(line.lstrip())]


def main():
    ap = argparse.ArgumentParser(description="Ensure every Caddy site block has access logging.")
    default_cf = os.environ.get("CADDYFILE_PATH") or os.path.expanduser("~/caddyfile")
    ap.add_argument("--caddyfile", default=default_cf, help=f"path to Caddyfile (default {default_cf})")
    ap.add_argument("--fix", action="store_true", help="inject `import accesslog` into any uncovered site block")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    try:
        with open(args.caddyfile) as f:
            text = f.read()
    except OSError as e:
        sys.exit(f"error: cannot read {args.caddyfile}: {e}")

    lines = text.splitlines()
    blocks = parse_blocks(lines)
    sites = [b for b in blocks if b["kind"] == "site"]
    gaps = [b for b in sites if not b["covered"]]

    if args.json and not args.fix:
        print(json.dumps({
            "caddyfile": args.caddyfile,
            "snippet_defined": snippet_defined(blocks),
            "sites": len(sites),
            "covered": len(sites) - len(gaps),
            "gaps": [b["header"] for b in gaps],
        }, indent=2))
        sys.exit(1 if gaps else 0)

    if not args.fix:
        print(f"Caddyfile: {args.caddyfile}")
        print(f"  sites: {len(sites)}   covered: {len(sites) - len(gaps)}   gaps: {len(gaps)}")
        if not snippet_defined(blocks):
            print(f"  ⚠ (accesslog) snippet is NOT defined — add it before using --fix")
        for b in sites:
            mark = "ok " if b["covered"] else "GAP"
            print(f"    [{mark}] {b['header']}")
        if gaps:
            print(f"\n{len(gaps)} site(s) not logging → invisible to the traffic monitor.")
            print("Run with --fix to inject `import accesslog`.")
        sys.exit(1 if gaps else 0)

    # --fix
    if not gaps:
        print("Nothing to fix — every site block already logs.")
        sys.exit(0)
    if not snippet_defined(blocks):
        sys.exit(f"error: (accesslog) snippet is not defined in {args.caddyfile}; "
                 "add it first (templates/accesslog.snippet), then re-run --fix")

    # Insert `import accesslog` right after each uncovered opener, working bottom-up
    # so earlier line indices stay valid.
    new_lines = list(lines)
    for b in sorted(gaps, key=lambda x: -x["open_idx"]):
        opener = new_lines[b["open_idx"]]
        ind = indent_of(opener) + "\t"
        new_lines.insert(b["open_idx"] + 1, f"{ind}import {SNIPPET}")

    backup = f"{args.caddyfile}.bak.ensurelog.{int(time.time())}"
    shutil.copy2(args.caddyfile, backup)
    with open(args.caddyfile, "w") as f:
        f.write("\n".join(new_lines) + "\n")

    print(f"Injected `import {SNIPPET}` into {len(gaps)} site block(s):")
    for b in gaps:
        print(f"    + {b['header']}")
    print(f"Backup: {backup}")
    print("\nNext: validate, then apply with a force-recreate (NOT `caddy reload`):")
    print("  docker run --rm -v <caddyfile>:/etc/caddy/Caddyfile:ro <caddy-image> \\")
    print("    caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile")
    print("  docker compose -f <caddy-compose-dir>/docker-compose.yml up -d --force-recreate")


if __name__ == "__main__":
    main()
