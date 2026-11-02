"""Refresh Localized Plates from the installed game. Run: python update_mod.py"""

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path

import release_support as b

ROOT = Path(__file__).resolve().parent
DEFAULT_PAKS = Path(
    r"X:\Games\Steam\steamapps\common\TokyoXtremeRacer\TokyoXtremeRacer\Content\Paks"
)
AES_KEY = "0xD499D0D1C8E2B87D576EA9756B5137306D1A96D378124C16A6F033BE2A9CBB4A"
TARGETS = ("Game", "EarlyAccess", "FullRelease")
PREFIX = "TokyoXtremeRacer/Content/Localization/"
PUBLISH = (
    "sources",
    "dist",
    "release.json",
    "source-info.json",
)


def compare(old_data, new_data):
    old = {e[:2]: e for e in b.parse(old_data)} if old_data is not None else {}
    new = {e[:2]: e for e in b.parse(new_data)}
    return {
        "before": len(old),
        "after": len(new),
        "added": len(new.keys() - old.keys()),
        "removed": len(old.keys() - new.keys()),
        "changed": sum(old[k] != new[k] for k in old.keys() & new.keys()),
    }


def release_valid():
    try:
        report = json.loads((ROOT / "dist/validation.json").read_text(encoding="utf-8"))
        archive = ROOT / "dist/Localized Plates.zip"
        if b.digest(archive) != report["archive"]["sha256"]:
            return False
        for variant, data in report["variants"].items():
            for name, details in data["files"].items():
                if b.digest(ROOT / "dist" / variant / name) != details["sha256"]:
                    return False
        with zipfile.ZipFile(archive) as z:
            return (
                z.testzip() is None
                and z.read("README.md") == (archive.parent / "README.md").read_bytes()
            )
    except (OSError, ValueError, KeyError, zipfile.BadZipFile):
        return False


