#!/usr/bin/env python3
"""Harah's eyes and hands on the apartment network: the AT&T BGW320-500 gateway.

Read side (no login; the gateway's status pages are open on the LAN):

  gateway.py status                 WAN, LAN/DHCP, radios, uptime, in one screen
  gateway.py devices [--json]       every device the gateway knows (MAC, IP, name,
                                    on/off, dhcp/static, link, last seen)
  gateway.py diff                   what changed since the last pass: new MACs,
                                    devices gone, IPs moved. State in
                                    ~/.harah/network-state.json. Exit 1 on change.
  gateway.py vault [--vault PATH]   rewrite the device table in the vault note
                                    Homelab/Network/Devices.md between the
                                    markers, PRESERVING the Owner and Purpose
                                    columns Alex fills in by hand (matched by MAC).

Write side (needs the gateway's Device Access Code, which Alex alone types:
write it, one line, to ~/.harah/gateway-access-code, mode 600):

  gateway.py login                  prove the code works; prints the session state
  gateway.py static <mac> <ip>      fixed DHCP allocation for a device (ipalloc.ha)
  gateway.py static --clear <mac>   back to a dynamic lease

The write side follows the BGW320's form flow (login.ha with the page nonce,
password hashed md5(code + nonce), as the gateway's own login.js does;
ipalloc.ha posts per-MAC allocation).
It is marked EXPERIMENTAL until the first run on a real code confirms the
field names; on any unexpected page it stops and prints what it saw instead
of guessing. Nothing here ever factory-resets, reboots, or changes Wi-Fi.

Set GATEWAY=https://192.168.1.254 to point elsewhere. TLS is self-signed.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

GATEWAY = os.environ.get("GATEWAY", "https://192.168.1.254").rstrip("/")
STATE = Path.home() / ".harah" / "network-state.json"
CODE_FILE = Path.home() / ".harah" / "gateway-access-code"
DEFAULT_VAULT = Path.home() / "lxrbckl" / "Obsidian" / "Homelab" / "Network" / "Devices.md"
MARK_START = "<!-- harah:devices:start -->"
MARK_END = "<!-- harah:devices:end -->"
TIMEOUT = 20

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE
_jar = CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=_ctx),
                                      urllib.request.HTTPCookieProcessor(_jar))


def get(path: str, data: dict | None = None) -> str:
    url = f"{GATEWAY}/cgi-bin/{path}"
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers={"User-Agent": "harah-network/1"})
    with _opener.open(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", "replace")


def strip_tags(s: str) -> str:
    s = re.sub(r"<script.*?</script>|<style.*?</style>", "", s, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return html.unescape(re.sub(r"\s+", " ", s)).strip()


def rows(page: str) -> list[list[str]]:
    """Every <tr> as a list of its non-empty cell texts."""
    page = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, flags=re.S):
        cells = [strip_tags(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, flags=re.S)]
        cells = [c for c in cells if c]
        if cells:
            out.append(cells)
    return out


def kv(page: str) -> dict[str, str]:
    d: dict[str, str] = {}
    for r in rows(page):
        if len(r) >= 2 and r[0] not in d:
            d[r[0]] = r[1]
    return d


# ── read side ────────────────────────────────────────────────────────────────

def status() -> dict:
    sysinfo, bb, lan = kv(get("sysinfo.ha")), kv(get("broadbandstatistics.ha")), kv(get("lanstatistics.ha"))
    return {
        "gateway": {k: sysinfo.get(k) for k in ("Manufacturer", "Model Number", "Software Version", "Time Since Last Reboot")},
        "wan": {k: bb.get(k) for k in ("Broadband Connection", "Broadband IPv4 Address", "Gateway IPv4 Address",
                                        "Primary DNS", "Secondary DNS", "Global Unicast IPv6 Address", "Current Speed (Mbps)")},
        "lan": {k: lan.get(k) for k in ("Device IPv4 Address", "DHCPv4 Netmask", "DHCPv4 Start Address", "DHCPv4 End Address",
                                         "DHCP Leases Allocated", "IP Passthrough Status", "Cascaded Router Status",
                                         "IPv6 Addressing Subnet (including length)")},
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def devices() -> list[dict]:
    """devices.ha is one table per device with rows 'MAC Address', 'IPv4 Address / Name',
    'Last Activity', 'Status', 'Allocation', 'Connection Type', ... Split on the MAC row."""
    page = get("devices.ha")
    out: list[dict] = []
    cur: dict | None = None
    for r in rows(page):
        key = r[0]
        val = " ".join(r[1:]) if len(r) > 1 else ""
        if key == "MAC Address" and re.match(r"^[0-9a-f:]{17}$", val):
            cur = {"mac": val, "ip": "", "name": "", "status": "", "allocation": "", "link": "", "last_seen": "", "ipv6": []}
            out.append(cur)
            continue
        if cur is None:
            continue
        if key == "IPv4 Address / Name":
            m = re.match(r"^(\d+\.\d+\.\d+\.\d+)\s*/\s*(.*)$", val)
            if m:
                cur["ip"], cur["name"] = m.group(1), m.group(2).strip()
            else:
                cur["name"] = val
        elif key == "Name" and not cur["name"]:
            cur["name"] = val
        elif key == "Last Activity":
            cur["last_seen"] = val
        elif key == "Status":
            cur["status"] = val
        elif key == "Allocation":
            cur["allocation"] = val
        elif key == "Connection Type":
            cur["link"] = re.sub(r"\s*(Type: Home|Name: \S+)\s*", " ", val).strip()
        elif key == "IPv6 Address" and val and not val.startswith("fe80"):
            cur["ipv6"].append(val.split()[0])
    return out


def load_state() -> dict:
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {}


def save_state(s: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(s, indent=2))
    tmp.replace(STATE)


def diff() -> int:
    now = {d["mac"]: d for d in devices()}
    st = load_state()
    prev = st.get("devices", {})
    changes = []
    for mac, d in now.items():
        p = prev.get(mac)
        if p is None:
            changes.append(f"NEW      {mac} {d['ip'] or '-':15} {d['name'] or '(no name)'}  via {d['link']}")
        else:
            if d["ip"] and p.get("ip") and d["ip"] != p["ip"]:
                changes.append(f"IP MOVED {mac} {p['ip']} -> {d['ip']}  {d['name']}")
            if d["status"] != p.get("status"):
                changes.append(f"{'ONLINE  ' if d['status'] == 'on' else 'OFFLINE '} {mac} {d['ip'] or '-':15} {d['name']}")
    for mac, p in prev.items():
        if mac not in now:
            changes.append(f"GONE     {mac} {p.get('ip') or '-':15} {p.get('name')}  (dropped from the gateway's list)")
    st["devices"] = now
    st["last_pass"] = time.time()
    hist = st.setdefault("history", [])
    if changes:
        hist.append({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "changes": changes})
        del hist[:-50]
    save_state(st)
    if not prev:
        print(f"baseline: {len(now)} devices recorded; nothing to compare yet")
        return 0
    if changes:
        print("\n".join(changes))
        return 1
    print(f"steady: {len(now)} devices, no change")
    return 0


def vault(path: Path) -> int:
    devs = sorted(devices(), key=lambda d: tuple(int(x) for x in d["ip"].split(".")) if d["ip"] else (999,))
    text = path.read_text() if path.exists() else ""
    # preserve Owner / Purpose by MAC from the existing table
    keep: dict[str, tuple[str, str]] = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 8 and re.match(r"^`?[0-9a-f:]{17}`?$", cells[1]):
            keep[cells[1].strip("`")] = (cells[6], cells[7])
    hdr = ["| IP | MAC | Name (gateway) | Status | Alloc | Link | Owner | Purpose | Last seen |",
           "|---|---|---|---|---|---|---|---|---|"]
    body = []
    for d in devs:
        owner, purpose = keep.get(d["mac"], ("", ""))
        body.append(f"| {d['ip'] or '-'} | `{d['mac']}` | {d['name'] or '-'} | {d['status']} | {d['allocation']} | "
                    f"{d['link']} | {owner} | {purpose} | {d['last_seen']} |")
    table = "\n".join([MARK_START, f"_Regenerated {time.strftime('%Y-%m-%d %-I:%M %p')} by `harah/network/gateway.py vault`. "
                       f"Edit **Owner** and **Purpose** freely; every other column is overwritten from the gateway._", ""] + hdr + body + [MARK_END])
    if MARK_START in text and MARK_END in text:
        new = text[:text.index(MARK_START)] + table + text[text.index(MARK_END) + len(MARK_END):]
    else:
        new = (text.rstrip() + "\n\n" if text else "") + table + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new)
    print(f"vault: {len(devs)} devices written to {path}")
    return 0


# ── write side (EXPERIMENTAL until first run with a real code) ───────────────

def access_code() -> str:
    try:
        code = CODE_FILE.read_text().strip().splitlines()[0].strip()
    except (OSError, IndexError):
        sys.exit(f"no access code: write the gateway's Device Access Code to {CODE_FILE} (chmod 600). Alex types it; Harah never prints it.")
    return code


def _nonce(page: str) -> str | None:
    m = re.search(r"""<input[^>]*name=["']nonce["'][^>]*value=["']([^"']+)["']""", page, flags=re.I | re.S) \
        or re.search(r"""<input[^>]*value=["']([^"']+)["'][^>]*name=["']nonce["']""", page, flags=re.I | re.S)
    return m.group(1) if m else None


def login() -> bool:
    get("home.ha")          # a cold login.ha renders "Cookies must be enabled"; any prior hit fixes it
    page = get("login.ha")
    nonce = _nonce(page)
    if not nonce:
        print("login.ha has no nonce field; page title:", (re.search(r"<title>(.*?)</title>", page, re.S) or [None, "?"])[1])
        return False
    code = access_code()
    # The gateway's own login.js: hashpassword = hex_md5(password + nonce); the
    # clear password field is blanked before submit.
    hashed = hashlib.md5((code + nonce).encode()).hexdigest()
    resp = get("login.ha", {"nonce": nonce, "password": "", "hashpassword": hashed, "Continue": "Continue"})
    ok = "Logout" in resp or "logout.ha" in resp
    print("login:", "ok" if ok else "FAILED (code wrong, or the form differs; see the page title)")
    if not ok:
        print("  title:", (re.search(r"<title>(.*?)</title>", resp, re.S) or [None, "?"])[1])
    return ok


def static(mac: str, ip: str | None, clear: bool = False) -> int:
    if not login():
        return 1
    page = get("ipalloc.ha")
    m = _nonce(page)
    if not m:
        print("ipalloc.ha: no nonce after login; not posting. First 300 chars of text:", strip_tags(page)[:300])
        return 1
    # The BGW320 ipalloc form names its per-device selects by MAC. Find the
    # field for this MAC; if the page has none, stop and show what it does have.
    fields = re.findall(r'name="([^"]*' + re.escape(mac.replace(":", "")) + r'[^"]*)"', page, flags=re.I)
    if not fields:
        print(f"ipalloc.ha has no field for {mac}. Fields on the page:", sorted(set(re.findall(r'name="([^"]+)"', page)))[:40])
        return 1
    print("EXPERIMENTAL: found form field(s) for this MAC:", fields)
    print("Not posting yet: this path needs its field layout confirmed on a real gateway once.")
    print(f"Requested: {mac} -> {'dynamic' if clear else ip}. Do it in the UI (Home Network > IP Allocation) and tell Harah; the next `vault` pass records it.")
    return 2


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, args = argv[0], argv[1:]
    if cmd == "status":
        print(json.dumps(status(), indent=2))
        return 0
    if cmd == "devices":
        devs = devices()
        if "--json" in args:
            print(json.dumps(devs, indent=2))
        else:
            for d in sorted(devs, key=lambda d: d["ip"] or "zz"):
                print(f"{d['ip'] or '-':15} {d['mac']}  {d['status']:3} {d['allocation']:6} {d['link']:22} {d['name']}")
        return 0
    if cmd == "diff":
        return diff()
    if cmd == "vault":
        p = Path(args[args.index("--vault") + 1]) if "--vault" in args else DEFAULT_VAULT
        return vault(p)
    if cmd == "login":
        return 0 if login() else 1
    if cmd == "static":
        if args and args[0] == "--clear":
            return static(args[1], None, clear=True)
        if len(args) != 2:
            print("usage: gateway.py static <mac> <ip> | static --clear <mac>")
            return 2
        return static(args[0], args[1])
    print(f"unknown command {cmd!r}")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
