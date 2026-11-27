#!/usr/bin/env python3
"""Pinned CoDCoop suite validation and launch preparation (standard library only).

No game state is trusted from the network. A receipt describes one complete
installation; gameplay fingerprints omit approved localization and personal settings.
"""
import argparse
from runtime_protocol import core_protocol, required_feature_mask, require_core_features
import configparser
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import stat
import subprocess
import sys
import tempfile
from frozen_runtime import external_environment, spawn_owned

HEX = re.compile(r"[0-9a-f]{64}\Z")
PROTOCOL = 9
RUNTIME = ("ddraw.dll", "codcoop_core.dll", "steam_api.dll", "plugins/yap/DDRAW.dll")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".coop-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def resolve(root, relative):
    """Resolve known package names on Main/main filesystems without traversal."""
    root = Path(root).resolve()
    name = PurePosixPath(relative)
    if not relative or name.is_absolute() or ".." in name.parts or "\\" in relative or ":" in relative:
        raise ValueError("unsafe package path: " + relative)
    path = root
    for part in name.parts:
        exact = path / part
        if path.is_dir():
            matches = [p for p in path.iterdir() if p.name.lower() == part.lower()]
            if len(matches) > 1:
                raise ValueError("ambiguous path: " + relative)
            path = matches[0] if matches else exact
        else:
            path = exact
    if not path.resolve().is_relative_to(root):
        raise ValueError("package symlink escapes installation: " + relative)
    return path


def approved_localizations(manifest):
    """Only reviewed path/hash pairs may differ without changing gameplay."""
    catalog = manifest.get("approved_localizations", {})
    if not isinstance(catalog, dict):
        raise ValueError("invalid approved localization catalog")
    result = {}
    for name, hashes in catalog.items():
        if (not re.fullmatch(r"(?:Main|uo)/localized_[A-Za-z0-9_]+\.pk3", name, re.I | re.ASCII)
                or name.lower() in result or not isinstance(hashes, list) or not hashes
                or any(not isinstance(value, str) or not HEX.fullmatch(value) for value in hashes)):
            raise ValueError("invalid approved localization entry: " + name)
        result[name.lower()] = frozenset(hashes)
    return result


def load_manifest(game, manifest=None):
    path = Path(manifest) if manifest else Path(game) / "coop/variants.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != 1 or data.get("protocol") != PROTOCOL or not data.get("complete_suite_required"):
        raise ValueError("unsupported suite manifest")
    ids = [v["id"] for v in data["variants"]]
    if ids != ["cod1", "uo", "sp_improved", "united_fronts"]:
        raise ValueError("incomplete/unknown campaign set")
    for variant in data["variants"]:
        if not re.fullmatch(r"[a-z_0-9]+", variant["id"]):
            raise ValueError("unsafe variant id")
        if not re.fullmatch(r"[A-Za-z_0-9]*", variant["fs_game"]):
            raise ValueError("unsafe fs_game")
        if variant.get("save_root", native_save_root(variant)) != native_save_root(variant):
            raise ValueError("campaign save area does not match its native profile")
    approved_localizations(data)
    required_feature_mask(data)
    return data, sha256(path)


def native_save_root(variant):
    return (variant["fs_game"] or ("Main" if variant["id"] == "cod1" else "uo")) + "/save"


def local_save_summary(game, manifest):
    """Read actual local save metadata; never infer mission completion from it."""
    result = {}
    for variant in manifest["variants"]:
        entry = {"count": 0, "latest": None}
        try:
            folder = resolve(game, native_save_root(variant))
            saves = []
            if folder.is_symlink():
                raise ValueError("save area is a symlink")
            if folder.is_dir():
                reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
                if getattr(folder.stat(follow_symlinks=False), "st_file_attributes", 0) & reparse:
                    raise ValueError("save area is a reparse point")
                base = folder.resolve()
                def real_node(path):
                    metadata = path.stat(follow_symlinks=False)
                    return (not path.is_symlink() and
                            not getattr(metadata, "st_file_attributes", 0) & reparse and
                            path.resolve().is_relative_to(base))
                def inaccessible(_error):
                    entry["unavailable"] = True
                for current, directories, filenames in os.walk(folder, followlinks=False, onerror=inaccessible):
                    parent = Path(current)
                    directories[:] = [name for name in directories if real_node(parent / name)]
                    for name in filenames:
                        path = parent / name
                        try:
                            if path.suffix.lower() == ".svg" and real_node(path) and path.is_file():
                                saves.append((path.stat().st_mtime, path.relative_to(folder).as_posix()))
                        except OSError:
                            entry["unavailable"] = True
            entry["count"] = len(saves)
            if saves:
                modified, name = max(saves)
                entry["latest"] = {"name": name, "modified": datetime.fromtimestamp(modified, timezone.utc).isoformat()}
        except (OSError, ValueError, OverflowError):
            entry["unavailable"] = True
        result[variant["id"]] = entry
    return result


