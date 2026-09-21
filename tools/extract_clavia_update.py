#!/usr/bin/env python3
"""
Extract Clavia "OS update file V1.0" payloads from official Nord Modular updaters.

The Windows updater embeds the update in a PE resource (type 0x4AE, id 0x80).
The payload is a proprietary, encrypted/obfuscated MIDI transfer image — not a
512 KB boot ROM. This tool extracts the header and raw payload for analysis;
it does not reconstruct Roms/NORD-MODULAR-RACK-VER-3.03.BIN (that requires
reversing the transform applied before/during transmission).

Usage:
  python3 tools/extract_clavia_update.py \\
    Roms/official-updater/win/Nord\\ Modular\\ OS\\ v3.03b\\ Update.exe \\
    -o /tmp/modular-update-payload.bin

  python3 tools/extract_clavia_update.py --dump-header payload.bin
"""

from __future__ import annotations

import argparse
import hashlib
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

MAGIC = b"Clavia OS update file V1.0\x00"
KNOWN_MODELS = (b"Modular\x00", b"Micro Modular\x00")


@dataclass(frozen=True)
class UpdateHeader:
    magic: bytes
    model: str
    version: int
    block_count: int
    digest: bytes
    payload_offset: int
    payload_size: int

    @property
    def version_str(self) -> str:
        return f"{self.version >> 8}.{(self.version & 0xFF):02d}"

    @property
    def payload_blocks(self) -> int:
        return self.block_count


def parse_header(data: bytes, base: int) -> UpdateHeader:
    """Parse header at base; payload immediately follows the 24-byte digest."""
    if not data.startswith(MAGIC, base):
        raise ValueError(f"no magic at offset 0x{base:x}")

    p = base + len(MAGIC)
    model_end = data.index(b"\x00", p)
    model = data[p : model_end + 1]
    if model not in KNOWN_MODELS:
        raise ValueError(f"unknown model {model!r} at 0x{base:x}")

    p = model_end + 1
    version = struct.unpack_from("<H", data, p)[0]
    if version != 0x0303:
        raise ValueError(f"unexpected version 0x{version:04x} at 0x{p:x}")

    # After the version, Clavia inserts zero padding then a uint16 block count
    # (payload bytes = count × 256), a zero separator, and a 24-byte digest.
    # "Micro Modular" is longer than "Modular", so the zero run length differs,
    # but the digest always sits immediately before the payload.
    search_from = p + 2
    search_to = min(len(data), base + 128)
    digest_start = -1
    for i in range(search_from, search_to - 25):
        if data[i + 1 : i + 4] == b"\x98\xde\x28":
            digest_start = i + 1
            break
    if digest_start < 0:
        raise ValueError(f"digest not found after header at 0x{base:x}")

    # uint16 block count sits two bytes before the separator (0x00) that
    # precedes the digest (… 66 05 00 98 de …).
    if data[digest_start - 1] != 0:
        raise ValueError(f"missing digest separator at 0x{digest_start - 1:x}")
    block_count = struct.unpack_from("<H", data, digest_start - 3)[0]
    digest = data[digest_start : digest_start + 24]
    payload_offset = digest_start + 24
    payload_size = block_count * 256
    if payload_offset + payload_size > len(data):
        raise ValueError(
            f"payload truncated: need {payload_size} bytes at 0x{payload_offset:x}, "
            f"file has {len(data) - payload_offset}"
        )
    return UpdateHeader(
        magic=MAGIC,
        model=model[:-1].decode(),
        version=version,
        block_count=block_count,
        digest=digest,
        payload_offset=payload_offset,
        payload_size=payload_size,
    )


def find_embedded_update(data: bytes) -> UpdateHeader:
    """Return the real embedded update (not RTTI false positives)."""
    hits: list[UpdateHeader] = []
    for model in KNOWN_MODELS:
        needle = MAGIC + model
        start = 0
        while True:
            idx = data.find(needle, start)
            if idx < 0:
                break
            try:
                hits.append(parse_header(data, idx))
            except ValueError:
                pass
            start = idx + 1
    if not hits:
        raise ValueError("no valid Clavia OS update header found")
    if len(hits) > 1:
        # Prefer the largest rack payload when scanning generic binaries.
        hits.sort(key=lambda h: h.payload_size, reverse=True)
    return hits[0]


