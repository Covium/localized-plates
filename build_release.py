"""Final multilingual release, using the packaging confirmed working in TXR."""

import atexit
import csv
import json
import os
import tempfile
import zipfile
import zlib
from pathlib import Path

import release_support as b

ROOT = Path(os.environ.get("LP_BUILD_ROOT", str(b.ROOT)))
if not __debug__:
    raise RuntimeError("Validation requires Python without -O")
source_info = (
    json.loads((ROOT / "source-info.json").read_text(encoding="utf-8"))
    if (ROOT / "source-info.json").exists()
    else {}
)
version = source_info.get("game_version")
from release_metadata import validate

release = validate(ROOT)
compatibility = (
    ("Built for Tokyo Xtreme Racer " + version + ".")
    if version
    else "Built from the installed Tokyo Xtreme Racer localization resources."
)
_temp = tempfile.TemporaryDirectory(prefix="localized-plates-")
atexit.register(_temp.cleanup)
WORK = Path(_temp.name)
TRANSLATIONS = json.loads(
    (ROOT / "plate-translations.json").read_text(encoding="utf-8")
)
OUT = ROOT / "dist"
RETOC = b.ROOT / "tools/retoc/retoc.exe"
TARGETS = {
    "Game": "original",
    "EarlyAccess": "earlyaccess",
    "FullRelease": "fullrelease",
}
variants = {}
report = {
    "mod_version": release["version"],
    "game_version": version,
    "source_info": source_info,
    "status": "Automated validation passed; in-game verification pending",
    "variants": variants,
}
for variant in ("Replacement", "Bilingual"):
    stage = WORK / "release-stage" / variant
    expected = {}
    counts = {}
    for culture in b.CULTURES:
        additions = []
        for entry in TRANSLATIONS:
            source = entry["source"]
            language = "en" if culture == "en-AU" else culture
            text = source if language == "ja" else entry["translations"][language]
            if variant == "Bilingual" and language != "ja":
                text += f"({source})"
            additions.append(
                (
                    entry["namespace"],
                    entry["key"],
                    zlib.crc32(source.encode("utf-32-le")),
                    text,
                )
            )
        assert len(additions) == 278
        for target, source in TARGETS.items():
            rel = (
                Path("TokyoXtremeRacer/Content/Localization")
                / target
                / culture
                / (target + ".locres")
            )
            original = b.parse(
                (
                    ROOT / "sources" / target / culture / (target + ".locres")
                ).read_bytes()
            )
            old = {e[:2]: e for e in original}
            merged = dict(old)
            for entry in additions:
                assert entry[:2] not in merged
                merged[entry[:2]] = entry
            data = b.make_locres(list(merged.values()))
            decoded = {e[:2]: e for e in b.parse(data)}
            assert decoded == merged
            assert all(decoded[k] == v for k, v in old.items())
            assert all("[LP TEST]" not in e[3] for e in decoded.values())
            path = stage / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            expected[rel.as_posix()] = data
            check = (
                WORK / "release-locres-check" / variant / target / (culture + ".csv")
            )
            check.parent.mkdir(parents=True, exist_ok=True)
            b.run(b.LOCRES, "export", path, "-o", check)
            with check.open(encoding="utf-8-sig", newline="") as f:
                rows = [e for e in csv.DictReader(f) if e["key"]]
            assert len(rows) == len(merged)
            # Independent exporter has a known bare trailing CR issue; binary equality above is exact.
            assert {e["key"]: e["source"].rstrip("\r") for e in rows} == {
                ns + "/" + key: text.rstrip("\r")
                for ns, key, h, text in merged.values()
            }
            counts[rel.as_posix()] = {
                "original_entries_preserved": len(old),
                "plate_entries_added": 278,
            }
    output = OUT / variant
    output.mkdir(parents=True, exist_ok=True)
    b.run(
        RETOC, "to-zen", stage, output / "LocalizedPlates_P.utoc", "--version", "UE5_6"
    )
    # retoc emits empty companion containers for these non-asset resources.
    # Supply their PAK explicitly, using the tested V11 format.
    b.run(b.REPAK, "pack", stage, output / "LocalizedPlates_P.pak", "--version", "V11")
    verified = b.run(RETOC, "verify", output / "LocalizedPlates_P.utoc")
    assert "verified" in verified
    assert "version: V11" in b.run(b.REPAK, "info", output / "LocalizedPlates_P.pak")
    assert set(
        b.run(b.REPAK, "list", output / "LocalizedPlates_P.pak").splitlines()
    ) == set(expected)
    extracted = WORK / "release-package-check" / variant
    extracted.mkdir(parents=True, exist_ok=True)
    b.run(
        b.REPAK, "unpack", output / "LocalizedPlates_P.pak", "-o", extracted, "--force"
    )
    for rel, data in expected.items():
        assert (extracted / rel).read_bytes() == data
    assert {p.name for p in output.iterdir()} == {
        "LocalizedPlates_P.pak",
        "LocalizedPlates_P.ucas",
        "LocalizedPlates_P.utoc",
    }
    variants[variant] = {
        "resources": counts,
        "independent_parser_verified": True,
        "pak_roundtrip_verified": True,
        "iostore_verified": True,
        "files": {
            p.name: {"sha256": b.assets.digest(p), "bytes": p.stat().st_size}
            for p in output.iterdir()
        },
    }
    print(
        variant
        + ": all original translations preserved; test marker absent; all three package files verified.",
        flush=True,
    )
readme = """# Localized Plates

Translates the location and prefecture names in Tokyo Xtreme Racer's license-plate menu. The language follows your in-game language setting, including changes made without restarting the game. The Japanese artwork on the plates remains unchanged.

Supported languages: English, French, Spanish (Spain), Simplified Chinese, and Traditional Chinese. Selecting Japanese displays the original names.

## Installation

Choose one folder:

- Replacement: translated names only, for example Naniwa.
- Bilingual: translated names followed by the original Japanese, for example Naniwa(なにわ).

Close Tokyo Xtreme Racer, then copy the chosen folder's `.pak`, `.ucas`, and `.utoc` files into:

```text
TokyoXtremeRacer/TokyoXtremeRacer/Content/Paks/~mods
```

Create `~mods` if it does not exist. Replace any existing `LocalizedPlates_P` files. Keep all three files together and install only one variant at a time: both variants use the same filenames.

To switch variants, close the game and replace all three files with those from the other folder. To uninstall, remove `LocalizedPlates_P.pak`, `LocalizedPlates_P.ucas`, and `LocalizedPlates_P.utoc`.

## Compatibility

{compatibility}

This mod includes merged copies of the game's localization resources. It may conflict with other mods that replace those resources, and may need an update when a game patch changes translations.
"""
readme = readme.replace("{compatibility}", compatibility)
(OUT / "README.md").write_text(readme, encoding="utf-8")
archive = OUT / "Localized Plates.zip"
expected_names = {"README.md"} | {
    f"{v}/LocalizedPlates_P.{ext}"
    for v in ("Replacement", "Bilingual")
    for ext in ("pak", "ucas", "utoc")
}
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for name in sorted(expected_names):
        z.write(OUT / name, name)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert set(z.namelist()) == expected_names
    for name in z.namelist():
        assert z.read(name) == (OUT / name).read_bytes()
        assert b"[LP TEST]" not in z.read(name)
        assert b"LicensePlateRegions_P" not in z.read(name)
report["archive"] = {
    "sha256": b.assets.digest(archive),
    "bytes": archive.stat().st_size,
    "entries": sorted(expected_names),
    "crc_verified": True,
}
b.assets.write(OUT / "validation.json", report)
print(str(archive), flush=True)