def read_lock(game, manifest, manifest_hash):
    path = resolve(game, "coop/runtime-lock.json")
    lock = json.loads(path.read_text(encoding="utf-8"))
    if lock.get("suite_version") != manifest["suite_version"] or lock.get("manifest_sha256") != manifest_hash:
        raise ValueError("runtime lock does not match suite manifest")
    files = lock.get("files", {})
    if not all(key in files for key in RUNTIME):
        raise ValueError("runtime lock is missing required Coop/YAP modules")
    if not files or not all(isinstance(v, str) and HEX.fullmatch(v) for v in files.values()):
        raise ValueError("invalid runtime lock hashes")
    return lock


def localization_inventory(game):
    path = resolve(game, "coop/languages/en/manifest.json")
    if not path.is_file():
        return {}
    inventory = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(inventory, dict) or inventory.get("schema") != 1 or inventory.get("language") != "en":
        raise ValueError("invalid canonical English inventory")
    files = inventory.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("empty canonical English inventory")
    for name, info in files.items():
        if not re.fullmatch(r"(?:Main|uo)/localized_english_[A-Za-z0-9_]+\.pk3", name):
            raise ValueError("unsafe canonical English path: " + name)
        if not isinstance(info, dict) or not isinstance(info.get("sha256"), str) or not HEX.fullmatch(info["sha256"]):
            raise ValueError("invalid canonical English hash: " + name)
    return files


def content_files(game, manifest):
    """All effective content, including additional PK3s, is accounted for."""
    names = {item["path"].lower(): item["path"] for item in manifest["required"]}
    for variant in manifest["variants"]:
        for folder in variant["content_roots"]:
            base = resolve(game, folder)
            if base.is_dir():
                for path in base.rglob("*"):
                    if path.is_file() and (path.suffix.lower() == ".pk3" or (path.suffix.lower() == ".json" and "eweapons" in [x.lower() for x in path.parts])) and "localized_backup" not in path.parts:
                        relative = folder + "/" + path.relative_to(base).as_posix()
                        names.setdefault(relative.lower(), relative)
    # YAP loads this optional global definition layer before uo/mod layers.
    # It lives outside the engine's normal content roots but changes weapons.
    global_weapons = resolve(game, "eWeapons")
    if global_weapons.is_dir():
        for path in global_weapons.rglob("*"):
            if path.is_file() and path.suffix.lower() == ".json":
                relative = "eWeapons/" + path.relative_to(global_weapons).as_posix()
                names.setdefault(relative.lower(), relative)
    english = localization_inventory(game)
    if english:
        names["coop/languages/en/manifest.json"] = "coop/languages/en/manifest.json"
        for name in english:
            relative = "coop/languages/en/" + name
            names[relative.lower()] = relative
    return set(names.values())


def fingerprints(game, manifest, files):
    localized = approved_localizations(manifest)
    result = {}
    for variant in manifest["variants"]:
        roots = {r.lower() for r in variant["content_roots"]}
        entries = []
        for name, digest in files.items():
            parts = PurePosixPath(name)
            lower = name.lower()
            included = (lower in {variant["exe"].lower(), "ddraw.dll", "codcoop_core.dll"}
                        or (parts.parts[0].lower() in roots and lower.endswith(".pk3")
                            and digest not in localized.get(lower, ()))
                        or (parts.parts[0].lower() in roots and "/eweapons/" in lower and lower.endswith(".json"))
                        or (variant["yap"] and lower.startswith("eweapons/") and lower.endswith(".json"))
                        or (variant["yap"] and (lower.startswith("plugins/yap/") or lower.startswith("menuwide/") or lower.startswith("yap_raw/"))))
            engine_dlls = ("uo_gamex86.dll", "uo_cgamex86.dll", "uo_uix86.dll") if variant["engine"] == "uo" else ("gamex86.dll", "cgamex86.dll", "uix86.dll")
            if included or lower in engine_dlls:
                entries.append([lower, digest])
        result[variant["id"]] = hashlib.sha256(canonical(sorted(entries))).hexdigest()
    return result


