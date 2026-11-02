"""Download checksum-pinned Windows tools from their authors' releases."""

import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def verified_payload(data, item):
    if hashlib.sha256(data).hexdigest() != item["sha256"]:
        raise ValueError("Downloaded tool checksum does not match tools-lock.json")
    if item["member"]:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = [n for n in archive.namelist() if Path(n).name == item["member"]]
            if len(names) != 1:
                raise ValueError(f"Expected exactly one {item['member']} in archive")
            return archive.read(names[0])
    return data


def main():
    lock = json.loads((ROOT / "tools-lock.json").read_text(encoding="utf-8"))
    for name, item in lock.items():
        request = urllib.request.Request(
            item["url"], headers={"User-Agent": "Localized-Plates-builder"}
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = verified_payload(response.read(), item)
        output = ROOT / "tools" / item["destination"]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(payload)
        print(f"Fetched and verified {name}")


if __name__ == "__main__":
    main()
