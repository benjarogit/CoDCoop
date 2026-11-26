#!/usr/bin/env python3
"""Install or repair a complete, pinned CoDCoop 0.6 campaign suite.

Development packages require an existing game and a target-OS payload:
    python3 tools/install-linux.py --game PATH --suite-source PAYLOAD
    python3 tools/install-linux.py --game PATH --check
    python3 tools/install-linux.py --game PATH --rollback

The graphical installer imports this same backend. A legacy 0.5.4 archive may
supply base data, but never constitutes a successful complete 0.6 installation.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from frozen_runtime import external_environment
try:
    from extract_installer import resources  # noqa: E402  (same folder, optional)
except Exception:  # pragma: no cover - only needed for --release
    resources = None

REPO = "benjarogit/CoDCoop"
TAG = os.environ.get("COD_COOP_TAG", "v0.5.4")
RELEASE_URL = "https://github.com/%s/releases/download/%%s/Install-CoD-Coop.exe" % REPO
API_URL = "https://api.github.com/repos/%s/releases" % REPO

# The ready package (United Offensive 1.51 + mod) lives on MEGA. The link is in
# README.md / docs/linux.md; override it here if you mirror the file:
READY_URL = os.environ.get("COD_READY_URL", "")
READY_SIZE = 1036938510
READY_SHA = "c5f22a300a4186ad07755e704606bde9e2dfc9fbb3c15ac214ea7d96ec5b2f3d"

EXE_SIZE = 1716224          # Call of Duty 1.5 (CoDSP.exe)
EXE_SHA = "c755c7da411c87039ade462a2299402c3c4ca5c4fc4f1ae5cea6e25b05c69f47"

# Optional German language pack: German text and voices for Call of Duty and
# United Offensive. It replaces Main/localized_*pak*.pk3 and uo/localized_*pakuo*.pk3
# (the file names stay "english" - the engine loads the language from that folder).
GERMAN_URL = os.environ.get(
    "COD_GERMAN_URL",
    "https://github.com/%s/releases/download/%%s/CoD-UO-German-Language.zip" % REPO)
GERMAN_SIZE = 657419767
GERMAN_SHA = "5f1113e82aa11c12c3769275a5048a5e3d0fe5e38fb5929c1305883cdf515b5c"

# Optional extras: Singleplayer Improved 1.5, United Fronts 1.1 beta and the
# official UO map pack. One ZIP, because the map pack is already part of the
# SP Improved download and the Kar98k FOV fix is only 25 KB.
EXTRAS_URL = os.environ.get(
    "COD_EXTRAS_URL",
    "https://github.com/%s/releases/download/%%s/CoD-SP-Extras.zip" % REPO)
EXTRAS_SIZE = 922302300
EXTRAS_SHA = "9630d73e2e87331f8a115816cfda38636c10917211419a11d0d72b49c1366d3c"

# Graphics presets written into config.cfg (Call of Duty 1 / United Offensive).
# Values follow the PCGamingWiki fixes: max model detail, no LOD pop-up and
# fewer dynamic entity lights (the latter fixes stuttering while shooting).
QUALITY = {
    "niedrig": {
        "r_picmip": "3", "r_picmip2": "1", "r_lodbias": "2", "r_lodscale": "2",
        "r_lodViewDist": "-1", "r_detailtextures": "0", "r_dlight": "0",
        "r_fastsky": "1", "r_flares": "0",
        "r_ext_texture_filter_anisotropic": "1", "r_texturebits": "16",
        "r_colorbits": "16", "r_depthbits": "16", "cg_shadows": "0",
        "r_maxEntLights": "4",
    },
    "mittel": {
        "r_picmip": "1", "r_picmip2": "0", "r_lodbias": "0", "r_lodscale": "1",
        "r_lodViewDist": "-1", "r_detailtextures": "1", "r_dlight": "1",
        "r_fastsky": "0", "r_flares": "1",
        "r_ext_texture_filter_anisotropic": "4", "r_texturebits": "32",
        "r_colorbits": "32", "r_depthbits": "24", "cg_shadows": "0",
        "r_maxEntLights": "4",
    },
    "hoch": {
        "r_picmip": "0", "r_picmip2": "0", "r_lodbias": "-1", "r_lodscale": "0",
        "r_lodViewDist": "-1", "r_detailtextures": "1", "r_dlight": "1",
        "r_fastsky": "0", "r_flares": "1",
        "r_ext_texture_filter_anisotropic": "16", "r_texturebits": "32",
        "r_colorbits": "32", "r_depthbits": "24", "cg_shadows": "1",
        "r_maxEntLights": "8",
    },
}

RESOLUTIONS = ["1280x720", "1600x900", "1920x1080", "2560x1440", "3440x1440", "3840x2160"]
FOVS = [70, 75, 80, 85, 90, 96, 100, 110, 120]

FILES = ["ddraw.dll", "codcoop_core.dll", "Main/pakz_coop.pk3", "CoD Coop README.txt", "steam_api.dll"]

# v0.5.2, the release this script was written against (mod-only fallback)
KNOWN = {
    "ddraw.dll": "db577adb35d94535ce42c8ae423bdbf39e7a1e36775dd6750fb084bf99832d45",
    "codcoop_core.dll": "2dc3815fbe78e42a371d43c009128661763b0462af82a7637a83392631d5f064",
    "steam_api.dll": "e0ccfcdde7bbba55dba4c19007299018a2cf86f92c7bc1df4af134c65dbf8003",
    "Main/pakz_coop.pk3": "fe54ce75c23dbfc8fd9379705a81a94c442ace22a1d5c04953c06ed9552e3dfc",
    "CoD Coop README.txt": "2b52cec91d70c6ebfd59647fa44e66dabd5c56124bd6f64dfec90ff0b852f4da",
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def find(parent, name):
    """Case-insensitive child lookup: on Linux the game may have Main/ or main/."""
    try:
        for entry in os.listdir(parent):
            if entry.lower() == name.lower():
                return os.path.join(parent, entry)
    except OSError:
        pass
    return None


def say(*a):
    print(*a, flush=True)


def install_progress(english, german, percent=-1):
    if os.environ.get('CODCOOP_INSTALL_PROGRESS') == '1':
        say('CODCOOP_PROGRESS ' + json.dumps([english, german, percent]))
    else:
        say(english)


def die(msg):
    say("ERROR: " + msg)
    sys.exit(2)


def read_configure_csv(game):
    """configure.csv holds the hardware table; it normally lives inside Main/pak0.pk3."""
    main = find(game, "Main") or game
    loose = find(main, "configure.csv")
    if loose:
        with open(loose, "rb") as f:
            return f.read()
    try:
        names = sorted(os.listdir(main))
    except OSError:
        return None
    for name in names:
        if not name.lower().endswith(".pk3"):
            continue
        try:
            with zipfile.ZipFile(os.path.join(main, name)) as z:
                for entry in z.namelist():
                    if entry.lower() == "configure.csv":
                        return z.read(entry)
        except (OSError, zipfile.BadZipFile):
            continue
    return None


def config_sum(data):
    """The checksum the engine compares with sys_configSum (28 bits, +1)."""
    value = 0
    for byte in data:
        value = (value * 31337 + (byte - 256 if byte > 127 else byte)) & 0xFFFFFFFF
    return (value & 0x0FFFFFFF) + 1


def repair_config_sum(game):
    """Keep the "configuration updated" prompt away (docs/linux.md, section 5)."""
    main = find(game, "Main")
    if not main:
        return
    cfg = find(main, "config.cfg")
    data = read_configure_csv(game) if cfg else None
    if not data:
        return
    want = config_sum(data)
    try:
        with open(cfg, "r", encoding="latin-1") as f:
            lines = f.read().splitlines()
    except OSError:
        return
    for i, line in enumerate(lines):
        m = re.match(r'\s*seta\s+sys_configSum\s+"?(-?\d+)"?\s*$', line, re.I)
        if not m:
            continue
        if int(m.group(1)) == want:
            say("config.cfg: sys_configSum is correct (%d)" % want)
        else:
            lines[i] = 'seta sys_configSum "%d"' % want
            with open(cfg, "w", encoding="latin-1") as f:
                f.write("\n".join(lines) + "\n")
            say("config.cfg: sys_configSum %s -> %d" % (m.group(1), want))
        return
    say("config.cfg: no sys_configSum yet (the game writes it on the first start)")


def steam_apps_dirs():
    """steamapps folders of the local Steam installation (all libraries)."""
    home = os.path.expanduser("~")
    out = []
    for base in (os.path.join(home, ".local/share/Steam"), os.path.join(home, ".steam/steam")):
        out.append(os.path.join(base, "steamapps"))
        vdf = os.path.join(base, "steamapps/libraryfolders.vdf")
        try:
            with open(vdf, errors="replace") as f:
                for line in f:
                    m = re.search(r'"path"\s+"([^"]+)"', line)
                    if m:
                        out.append(os.path.join(m.group(1), "steamapps"))
        except OSError:
            pass
    return out


def ankergames_dirs():
    """Game folders from the AnkerGames launcher library (games.<id>.root)."""
    out = []
    base = os.path.join(os.path.expanduser("~"), ".config", "net.ankergames.launcher")
    try:
        with open(os.path.join(base, "library.json"), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return out
    games = data.get("games") if isinstance(data, dict) else None
    if isinstance(games, dict):
        entries = games.values()
    elif isinstance(games, list):
        entries = games
    else:
        entries = []
    for g in entries:
        root = g.get("root") if isinstance(g, dict) else None
        if isinstance(root, str) and root:
            out.append(root)
    return out


def detect_games():
    """Folders that contain CoDSP.exe: Steam (all libraries), AnkerGames and the current folder."""
    found = []
    for apps in steam_apps_dirs():
        found.append(os.path.join(apps, "common", "Call of Duty"))
    found += ankergames_dirs()
    found.append(os.getcwd())
    # the ready package itself has game/CoDSP.exe - that is not an installation
    package = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "game"))
    out = []
    for d in found:
        d = os.path.abspath(os.path.expanduser(d))
        if not os.path.isdir(d):
            continue
        # the launcher root may be one level above the game folder (…/Call of Duty (2003)-3278/Call of Duty)
        for cand in [d] + [os.path.join(d, n) for n in sorted(os.listdir(d))]:
            cand = os.path.abspath(cand)
            if cand == package or cand.startswith(package + os.sep):
                continue
            if os.path.isdir(cand) and find(cand, "CoDSP.exe") and cand not in out:
                out.append(cand)
    # a real installation has the game data; put those first (the package folder has only the exe)
    out.sort(key=lambda p: 0 if os.path.isdir(os.path.join(p, "Main")) else 1)
    return out


def spacewar_installed():
    return any(os.path.exists(os.path.join(d, "appmanifest_480.acf")) for d in steam_apps_dirs())


def offer_spacewar():
    """Spacewar (AppID 480) is what the mod uses to talk to Steam; it is free but has to be installed once."""
    url = "steam://install/480"
    if spacewar_installed():
        say("Spacewar (AppID 480): installed (Steam invites ready once Steam runs).")
        return
    say("Spacewar (AppID 480) is not installed: Steam invites need it once, it is free.")
    if not sys.stdin.isatty():
        say("Install it later with: " + url)
        return
    try:
        ans = input("Open Steam now to install Spacewar? [Y/n] ").strip().lower()
    except EOFError:
        ans = "n"
    if ans not in ("", "y", "yes", "j", "ja"):
        say("Skipped. You can install it later with: " + url)
        return
    for cmd in (["xdg-open", url], ["steam", url]):
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=external_environment())
            say("asked Steam to install Spacewar (" + url + ")")
            return
        except FileNotFoundError:
            continue
    say("could not open Steam - open this link: " + url)


def download(url, dest, expected_sha=None, expected_size=None):
    """Resume a pinned download; never promote partial or unverified bytes."""
    if not expected_sha or not expected_size:
        raise ValueError("a pinned SHA-256 and size are required for downloads")
    name = os.path.basename(dest)

    def verify():
        install_progress(f'Verifying {name}', f'{name} wird geprüft')

    def report(done):
        percent = done * 100 // expected_size
        size = f'{done / (1 << 20):.1f} / {expected_size / (1 << 20):.1f} MiB ({percent}%)'
        install_progress(f'Downloading {name}  {size}', f'Download {name}  {size}', percent)

    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    if os.path.isfile(dest) and os.path.getsize(dest) == expected_size:
        verify()
        if sha256(dest) == expected_sha:
            return dest
    part = dest + ".part"
    offset = os.path.getsize(part) if os.path.isfile(part) else 0
    if offset > expected_size:
        os.unlink(part)
        offset = 0
    if offset == expected_size:
        verify()
        if sha256(part) == expected_sha:
            os.replace(part, dest)
            return dest
        os.unlink(part)
        offset = 0
    headers = {"User-Agent": "cod-coop-suite-installer/0.6", "Accept-Encoding": "identity"}
    if offset:
        headers["Range"] = "bytes=%d-" % offset
    report(offset)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        partial = r.status == 206
        response_end = expected_size
        if partial:
            content_range = r.headers.get("Content-Range", "")
            match = re.fullmatch(r"bytes ([0-9]+)-([0-9]+)/([0-9]+)", content_range.strip())
            if (not match or int(match[1]) != offset or int(match[3]) != expected_size
                    or not offset <= int(match[2]) < expected_size):
                raise ValueError("server returned an invalid resume range")
            response_end = int(match[2]) + 1
        elif r.status != 200:
            raise ValueError("unexpected download response: %s" % r.status)
        if not partial and offset:
            offset = 0  # A server ignoring Range must replace, never append.
            report(offset)
        content_length = r.headers.get("Content-Length")
        if content_length is not None and (not re.fullmatch(r"[0-9]+", content_length.strip())
                                           or int(content_length) != response_end - offset):
            raise ValueError("server returned an invalid download length")
        done, last = offset, offset * 100 // expected_size
        with open(part, "ab" if partial else "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                done += len(chunk)
                if done > response_end:
                    raise ValueError("download exceeds the declared response range")
                f.write(chunk)
                pct = done * 100 // expected_size
                if pct >= last + 5 or (pct == 100 and last != 100):
                    report(done)
                    last = pct
    if os.path.getsize(part) != expected_size:
        raise ValueError("download incomplete; rerun to resume")
    verify()
    if sha256(part) != expected_sha:
        os.unlink(part)
        raise ValueError("download checksum mismatch; partial download removed")
    os.replace(part, dest)
    return dest


def latest_tag():
    try:
        req = urllib.request.Request(API_URL, headers={"User-Agent": "cod-coop-linux-installer"})
        with urllib.request.urlopen(req, timeout=30) as r:
            for rel in json.load(r):
                if not rel.get("draft"):
                    return rel["tag_name"]
    except Exception as e:  # offline / rate limit: fall back to the version this script knows
        say("could not ask GitHub for the latest release (%s), using v0.5.2" % e)
    return "v0.5.2"


def from_release(tag, cache):
    """Download Install-CoD-Coop.exe and extract it into the cache (mod only)."""
    if resources is None:
        die("extract_installer.py is missing - cannot read the GitHub installer")
    tag = tag or latest_tag()
    os.makedirs(cache, exist_ok=True)
    exe = os.path.join(cache, "Install-CoD-Coop-%s.exe" % tag)
    if not os.path.exists(exe):
        download(RELEASE_URL % tag, exe)
    out = os.path.join(cache, "mod-%s" % tag)
    shutil.rmtree(out, ignore_errors=True)
    with open(exe, "rb") as f:
        res = resources(f.read())
    dest = {1: "ddraw.dll", 2: "codcoop_core.dll", 3: "Main/pakz_coop.pk3", 4: "CoD Coop README.txt",
            5: "steam_api.dll", 6: "uo/pakz_coop.pk3"}
    for rid, name in dest.items():
        if rid not in res:
            continue
        path = os.path.join(out, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(res[rid])
    say("extracted %s to %s" % (tag, out))
    return out, tag


def from_build(build):
    """A build/ folder only has the DLLs; the menu pak and README come from the repository."""
    missing = [f for f in ("ddraw.dll", "codcoop_core.dll") if not os.path.exists(os.path.join(build, f))]
    if missing:
        die("%s is missing - run ./build.sh first" % ", ".join(missing))
    return build


def build_extras(build, pak):
    """Repository files that replace the ones the Windows installer embeds."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    alt = {}
    if pak:
        alt["Main/pakz_coop.pk3"] = pak
    else:
        for rel in ("game/Main/pakz_coop.pk3", "game/main/pakz_coop.pk3"):
            if os.path.exists(os.path.join(here, rel)):
                alt["Main/pakz_coop.pk3"] = os.path.join(here, rel)
                break
        else:
            die("no menu pak found - run ./build.sh --install once (it builds game/Main/pakz_coop.pk3)\n"
                "       or pass --pak /path/to/pakz_coop.pk3")
    if not os.path.exists(alt["Main/pakz_coop.pk3"]):
        die("no such pak: %s" % alt["Main/pakz_coop.pk3"])
    if not pak_ok(alt["Main/pakz_coop.pk3"]):
        die("%s is not a CoD Coop menu pak - rebuild it with ./build.sh --install" % alt["Main/pakz_coop.pk3"])
    alt["CoD Coop README.txt"] = os.path.join(here, "installer/README.txt")
    uo = os.path.join(here, "game/uo/pakz_coop.pk3")
    if os.path.exists(uo):
        alt["uo/pakz_coop.pk3"] = uo
    return alt


