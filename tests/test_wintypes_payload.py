#!/usr/bin/env python3
"""Verify the WinRT module, its imports and registered activation class in a farm or IPA."""
from pathlib import Path
import struct
import sys
import tarfile
import io
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FARMS = {"arm64ec-windows": 0xA641, "aarch64-windows": 0xAA64, "i386-windows": 0x14C}
CLASS = "Windows.Foundation.Metadata.ApiInformation"


class PE:
    def __init__(self, data):
        self.data = data
        assert data[:2] == b"MZ", "Missing PE header"
        pe = self.u32(0x3C)
        assert data[pe:pe + 4] == b"PE\0\0", "Invalid PE signature"
        self.machine, count = struct.unpack_from("<HH", data, pe + 4)
        optional = pe + 24
        magic = struct.unpack_from("<H", data, optional)[0]
        assert magic in (0x10B, 0x20B)
        self.directories = optional + (112 if magic == 0x20B else 96)
        self.image_base = struct.unpack_from("<Q" if magic == 0x20B else "<I", data,
                                             optional + (24 if magic == 0x20B else 28))[0]
        section = optional + struct.unpack_from("<H", data, pe + 20)[0]
        self.sections = []
        for n in range(count):
            pos = section + n * 40
            name = data[pos:pos + 8].rstrip(b"\0")
            assert not name.startswith(b".debug"), "PE debug section in release"
            size, rva, raw_size, raw = struct.unpack_from("<IIII", data, pos + 8)
            self.sections.append((rva, max(size, raw_size), raw))
        # Wine's --builtin publishes ARM64EC with an AMD64 compatibility header.
        # Its load-config CHPE metadata identifies the actual hybrid architecture.
        if self.machine == 0x8664 and magic == 0x20B:
            config, size = struct.unpack_from("<II", data, self.directories + 10 * 8)
            if config and size >= 0xD0:
                metadata = struct.unpack_from("<Q", data, self.offset(config) + 0xC8)[0]
                if metadata >= self.image_base:
                    self.offset(metadata - self.image_base)
                    self.machine = 0xA641

    def u32(self, offset):
        return struct.unpack_from("<I", self.data, offset)[0]

    def offset(self, rva):
        for start, size, raw in self.sections:
            if start <= rva < start + size:
                return raw + rva - start
        raise AssertionError(f"Unmapped PE RVA {rva:#x}")

    def string(self, rva):
        offset = self.offset(rva)
        return self.data[offset:self.data.index(b"\0", offset)].decode("ascii")

    def imports(self):
        pos = self.offset(self.u32(self.directories + 8))
        result = []
        while any(self.data[pos:pos + 20]):
            result.append(self.string(self.u32(pos + 12)).lower())
            pos += 20
        return result

    def exports(self):
        pos = self.offset(self.u32(self.directories))
        count = self.u32(pos + 24)
        names = self.offset(self.u32(pos + 32))
        return {self.string(self.u32(names + n * 4)) for n in range(count)}


def verify(files):
    with tarfile.open(fileobj=io.BytesIO(files["prefix-template.tar.gz"])) as archive:
        registry = archive.extractfile("prefix/system.reg").read().decode("utf-8")
    key = r"[Software\\Microsoft\\WindowsRuntime\\ActivatableClassId\\" + CLASS + "]"
    pos = registry.index(key)
    block = registry[pos:registry.index("\n[", pos + 1)]
    assert '"DllPath"="C:\\\\windows\\\\system32\\\\wintypes.dll"' in block
    for farm, machine in FARMS.items():
        path = farm + "/wintypes.dll"
        assert path in files, "Missing registered WinRT module: " + path
        data = files[path]
        module = PE(data)
        assert module.machine == machine, "Wrong PE architecture: " + path
        assert CLASS.encode("utf-16le") in data, "Missing activation class: " + path
        assert "DllGetActivationFactory" in module.exports(), "Missing WinRT export: " + path
        for dependency in module.imports():
            assert farm + "/" + dependency in files, "Missing module import: " + farm + "/" + dependency


def files_from_ipa(path):
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        prefix = "Payload/Madeira.app/"
        return {name[len(prefix):]: archive.read(name) for name in archive.namelist()
                if name.startswith(prefix) and not name.endswith("/")}


if __name__ == "__main__":
    if len(sys.argv) == 2:
        files = files_from_ipa(sys.argv[1])
    else:
        app = ROOT / "app/Madeira"
        files = {str(p.relative_to(app)): p.read_bytes() for farm in FARMS for p in (app / farm).iterdir() if p.is_file()}
        files["prefix-template.tar.gz"] = (app / "prefix-template.tar.gz").read_bytes()
    verify(files)
    for missing in ("arm64ec-windows/wintypes.dll", "aarch64-windows/wintypes.dll", "arm64ec-windows/combase.dll"):
        broken = dict(files)
        del broken[missing]
        try:
            verify(broken)
        except AssertionError:
            pass
        else:
            raise AssertionError("Missing dependency accepted: " + missing)
    print("PASS: registered ApiInformation, WinRT export, architecture and import availability in all three farms; missing-module regressions rejected")