def find_pe_resource_update(data: bytes) -> UpdateHeader | None:
    """Locate update blob in a Windows PE .rsrc section (Win updater layout)."""
    if data[:2] != b"MZ":
        return None
    pe_off = struct.unpack_from("<I", data, 0x3C)[0]
    if pe_off + 4 > len(data) or data[pe_off : pe_off + 4] != b"PE\0\0":
        return None
    opt = pe_off + 24
    magic = struct.unpack_from("<H", data, opt)[0]
    if magic != 0x10B:
        return None
    dd_off = opt + 96
    rsrc_rva, _rsrc_size = struct.unpack_from("<II", data, dd_off + 2 * 8)
    nsects = struct.unpack_from("<H", data, pe_off + 6)[0]
    opt_size = struct.unpack_from("<H", data, pe_off + 20)[0]
    sh = opt + opt_size

    def rva_to_off(rva: int) -> int | None:
        for i in range(nsects):
            o = sh + i * 40
            vaddr, raw_size, raw_off = struct.unpack_from("<III", data, o + 12)
            if vaddr <= rva < vaddr + raw_size:
                return raw_off + (rva - vaddr)
        return None

    rsrc_off = rva_to_off(rsrc_rva)
    if rsrc_off is None:
        return None

    def walk_dir(off: int, path: tuple[int, ...]) -> list[tuple[tuple[int, ...], int, int]]:
        out: list[tuple[tuple[int, ...], int, int]] = []
        num = struct.unpack_from("<HH", data, off + 12)[0] + struct.unpack_from(
            "<H", data, off + 14
        )[0]
        for i in range(num):
            name_rva, entry_rva = struct.unpack_from("<II", data, off + 16 + i * 8)
            is_dir = entry_rva & 0x80000000
            entry_rva &= 0x7FFFFFFF
            if is_dir:
                out.extend(walk_dir(rsrc_off + entry_rva, path + (name_rva,)))
            else:
                de = rsrc_off + entry_rva
                data_rva, size, _cp, _res = struct.unpack_from("<IIII", data, de)
                file_off = rva_to_off(data_rva)
                if file_off is not None:
                    out.append((path + (name_rva,), size, file_off))
        return out

    for path, _size, file_off in walk_dir(rsrc_off, ()):
        if len(path) >= 2 and (path[0] & 0xFFFF) == 0x4AE and (path[1] & 0xFFFF) == 0x80:
            try:
                return parse_header(data, file_off)
            except ValueError:
                continue
    return None


def extract_payload(data: bytes) -> tuple[UpdateHeader, bytes]:
    header = find_pe_resource_update(data) or find_embedded_update(data)
    payload = data[header.payload_offset : header.payload_offset + header.payload_size]
    return header, payload


def count_f0_f7_frames(payload: bytes) -> int:
    count = 0
    i = 0
    while i < len(payload):
        if payload[i] == 0xF0:
            j = payload.find(b"\xF7", i + 1)
            if j != -1 and j - i < 512:
                count += 1
                i = j + 1
                continue
        i += 1
    return count


def print_header(header: UpdateHeader, payload: bytes) -> None:
    print(f"magic:        {header.magic[:-1].decode()}")
    print(f"model:        {header.model}")
    print(f"version:      0x{header.version:04X} ({header.version_str})")
    print(f"block_count:  {header.block_count} (payload = blocks × 256 bytes)")
    print(f"payload_size: {header.payload_size} (0x{header.payload_size:X})")
    print(f"digest:       {header.digest.hex()}")
    print(f"payload_off:  0x{header.payload_offset:X}")
    print(f"payload_sha256: {hashlib.sha256(payload).hexdigest()}")
    print(f"F0..F7 frames (<512 B): {count_f0_f7_frames(payload)}")
    print(
        "note: frames use F0 01 xx… / F0 xx… prefixes, not Clavia F0 33 sysex; "
        "payload entropy ≈ 8 bits/byte"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        help="Official updater (.exe) or raw payload file",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write extracted payload bytes here",
    )
    parser.add_argument(
        "--dump-header",
        action="store_true",
        help="With a payload file, re-parse header from a sibling .exe if given",
    )
    args = parser.parse_args()

    if args.input is None:
        parser.print_help()
        return 1

    data = args.input.read_bytes()
    if args.dump_header and len(data) == 385024:
        print("Raw payload file; header not present in standalone blob.", file=sys.stderr)
        print(f"sha256: {hashlib.sha256(data).hexdigest()}")
        print(f"F0..F7 frames: {count_f0_f7_frames(data)}")
        return 0

    try:
        header, payload = extract_payload(data)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print_header(header, payload)

    if args.output:
        args.output.write_bytes(payload)
        print(f"wrote {len(payload)} bytes to {args.output}")

    print(
        "\nROM reconstruction: NOT AVAILABLE from this tool. "
        "The payload is not a 512 KB ROM image and is not a plain flash dump; "
        "the 1999 updater decrypts/transforms it before sending MIDI update packets."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