def iter_files(root):
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            src = os.path.join(dirpath, name)
            rel = os.path.relpath(src, root).replace(os.sep, "/")
            yield src, rel


def find_game_tree(root):
    """Find the folder that holds CoDUOSP.exe / CoD Coop README.txt inside an extracted ZIP."""
    for candidate in (os.path.join(root, "game"), root):
        if os.path.exists(os.path.join(candidate, "CoDUOSP.exe")):
            return candidate
    for dirpath, dirnames, filenames in os.walk(root):
        if "CoDUOSP.exe" in filenames:
            return dirpath
        # Do not descend into the game data more than needed.
        dirnames[:] = [d for d in dirnames if d.lower() not in ("uo", "main")]
    return None


def load_manifest(source):
    """manifest.json sits next to game/ (or inside the extracted ZIP root)."""
    for base in (os.path.dirname(source), source, os.path.dirname(os.path.dirname(source))):
        p = os.path.join(base, "manifest.json")
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as f:
                    return json.load(f)
            except (OSError, ValueError):
                return None
    return None


def plan(game, source, alt=None):
    """Return (source file, destination relative path) pairs for the mod-only fallback."""
    alt = alt or {}
    todo = []
    for name in FILES:
        src = alt.get(name) or os.path.join(source, name)
        if not os.path.exists(src):
            if name == "steam_api.dll":
                say("NOTE: steam_api.dll is not in the source - Steam invites will be unavailable (IP works)")
                continue
            die("%s is missing in %s" % (name, src))
        todo.append((src, name))
    uo = alt.get("uo/pakz_coop.pk3") or os.path.join(source, "uo/pakz_coop.pk3")
    if find(game, "CoDUOSP.exe") and os.path.exists(uo):
        todo.append((uo, "uo/pakz_coop.pk3"))
    return todo


def backup(path):
    if not os.path.exists(path):
        return None
    bak = path + ".bak"
    n = 1
    while os.path.exists(bak):
        bak = "%s.bak.%d" % (path, n)
        n += 1
    shutil.copy2(path, bak)
    return bak


def target(game, rel):
    """Main/ vs main/: reuse the folder that exists, create Main/ otherwise."""
    parts = rel.split("/")
    if len(parts) == 1:
        return os.path.join(game, rel)
    folder = find(game, parts[0]) or os.path.join(game, parts[0])
    return os.path.join(folder, *parts[1:])


def install(game, todo, dry, force, known=True, manifest=None):
    manifest = manifest or {}
    files = manifest.get("files", {})
    for src, rel in todo:
        dst = target(game, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        same = os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(src) and sha256(dst) == sha256(src)
        if same:
            say("  unchanged  %s" % rel)
            continue
        if dry:
            say("  [dry-run]  %s -> %s" % (rel, dst))
            continue
        bak = backup(dst)
        shutil.copy2(src, dst)
        got = sha256(dst)
        want = files.get(rel, {}).get("sha256")
        if want and got != want:
            say("WARNING: %s was copied but its sha256 is %s, expected %s" % (rel, got[:16], want[:16]))
        say("  installed  %s%s" % (rel, "  (backup: %s)" % os.path.basename(bak) if bak else ""))
        if known and not force and rel in KNOWN and got != KNOWN[rel]:
            say("WARNING: %s does not match the v0.5.2 build" % rel)


def pak_ok(path):
    """The menu pak is the game's main.menu with the Co-op button and window spliced in (make_ui.py)."""
    try:
        with zipfile.ZipFile(path) as z:
            menu = z.read("ui/main.menu").decode("latin-1", "replace")
    except (OSError, KeyError, zipfile.BadZipFile):
        return False
    return "ui_coop_paused" in menu and re.search(r"name\s+coop\b", menu) is not None


def pak_hosting_fix(path):
    """True if the pak also contains the hosting-state fix (mod 0.5.2+); older paks work but mislabel the menu."""
    try:
        with zipfile.ZipFile(path) as z:
            return "ui_coop_hosting" in z.read("ui/main.menu").decode("latin-1", "replace")
    except (OSError, KeyError, zipfile.BadZipFile):
        return False


def uo_version(game):
    p = target(game, "uo/version.inf")
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="latin-1") as f:
            for line in f:
                m = re.match(r"\s*ExtVersion\s*=\s*(\S+)", line, re.I)
                if m:
                    return m.group(1)
    except OSError:
        pass
    return None


