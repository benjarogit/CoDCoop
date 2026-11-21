#!/usr/bin/env python3
"""Install Call of Duty Coop + United Offensive 1.51 into a Call of Duty folder on Linux.

The easy way: download "Call of Duty - UO Coop Ready.zip" from MEGA, extract it,
and run this script from the extracted folder (it finds the game itself):

    python3 install-linux.py

    # or point it at the folder / the ZIP
    python3 install-linux.py --game "/path/to/Call of Duty"
    python3 install-linux.py --archive "Call of Duty - UO Coop Ready.zip"

It copies the ready game/ tree (United Offensive 1.51 + the mod) into the game
folder. Nothing is mounted and no Windows patch wizard is involved.

Other ways:

    # from the ready ZIP, without extracting it first
    python3 install-linux.py --game "..." --archive "Call of Duty - UO Coop Ready.zip"

    # from a folder that contains game/ (for example the extracted ZIP)
    python3 install-linux.py --game "..." --source "/path/to/Call of Duty - UO Coop Ready"

    # mod only, from the latest GitHub release (old behaviour)
    python3 install-linux.py --game "..." --release

    # mod only, from a local build/ produced by ./build.sh
    python3 install-linux.py --game "..." --build build

    # only check an existing installation
    python3 install-linux.py --game "..." --check

Nothing is written without a backup: an existing file is copied to <name>.bak first.
Call of Duty 1.5 (CoDSP.exe, 1,716,224 bytes) is required and checked before
anything is written.
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
import urllib.request
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from extract_installer import resources  # noqa: E402  (same folder, optional)
except Exception:  # pragma: no cover - only needed for --release
    resources = None

REPO = "benjarogit/CoDCoop"
RELEASE_URL = "https://github.com/%s/releases/download/%%s/Install-CoD-Coop.exe" % REPO
API_URL = "https://api.github.com/repos/%s/releases" % REPO

# The ready package (United Offensive 1.51 + mod) lives on MEGA. The link is in
# README.md / docs/linux.md; override it here if you mirror the file:
READY_URL = os.environ.get("COD_READY_URL", "")
READY_SIZE = 0       # 0 = do not check (the ZIP is rebuilt from time to time)
READY_SHA = ""

EXE_SIZE = 1716224          # Call of Duty 1.5 (CoDSP.exe)
EXE_SHA = "c755c7da411c87039ade462a2299402c3c4ca5c4fc4f1ae5cea6e25b05c69f47"

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
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            say("asked Steam to install Spacewar (" + url + ")")
            return
        except FileNotFoundError:
            continue
    say("could not open Steam - open this link: " + url)


def download(url, dest, expected_sha=None, expected_size=None):
    """Download with a .part file; verify size and sha256 when they are known."""
    say("downloading %s" % url)
    req = urllib.request.Request(url, headers={"User-Agent": "cod-coop-linux-installer"})
    part = dest + ".part"
    with urllib.request.urlopen(req, timeout=60) as r, open(part, "wb") as f:
        shutil.copyfileobj(r, f)
    size = os.path.getsize(part)
    if expected_size and size != expected_size:
        os.unlink(part)
        die("download is %d bytes, expected %d - delete the cache and try again" % (size, expected_size))
    if expected_sha:
        got = sha256(part)
        if got != expected_sha:
            os.unlink(part)
            die("download sha256 %s does not match %s" % (got, expected_sha))
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
    subprocess.check_call([exe, READY_URL, dest])
    # mega-get writes the file with the name from MEGA; find it.
    for name in os.listdir(dest):
        if name.lower().endswith(".zip"):
            return os.path.join(dest, name)
    return None


def main():
    ap = argparse.ArgumentParser(description="Install CoD Coop + United Offensive 1.51 on Linux")
    ap.add_argument("--game", help="the Call of Duty folder (with CoDSP.exe); default: auto-detect")
    ap.add_argument("--archive", metavar="ZIP", help="the ready ZIP (Call of Duty - UO Coop Ready.zip)")
    ap.add_argument("--source", metavar="DIR", help="a folder with game/ (for example the extracted ZIP)")
    ap.add_argument("--release", nargs="?", const="", metavar="TAG",
                    help="mod only: install from a GitHub release (default tag: latest)")
    ap.add_argument("--build", metavar="DIR", help="mod only: install the DLLs from a local build (see ./build.sh)")
    ap.add_argument("--pak", metavar="FILE", help="menu pak for --build (default: game/Main/pakz_coop.pk3)")
    ap.add_argument("--mega", action="store_true", help="download the ready ZIP with mega-get if it is installed")
    ap.add_argument("--check", action="store_true", help="only verify the installation")
    ap.add_argument("--dry-run", action="store_true", help="show what would be copied")
    ap.add_argument("--allow-incomplete", action="store_true", help="install even if CoDSP.exe is not 1.5")
    ap.add_argument("--force", action="store_true", help="ignore checksum warnings")
    args = ap.parse_args()

    if args.game:
        game = os.path.abspath(os.path.expanduser(args.game))
        if not os.path.isdir(game):
            die("no such folder: %s" % game)
    else:
        found = detect_games()
        if not found:
            die("Call of Duty was not found automatically.\n"
                "       Pass the folder with CoDSP.exe: --game \"/path/to/Call of Duty\"")
        if len(found) == 1:
            game = found[0]
            say("game: %s (detected)" % game)
        elif sys.stdin.isatty():
            say("Several Call of Duty installations found:")
            for i, d in enumerate(found, 1):
                say("  %d) %s" % (i, d))
            try:
                choice = input("Which one? [1] ").strip() or "1"
                game = found[int(choice) - 1]
            except (EOFError, ValueError, IndexError):
                die("no valid choice - pass --game")
        else:
            # started with "curl ... | sh": no keyboard to ask, take the first (a real
            # installation, because those are sorted first) and say which one it is
            game = found[0]
            say("game: %s (detected)" % game)
            for d in found[1:]:
                say("      also found: %s (use --game to install there instead)" % d)

    here = os.path.dirname(os.path.abspath(__file__))
    tmp = None
    manifest = None

    if args.check:
        src = args.source or (args.archive and extract_archive(os.path.abspath(os.path.expanduser(args.archive))))
        if src:
            tree = find_game_tree(src)
            manifest = load_manifest(tree) if tree else None
        return check(game, manifest)

    exe = find(game, "CoDSP.exe")
    if not exe:
        die("CoDSP.exe not found in %s - is this the Call of Duty folder?" % game)
    size = os.path.getsize(exe)

    source_tree = None
    if args.archive:
        tmp = extract_archive(os.path.abspath(os.path.expanduser(args.archive)))
        source_tree = find_game_tree(tmp)
        if not source_tree:
            die("no game/ folder with CoDUOSP.exe in %s" % args.archive)
    elif args.source:
        base = os.path.abspath(os.path.expanduser(args.source))
        source_tree = find_game_tree(base)
        if not source_tree:
            die("no game/ folder with CoDUOSP.exe in %s" % base)
    elif args.mega:
        tmp = tempfile.mkdtemp(prefix="cod-coop-mega-")
        zip_path = mega_download(tmp)
        if not zip_path:
            return 2
        if READY_SIZE and os.path.getsize(zip_path) != READY_SIZE:
            die("download is %d bytes, expected %d" % (os.path.getsize(zip_path), READY_SIZE))
        if READY_SHA and not READY_SHA.startswith("REPLACE") and sha256(zip_path) != READY_SHA:
            die("download sha256 does not match")
        source_tree = find_game_tree(extract_archive(zip_path))
        if not source_tree:
            die("no game/ folder in the downloaded ZIP")
    elif os.path.isdir(os.path.join(here, "game")) and os.path.exists(os.path.join(here, "game", "CoDUOSP.exe")):
        source_tree = os.path.join(here, "game")
        say("source: %s (ready package next to this script)" % source_tree)

    # CoD 1.5: the ready package brings the 1.5 CoDSP.exe, so it is installed with
    # the rest (the previous one is kept as .bak). Only the mod-only paths need it.
    have15 = size == EXE_SIZE
    pkg_exe = os.path.join(source_tree, "CoDSP.exe") if source_tree else None
    if not have15 and pkg_exe and os.path.exists(pkg_exe) and os.path.getsize(pkg_exe) == EXE_SIZE:
        say("CoDSP.exe: %d bytes -> the ready package installs 1.5 (%d bytes)" % (size, EXE_SIZE))
        have15 = True
    if have15 and size == EXE_SIZE:
        say("CoDSP.exe: 1.5 (%d bytes)" % size)
    elif not have15 and not args.allow_incomplete:
        exe_help(game, size)
        return 2

    if source_tree:
        manifest = load_manifest(source_tree)
        todo = list(iter_files(source_tree))
        say("source: %s (%d files)" % (source_tree, len(todo)))
        if manifest:
            say("manifest: %s" % os.path.join(os.path.dirname(source_tree), "manifest.json"))
        say("")
        install(game, todo, args.dry_run, args.force, known=False, manifest=manifest)
        if not args.dry_run:
            repair_config_sum(game)
            say("")
            offer_spacewar()
        say("""
