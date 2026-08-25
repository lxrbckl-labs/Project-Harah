#!/usr/bin/env python3
"""Guard the suppression rule: a known-bad target must still be able to die.

`KNOWN_BAD` exists so a chronic, understood failure does not shout every ten
minutes. The trap it walked into (found 2026-08-25) is that suppression used to
be unconditional: `showalter` was excluded from `problems` AND from transition
detection, so the one container the estate had stopped watching was also the
only one that could never report that it had stopped running. A monitor with a
permanent blind spot is worse than one target fewer.

The rule this file enforces: the suppression covers the KNOWN failure only.
`unhealthy` while up is the accepted condition; not running at all is a new
failure wearing the same name, and it reports.

`classify_container` is IMPORTED from watch.py, never re-typed here, so the
test cannot drift from the code it is testing (the dispatch-selftest.py
discipline).

    python3 skill/watchdog/watchdog-selftest.py    # exit 0 = the rule holds
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("harah_watchdog", HERE / "watch.py")
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)

KNOWN = "showalter"          # carries a reason in watch.KNOWN_BAD
UNKNOWN = "project-jordyn"   # carries none

# (label, name, docker-ps status, exit code, expect ok, expect suppressed)
CASES = [
    ("known-bad, up but unhealthy — the accepted condition",
     KNOWN, "Up 4 days (unhealthy)", 0, False, True),
    ("known-bad, STOPPED — a new failure, must NOT be suppressed",
     KNOWN, "", 0, False, False),
    ("known-bad, docker call failed — must NOT be suppressed",
     KNOWN, "Up 4 days (unhealthy)", 1, False, False),
    ("known-bad, recovered to healthy — reads ok, nothing to suppress",
     KNOWN, "Up 4 days (healthy)", 0, True, False),
    ("ordinary container, healthy",
     UNKNOWN, "Up 4 days (healthy)", 0, True, False),
    ("ordinary container, no health check reported",
     UNKNOWN, "Up 4 days", 0, True, False),
    ("ordinary container, unhealthy — reports",
     UNKNOWN, "Up 4 days (unhealthy)", 0, False, False),
    ("ordinary container, stopped — reports",
     UNKNOWN, "", 0, False, False),
]

failures: list[str] = []
print("watchdog self-test — a suppressed target must still be able to die\n")

for label, name, status, code, want_ok, want_suppressed in CASES:
    e = watch.classify_container(name, status, code)
    bad = []
    if e["ok"] is not want_ok:
        bad.append(f"ok={e['ok']} want {want_ok}")
    if e["known_bad"] is not want_suppressed:
        bad.append(f"known_bad={e['known_bad']} want {want_suppressed}")
    # A suppression is only legitimate if it says why — the dashboard prints it.
    if e["known_bad"] and not (e.get("known_bad_reason") or "").strip():
        bad.append("suppressed with no stated reason")
    if not e["known_bad"] and e.get("known_bad_reason"):
        bad.append("reason present on an unsuppressed target")
    # `problems` is built from exactly this pair; keep the derived meaning honest.
    reported = (not e["ok"]) and (not e["known_bad"])
    print(f"  {'ok ' if not bad else '✗  '}{label}")
    print(f"       -> ok={e['ok']} suppressed={e['known_bad']} reported={reported} detail={e['detail']!r}")
    if bad:
        failures.append(f"{label}: " + "; ".join(bad))

# --- the log-noise rule -------------------------------------------------
# watch.sh logs a pass only if the output contains UNHEALTHY / WENT DOWN /
# RECOVERED. An unchanged problem must therefore print none of them, or one
# long-lived failure writes an identical line every ten minutes and buries the
# events the log exists for.
LOG_TRIGGERS = ("UNHEALTHY", "WENT DOWN", "RECOVERED")
T = [{"name": "a"}] * 13
P = ["https://ds.lxrbckl.com: HTTP 502"]
P2 = P + ["voicetocolumn: NOT RUNNING"]

SUMMARY_CASES = [
    ("healthy estate — quiet",            T, [],  [],  [],   False),
    ("new problem — logs",                T, P,   [],  [],   True),
    ("same problem next pass — quiet",    T, P,   P,   [],   False),
    ("problem set grew — logs",           T, P2,  P,   [],   True),
    ("problem set shrank — logs",         T, P,   P2,  [],   True),
    ("unchanged, but a transition — logs", T, P,  P,   ["WENT DOWN: x — y"], True),
    ("problem cleared — quiet line, transition carries the news",
                                          T, [],  P,   [],   False),
]

print("\nsummary line — an unchanged problem must not trigger a log write\n")
for label, targets, probs, prev, trans, want_log in SUMMARY_CASES:
    line = watch.summarize(targets, probs, prev, trans)
    logs = any(w in line for w in LOG_TRIGGERS)
    bad = []
    if logs is not want_log:
        bad.append(f"logs={logs} want {want_log}")
    # Whatever it decides, the problem must stay visible in the text.
    if probs and probs[0] not in line:
        bad.append("dropped the problem from the line")
    print(f"  {'ok ' if not bad else '✗  '}{label}")
    print(f"       -> {line[:110]}")
    if bad:
        failures.append(f"{label}: " + "; ".join(bad))

# Every entry in KNOWN_BAD must justify itself in the UI.
for name, reason in watch.KNOWN_BAD.items():
    if not str(reason).strip():
        failures.append(f"KNOWN_BAD[{name}] has no reason")

if failures:
    print("\nFAILED:")
    for f in failures:
        print(f"  ✗ {f}")
    sys.exit(1)
print("\nsuppression rule holds")