def check(game, manifest=None):
    ok = True

    def row(name, value, good):
        nonlocal ok
        say("  %-38s %s" % (name, value))
        if not good:
            ok = False

    exe = find(game, "CoDSP.exe")
    if not exe:
        row("CoDSP.exe", "MISSING", False)
    else:
        size = os.path.getsize(exe)
        row("CoDSP.exe (1.5 = %d B)" % EXE_SIZE, "%d B" % size, size == EXE_SIZE)
    for name in ("ddraw.dll", "codcoop_core.dll"):
        p = target(game, name)
        row(name, "ok" if os.path.exists(p) else "MISSING", os.path.exists(p))
    row("steam_api.dll (Steam invites)", "ok" if os.path.exists(target(game, "steam_api.dll"))
        else "missing (IP games work)", True)
    pak = target(game, "Main/pakz_coop.pk3")
    if not os.path.exists(pak):
        row("Main/pakz_coop.pk3", "MISSING", False)
    else:
        row("Main/pakz_coop.pk3", "ok" if pak_ok(pak) else "not a CoD Coop menu pak", pak_ok(pak))
        if pak_ok(pak) and not pak_hosting_fix(pak):
            say("  %-38s %s" % ("  (menu)", "old menu pak - the hosting fix needs a newer release/build"))
    uo = find(game, "CoDUOSP.exe")
    if uo:
        row("United Offensive", "ok" if os.path.exists(target(game, "uo/pakz_coop.pk3")) else "pak missing",
            os.path.exists(target(game, "uo/pakz_coop.pk3")))
        ver = uo_version(game)
        row("United Offensive version", ver or "unknown", ver == "1.51")
        upak = target(game, "uo/pakz_coop.pk3")
        if os.path.exists(upak) and not pak_hosting_fix(upak):
            say("  %-38s %s" % ("  (menu)", "old UO menu pak - rebuild it with tools/make_ui.py"))
    if manifest:
        files = manifest.get("files", {})
        bad = []
        for rel, info in files.items():
            p = target(game, rel)
            if not os.path.exists(p):
                bad.append("%s (missing)" % rel)
            elif info.get("size") and os.path.getsize(p) != info["size"]:
                bad.append("%s (size)" % rel)
            elif info.get("sha256") and sha256(p) != info["sha256"]:
                bad.append("%s (sha256)" % rel)
        row("ready package files (%d)" % len(files), "ok" if not bad else "%d bad" % len(bad), not bad)
        for b in bad[:8]:
            say("    %s" % b)
    say("")
    say("  complete" if ok else "  incomplete - see above")
    return 0 if ok else 1


def exe_help(game, size):
    say("""

  ---------------------------------------------------------------------------
  Call of Duty 1.5 is missing

  expected:  %s/CoDSP.exe  (%d bytes)
  found:     %d bytes - that is the version your launcher installed, not 1.5

  A) Official patch (recommended)
     https://www.moddb.com/games/call-of-duty/downloads/call-of-duty-v15-patch
     Run it and choose the game folder above as the target.

  B) Copy CoDSP.exe (1,716,224 bytes) from a PC where the game is already 1.5
     (USB stick / network), then copy it here as CoDSP.exe.

  C) Launcher that already ships 1.5
     Point the launcher at this folder, or use its "verify files" option.

  The ready package also contains optional/patches/CoD_1.5_Patch.exe and
  optional/patches/codsp.exe if you need them. Nothing was written.
  Then run this script again. --allow-incomplete installs the mod anyway.
  ---------------------------------------------------------------------------
""" % (game, EXE_SIZE, size))


def extract_archive(path):
    tmp = tempfile.mkdtemp(prefix="cod-coop-ready-")
    say("extracting %s to %s" % (path, tmp))
    with zipfile.ZipFile(path) as z:
        z.extractall(tmp)
    return tmp


def mega_download(dest):
    """Use mega-get if the user already has it. Never install it automatically."""
    exe = shutil.which("mega-get")
    if not READY_URL:
        say("The MEGA link is not set in this script (see README.md).")
        say("Download the ZIP in your browser, then run this script again with")
        say("  --archive <downloaded.zip>")
        return None
    if not exe:
        say("mega-get is not installed - download the ZIP in your browser:")
        say("  " + READY_URL)
        say("Then run this script again with --archive <downloaded.zip>.")
        return None
    say("downloading with mega-get (this can take a while, ~1.1 GiB)")
    subprocess.check_call([exe, READY_URL, dest], env=external_environment())
    # mega-get writes the file with the name from MEGA; find it.
    for name in os.listdir(dest):
        if name.lower().endswith(".zip"):
            return os.path.join(dest, name)
    return None


# ---------------------------------------------------------------------------
# Interactive setup: what the installer found, where to install, language,
# player name, resolution, fullscreen, FOV and graphics quality.
# ---------------------------------------------------------------------------

def is_interactive():
    try:
        return sys.stdin.isatty()
    except (AttributeError, OSError):
        return False


def ask(prompt, default="", choices=None):
    """Ask on the terminal; without a terminal (curl | sh) the default is used."""
    if not is_interactive():
        return default
    while True:
        try:
            raw = input(prompt).strip()
        except EOFError:
            return default
        if not raw:
            return default
        if choices:
            low = raw.lower()
            for c in choices:
                if low == c.lower():
                    return c
            if len(raw) == 1 and raw.isdigit():
                try:
                    return choices[int(raw) - 1]
                except IndexError:
                    pass
            say("  Bitte eine der Optionen: " + ", ".join(choices))
            continue
        return raw


def ask_yes(prompt, default=True):
    if not is_interactive():
        return default
    default_text = "J/n" if default else "j/N"
    while True:
        try:
            raw = input("%s [%s] " % (prompt, default_text)).strip().lower()
        except EOFError:
            return default
        if not raw:
            return default
        if raw in ("j", "ja", "y", "yes"):
            return True
        if raw in ("n", "nein", "no"):
            return False


def _run(cmd, timeout=5):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=external_environment()).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def sys_resolution():
    """Desktop resolution (X11, Wayland or a sane fallback)."""
    best = None
    for line in _run(["xrandr", "--current"]).splitlines():
        m = re.match(r"\s+(\d+)x(\d+)\s+.*\*", line)
        if m:
            w, h = int(m.group(1)), int(m.group(2))
            if not best or w * h > best[0] * best[1]:
                best = (w, h)
    if best:
        return "%dx%d" % best
    m = re.search(r"dimensions:\s+(\d+)x(\d+)", _run(["xdpyinfo"]))
    if m:
        return "%sx%s" % (m.group(1), m.group(2))
    for line in _run(["wlr-randr"]).splitlines():
        m = re.match(r"\s*(\d+)x(\d+)\s+px.*current", line)
        if m:
            return "%sx%s" % (m.group(1), m.group(2))
    return "1920x1080"


def sys_ram_gb():
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return round(int(line.split()[1]) / 1048576.0, 1)
    except OSError:
        pass
    return 8.0


def sys_gpu():
    for line in _run(["lspci"]).splitlines():
        if re.search(r"(VGA compatible controller|3D controller|Display controller)", line):
            return line.split(": ", 1)[-1].strip()
    try:
        with open("/sys/class/dmi/id/product_name") as f:
            product = f.read().strip()
    except OSError:
        product = ""
    if product in ("Jupiter", "Galileo"):
        return "Steam Deck"
    return "unbekannt"


def auto_quality(ram, gpu):
    g = gpu.lower()
    weak = ("intel", "hd graphics", "gma", "geforce 6", "geforce 7", "radeon 9",
            "xpress", "via ", "steam deck")
    mid = ("geforce 8", "geforce 9", "gt 2", "gt 4", "gt 6", "gt 7",
           "hd 4", "hd 5", "hd 6", "hd 7", "uhd")
    if ram < 4 or any(x in g for x in weak):
        return "niedrig"
    if ram < 8 or any(x in g for x in mid):
        return "mittel"
    return "hoch"


def system_info():
    ram = sys_ram_gb()
    gpu = sys_gpu()
    return {"resolution": sys_resolution(), "ram": ram, "gpu": gpu,
            "quality": auto_quality(ram, gpu)}


def steam_common_dirs():
    return {os.path.abspath(os.path.join(a, "common", "Call of Duty")) for a in steam_apps_dirs()}


def installation_info(path):
    exe = find(path, "CoDSP.exe")
    size = os.path.getsize(exe) if exe else 0
    main = find(path, "Main")
    uo = find(path, "uo")
    german = bool(main and os.path.exists(os.path.join(main, ".cod-coop-german")))
    if not german and main:
        try:
            german = any(n.lower().startswith("localized_german_pak") for n in os.listdir(main))
        except OSError:
            pass
    if not german and uo:
        try:
            german = any("german" in n.lower() for n in os.listdir(uo))
        except OSError:
            pass
    kind = "portable"
    absolute = os.path.abspath(path)
    if absolute in steam_common_dirs():
        kind = "Steam"
    else:
        for d in ankergames_dirs():
            d = os.path.abspath(os.path.expanduser(d))
            if absolute == d or absolute.startswith(d + os.sep):
                kind = "AnkerGames"
                break
    return {
        "path": path,
        "kind": kind,
        "version": "1.5" if size == EXE_SIZE else ("%d B" % size if size else "?"),
        "uo": bool(find(path, "CoDUOSP.exe")),
        "german": german,
    }


def print_detection(found, info):
    say("")
    say("System:   %s, %s GB RAM, %s" % (info["resolution"], info["ram"], info["gpu"]))
    say("Empfohlen: %s, %s, Vollbild, FOV 80"
        % (info["quality"].capitalize(), info["resolution"]))
    say("")
    say("Gefundene Installationen:")
    for i, d in enumerate(found, 1):
        inf = installation_info(d)
        bits = ["CoD " + inf["version"]]
        if inf["uo"]:
            bits.append("UO 1.51")
        bits.append("Deutsch" if inf["german"] else "English")
        say("  %d) %s" % (i, d))
        say("     [%s] %s" % (inf["kind"], ", ".join(bits)))