Done. In the game: Co-op -> Host game -> Back -> New Game.
Friends: same CoD 1.5 and same mod version, then Host IP -> Join, or Steam invites.

United Offensive 1.51 is included: start CoDUOSP.exe. The game's own version
label may still say 1.41 - the 1.51 patch does not change the exe, only the
paks/DLLs (uo/version.inf says 1.51).

Steam invites (cross-platform) need all three:
  * Steam running and signed in on both PCs
  * Spacewar (AppID 480) installed once - the installer offers it, or: steam://install/480
  * on Linux the game has to be started through Steam (Add a Non-Steam Game ->
    CoDSP.exe, force Proton); on Windows starting it normally is enough

Launch Options of that Steam entry (Linux):
  WINEDLLOVERRIDES="ddraw=n,b" __GL_ExtensionStringVersion=15000 MESA_EXTENSION_MAX_YEAR=2003 %command%
  (WINEDLLOVERRIDES is required - without it Wine uses its own ddraw.dll and the
   mod is not loaded: no Co-op entry, no codcoop.log)

First start: if Call of Duty asks whether the computer changed, click "Ja" once.
See docs/linux.md for the exact steps.
""")
        return 0

    # Mod-only fallbacks (old behaviour).
    if args.build:
        source = from_build(args.build)
        alt = build_extras(args.build, args.pak and os.path.abspath(os.path.expanduser(args.pak)))
        say("source: %s (local build)" % source)
    else:
        if args.pak:
            die("--pak only applies to --build")
        if resources is None:
            die("extract_installer.py is missing - use --archive or --source")
        cache = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "cod-coop")
        source, tag = from_release(args.release, cache)
        alt = {}
        say("source: %s" % tag)

    todo = plan(game, source, alt)
    say("")
    install(game, todo, args.dry_run, args.force, known=not args.build)
    if not args.dry_run:
        repair_config_sum(game)
        say("")
        offer_spacewar()
    say("""
Done. In the game: Co-op -> Host game -> Back -> New Game.
Friends: same CoD 1.5 and same mod version, then Host IP -> Join, or Steam invites.

Steam invites (cross-platform) need all three:
  * Steam running and signed in on both PCs
  * Spacewar (AppID 480) installed once - the installer offers it, or: steam://install/480
  * on Linux the game has to be started through Steam (Add a Non-Steam Game ->
    CoDSP.exe, force Proton); on Windows starting it normally is enough

Launch Options of that Steam entry (Linux):
  WINEDLLOVERRIDES="ddraw=n,b" __GL_ExtensionStringVersion=15000 MESA_EXTENSION_MAX_YEAR=2003 %command%
  (WINEDLLOVERRIDES is required - without it Wine uses its own ddraw.dll and the
   mod is not loaded: no Co-op entry, no codcoop.log)

First start: if Call of Duty asks whether the computer changed, click "Ja" once.
See docs/linux.md for the exact steps.
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
