"""Validate portable release inputs and prepare GitHub/Nexus release notes."""

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def next_patch(version):
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError(f"Invalid mod version: {version!r}")
    major, minor, patch = map(int, version.split("."))
    return f"{major}.{minor}.{patch + 1}"


def validate(root=ROOT):
    import release_support as b

    release = json.loads((root / "release.json").read_text(encoding="utf-8"))
    info = json.loads((root / "source-info.json").read_text(encoding="utf-8"))
    next_patch(release["version"])
    if not re.fullmatch(r"\d+\.\d+\.\d+", release["game_version"] or ""):
        raise ValueError("Set a valid game_version in release.json")
    if release["game_version"] != info["game_version"]:
        raise ValueError("Release game version does not match the extracted sources")
    expected = {
        f"{t}/{c}/{t}.locres"
        for t in ("Game", "EarlyAccess", "FullRelease")
        for c in b.CULTURES
    }
    if set(info["resource_sha256"]) != expected:
        raise ValueError(
            "Source manifest does not cover the expected localization resources"
        )
    for rel, digest in info["resource_sha256"].items():
        if b.digest(root / "sources" / rel) != digest:
            raise ValueError(f"Source checksum mismatch: {rel}")
    if b.digest(root / "plate-translations.json") != info["plate_translations_sha256"]:
        raise ValueError("Translations changed; run update_mod.py --force first")
    return release


def main():
    release = validate()
    notes = f"Updated for TXR {release['game_version']}."
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    (dist / "release-notes.md").write_text(notes + "\n", encoding="utf-8")
    values = {"version": release["version"], "changelog": notes, **release["nexus"]}
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            for key, value in values.items():
                if "\n" in str(value) or "\r" in str(value):
                    raise ValueError("Release fields must be single-line values")
                output.write(f"{key}={value}\n")
    print(f"Localized Plates {release['version']}: {notes}")


if __name__ == "__main__":
    main()