def wizard_options(args, info, found, game):
    de = False  # English is the documented default; --language de is explicit.
    opts = {
        "language": "en",
        "name": os.environ.get("USER") or os.environ.get("LOGNAME") or "Player",
        "resolution": info["resolution"],
        "fullscreen": True,
        "fov": recommended_fov(info["resolution"]),
        "quality": info["quality"],
        "extras": {"sp", "uf"},
    }
    if args.language:
        opts["language"] = args.language
    if args.name:
        opts["name"] = args.name
    if args.resolution:
        opts["resolution"] = args.resolution
        opts["fov"] = recommended_fov(args.resolution)
    if args.fullscreen is not None:
        opts["fullscreen"] = args.fullscreen
    if args.fov:
        opts["fov"] = args.fov
    if args.quality and args.quality != "auto":
        opts["quality"] = args.quality
    if args.extras:
        opts["extras"] = parse_extras(args.extras)
    elif args.extras_archive or args.extras_source or extras_local():
        opts["extras"] = {"sp", "uf", "mappack"}

    if args.yes or not is_interactive():
        return opts

    print_detection(found, info)
    say("")
    say("Sprache des Spiels:")
    say("  1) Deutsch  (Text und Stimmen, laedt ~630 MB Sprachpaket)")
    say("  2) English")
    default = "1" if opts["language"] == "de" else "2"
    choice = ask("Sprache [1/2] (%s): " % default, default, ["1", "2"])
    opts["language"] = "de" if choice == "1" else "en"

    opts["name"] = ask("Spielername (%s): " % opts["name"], opts["name"]).strip() or opts["name"]

    resolutions = [info["resolution"]] + [r for r in RESOLUTIONS if r != info["resolution"]]
    say("")
    say("Aufloesung:")
    for i, r in enumerate(resolutions, 1):
        say("  %d) %s%s" % (i, r, "   (Desktop)" if i == 1 else ""))
    choice = ask("Aufloesung [1-%d] (1): " % len(resolutions), "1")
    try:
        opts["resolution"] = resolutions[int(choice) - 1]
    except (ValueError, IndexError):
        opts["resolution"] = resolutions[0]

    opts["fullscreen"] = ask_yes("Vollbild?", True)

    # Hor+ recommendation for the chosen resolution (PCGamingWiki).
    recommended = recommended_fov(opts["resolution"])
    opts["fov"] = recommended
    fovs = [str(f) for f in FOVS]
    choice = ask("FOV (%s) [%d = empfohlen fuer %s]: "
                 % ("/".join(fovs), recommended, opts["resolution"]), str(recommended))
    try:
        opts["fov"] = int(choice)
    except ValueError:
        pass
    if opts["fov"] not in FOVS:
        opts["fov"] = min(FOVS, key=lambda f: abs(f - opts["fov"]))

    choice = ask("Qualitaet (niedrig/mittel/hoch) [%s]: " % opts["quality"], opts["quality"],
                 ["niedrig", "mittel", "hoch"])
    opts["quality"] = choice

    say("")
    say("Full Coop suite: SP Improved and United Fronts are required.")
    say("The UO Map Pack is a separate multiplayer addition.")
    opts["extras"] = {"sp", "uf"}
    return opts


def parse_extras(text):
    text = (text or "").strip().lower()
    if text in ("", "none", "nein", "no", "0"):
        return set()
    if text in ("all", "alle", "1"):
        return {"sp", "uf", "mappack"}
    out = set()
    for part in text.replace("+", ",").split(","):
        part = part.strip()
        if part in ("sp", "sp_improved", "improved"):
            out.add("sp")
        elif part in ("uf", "unitedfronts", "united-fronts", "fronts"):
            out.add("uf")
        elif part in ("mappack", "map", "maps", "uomappack"):
            out.add("mappack")
    return out


def extras_local():
    here = os.path.dirname(os.path.abspath(__file__))
    for base in (here, os.path.dirname(here)):
        for name in ("extras", "CoD-SP-Extras"):
            if os.path.isdir(os.path.join(base, name)):
                return True
        for name in ("CoD-SP-Extras.zip",):
            if os.path.exists(os.path.join(base, name)):
                return True
    return False


def print_summary(game, opts, info):
    inf = installation_info(game)
    say("")
    say("Zusammenfassung")
    say("  Ziel:       %s" % game)
    say("  Erkannt:    [%s] CoD %s%s" % (inf["kind"], inf["version"],
                                        ", UO 1.51" if inf["uo"] else ""))
    say("  Sprache:    %s%s" % ("Deutsch" if opts["language"] == "de" else "English",
                               "" if opts["language"] == "en" else "  (Sprachpaket, ~630 MB)"))
    say("  Spieler:    %s" % opts["name"])
    say("  Grafik:     %s, %s, FOV %d (Hor+), Qualitaet %s"
        % (opts["resolution"], "Vollbild" if opts["fullscreen"] else "Fenster",
           opts["fov"], opts["quality"]))
    if opts["extras"]:
        names = {"sp": "SP Improved", "uf": "United Fronts", "mappack": "UO Map Pack"}
        say("  Zusatz:     %s  (~980 MB)" % ", ".join(names[x] for x in ("sp", "uf", "mappack")
                                                       if x in opts["extras"]))
    else:
        say("  Zusatz:     keine")
    say("  Aenderungen: CoD 1.5 (falls noetig), UO 1.51, Co-op-Mod; alte Dateien als .bak")
    say("")


def find_german_tree(root):
    """Folder that holds the most Main/localized_*.pk3 files (the German language pack)."""
    best = None
    best_count = 0
    for dirpath, _dirnames, filenames in os.walk(root):
        if os.path.basename(dirpath).lower() != "main":
            continue
        count = sum(1 for f in filenames
                    if f.lower().startswith("localized_") and f.lower().endswith(".pk3"))
        if count > best_count:
            best = os.path.dirname(dirpath)
            best_count = count
    return best if best_count else None


def german_installed(game):
    main = find(game, "Main")
    return bool(main and os.path.exists(os.path.join(main, ".cod-coop-german")))


def install_german(game, source, dry):
    """Replace the localized paks by the German ones; the old files stay in localized_backup/."""
    main = find(game, "Main")
    if not main:
        die("Main/ not found in %s" % game)
    for dst_dir, src_name in ((main, "Main"), (find(game, "uo"), "uo")):
        if not dst_dir:
            continue
        src_dir = find(source, src_name)
        if not src_dir:
            continue
        try:
            paks = sorted(n for n in os.listdir(dst_dir)
                          if n.lower().startswith("localized_") and n.lower().endswith(".pk3"))
        except OSError:
            paks = []
        backup_dir = os.path.join(dst_dir, "localized_backup")
        if not os.path.isdir(backup_dir):
            if not dry:
                os.makedirs(backup_dir)
            for n in paks:
                if dry:
                    say("  [dry-run]  %s/%s -> localized_backup/" % (src_name, n))
                else:
                    shutil.move(os.path.join(dst_dir, n), os.path.join(backup_dir, n))
            if not dry:
                say("  %s: %d alte Sprachdateien gesichert (localized_backup/)" % (src_name, len(paks)))
        else:
            for n in paks:
                if dry:
                    say("  [dry-run]  remove %s/%s" % (src_name, n))
                else:
                    os.remove(os.path.join(dst_dir, n))
        for n in sorted(os.listdir(src_dir)):
            if not (n.lower().startswith("localized_") and n.lower().endswith(".pk3")):
                continue
            if dry:
                say("  [dry-run]  %s/%s" % (src_name, n))
                continue
            shutil.copy2(os.path.join(src_dir, n), os.path.join(dst_dir, n))
            say("  installed  %s/%s" % (src_name, n))
    if not dry:
        with open(os.path.join(main, ".cod-coop-german"), "w", encoding="utf-8") as f:
            json.dump({"installed": time.strftime("%Y-%m-%d %H:%M:%S")}, f)
        say("  Deutsch installiert (Sprachpaket).")


def restore_english(game, dry):
    """Switch back to the paks that were there before the German pack."""
    main = find(game, "Main")
    if not main or not os.path.exists(os.path.join(main, ".cod-coop-german")):
        return False
    for dst_dir in (main, find(game, "uo")):
        if not dst_dir:
            continue
        backup_dir = os.path.join(dst_dir, "localized_backup")
        if not os.path.isdir(backup_dir):
            continue
        for n in os.listdir(dst_dir):
            if n.lower().startswith("localized_") and n.lower().endswith(".pk3"):
                if dry:
                    say("  [dry-run]  remove %s/%s" % (os.path.basename(dst_dir), n))
                else:
                    os.remove(os.path.join(dst_dir, n))
        for n in os.listdir(backup_dir):
            if dry:
                say("  [dry-run]  restore %s/%s" % (os.path.basename(dst_dir), n))
            else:
                shutil.move(os.path.join(backup_dir, n), os.path.join(dst_dir, n))
        if not dry:
            os.rmdir(backup_dir)
    if not dry:
        os.remove(os.path.join(main, ".cod-coop-german"))
    say("  English wiederhergestellt.")
    return True


def set_cvars(cfg, values, dry):
    lines = []
    if os.path.exists(cfg):
        try:
            with open(cfg, encoding="latin-1") as f:
                lines = f.read().splitlines()
        except OSError:
            lines = []
    for key, value in values.items():
        text = str(value).replace("\\", "\\\\").replace('"', '\\"')
        line = 'seta %s "%s"' % (key, text)
        pattern = re.compile(r"^\s*seta\s+%s\s" % re.escape(key), re.I)
        for i, old in enumerate(lines):
            if pattern.match(old):
                lines[i] = line
                break
        else:
            lines.append(line)
    if dry:
        say("  [dry-run]  %s: %s" % (cfg, ", ".join("%s=%s" % kv for kv in values.items())))
        return
    os.makedirs(os.path.dirname(cfg), exist_ok=True)
    with open(cfg, "w", encoding="latin-1", newline="\r\n") as f:
        f.write("\n".join(lines) + "\n")


def recommended_fov(resolution):
    """Hor+ FOV: keep the 4:3 image (80) and widen it for the aspect ratio."""
    try:
        w, h = (int(x) for x in resolution.lower().split("x"))
    except (ValueError, AttributeError):
        return 80
    if not w or not h:
        return 80
    import math
    aspect = float(w) / float(h)
    fov = math.degrees(2.0 * math.atan(math.tan(math.radians(80) / 2.0) * aspect / (4.0 / 3.0)))
    return int(round(fov))


