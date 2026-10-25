#!/usr/bin/env python3
"""Regression tests for prove.py's comparison logic. No network, no docker.

    python3 skill/prove/prove-selftest.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prove  # noqa: E402

ok = fail = 0


def check(name, cond):
    global ok, fail
    if cond:
        ok += 1
    else:
        fail += 1
        print(f"FAIL: {name}")


P = {"pass": True, "ms": 120}
F = {"pass": False, "ms": 80}

# 1. passed before, fails now -> regression
c = prove.compare({"home": P}, {"home": F})
check("regression detected", c["regressions"] == ["home"] and not c["still_failing"])

# 2. failed before, fails now -> still failing, NOT a regression (showalter's cosmetic flag)
c = prove.compare({"health": F}, {"health": F})
check("pre-existing failure is not a regression", c["still_failing"] == ["health"] and not c["regressions"])

# 3. failed before, passes now -> fixed
c = prove.compare({"health": F}, {"health": P})
check("fix recorded", c["fixed"] == ["health"] and not c["regressions"])

# 4. no baseline at all -> failing_new, never a regression
c = prove.compare(None, {"home": F, "api": P})
check("first sight cannot regress", c["failing_new"] == ["home"] and not c["regressions"])

# 5. a check that is new in this deploy (not in baseline) and fails -> failing_new
c = prove.compare({"home": P}, {"home": P, "new": F})
check("new check failing is not a regression", c["failing_new"] == ["new"] and not c["regressions"])

# 6. slow: 10x slower and over a second -> warning, still a pass
c = prove.compare({"home": {"pass": True, "ms": 150}}, {"home": {"pass": True, "ms": 1600}})
check("10x slower warns", len(c["slow"]) == 1 and not c["regressions"])

# 7. slow but still fast in absolute terms (40ms -> 500ms) -> no warning
c = prove.compare({"home": {"pass": True, "ms": 40}}, {"home": {"pass": True, "ms": 500}})
check("sub-second slowdown is noise", c["slow"] == [])

# 8. a check that disappeared from current is simply not evaluated
c = prove.compare({"home": P, "gone": P}, {"home": P})
check("removed check is silent", c == {"regressions": [], "still_failing": [], "fixed": [], "slow": [], "failing_new": []})

# 9. default checks: urls -> one GET per url; explicit checks win
check("default checks from urls",
      [x["url"] for x in prove.default_checks({"urls": ["https://a", "https://b"]})] == ["https://a", "https://b"])
check("explicit checks win over urls",
      prove.default_checks({"urls": ["https://a"], "checks": [{"name": "x", "url": "https://x"}]})[0]["name"] == "x")

# 10. run_check: status rule without a server (refused/unknown host) -> fail with detail, no exception
r = prove.run_check({"name": "nowhere", "url": "http://127.0.0.1:9/"})
check("unreachable url fails cleanly", r["pass"] is False and "HTTP 000" in r["detail"])

print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
