#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Madeira Converter Exception: see ../LICENSE-EXCEPTION.md
"""Add locally supplied, unmodified Microsoft x64 runtimes to an unsigned IPA.

No download, signing, installation or network activity. The output is a personal
build; this project does not distribute Microsoft's runtime binaries.
"""
import argparse
import hashlib
import os
from pathlib import Path
import struct
import tempfile
import zipfile

PREFIX = "Payload/Madeira.app/x86_64-vcruntime/"
DLLS = (
    "concrt140.dll", "msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll",
    "msvcp140_atomic_wait.dll", "msvcp140_codecvt_ids.dll", "vcamp140.dll",
    "vccorlib140.dll", "vcomp140.dll", "vcruntime140.dll", "vcruntime140_1.dll",
    "vcruntime140_threads.dll",
)


def runtime_bytes(path):
    data = path.read_bytes()
    if len(data) < 0x100 or data[:2] != b"MZ":
        raise ValueError(f"Not a PE runtime: {path.name}")
    pe = struct.unpack_from("<I", data, 0x3c)[0]
    if pe + 24 + 152 > len(data) or data[pe:pe + 4] != b"PE\0\0":
        raise ValueError(f"Invalid PE header: {path.name}")
    if struct.unpack_from("<H", data, pe + 4)[0] != 0x8664 or struct.unpack_from("<H", data, pe + 24)[0] != 0x20b:
        raise ValueError(f"Expected an x64 PE32+ runtime: {path.name}")
    cert, size = struct.unpack_from("<II", data, pe + 24 + 112 + 4 * 8)
    if not cert or size < 8 or cert + size > len(data):
        raise ValueError(f"Missing/truncated certificate payload: {path.name}; supply Microsoft's unmodified DLL")
    # Presence is a structural check, not cryptographic signature verification.
    return data


def prepare(ipa, runtime_dir, output):
    ipa, runtime_dir, output = Path(ipa), Path(runtime_dir), Path(output)
    if output.exists() or output.resolve() == ipa.resolve():
        raise ValueError("Output must be a new file; the input is never overwritten")
    payloads = {name: runtime_bytes(runtime_dir / name) for name in DLLS}
    terms = (runtime_dir / "MICROSOFT-LICENSE.rtf").read_bytes()
    if not terms:
        raise ValueError("Supply the accompanying MICROSOFT-LICENSE.rtf terms")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ipa) as source:
        names = source.namelist()
        if len(names) != len(set(names)) or source.testzip() is not None:
            raise ValueError("Invalid or duplicate IPA entries")
        if "Payload/Madeira.app/Madeira" not in names:
            raise ValueError("Expected a Madeira IPA")
        if any("/_CodeSignature/" in n or n.endswith("embedded.mobileprovision") for n in names):
            raise ValueError("Supply the unsigned release IPA")
        native = source.read("Payload/Madeira.app/Madeira")
        if native[:4] != b"\xcf\xfa\xed\xfe" or len(native) < 32:
            raise ValueError("Expected the arm64 Madeira executable")
        position = 32
        for _ in range(struct.unpack_from("<I", native, 16)[0]):
            if position + 8 > len(native):
                raise ValueError("Truncated Mach-O load commands")
            command, size = struct.unpack_from("<II", native, position)
            if size < 8 or position + size > len(native):
                raise ValueError("Invalid Mach-O load command")
            if command == 0x1d:
                raise ValueError("Supply the unsigned release IPA")
            position += size
        if any(n.startswith(PREFIX) and n.lower().endswith(".dll") for n in names):
            raise ValueError("Input already contains Microsoft runtimes; use the public runtime-free IPA")
        fd, scratch = tempfile.mkstemp(prefix="madeira-personal-", suffix=".ipa", dir=output.parent)
        os.close(fd)
        scratch = Path(scratch)
        try:
            with zipfile.ZipFile(scratch, "w", compression=zipfile.ZIP_DEFLATED) as target:
                for item in source.infolist():
                    if item.filename != PREFIX + "MICROSOFT-LICENSE.rtf":
                        target.writestr(item, source.read(item.filename))
                for name, data in payloads.items():
                    target.writestr(PREFIX + name, data)
                target.writestr(PREFIX + "MICROSOFT-LICENSE.rtf", terms)
            with zipfile.ZipFile(scratch) as target:
                if target.testzip() is not None:
                    raise ValueError("Output verification failed")
                for name, data in payloads.items():
                    if target.read(PREFIX + name) != data:
                        raise ValueError("Runtime byte preservation failed")
            os.link(scratch, output)  # exclusive publication, including concurrent runs
        finally:
            scratch.unlink(missing_ok=True)
    return {name: hashlib.sha256(data).hexdigest() for name, data in payloads.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", type=Path, required=True)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        hashes = prepare(args.ipa, args.runtime_dir, args.output)
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        parser.exit(1, f"Error: {error}\n")
    print(f"Created {args.output.name}: {len(hashes)} runtime DLLs copied without modifying bytes.")
    print("Sign/sideload your personal IPA, enable JIT, then enable Native VC++ Runtime on the game's card.")


if __name__ == "__main__":
    main()