def write_settings(game, opts, dry):
    """Player name, resolution, fullscreen, FOV and PCGamingWiki fixes."""
    main = find(game, "Main")
    if not main:
        return
    width, height = opts["resolution"].split("x")
    values = {
        "name": opts["name"],
        "cl_language": "0",
        "r_mode": "-1",
        "r_customwidth": width,
        "r_customheight": height,
        "r_customaspect": "1",
        "r_fullscreen": "1" if opts["fullscreen"] else "0",
        "cg_fov": str(opts["fov"]),
        # PCGamingWiki fixes that are safe for everyone:
        "com_introplayed": "1",      # no intro videos on every start
        "r_smp": "1",                # multicore renderer
        "com_maxfps": "125",         # >144 fps makes footsteps inaudible
        "com_hunkmegs": "256",       # UO quick-save crash
        "r_ignorehwgamma": "1",      # alt-tab does not wash out the screen
        "cg_nopredict": "0",         # no mouse lag / jittery weapon animations
        "r_overBrightBits": "0",     # correct brightness in recordings
    }
    values.update(QUALITY[opts["quality"]])
    set_cvars(os.path.join(main, "config.cfg"), values, dry)
    set_cvars(os.path.join(main, "config_mp.cfg"), values, dry)

    # United Offensive keeps its own config in uo/. Seed it from the main one so
    # the first UO start already has the same name, resolution and fixes.
    uo = find(game, "uo")
    if uo:
        uo_cfg = os.path.join(uo, "config.cfg")
        if not os.path.exists(uo_cfg) and not dry:
            src_cfg = os.path.join(main, "config.cfg")
            if os.path.exists(src_cfg):
                shutil.copy2(src_cfg, uo_cfg)
        set_cvars(uo_cfg, values, dry)
        set_cvars(os.path.join(uo, "config_mp.cfg"), values, dry)
    say("  Einstellungen: %s, %s, FOV %d (Hor+), %s, Name \"%s\""
        % (opts["resolution"], "Vollbild" if opts["fullscreen"] else "Fenster",
           opts["fov"], opts["quality"], opts["name"]))
    say("  PCGamingWiki-Fixes: Intro aus, Multicore, maxfps 125, hunkmegs 256,")
    say("                      kein Maus-Lag, korrekte Helligkeit nach Alt+Tab")


def install_bink_fallback(game, dry, extra_bases=()):
    """United Offensive needs binkw32.dll for its videos; some installs lack it."""
    if find(game, "binkw32.dll"):
        return
    here = os.path.dirname(os.path.abspath(__file__))
    bases = list(extra_bases) + [here, os.path.dirname(here)]
    for base in bases:
        for cand in (os.path.join(base, "optional", "binkw32-uo-1.41.dll"),
                     os.path.join(base, "binkw32-uo-1.41.dll")):
            if not os.path.exists(cand):
                continue
            if dry:
                say("  [dry-run]  binkw32.dll (UO-Videofallback)")
                return
            shutil.copy2(cand, os.path.join(game, "binkw32.dll"))
            say("  binkw32.dll installiert (UO-Videos)")
            return
    say("  Hinweis: binkw32.dll fehlt; UO braucht sie fuer die Videos.")


def install_kar98k_fix(game, dry, extra_bases=()):
    """The Kar98k shows a ghost bullet at cg_fov > 80; install the small fix."""
    main = find(game, "Main")
    if not main:
        return
    try:
        if any("kar98k" in n.lower() and n.lower().endswith(".pk3") for n in os.listdir(main)):
            return
    except OSError:
        pass
    here = os.path.dirname(os.path.abspath(__file__))
    bases = list(extra_bases) + [here, os.path.dirname(here)]
    for base in bases:
        for cand in (os.path.join(base, "optional", "kar98k-fov-fix.zip"),
                     os.path.join(base, "optional", "zzz_patch.pk3"),
                     os.path.join(base, "Main", "zzz_patch.pk3")):
            if not os.path.exists(cand):
                continue
            if cand.lower().endswith(".zip"):
                tmp = extract_archive(cand)
                found = None
                for dirpath, _dirs, files in os.walk(tmp):
                    for n in files:
                        if n.lower().endswith(".pk3"):
                            found = os.path.join(dirpath, n)
                if not found:
                    continue
                src = found
            else:
                src = cand
            name = os.path.basename(src)
            if dry:
                say("  [dry-run]  Main/%s (Kar98k-FOV-Fix)" % name)
                return
            shutil.copy2(src, os.path.join(main, name))
            say("  Kar98k-FOV-Fix installiert (Main/%s)" % name)
            return
    say("  Hinweis: Kar98k-FOV-Fix nicht gefunden (cg_fov > 80 kann ein")
    say("           Geistergeschoss zeigen). Liegt in optional/ des Pakets.")


def detect_language(game):
    """'de' if the current paks are German, 'en' otherwise."""
    if german_installed(game):
        return "de"
    main = find(game, "Main")
    if main:
        try:
            if any(n.lower().startswith("localized_german_pak") for n in os.listdir(main)):
                return "de"
        except OSError:
            pass
    return "en"


def german_local():
    here = os.path.dirname(os.path.abspath(__file__))
    for base in (here, os.path.dirname(here)):
        for name in ("german", "CoD-UO-German-Language"):
            if os.path.isdir(os.path.join(base, name)):
                return True
        if os.path.exists(os.path.join(base, "CoD-UO-German-Language.zip")):
            return True
    return False


def resolve_german_source(args, cache_dir):
    """German pack from --german-archive / --german-source / next to the script / download."""
    if args.german_source:
        tree = find_german_tree(os.path.abspath(os.path.expanduser(args.german_source)))
        if not tree:
            die("no Main/localized_english_pak*.pk3 in %s" % args.german_source)
        return tree, None
    if args.german_archive:
        tmp = extract_archive(os.path.abspath(os.path.expanduser(args.german_archive)))
        tree = find_german_tree(tmp)
        if not tree:
            die("no Main/localized_english_pak*.pk3 in %s" % args.german_archive)
        return tree, tmp
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, "german"), os.path.join(os.path.dirname(here), "german")):
        if os.path.isdir(cand):
            tree = find_german_tree(cand)
            if tree:
                say("source: %s (German language pack next to the installer)" % tree)
                return tree, None
    os.makedirs(cache_dir, exist_ok=True)
    zip_path = os.path.join(cache_dir, "CoD-UO-German-Language.zip")
    if not os.path.exists(zip_path) or (GERMAN_SIZE and os.path.getsize(zip_path) != GERMAN_SIZE):
        if not GERMAN_URL:
            die("German language pack is not available - pass --german-archive FILE")
        url = GERMAN_URL % (args.release if args.release else TAG)
        download(url, zip_path, GERMAN_SHA or None, GERMAN_SIZE or None)
    tmp = extract_archive(zip_path)
    tree = find_german_tree(tmp)
    if not tree:
        die("no Main/localized_english_pak*.pk3 in the German language pack")
    return tree, tmp


def find_extras_tree(root):
    """Folder that contains sp_improved/ or UnitedFronts/ (the extras pack)."""
    best = None
    best_score = 0
    for dirpath, dirnames, _filenames in os.walk(root):
        low = {d.lower() for d in dirnames}
        score = 0
        if "sp_improved" in low:
            score += 2
        if "unitedfronts" in low:
            score += 2
        if "uomappack00.pk3" in {f.lower() for f in _filenames}:
            score += 1
        if score > best_score:
            best = dirpath
            best_score = score
        # do not descend into the mod folders themselves
        dirnames[:] = [d for d in dirnames if d.lower() not in ("sp_improved", "unitedfronts")]
    return best if best_score else None


def extras_installed(game):
    return bool(find(game, "sp_improved") or find(game, "UnitedFronts"))


def resolve_extras_source(args, cache_dir):
    """Extras from --extras-source / --extras-archive / next to the script / download."""
    if args.extras_source:
        tree = find_extras_tree(os.path.abspath(os.path.expanduser(args.extras_source)))
        if not tree:
            die("no sp_improved/ or UnitedFronts/ in %s" % args.extras_source)
        return tree, None
    if args.extras_archive:
        tmp = extract_archive(os.path.abspath(os.path.expanduser(args.extras_archive)))
        tree = find_extras_tree(tmp)
        if not tree:
            die("no sp_improved/ or UnitedFronts/ in %s" % args.extras_archive)
        return tree, tmp
    here = os.path.dirname(os.path.abspath(__file__))
    for base in (here, os.path.dirname(here)):
        for name in ("extras", "CoD-SP-Extras"):
            cand = os.path.join(base, name)
            if os.path.isdir(cand):
                tree = find_extras_tree(cand)
                if tree:
                    say("source: %s (extras next to the installer)" % tree)
                    return tree, None
        cand = os.path.join(base, "CoD-SP-Extras.zip")
        if os.path.exists(cand):
            tmp = extract_archive(cand)
            tree = find_extras_tree(tmp)
            if tree:
                return tree, tmp
    os.makedirs(cache_dir, exist_ok=True)
    zip_path = os.path.join(cache_dir, "CoD-SP-Extras.zip")
    if not os.path.exists(zip_path) or (EXTRAS_SIZE and os.path.getsize(zip_path) != EXTRAS_SIZE):
        if not EXTRAS_URL:
            die("extras are not available - pass --extras-archive FILE or --extras none")
        url = EXTRAS_URL % (args.release if args.release else TAG)
        download(url, zip_path, EXTRAS_SHA or None, EXTRAS_SIZE or None)
    tmp = extract_archive(zip_path)
    tree = find_extras_tree(tmp)
    if not tree:
        die("no sp_improved/ or UnitedFronts/ in the extras pack")
    return tree, tmp


def copy_tree_files(src, dst, dry, label):
    count = 0
    for dirpath, _dirnames, filenames in os.walk(src):
        rel = os.path.relpath(dirpath, src)
        out_dir = dst if rel == "." else os.path.join(dst, rel)
        for name in filenames:
            target = os.path.join(out_dir, name)
            if dry:
                say("  [dry-run]  %s" % os.path.relpath(target, os.path.dirname(dst)))
            else:
                os.makedirs(out_dir, exist_ok=True)
                shutil.copy2(os.path.join(dirpath, name), target)
            count += 1
    if not dry:
        say("  %s: %d Dateien" % (label, count))
    return count