def collect(game, manifest, manifest_hash):
    if core_protocol(resolve(game, "codcoop_core.dll")) != PROTOCOL:
        raise ValueError("Core protocol does not match manifest/checker protocol")
    require_core_features(resolve(game, "codcoop_core.dll"), required_feature_mask(manifest))
    game = Path(game).resolve()
    lock = read_lock(game, manifest, manifest_hash)
    inventory_path = "coop/languages/en/manifest.json"
    if resolve(game, inventory_path).is_file() and inventory_path not in {name.lower() for name in lock["files"]}:
        raise ValueError("unowned canonical English inventory; repair with a complete suite payload")
    names_by_case = {n.lower(): n for n in content_files(game, manifest)}
    names_by_case.update({n.lower(): n for n in lock["files"]})
    names_by_case.update({item["path"].lower(): item["path"] for item in manifest["required"]})
    names = set(names_by_case.values())
    files = {}
    for name in sorted(names):
        path = resolve(game, name)
        if not path.is_file():
            raise ValueError("missing required file: " + name)
        files[name] = sha256(path)
    for item in manifest["required"]:
        expected = item.get("sha256")
        allowed = item.get("sha256_any", [expected] if expected else [])
        if allowed and files[item["path"]] not in allowed:
            raise ValueError("wrong pinned content: " + item["path"])
    for name, expected in lock["files"].items():
        if files[name] != expected:
            raise ValueError("wrong runtime module: " + name)
    for name, info in localization_inventory(game).items():
        if files["coop/languages/en/" + name] != info["sha256"]:
            raise ValueError("wrong canonical English backup: " + name)
    return files


def seal_installation(game):
    manifest, manifest_hash = load_manifest(game)
    files = collect(game, manifest, manifest_hash)
    receipt = {"schema": 1, "suite_version": manifest["suite_version"],
               "manifest_sha256": manifest_hash,
               "runtime_lock_sha256": sha256(resolve(game, "coop/runtime-lock.json")),
               "files": files, "variants": fingerprints(game, manifest, files)}
    atomic_write(Path(game) / "coop/install.json", canonical(receipt) + b"\n")
    return receipt


def check_installation(game):
    errors = []
    try:
        manifest, manifest_hash = load_manifest(game)
        receipt = json.loads(resolve(game, "coop/install.json").read_text(encoding="utf-8"))
        if receipt.get("schema") != 1 or receipt.get("suite_version") != manifest["suite_version"] or receipt.get("manifest_sha256") != manifest_hash:
            raise ValueError("installation receipt belongs to a different suite")
        if receipt.get("runtime_lock_sha256") != sha256(resolve(game, "coop/runtime-lock.json")):
            raise ValueError("runtime lock changed since installation")
        files = collect(game, manifest, manifest_hash)
        if files != receipt.get("files"):
            changed = sorted(k for k in files.keys() | receipt.get("files", {}).keys() if files.get(k) != receipt.get("files", {}).get(k))
            raise ValueError("content changed since installation: " + ", ".join(changed[:12]))
        if fingerprints(game, manifest, files) != receipt.get("variants"):
            raise ValueError("campaign fingerprints do not match receipt")
        return {"ok": True, "errors": [], "suite_version": manifest["suite_version"], "variants": receipt["variants"],
                "local_saves": local_save_summary(game, manifest)}
    except (OSError, ValueError, KeyError, TypeError) as error:
        errors.append(str(error))
    return {"ok": False, "errors": errors}


def _write_profile(game, variant_id, manifest, digests, core_hash, loader_hash):
    variant = next((v for v in manifest["variants"] if v["id"] == variant_id), None)
    if not variant:
        raise ValueError("unknown campaign variant")
    profile = ("[coop]\nprotocol={protocol}\nvariant={id}\nengine={engine}\ndigest={digest}\ncore_sha256={core}\nloader_sha256={loader}\n".format(
        **variant, protocol=PROTOCOL, digest=digests[variant_id], core=core_hash, loader=loader_hash))
    atomic_write(game / "coop/profile.ini", profile.encode("ascii"))
    return variant


