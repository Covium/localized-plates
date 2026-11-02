"""Binary localization helpers for the verified multilingual release builder."""

import hashlib
import io
import json
import struct
import subprocess
import zlib
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
REPAK = ROOT / "tools/repak/repak.exe"
LOCRES = ROOT / "tools/UnrealLocres.exe"
CULTURES = ("en", "en-AU", "fr", "es", "zh-CN", "zh-TW", "ja")
MAGIC = bytes.fromhex("0e147475674a03fc4a15909dc3377f1b")


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


assets = SimpleNamespace(digest=digest, write=write)


def fstring(s):
    if s.isascii():
        b = s.encode() + b"\0"
        return struct.pack("<i", len(b)) + b
    b = s.encode("utf-16-le") + b"\0\0"
    return struct.pack("<i", -len(b) // 2) + b


def make_locres(entries):
    # Compact v1: no precomputed key hashes; engine computes its native key hashes.
    f = io.BytesIO()
    f.write(MAGIC + b"\x01" + struct.pack("<q", 0))
    namespaces = {}
    for ns, key, source, text in entries:
        namespaces.setdefault(ns, []).append((key, source, text))
    strings = []
    indexes = {}
    f.write(struct.pack("<i", len(namespaces)))
    for ns, rows in namespaces.items():
        f.write(fstring(ns))
        f.write(struct.pack("<i", len(rows)))
        for key, source, text in rows:
            if text not in indexes:
                indexes[text] = len(strings)
                strings.append(text)
            f.write(fstring(key))
            f.write(
                struct.pack(
                    "<Ii",
                    (
                        source
                        if isinstance(source, int)
                        else zlib.crc32(source.encode("utf-32-le"))
                    ),
                    indexes[text],
                )
            )
    offset = f.tell()
    f.write(struct.pack("<i", len(strings)))
    for text in strings:
        f.write(fstring(text))
    f.seek(17)
    f.write(struct.pack("<q", offset))
    return f.getvalue()


def run(exe, *args):
    p = subprocess.run(
        [str(exe), *map(str, args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW,
        timeout=60,
        check=False,
    )
    assert p.returncode == 0, p.stdout + p.stderr
    return p.stdout + p.stderr


def parse(data):
    f = io.BytesIO(data)

    def num(fmt):
        return struct.unpack(fmt, f.read(struct.calcsize(fmt)))[0]

    def string():
        n = num("<i")
        if n == 0:
            return ""
        raw = f.read(abs(n) * (2 if n < 0 else 1))
        return raw[:-2].decode("utf-16-le") if n < 0 else raw[:-1].decode("utf-8")

    magic = f.read(16)
    if magic == MAGIC:
        v = num("<B")
    else:
        v = 0
        f.seek(0)
    assert 0 <= v <= 3
    strings = []
    if v >= 1:
        offset = num("<q")
        pos = f.tell()
        f.seek(offset)
        for _ in range(num("<i")):
            strings.append(string())
            if v >= 2:
                num("<i")
        f.seek(pos)
    total = num("<i") if v >= 2 else None
    entries = []
    for _ in range(num("<i")):
        if v >= 2:
            num("<I")
        ns = string()
        for _ in range(num("<i")):
            if v >= 2:
                num("<I")
            key = string()
            h = num("<I")
            text = strings[num("<i")] if v >= 1 else string()
            entries.append((ns, key, h, text))
    assert len({(ns, k) for ns, k, _, _ in entries}) == len(entries)
    if total is not None:
        assert len(entries) == total
    return entries