def write_launchers(game, dry):
    """Start scripts for the singleplayer mods (fs_game needs a command line)."""
    if dry:
        say("  [dry-run]  Start-SP-Improved.sh / Start-United-Fronts.sh")
        return
    umu = os.path.expanduser("~/.local/bin/umu-run")
    if not os.path.exists(umu):
        umu = shutil.which("umu-run") or ""
    proton = ""
    for cand in ("Proton - Experimental", "Proton 9.0", "Proton 8.0"):
        p = os.path.expanduser("~/.local/share/Steam/steamapps/common/" + cand)
        if os.path.isdir(p):
            proton = p
            break
    prefix = ""
    for cand in ("/mnt/daten/Games/AnkerGames/Games/Prefixes/3278",
                 os.path.expanduser("~/.local/share/Steam/steamapps/compatdata/2620/pfx")):
        if os.path.isdir(cand):
            prefix = cand
            break
    gameid = "2620"
    m = re.search(r"Prefixes/(\d+)", prefix)
    if m:
        gameid = m.group(1)
    header = """#!/bin/sh
# Generated by the CoD Coop installer. Starts United Offensive with a mod.
cd "$(dirname "$0")" || exit 1
EXE=CoDUOSP.exe
export WINEDLLOVERRIDES="ddraw=n,b"
export __GL_ExtensionStringVersion=15000
export MESA_EXTENSION_MAX_YEAR=2003
if [ -n "$SteamAppId$SteamGameId" ]; then
    exec ./$EXE "$@"
fi
"""
    if umu and proton:
        header += ('GAMEID=%s PROTONPATH="%s" WINEPREFIX="%s" '
                   'STEAM_COMPAT_CLIENT_INSTALL_PATH="$HOME/.local/share/Steam" '
                   'exec "%s" "$PWD/$EXE" "$@"\n') % (gameid, proton, prefix or os.path.expanduser(
                       "~/.local/share/Steam/steamapps/compatdata/2620/pfx"), umu)
    else:
        header += 'exec wine "$EXE" "$@"\n'
    for mod, label in (("sp_improved", "Start-SP-Improved.sh"),
                       ("UnitedFronts", "Start-United-Fronts.sh")):
        if not find(game, mod):
            continue
        path = os.path.join(game, label)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(header.replace('"$@"', '+set fs_game %s +set com_introplayed 1 "$@"' % mod))
        os.chmod(path, 0o755)
        say("  Starter: %s" % label)
    # Windows-style starters are also useful when the folder is shared with Windows.
    for mod, label in (("sp_improved", "Start-SP-Improved.bat"),
                       ("UnitedFronts", "Start-United-Fronts.bat")):
        if not find(game, mod):
            continue
        path = os.path.join(game, label)
        with open(path, "w", encoding="ascii", newline="\r\n") as f:
            f.write('@echo off\r\ncd /d "%%~dp0"\r\nstart "" CoDUOSP.exe +set fs_game %s +set com_introplayed 1\r\n' % mod)


def install_extras(game, source, selected, dry):
    """Copy the optional singleplayer mods and the official UO map pack."""
    if not selected:
        return
    uo = find(game, "uo")
    main = find(game, "Main")
    if "sp" in selected:
        src = find(source, "sp_improved")
        if src:
            say("  Singleplayer Improved 1.5...")
            copy_tree_files(src, os.path.join(game, "sp_improved"), dry, "sp_improved")
        else:
            say("  Singleplayer Improved: nicht im Paket enthalten.")
    if "uf" in selected:
        src = find(source, "UnitedFronts")
        if src:
            say("  United Fronts 1.1 beta...")
            copy_tree_files(src, os.path.join(game, "UnitedFronts"), dry, "UnitedFronts")
        else:
            say("  United Fronts: nicht im Paket enthalten.")
    if "mappack" in selected and uo:
        src = find(source, "uo")
        pak = find(src, "uomappack00.pk3") if src else None
        if pak:
            target = os.path.join(uo, "uomappack00.pk3")
            if dry:
                say("  [dry-run]  uo/uomappack00.pk3")
            elif os.path.exists(target):
                say("  uo/uomappack00.pk3 ist schon vorhanden.")
            else:
                shutil.copy2(pak, target)
                say("  UO Map Pack installiert (uo/uomappack00.pk3)")
        docs = find(source, "UODocs")
        if docs:
            copy_tree_files(docs, os.path.join(game, "UODocs"), dry, "UODocs")
    # The Kar98k fix is part of the extras pack as well.
    fix = find(source, "Main")
    if fix:
        pak = find(fix, "zzz_patch.pk3")
        if pak and main:
            target = os.path.join(main, "zzz_patch.pk3")
            if dry:
                say("  [dry-run]  Main/zzz_patch.pk3")
            elif not os.path.exists(target):
                shutil.copy2(pak, target)
                say("  Kar98k-FOV-Fix installiert (Main/zzz_patch.pk3)")
    write_launchers(game, dry)


def finish_install(game, args, opts, cache, dry, extra_bases=()):
    """Language pack, settings, PCGamingWiki fixes and optional extras."""
    # Language pack: German replaces the localized paks (the old ones stay in
    # localized_backup/, so switching back to English is lossless). This runs
    # after the game files, otherwise the package's English paks would win.
    if opts["language"] == "de":
        if german_installed(game):
            say("")
            say("Deutsch: Sprachpaket ist bereits installiert.")
        elif dry and not (args.german_source or args.german_archive) and not german_local():
            say("")
            say("  [dry-run] deutsches Sprachpaket wird heruntergeladen (~630 MB)")
        else:
            say("")
            say("Deutsches Sprachpaket (Text und Stimmen)...")
            german_source, german_tmp = resolve_german_source(args, cache)
            try:
                install_german(game, german_source, dry)
            finally:
                if german_tmp:
                    shutil.rmtree(german_tmp, ignore_errors=True)
    elif german_installed(game):
        say("")
        say("English: vorherige Sprachdateien werden wiederhergestellt...")
        restore_english(game, dry)
    elif detect_language(game) == "de":
        say("")
        say("Hinweis: Diese Installation enthaelt nur deutsche Sprachdateien.")
        say("         Fuer Englisch waeren englische Paks noetig (z. B. aus")
        say("         einer Steam-Installation). Die vorhandenen bleiben unveraendert.")

    say("")
    write_settings(game, opts, dry)
    install_bink_fallback(game, dry, extra_bases)
    if opts["fov"] > 80:
        install_kar98k_fix(game, dry, extra_bases)

    if opts["extras"]:
        say("")
        say("Zusatzinhalte...")
        if dry and not (args.extras_source or args.extras_archive) and not extras_local():
            say("  [dry-run] Zusatzpaket wird heruntergeladen (~980 MB)")
        else:
            extras_source, extras_tmp = resolve_extras_source(args, cache)
            try:
                install_extras(game, extras_source, opts["extras"], dry)
            finally:
                if extras_tmp:
                    shutil.rmtree(extras_tmp, ignore_errors=True)

    if not dry:
        repair_config_sum(game)
        # The improper-quit marker makes the game show the "computer changed"
        # dialog on the next start. Remove it, the game recreates it on a crash.
        for marker in ("__CoDSP", "__CoDUOSP"):
            marker_path = os.path.join(game, marker)
            if os.path.exists(marker_path):
                os.remove(marker_path)



# 0.6 suite entry point. Legacy helpers above remain reusable, but an old
# mod-only package is never reported as a complete 0.6 installation.
def protected_user_file(rel):
    parts = rel.replace('\\', '/').lower().split('/')
    return ('save' in parts or 'saves' in parts or 'players' in parts or
            parts[-1].endswith(('.sav', '.svg')) or
            parts[-1] in ('config.cfg', 'config_mp.cfg', 'uoconfig.cfg', 'autoexec.cfg'))


class InstallTransaction:
    """Keep original bytes once per touched path and roll back failed installs."""
    def __init__(self, game):
        from pathlib import Path
        self.game = Path(game).resolve()
        self.root = self.game / 'coop' / 'backups' / (time.strftime('%Y%m%d-%H%M%S') + '-' + str(os.getpid()))
        self.entries = {}
        if not self.root.resolve().is_relative_to(self.game):
            raise ValueError('backup path escapes the game folder')

    def destination(self, rel):
        path = self.game
        for part in rel.replace('\\', '/').split('/'):
            if path.is_dir():
                matches = [p for p in path.iterdir() if p.name.lower() == part.lower()]
                if len(matches) > 1:
                    raise ValueError('ambiguous installation path: ' + rel)
                path = matches[0] if matches else path / part
            else:
                path = path / part
        return path

    def remember(self, rel):
        from pathlib import PurePosixPath
        rel = rel.replace('\\', '/')
        path = PurePosixPath(rel)
        if path.is_absolute() or '..' in path.parts or not path.parts or ':' in rel:
            raise ValueError('unsafe installation path: ' + rel)
        dst = self.destination(rel)
        if not dst.resolve().is_relative_to(self.game):
            raise ValueError('installation path escapes through symlink: ' + rel)
        if rel in self.entries:
            return dst
        existed = dst.exists()
        if existed and not dst.is_file():
            raise ValueError('destination is not a regular file: ' + rel)
        self.entries[rel] = existed
        if existed:
            saved = self.root / 'files' / rel
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, saved)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / 'journal.json').write_text(json.dumps({'entries': self.entries, 'state': 'running'}, indent=2))
        return dst

    def copy(self, src, rel, preserve=True):
        dst = self.destination(rel)
        if preserve and protected_user_file(rel):
            say(('  preserved  ' if dst.exists() else '  skipped package personal file  ') + rel)
            return
        if dst.is_file() and sha256(dst) == sha256(src):
            return
        dst = self.remember(rel)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        if sha256(src) != sha256(dst):
            raise OSError('copy verification failed: ' + rel)
        say('  installed  ' + rel)

    def rollback(self):
        for rel, existed in reversed(list(self.entries.items())):
            dst = self.destination(rel)
            if existed:
                shutil.copy2(self.root / 'files' / rel, dst)
            elif dst.is_file():
                dst.unlink()
        self.complete('rolled-back')

    def complete(self, state='complete'):
        if self.entries:
            (self.root / 'journal.json').write_text(json.dumps({'entries': self.entries, 'state': state}, indent=2))


def rollback_installation(game, backup_id='latest'):
    """Restore the selected successful transaction, never touch unrelated files."""
    from pathlib import Path, PurePosixPath
    game = Path(game).resolve()
    backups = game / 'coop/backups'
    candidates = list(backups.glob('*/journal.json')) if backups.is_dir() else []
    candidates = [p for p in candidates if json.loads(p.read_text()).get('state') == 'complete']
    if backup_id == 'latest':
        if not candidates:
            raise ValueError('no completed installation backup exists')
        journal = max(candidates, key=lambda p: p.stat().st_mtime_ns)
    else:
        if not re.fullmatch(r'[A-Za-z0-9_-]+', backup_id):
            raise ValueError('invalid backup identifier')
        journal = backups / backup_id / 'journal.json'
        if journal not in candidates:
            raise ValueError('unknown completed installation backup')
    data = json.loads(journal.read_text())
    entries = data.get('entries')
    if not isinstance(entries, dict):
        raise ValueError('invalid backup journal')
    tx = InstallTransaction(game)
    tx.root = journal.parent
    # Rollback of a completed update never discards settings changed since then.
    tx.entries = {rel: existed for rel, existed in entries.items() if not protected_user_file(rel)}
    for rel, existed in tx.entries.items():
        parts = PurePosixPath(rel)
        if not isinstance(existed, bool) or parts.is_absolute() or '..' in parts.parts or ':' in rel or '\\' in rel:
            raise ValueError('unsafe backup journal entry')
        dest = tx.destination(rel)
        if not dest.resolve().is_relative_to(game):
            raise ValueError('backup destination escapes game folder')
        saved = tx.root / 'files' / rel
        if existed and (not saved.is_file() or not saved.resolve().is_relative_to(tx.root.resolve())):
            raise ValueError('backup file missing or unsafe: ' + rel)
    tx.rollback()
    say('Installation restored from backup: ' + journal.parent.name)


