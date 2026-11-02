import hashlib
import io
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

import fetch_tools
import release_metadata
import release_support as b
import update_mod


class ReleaseTests(unittest.TestCase):
    def test_source_hash_change_is_not_hidden_by_identical_text(self):
        old = b.make_locres([("ns", "key", 1, "Engine Type")])
        new = b.make_locres([("ns", "key", 2, "Engine Type")])
        self.assertEqual(update_mod.compare(old, new)["changed"], 1)

    def test_patch_increment(self):
        self.assertEqual(release_metadata.next_patch("1.0.2"), "1.0.3")
        self.assertEqual(release_metadata.next_patch("1.0.9"), "1.0.10")
        with self.assertRaises(ValueError):
            release_metadata.next_patch("1.0.2\nmalformed")

    def test_download_checksum_and_nested_archive(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("nested/tool.exe", b"example binary")
        data = stream.getvalue()
        item = {"sha256": hashlib.sha256(data).hexdigest(), "member": "tool.exe"}
        self.assertEqual(fetch_tools.verified_payload(data, item), b"example binary")
        with self.assertRaises(ValueError):
            fetch_tools.verified_payload(data + b"changed", item)

    def test_source_and_version_mismatches_block_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("release.json", "source-info.json", "plate-translations.json"):
                shutil.copy2(b.ROOT / name, root / name)
            shutil.copytree(b.ROOT / "sources", root / "sources")
            release_metadata.validate(root)
            target = next((root / "sources").rglob("*.locres"))
            original = target.read_bytes()
            target.write_bytes(original + b"changed")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                release_metadata.validate(root)
            target.write_bytes(original)
            release = json.loads((root / "release.json").read_text())
            release["game_version"] = "9.9.9"
            (root / "release.json").write_text(json.dumps(release))
            with self.assertRaisesRegex(ValueError, "does not match"):
                release_metadata.validate(root)


if __name__ == "__main__":
    unittest.main()
