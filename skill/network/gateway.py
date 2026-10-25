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
  gateway.py static <mac> <ip>      fixed DHCP allocation for a device (ipalloc.ha);
                                    the address must be inside the DHCP pool, the
                                    only range the gateway offers. --dry-run stops
                                    before Save.
  gateway.py static --clear <mac>   back to a dynamic lease

The write side follows the BGW320's form flow (login.ha with the page nonce,
password hashed md5(code + nonce), as the gateway's own login.js does;
ipalloc.ha posts per-MAC allocation).
Verified against the real form 2026-10-25. On any unexpected page it stops
and prints what it saw instead of guessing. Nothing here ever factory-resets,
reboots, or changes Wi-Fi.

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
    get("login.ha", {"nonce": nonce, "password": "", "hashpassword": hashed, "Continue": "Continue"})
    # A good login lands on Status with no "Logout" marker; the proof is that a
    # gated page now renders instead of the login wall.
    probe = get("ipalloc.ha")
    title = (re.search(r"<title>(.*?)</title>", probe, re.S) or [None, "?"])[1].strip()
    ok = title != "Login" and "Access Code Required" not in probe
    print("login:", "ok" if ok else "FAILED (code wrong, or the form differs)")
    if not ok:
        print("  ipalloc title after login:", title)
    return ok


def static(mac: str, ip: str | None, clear: bool = False, dry: bool = False) -> int:
    """Fixed DHCP allocation on the BGW320 (Home Network > IP Allocation).
    The gateway's own flow, verified 2026-10-25: POST Allocate_<mac> to open the
    device's editor; it renders a <select name="alloc_<mac>"> whose options are
    "normal" (address from the DHCP pool) and every address IN THE POOL as
    "Private fixed"; POST alloc_<mac>=<choice> with Save. Addresses outside the
    pool are not offered, so a fixed address must be inside .64-.253 here."""
    mac = mac.lower()
    want = "normal" if clear else ip
    if not login():
        return 1
    page = get("ipalloc.ha")
    nonce = _nonce(page)
    if not nonce or f'name="Allocate_{mac}"' not in page:
        known = sorted(set(re.findall(r'name="Allocate_([0-9a-f:]{17})"', page)))
        print(f"{mac} is not on the gateway's allocation list. Known: {known}")
        return 1
    editor = get("ipalloc.ha", {"nonce": nonce, f"Allocate_{mac}": "Allocate"})
    sel = re.search(r'<select[^>]*name="alloc_' + re.escape(mac) + r'"[^>]*>(.*?)</select>', editor, re.S)
    if not sel:
        print("the editor did not render a select for this MAC; not posting. Page text:", strip_tags(editor)[:300])
        return 1
    options = dict(re.findall(r'<option[^>]*value="([^"]+)"[^>]*>(.*?)</option>', sel.group(1), re.S))
    current = next((m for m in re.finditer(r'<option([^>]*)>', sel.group(1)) if "selected" in m.group(1).lower()), None)
    # no "selected" attribute means the browser would show the first option, which is "normal"
    current_val = (re.search(r'value="([^"]+)"', current.group(1)).group(1) if current else next(iter(options), None))
    if want not in options:
        pool = [k for k in options if k != "normal"]
        print(f"{want} is not offered for {mac}. The gateway only allows addresses in its DHCP pool: "
              f"{pool[0] if pool else '?'} .. {pool[-1] if pool else '?'} (or 'normal').")
        return 1
    label = strip_tags(options[want])
    print(f"{mac}: {(strip_tags(options.get(current_val, current_val)) if current_val else 'current unknown')}  ->  {label}")
    if dry:
        print("dry run: not saving")
        return 0
    nonce2 = _nonce(editor) or nonce
    get("ipalloc.ha", {"nonce": nonce2, f"alloc_{mac}": want, "Save": "Save"})
    after = get("ipalloc.ha")
    row = re.search(r'<tr[^>]*>(?:(?!</tr>).)*' + re.escape(mac) + r'(?:(?!</tr>).)*</tr>', after, re.S)
    row_text = strip_tags(row.group(0)) if row else "(row not found)"
    ok = ("Private fixed" in row_text and (clear is False and (want in row_text))) or (clear and "DHCP" in row_text)
    print("gateway now shows:", row_text)
    print("saved" if ok else "WARNING: the row does not show the requested allocation; check the UI")
    return 0 if ok else 1


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
        dry = "--dry-run" in args
        args = [a for a in args if a != "--dry-run"]
        if args and args[0] == "--clear" and len(args) == 2:
            return static(args[1], None, clear=True, dry=dry)
        if len(args) != 2:
            print("usage: gateway.py static <mac> <ip> [--dry-run] | static --clear <mac> [--dry-run]")
            return 2
        return static(args[0], args[1], dry=dry)
    print(f"unknown command {cmd!r}")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