def suite_validator():
    from pathlib import Path
    candidates = [Path(__file__).with_name('coop_suite.py'),
                  Path(getattr(sys, '_MEIPASS', '.')) / 'coop_suite.py']
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise ValueError('coop_suite.py is missing; use the complete 0.6 development package')


def run_suite_validator(action, game):
    import importlib.util
    spec = importlib.util.spec_from_file_location('coop_suite_validator', suite_validator())
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main([action, '--game', str(game)])


def safe_extract(path):
    from pathlib import Path
    name = Path(path).name
    install_progress(f'Extracting {name}', f'{name} wird entpackt')
    tmp = tempfile.mkdtemp(prefix='cod-coop-suite-')
    try:
        root = Path(tmp).resolve()
        with zipfile.ZipFile(path) as archive:
            for entry in archive.infolist():
                name = entry.filename.replace('\\', '/')
                if not (root / name).resolve().is_relative_to(root) or ':' in name:
                    raise ValueError('unsafe archive entry: ' + name)
                if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError('archive symlinks are not supported: ' + name)
            archive.extractall(tmp)
        return tmp
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def write_suite_launchers(game, transaction):
    """Every public launcher prepares the guarded profile before starting."""
    from pathlib import Path
    default_variant = json.loads((Path(game) / 'coop/variants.json').read_text()).get('default_variant', 'sp_improved')
    if default_variant not in ('cod1', 'uo', 'sp_improved', 'united_fronts'):
        raise ValueError('unknown default campaign variant')
    profiles = [(default_variant, 'Start-CoD-Coop'), ('cod1', 'Start-CoD-Classic'), ('uo', 'Start-UO-Coop'),
                ('sp_improved', 'Start-SP-Improved'), ('united_fronts', 'Start-United-Fronts')]
    for variant, stem in profiles:
        text = ('#!/bin/sh\nset -eu\nDIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\n'
                'if [ -x "$DIR/coop/launcher/CoD-Coop-Launcher" ]; then\n'
                '  exec "$DIR/coop/launcher/CoD-Coop-Launcher" --game "$DIR" --variant ' + variant + ' "$@"\n'
                'fi\nexec python3 "$DIR/coop/launch-gui.py" --game "$DIR" --variant ' + variant + ' "$@"\n')
        path = transaction.remember(stem + '.sh')
        path.write_text(text)
        path.chmod(0o755)

        text = ('@echo off\r\ncd /d "%~dp0"\r\n'
                'if not exist "%~dp0coop\\launcher\\CoD-Coop-Launcher.exe" (echo Windows launcher is missing. Repair with a Windows 0.6 package. & exit /b 2)\r\n'
                'start "" "%~dp0coop\\launcher\\CoD-Coop-Launcher.exe" --game "%~dp0." --variant ' + variant + '\r\n')
        transaction.remember(stem + '.bat').write_bytes(text.encode('ascii'))


RETIRED_TRIGGER_BASENAMES = ('zzzzz_codcoop_triggers.pk3', 'zzzzz_coop_triggers.pk3')


def preflight_retired_trigger_overlays(game, overlay):
    """A renamed effective script layer must not leave a stale extra PK3 loaded.

    Only a previous payload's unchanged owned bytes may be retired. An edited
    or manually supplied overlay needs an explicit user backup/decision instead.
    This check runs before downloads and again immediately before mutation.
    """
    from pathlib import Path
    game, overlay = Path(game), Path(overlay)
    new_path = overlay / 'coop/runtime-lock.json'
    if not new_path.is_file():
        return
    new = json.loads(new_path.read_text()).get('files', {})
    old_path = game / 'coop/runtime-lock.json'
    old = json.loads(old_path.read_text()).get('files', {}) if old_path.is_file() else {}
    if not isinstance(new, dict) or not isinstance(old, dict):
        raise ValueError('invalid previous or replacement payload ownership')
    new = {name.lower(): (name, digest) for name, digest in new.items()}
    old = {name.lower(): digest for name, digest in old.items()}
    destination = InstallTransaction(game)
    source = InstallTransaction(overlay)
    for folder in ('Main', 'uo', 'sp_improved', 'UnitedFronts'):
        replacement = folder + '/zzzz_coop_triggers.pk3'
        pin = new.get(replacement.lower())
        if pin is None:
            continue
        replacement_file = source.destination(replacement)
        if (replacement_file.is_symlink() or not replacement_file.resolve().is_relative_to(source.game) or
                not replacement_file.is_file() or
                not isinstance(pin[1], str) or not re.fullmatch(r'[0-9a-f]{64}', pin[1]) or
                sha256(replacement_file) != pin[1]):
            raise ValueError('replacement mission overlay is missing or changed: ' + replacement)
        for basename in RETIRED_TRIGGER_BASENAMES:
            relative = folder + '/' + basename
            if relative.lower() in new:
                continue
            path = destination.destination(relative)
            if not path.exists() and not path.is_symlink():
                continue
            if (path.is_symlink() or not path.resolve().is_relative_to(destination.game) or
                    not path.is_file() or old.get(relative.lower()) != sha256(path)):
                raise ValueError('Previous mission overlay is modified or not payload-owned; back it up and '
                                 'remove it explicitly before updating: ' + relative)


def remove_obsolete_owned_files(game, overlay, transaction):
    """Retire only unchanged publisher-owned overlays and launcher libraries."""
    from pathlib import Path, PurePosixPath
    old_path = Path(game) / 'coop/runtime-lock.json'
    new_path = Path(overlay) / 'coop/runtime-lock.json'
    preflight_retired_trigger_overlays(game, overlay)
    if not old_path.is_file() or not new_path.is_file():
        return
    old = json.loads(old_path.read_text()).get('files', {})
    new = json.loads(new_path.read_text()).get('files', {})
    new_names = {name.lower() for name in new}
    for rel, expected in old.items():
        lower = rel.lower()
        generated = ((lower.endswith('.pk3') and ('codcoop' in lower.rsplit('/', 1)[-1] or
                     lower.rsplit('/', 1)[-1] in (*RETIRED_TRIGGER_BASENAMES, 'zzzz_coop_triggers.pk3', 'zzzz_coop_campaign.pk3'))) or
                     lower.startswith('coop/launcher/'))
        if not generated or lower in new_names or protected_user_file(rel):
            continue
        parts = PurePosixPath(rel)
        if parts.is_absolute() or '..' in parts.parts or ':' in rel or '\\' in rel:
            raise ValueError('unsafe previous payload path')
        dest = transaction.destination(rel)
        if not dest.resolve().is_relative_to(transaction.game):
            raise ValueError('previous payload path escapes game folder')
        if dest.is_file() and sha256(dest) == expected:
            transaction.remember(rel).unlink()
            say('  retired previous owned file  ' + rel)


def canonical_english_files(game):
    """Validate the explicit English source inventory, never guess by filename."""
    from pathlib import Path, PurePosixPath
    base = Path(game) / 'coop/languages/en'
    manifest = base / 'manifest.json'
    if not manifest.is_file():
        return None
    data = json.loads(manifest.read_text())
    if data.get('schema') != 1 or data.get('language') != 'en' or not data.get('files'):
        raise ValueError('invalid canonical English inventory')
    result = []
    for relative, item in data['files'].items():
        parts = PurePosixPath(relative)
        if not re.fullmatch(r'(?:Main|uo)/localized_english_[A-Za-z0-9_]+\.pk3', relative):
            raise ValueError('unsafe canonical English path: ' + relative)
        digest = item.get('sha256') if isinstance(item, dict) else None
        source = base / relative
        if not re.fullmatch('[0-9a-f]{64}', digest or '') or not source.is_file() or sha256(source) != digest:
            raise ValueError('canonical English file missing or changed: ' + relative)
        result.append((source, relative))
    return result


def remove_active_localizations(game, transaction):
    from pathlib import Path
    for folder in ('Main', 'uo'):
        root = Path(find(str(game), folder) or Path(game)/folder)
        if not root.is_dir():
            continue
        for path in root.iterdir():
            if path.is_file() and path.name.lower().startswith('localized_') and path.suffix.lower() == '.pk3':
                transaction.remember(folder + '/' + path.name).unlink()


def require_suite_owned_patches(overlay):
    """Required suite patches cannot be skipped because SPI/UF already exist."""
    from pathlib import Path, PurePosixPath
    base=Path(overlay).resolve()
    manifest=json.loads((base/'coop/variants.json').read_text())
    for item in manifest.get('required', []):
        if not isinstance(item,dict):raise ValueError('invalid required suite content entry')
        if item.get('install_source')!='suite':continue
        name=item.get('path')
        if not isinstance(name,str) or not name or '\\' in name or ':' in name:
            raise ValueError('invalid required suite patch path')
        relative=PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('invalid required suite patch path')
        source=base.joinpath(*relative.parts)
        if item.get('kind')=='coop_localization':
            from coop_localization import preflight
            preflight(base,manifest)
            continue
        expected=item.get('sha256')
        if not re.fullmatch('[0-9a-f]{64}',expected or ''):
            raise ValueError('invalid required suite patch pin: '+name)
        if (source.is_symlink() or not source.resolve().is_relative_to(base) or not source.is_file() or
                ('size' in item and (type(item['size']) is not int or item['size']<=0 or source.stat().st_size!=item['size'])) or
                sha256(source)!=expected):
            raise ValueError('Required suite patch missing or changed in payload: '+name+
                             '. Rebuild or download the complete matching suite payload.')


def require_original_campaign_source(game, overlay, offline_source=None):
    """The UO Ready ZIP cannot supply missing original CoD mission packages."""
    from pathlib import Path
    manifest = json.loads((Path(overlay)/'coop/variants.json').read_text())
    locations = [Path(game), Path(overlay)]
    if offline_source:
        base = find_game_tree(str(offline_source))
        if base: locations.append(Path(base))
    missing=[]
    for item in manifest.get('required', []):
        if item.get('kind') != 'base_content' or item.get('engine') != 'cod1': continue
        relative=item['path']
        if not re.fullmatch(r'Main/pak[0-9a-z]+\.pk3', relative):
            raise ValueError('invalid original CoD base inventory')
        found=False
        for location in locations:
            candidate=location
            for component in relative.split('/'):
                candidate=Path(find(str(candidate),component) or candidate/component)
            found=found or candidate.is_file()
        if not found: missing.append(relative)
    if missing:
        raise ValueError('Original CoD campaign content is missing: '+', '.join(missing)+
                         '. Restore your complete owned CoD 1.5 installation or use a verified full suite payload; the UO Ready ZIP does not contain this base game data.')