def prepare(game, variant_id):
    game = Path(game).resolve()
    result = check_installation(game)
    if not result["ok"]:
        raise ValueError("; ".join(result["errors"]))
    manifest, _ = load_manifest(game)
    return _write_profile(game, variant_id, manifest, result["variants"],
                          sha256(game / "codcoop_core.dll"), sha256(game / "ddraw.dll"))


def seal_and_prepare(game, variant_id):
    """One complete hash pass, reused only within this installation operation.

    Normal check/prepare/launch still rehash the complete installation. No
    timestamp cache or receipt from another invocation can skip verification.
    """
    game = Path(game).resolve()
    receipt = seal_installation(game)
    manifest, manifest_hash = load_manifest(game)
    if receipt["manifest_sha256"] != manifest_hash:
        raise ValueError("suite manifest changed while preparing installation")
    return _write_profile(game, variant_id, manifest, receipt["variants"],
                          receipt["files"]["codcoop_core.dll"], receipt["files"]["ddraw.dll"])


def launch_arguments(game, variant_id, runner=None, host=None, map_name=None, hosting=False, port=28960, difficulty=1, expected_players=1):
    game = Path(game).resolve()
    variant = prepare(game, variant_id)
    args = [] if os.name == "nt" else shlex.split(runner or "wine")
    args += [str(resolve(game, variant["exe"])), "+set", "fs_basepath", str(game), "+set", "fs_homepath", str(game), "+set", "fs_cdpath", str(game), "+set", "fs_game", variant["fs_game"], "+set", "com_introplayed", "1", "+set", "coop_mainline", "1" if variant_id == "sp_improved" else "0"]
    args += ["+set", "coop_mainline_handoff", "1" if hosting and variant_id == "sp_improved" else "0",
             "+set", "coop_mainline_finished", "0"]
    if not isinstance(difficulty, int) or not 0 <= difficulty <= 3:
        raise ValueError("invalid difficulty")
    if type(expected_players) is not int or not 1 <= expected_players <= 4:
        raise ValueError("invalid expected player count")
    # Match both original native menu preset values before world creation.
    # Setting only the skill leaves health from a previous preset unchanged.
    args += ["+set", "g_gameskill", str(difficulty), "+set", "g_player_maxhealth",
             str((1200, 600, 300, 200)[difficulty]),
             "+set", "coop_expected_players", str(expected_players)]
    if map_name:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,63}", map_name):
            raise ValueError("invalid map name")
        args += ["+spmap", map_name]
    if host:
        if not re.fullmatch(r"(?:[0-9.]+(?::[0-9]+)?|steam:[0-9]+)", host):
            raise ValueError("invalid host address")
        args += ["+coopjoin", host]
    if hosting:
        if not 1 <= port <= 65535:
            raise ValueError("invalid host port")
        args += ["+coophost", str(port)]
    env = external_environment()
    env["WINEDLLOVERRIDES"] = env.get("WINEDLLOVERRIDES", "") + ";ddraw=n,b"
    env["__GL_ExtensionStringVersion"] = "15000"
    env["MESA_EXTENSION_MAX_YEAR"] = "2003"
    return args, env


def launch(game, variant_id, runner=None, host=None, map_name=None):
    args, env = launch_arguments(game, variant_id, runner, host, map_name)
    return spawn_owned(args, cwd=game, env=env).wait()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "seal", "prepare", "launch"))
    parser.add_argument("--game", required=True, type=Path)
    parser.add_argument("--variant", default="sp_improved")
    parser.add_argument("--runner", help="Wine/Proton command, parsed without a shell")
    parser.add_argument("--host")
    parser.add_argument("--map", dest="map_name")
    args = parser.parse_args(argv)
    try:
        if args.action == "check":
            result = check_installation(args.game)
            print(json.dumps(result, indent=2))
            return 0 if result["ok"] else 1
        if args.action == "seal":
            seal_and_prepare(args.game, args.variant)
        elif args.action == "prepare":
            prepare(args.game, args.variant)
        else:
            return launch(args.game, args.variant, args.runner, args.host, args.map_name)
        print("CoDCoop: " + args.action + " complete")
        return 0
    except (OSError, ValueError, KeyError) as error:
        print("CoDCoop: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
