"""Local personal-package helper: synthetic PE/Mach-O bytes, no Microsoft DLLs."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import zipfile

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("runtime_ipa", root / "tools/prepare-vcruntime-ipa.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
with tempfile.TemporaryDirectory(prefix="madeira-personal-test-") as folder:
    p = Path(folder); runtimes = p / "runtime"; runtimes.mkdir()
    native = bytearray(32); native[:4] = b"\xcf\xfa\xed\xfe"
    dll = bytearray(1024); dll[:2] = b"MZ"; struct.pack_into("<I", dll, 0x3c, 128)
    dll[128:132] = b"PE\0\0"; struct.pack_into("<H", dll, 132, 0x8664)
    struct.pack_into("<H", dll, 152, 0x20b); struct.pack_into("<II", dll, 296, 1000, 24)
    for name in module.DLLS: (runtimes / name).write_bytes(dll)
    (runtimes / "MICROSOFT-LICENSE.rtf").write_text("Synthetic test terms, no Microsoft binaries")
    source = p / "input.ipa"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("Payload/Madeira.app/Madeira", native)
        archive.writestr("Payload/Madeira.app/kept.txt", b"unchanged")
    before = source.read_bytes(); output = p / "personal.ipa"
    result = module.prepare(source, runtimes, output)
    assert len(result) == 12 and source.read_bytes() == before
    with zipfile.ZipFile(output) as archive:
        assert archive.read("Payload/Madeira.app/kept.txt") == b"unchanged"
        for name in module.DLLS: assert archive.read(module.PREFIX + name) == bytes(dll)
    def rejected(action):
        try: action()
        except ValueError: return
        raise AssertionError("Invalid input accepted")
    rejected(lambda: module.prepare(source, runtimes, output))
    rejected(lambda: module.prepare(output, runtimes, p / "duplicate.ipa"))
    (runtimes / module.DLLS[0]).write_bytes(dll[:1000])
    rejected(lambda: module.prepare(source, runtimes, p / "truncated.ipa"))
    assert not (p / "truncated.ipa").exists()
    bad = bytearray(dll); struct.pack_into("<H", bad, 132, 0xaa64)
    (runtimes / module.DLLS[0]).write_bytes(bad)
    rejected(lambda: module.prepare(source, runtimes, p / "arm.ipa"))
    (runtimes / module.DLLS[0]).write_bytes(dll)
    signed = p / "signed.ipa"; command = struct.pack("<IIII", 0x1d, 16, 0, 0)
    struct.pack_into("<I", native, 16, 1)
    with zipfile.ZipFile(signed, "w") as archive:
        archive.writestr("Payload/Madeira.app/Madeira", native + command)
    rejected(lambda: module.prepare(signed, runtimes, p / "signed-copy.ipa"))
    assert not list(p.glob("madeira-personal-*"))
print("PASS: 12 synthetic runtimes preserved; no overwrite/download; existing payload, PE architecture, certificate truncation and signed-IPA refusal")