def remove_known_invalid_placeholder(game, overlay, transaction):
    from pathlib import Path
    manifest=json.loads((Path(overlay)/'coop/variants.json').read_text())
    item=manifest.get('ignored_placeholder', {})
    if item.get('path') != 'Main/pakb.pk3' or item.get('size') != 1: return
    file=Path(target(str(game),'Main/pakb.pk3'))
    if file.is_file() and file.stat().st_size==1 and sha256(file)==item.get('sha256'):
        transaction.remember('Main/pakb.pk3').unlink()
        say('  removed known invalid one-byte pakb placeholder (backed up)')


def suite_main(argv=None):
    from pathlib import Path
    parser = argparse.ArgumentParser(description='CoDCoop 0.6 full-suite setup (development)')
    parser.add_argument('--game', help='existing Call of Duty installation')
    parser.add_argument('--suite-source', type=Path, help='complete pinned 0.6 overlay laid out as a game root')
    parser.add_argument('--source', type=Path, help='offline base package directory containing game/')
    parser.add_argument('--archive', type=Path, help='pinned v0.5.4 base archive (used only as base game data)')
    parser.add_argument('--extras-source', type=Path, help='offline directory containing sp_improved and UnitedFronts')
    parser.add_argument('--extras-archive', type=Path, help='pinned SP extras archive')
    parser.add_argument('--german-archive', type=Path, help='pinned German language archive')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--rollback', nargs='?', const='latest', help='restore a completed installation backup (default: latest)')
    parser.add_argument('--repair', action='store_true', help='preserve all personal settings')
    parser.add_argument('--configure', action='store_true', help='explicitly apply the chosen settings to existing configs')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--yes', '-y', action='store_true')
    parser.add_argument('--language', choices=('en', 'de'), default='en')
    parser.add_argument('--name', default=os.environ.get('USER', 'Player'))
    parser.add_argument('--resolution', default='1920x1080')
    parser.add_argument('--fov', type=int, default=96)
    parser.add_argument('--quality', choices=tuple(QUALITY), default='hoch')
    parser.add_argument('--fullscreen', action='store_true', default=True)
    parser.add_argument('--windowed', dest='fullscreen', action='store_false')
    args = parser.parse_args(argv)
    detected = detect_games() if not args.game else []
    if not args.game:
        if len(detected) != 1:
            parser.error('specify --game; found %d installations' % len(detected))
        args.game = detected[0]
    game = Path(args.game).expanduser().resolve()
    if not game.is_dir() or not find(str(game), 'CoDSP.exe'):
        parser.error('--game must contain an existing CoDSP.exe')
    if args.rollback:
        try:
            rollback_installation(game, args.rollback)
            return 0
        except (OSError, ValueError) as error:
            say('ROLLBACK FAILED: ' + str(error))
            return 2
    if args.check:
        return run_suite_validator('check', game)
    if not args.suite_source:
        parser.error('--suite-source is required until a complete 0.6 release is published; 0.5.4 is not a complete suite')
    overlay = args.suite_source.expanduser().resolve()
    if overlay == game or overlay.is_relative_to(game) or not (overlay / 'coop/variants.json').is_file():
        parser.error('--suite-source must be a separate 0.6 payload containing coop/variants.json')
    launcher_name = 'CoD-Coop-Launcher.exe' if os.name == 'nt' else 'CoD-Coop-Launcher'
    if not (overlay / 'coop/launcher' / launcher_name).is_file():
        parser.error('the suite payload is missing the native launcher for this operating system')
    if not re.fullmatch(r'[1-9][0-9]{2,4}x[1-9][0-9]{2,4}', args.resolution):
        parser.error('resolution must look like 1920x1080')
    if not 60 <= args.fov <= 130 or any(c in args.name for c in '\r\n";'):
        parser.error('invalid FOV or player name')
    if args.repair and args.configure:
        parser.error('--repair preserves settings; do not combine it with --configure')
    say('CoDCoop 0.6 development setup: full suite, English/German, original + UO + SP Improved + United Fronts + YAP.')
    say('Target: %s\nOverlay: %s\nGame language: %s' % (game, overlay, args.language))
    say('Base/extras downloads, when required: 1,036,938,510 / 922,302,300 bytes. German: 657,419,767 bytes.')
    try:
        require_suite_owned_patches(overlay)
        require_original_campaign_source(game, overlay, args.source)
        preflight_retired_trigger_overlays(game, overlay)
    except (OSError, ValueError, TypeError, KeyError) as error:
        say('INSTALLATION FAILED: '+str(error))
        return 2
    if args.dry_run:
        say('DRY RUN: no files changed and no downloads started. Final validation is required for installation success.')
        return 0
    if not args.yes and not ask_yes('Install the complete suite? Existing settings and saves are preserved.', True):
        return 0
    cache = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache')) / 'cod-coop' / 'v0.5.4'
    temporary = []
    try:
        tx = InstallTransaction(game)
    except ValueError as error:
        say('INSTALLATION FAILED: ' + str(error))
        return 2
    try:
        sources = []
        if args.source:
            base = find_game_tree(str(args.source))
            if not base:
                raise ValueError('offline source contains no game/ directory')
            sources.append(Path(base))
        elif args.archive or not find(str(game), 'CoDUOSP.exe'):
            archive = args.archive or cache / 'Call-of-Duty-UO-Coop-Ready.zip'
            if not args.archive:
                download('https://github.com/%s/releases/download/v0.5.4/Call-of-Duty-UO-Coop-Ready.zip' % REPO,
                         str(archive), READY_SHA, READY_SIZE)
            if archive.stat().st_size != READY_SIZE or sha256(archive) != READY_SHA:
                raise ValueError('base archive does not match the pinned v0.5.4 base')
            extracted = safe_extract(archive)
            temporary.append(extracted)
            base = find_game_tree(extracted)
            if not base:
                raise ValueError('base archive contains no game/ directory')
            sources.append(Path(base))
        # A complete overlay may already include the campaign packages.
        missing_extras = not all((game / rel).is_file() or (overlay / rel).is_file() for rel in
                                ('sp_improved/sp_improved_1.5.pk3', 'UnitedFronts/ZUnitedFronts_1.1_beta.pk3'))
        if args.extras_source:
            extra = find_extras_tree(str(args.extras_source))
            if not extra:
                raise ValueError('extras source contains no campaign variants')
            sources.append(Path(extra))
        elif args.extras_archive or missing_extras:
            archive = args.extras_archive or cache / 'CoD-SP-Extras.zip'
            if not args.extras_archive:
                download(EXTRAS_URL % 'v0.5.4', str(archive), EXTRAS_SHA, EXTRAS_SIZE)
            if archive.stat().st_size != EXTRAS_SIZE or sha256(archive) != EXTRAS_SHA:
                raise ValueError('extras archive does not match the pinned version')
            extracted = safe_extract(archive)
            temporary.append(extracted)
            extra = find_extras_tree(extracted)
            if not extra:
                raise ValueError('extras archive contains no campaign variants')
            sources.append(Path(extra))
        remove_obsolete_owned_files(game, overlay, tx)
        remove_known_invalid_placeholder(game, overlay, tx)
        sources.append(overlay)  # Always replace old 0.5 binaries with the pinned 0.6 payload last.
        install_progress('Copying the game files', 'Spieldateien werden kopiert')
        # Materialize only package-owned files; never import user saves/configs.
        for source in sources:
            for path in sorted(source.rglob('*')):
                if not path.is_file():
                    continue
                rel = path.relative_to(source).as_posix()
                if path.is_symlink():
                    raise ValueError('package symlink is not allowed: ' + rel)
                if rel.startswith(('coop/backups/', 'coop/install.json', 'coop/profile.ini')):
                    continue
                tx.copy(path, rel)
        english_files = canonical_english_files(game)
        if args.language == 'de' and (english_files is not None or not german_installed(str(game))):
            archive = args.german_archive or cache / 'CoD-UO-German-Language.zip'
            if not args.german_archive:
                download(GERMAN_URL % 'v0.5.4', str(archive), GERMAN_SHA, GERMAN_SIZE)
            if archive.stat().st_size != GERMAN_SIZE or sha256(archive) != GERMAN_SHA:
                raise ValueError('German archive does not match the pinned version')
            extracted = safe_extract(archive)
            temporary.append(extracted)
            german = find_german_tree(extracted)
            if not german:
                raise ValueError('German archive contains no language files')
            if english_files is not None:
                remove_active_localizations(game, tx)
            for path in sorted(Path(german).rglob('*.pk3')):
                rel = path.relative_to(german).as_posix()
                if 'localized_' in path.name:
                    original = game / rel
                    english_copy = game / 'coop/languages/en' / rel
                    if english_files is None and original.is_file() and not english_copy.exists():
                        tx.copy(original, 'coop/languages/en/' + rel, preserve=False)
                    tx.copy(path, rel)
            marker = tx.remember('Main/.cod-coop-german')
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text('de\n')
        if args.language == 'en' and english_files is not None:
            remove_active_localizations(game, tx)
            for path, relative in english_files:
                tx.copy(path, relative, preserve=False)
            marker = tx.remember('Main/.cod-coop-german')
            marker.unlink(missing_ok=True)
        elif args.language == 'en' and german_installed(str(game)):
            raise ValueError('Verified English localization inventory is missing; use a complete canonical suite payload to change language')
        if any(item.get('kind')=='coop_localization' for item in json.loads((game/'coop/variants.json').read_text()).get('required',[])):
            from coop_localization import apply
            apply(game,args.language,tx)
        # Existing settings are preserved unless the person explicitly requests reconfiguration.
        if not args.repair and (args.configure or not Path(target(str(game), 'Main/config.cfg')).exists()):
            for rel in ('Main/config.cfg', 'Main/config_mp.cfg', 'uo/config.cfg', 'uo/config_mp.cfg'):
                tx.remember(rel)
            opts = vars(args).copy()
            write_settings(str(game), opts, False)
        write_suite_launchers(game, tx)
        for rel in ('coop/install.json', 'coop/profile.ini'):
            tx.remember(rel)
        # seal verifies every pinned byte and writes the receipt/profile in the
        # same invocation. Later launches/checks independently rehash content.
        install_progress('Verifying the installation', 'Installation wird geprüft')
        if run_suite_validator('seal', game) != 0:
            raise ValueError('full-suite validation failed; no successful installation receipt was accepted')
        tx.complete()
        say('INSTALLATION COMPLETE: required suite files verified. Gameplay acceptance is tracked separately.')
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        say('INSTALLATION FAILED: %s\nRestoring files changed by this attempt.' % exc)
        tx.rollback()
        return 2
    finally:
        for path in temporary:
            shutil.rmtree(path, ignore_errors=True)


def main(argv=None):
    return suite_main(argv)


if __name__ == "__main__":
    sys.exit(main())