def publish(stage):
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d-%H%M%S")
    backup = ROOT / "backups" / f"before-update-{stamp}-{uuid.uuid4().hex[:8]}.zip"
    backup.parent.mkdir(exist_ok=True)
    existing = [name for name in PUBLISH if (ROOT / name).exists()]
    with zipfile.ZipFile(backup, "x", zipfile.ZIP_DEFLATED) as z:
        for name in existing:
            path = ROOT / name
            for p in path.rglob("*") if path.is_dir() else [path]:
                if p.is_file():
                    z.write(p, p.relative_to(ROOT))
    with zipfile.ZipFile(backup) as z:
        if z.testzip() is not None:
            raise RuntimeError("Backup verification failed.")
    # The new release is fully validated before any existing output is replaced.
    # All destinations are fixed children of ROOT; rollback restores their old bytes.
    try:
        for name in PUBLISH:
            src, dst = stage / name, ROOT / name
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
    except BaseException:
        with zipfile.ZipFile(backup) as z:
            z.extractall(ROOT)
        for name in PUBLISH:
            path = ROOT / name
            if name not in existing and path.is_file():
                path.unlink()
        raise
    print(f"Previous release backed up: {backup}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paks", type=Path, default=DEFAULT_PAKS, help="Game Content/Paks folder"
    )
    parser.add_argument(
        "--game-version", help="Optional display label, e.g. 1.6.2; never guessed"
    )
    parser.add_argument(
        "--check", action="store_true", help="Compare only; do not modify the workspace"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild even when translations are unchanged",
    )
    parser.add_argument(
        "--mod-version",
        help="Override the mod version (normally the patch number increments for each new game version)",
    )
    args = parser.parse_args()
    if not __debug__:
        raise RuntimeError("Run without -O: validation assertions must remain enabled.")
    paks = args.paks.resolve()
    packages = sorted(paks.glob("*.pak"))  # Deliberately excludes ~mods.
    if not packages:
        raise RuntimeError(f"No game PAK files found in {paks}")
    retoc = ROOT / "tools/retoc/retoc.exe"
    for path in (
        b.REPAK,
        b.LOCRES,
        retoc,
        ROOT / "build_release.py",
        ROOT / "plate-translations.json",
    ):
        if not path.is_file():
            raise RuntimeError(f"Required file is missing: {path}")
    key = os.environ.get("TXR_AES_KEY", AES_KEY)
    expected = {
        f"{target}/{culture}/{target}.locres"
        for target in TARGETS
        for culture in b.CULTURES
    }
    with tempfile.TemporaryDirectory(prefix="localized-plates-update-") as work:
        work = Path(work)
        fresh = work / "build/sources"
        fresh.mkdir(parents=True)
        owners = {}
        print("Reading installed game localization resources...", flush=True)
        for number, pak in enumerate(packages):
            paths = b.run(b.REPAK, "--aes-key", key, "list", pak).splitlines()
            selected = [
                p
                for p in paths
                if any(p.startswith(PREFIX + t + "/") for t in TARGETS)
                and p.endswith((".locres", ".locmeta"))
            ]
            if not selected:
                continue
            output = work / f"extract-{number}"
            output.mkdir()
            include = []
            for target in TARGETS:
                include += ["-i", PREFIX + target + "/"]
            b.run(b.REPAK, "--aes-key", key, "unpack", pak, "-o", output, *include)
            for name in selected:
                rel = Path(name.removeprefix(PREFIX))
                if rel.is_absolute() or ".." in rel.parts:
                    raise RuntimeError("Unexpected localization path in package.")
                data = (output / name).read_bytes()
                if rel.as_posix() in owners and (fresh / rel).read_bytes() != data:
                    raise RuntimeError(
                        f"Conflicting copies of {rel} in game packages; manual review needed."
                    )
                owners[rel.as_posix()] = pak.name
                (fresh / rel).parent.mkdir(parents=True, exist_ok=True)
                (fresh / rel).write_bytes(data)
        actual = {p.relative_to(fresh).as_posix() for p in fresh.rglob("*.locres")}
        if actual != expected:
            raise RuntimeError(
                f"Localization layout changed. Missing: {sorted(expected - actual)}; unexpected: {sorted(actual - expected)}"
            )
        translations = json.loads(
            (ROOT / "plate-translations.json").read_text(encoding="utf-8")
        )
        plate_ids = {(e["namespace"], e["key"]) for e in translations}
        changes = {}
        hashes = {}
        for rel in sorted(expected):
            data = (fresh / rel).read_bytes()
            if plate_ids & {e[:2] for e in b.parse(data)}:
                raise RuntimeError(
                    f"The game now includes plate translations in {rel}; manual merge needed."
                )
            previous = ROOT / "sources" / rel
            changes[rel] = compare(
                previous.read_bytes() if previous.exists() else None, data
            )
            hashes[rel] = b.digest(fresh / rel)
        changed = {
            k: v
            for k, v in changes.items()
            if any(v[n] for n in ("added", "removed", "changed"))
        }
        for rel, counts in changed.items():
            print(
                f"{rel}: {counts['added']} added, {counts['removed']} removed, {counts['changed']} changed"
            )
        info_path = ROOT / "source-info.json"
        prior = (
            json.loads(info_path.read_text(encoding="utf-8"))
            if info_path.exists()
            else {}
        )
        translation_hash = b.digest(ROOT / "plate-translations.json")
        inputs_changed = prior.get("plate_translations_sha256") not in (
            None,
            translation_hash,
        )
        release = json.loads((ROOT / "release.json").read_text(encoding="utf-8"))
        from release_metadata import next_patch

        version_changed = bool(
            args.game_version and args.game_version != release["game_version"]
        )
        needed = (
            bool(changed)
            or inputs_changed
            or version_changed
            or bool(args.mod_version)
            or not release_valid()
        )
        print(
            f"Localization files changed: {len(changed)} / {len(expected)}", flush=True
        )
        if args.check:
            print("Update needed." if needed else "No update needed.")
            return
        if not needed and not args.force:
            print("No update needed. Existing release left unchanged.")
            return
        stage = fresh.parent
        # Preserve a known version label only if the installed source bytes match.
        version = args.game_version
        if not version and prior.get("resource_sha256") == hashes:
            version = prior.get("game_version")
        if not version:
            raise RuntimeError(
                "Localization changed: rerun with --game-version X.Y.Z to label the release correctly."
            )
        if args.mod_version:
            next_patch(args.mod_version)
            release["version"] = args.mod_version
        elif version != release["game_version"]:
            release["version"] = next_patch(release["version"])
        release["game_version"] = version
        b.write(stage / "release.json", release)
        info = {
            "game_version": version,
            "built_at_utc": dt.datetime.now(dt.UTC).isoformat(),
            "resource_sha256": hashes,
            "plate_translations_sha256": translation_hash,
            "packages": owners,
        }
        b.write(stage / "source-info.json", info)
        b.write(
            stage / "dist/update-report.json",
            {"resources": changes, "plate_translations_changed": inputs_changed},
        )
        shutil.copy2(
            ROOT / "plate-translations.json", stage / "plate-translations.json"
        )
        env = dict(os.environ, LP_BUILD_ROOT=str(stage))
        env.pop("PYTHONOPTIMIZE", None)
        print("Building and validating both variants...", flush=True)
        subprocess.run(
            [sys.executable, "-B", str(ROOT / "build_release.py")], env=env, check=True
        )
        publish(stage)
        print(f"Ready: {ROOT / 'dist/Localized Plates.zip'}")
        print(
            "Install one variant and verify it in-game. Installed mods were not changed."
        )


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        ValueError,
        RuntimeError,
        AssertionError,
        subprocess.SubprocessError,
        zipfile.BadZipFile,
        KeyboardInterrupt,
    ) as exc:
        print(f"Update failed: {exc}", file=sys.stderr)
        sys.exit(1)
