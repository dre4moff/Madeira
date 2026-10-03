#!/usr/bin/env python3
"""Package r23 without losing r22 runtime resources; no app/Wine execution."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import re
import shutil
import struct
import subprocess
import tempfile
import zipfile

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--baseline", type=Path, required=True, help="Verified public r22 unsigned IPA")
parser.add_argument("--products", type=Path, required=True, help="Release-iphoneos products directory")
parser.add_argument("--output-directory", type=Path, required=True)
args = parser.parse_args()
baseline = args.baseline.resolve()
products = args.products.resolve()
output = args.output_directory.resolve()
assert hashlib.sha256(baseline.read_bytes()).hexdigest() == "2a1479f05f6dfd350939015a856ac18a0e7148110ee9083de8953028c47a2c82"
output.mkdir(parents=True, exist_ok=True)
name = "Madeira-0.1.1-Fork-r23-Release-unsigned"
ipa = output / (name + ".ipa")
symbols = output / "Madeira-0.1.1-Fork-r23-symbols.zip"
assert not ipa.exists() and not symbols.exists(), "Refusing to overwrite a release"
prefix = "Payload/Madeira.app/"
replacements = {
    "Madeira": products / "Madeira.app/Madeira",
    "Info.plist": products / "Madeira.app/Info.plist",
    "arm64ec-windows/dockhost.exe": root / "app/Madeira/arm64ec-windows/dockhost.exe",
    "arm64ec-windows/dock-notices.txt": root / "app/Madeira/arm64ec-windows/dock-notices.txt",
}
with tempfile.TemporaryDirectory(prefix="madeira-r23-package-") as folder:
    stage = Path(folder)
    with zipfile.ZipFile(baseline) as old:
        assert old.testzip() is None
        for item in old.infolist():
            assert not item.filename.startswith("/") and ".." not in Path(item.filename).parts
        old.extractall(stage)
    app = stage / "Payload/Madeira.app"
    for relative, src in replacements.items():
        shutil.copyfile(src, app / relative)
    executable = app / "Madeira"
    result = subprocess.run(["codesign", "--remove-signature", str(executable)], capture_output=True, text=True)
    assert result.returncode == 0 or "not signed at all" in result.stderr, result.stderr
    info = plistlib.loads((app / "Info.plist").read_bytes())
    assert info["CFBundleVersion"] == "7" and info["CFBundleShortVersionString"] == "0.1.1"
    assert info["CFBundleIdentifier"] == "com.willfaust.madeora"
    assert info["MadeiraProfileBuild"] is False and "r23-launch-clock" in info["MadeiraBuild"]
    assert not list(app.rglob("*.dSYM")) and not list(app.rglob("*debug.dylib"))
    uuid_text = subprocess.check_output(["xcrun", "dwarfdump", "--uuid", str(executable), str(products / "Madeira.app.dSYM")], text=True)
    uuids = re.findall(r"UUID: ([A-F0-9-]+) \(arm64\)", uuid_text)
    assert len(uuids) == 2 and uuids[0] == uuids[1]
    subprocess.run(["ditto", "-c", "-k", "--norsrc", "--noextattr", "--keepParent", "Payload", str(ipa)], cwd=stage, check=True)
    subprocess.run(["ditto", "-c", "-k", "--norsrc", "--noextattr", "--keepParent", str(products / "Madeira.app.dSYM"), str(symbols)], check=True)

changed = []
machos = []
with zipfile.ZipFile(baseline) as old, zipfile.ZipFile(ipa) as new:
    assert new.testzip() is None
    before = {n for n in old.namelist() if not n.endswith("/")}
    after = {n for n in new.namelist() if not n.endswith("/")}
    assert before == after, {"added": sorted(after-before), "removed": sorted(before-after)}
    for n in sorted(after):
        data = new.read(n)
        if data != old.read(n):
            changed.append(n.removeprefix(prefix))
        assert "/x86_64-vcruntime/" not in n and not n.endswith("MICROSOFT-LICENSE.rtf")
        assert "_CodeSignature" not in n and not n.endswith("embedded.mobileprovision")
        if data[:4] == b"\xcf\xfa\xed\xfe":
            assert struct.unpack_from("<I", data, 4)[0] == 0x100000c
            pos = 32
            for _ in range(struct.unpack_from("<I", data, 16)[0]):
                cmd, size = struct.unpack_from("<II", data, pos)
                assert cmd != 0x1d, "Apple signature remains: " + n
                pos += size
            assert b"__DWARF" not in data[:pos]
            machos.append(n.removeprefix(prefix))
    assert set(changed) == set(replacements), changed
    pe = new.read(prefix+"arm64ec-windows/combase.dll")
    pe_offset = struct.unpack_from("<I", pe, 0x3c)[0]
    # Wine publishes the hybrid DLL with an AMD64 compatibility PE header;
    # LLVM identifies the actual ARM64EC image from its hybrid metadata.
    assert struct.unpack_from("<H", pe, pe_offset+4)[0] == 0x8664
    assert pe == old.read(prefix+"arm64ec-windows/combase.dll")
    reader = root / "toolchains/llvm-mingw-20260421-ucrt-macos-universal/bin/llvm-readobj"
    headers = subprocess.check_output([str(reader), "--file-headers", str(root / "app/Madeira/arm64ec-windows/combase.dll")], text=True)
    assert "Format: COFF-ARM64EC" in headers
    assert "MADEIRA_MMDEVICE_IMPLICIT_MTA".encode("utf-16le") in pe
    section_start = pe_offset+24+struct.unpack_from("<H", pe, pe_offset+20)[0]
    for index in range(struct.unpack_from("<H", pe, pe_offset+6)[0]):
        section = pe[section_start+40*index:section_start+40*index+8]
        assert not section.startswith(b".debug"), "PE debug section remains"

    assert len(machos) == 2
    for relative in ("arm64ec-windows/xtajit64.dll", "aarch64-windows/xtajit.dll"):
        assert new.read(prefix+relative) == old.read(prefix+relative)
    assert new.read(prefix+"arm64ec-windows/d3d12.dll") == new.read(prefix+"arm64ec-windows/madeira_d3d12.dll")
report = {
    "configuration": "Release", "native_optimization": "-O2", "swift_optimization": "-O whole-module",
    "build": "7", "debug_support_dylibs": False, "testability": False,
    "profiling_phase_controls": False, "jit_dump_default": "disabled; explicit MADEIRA_JIT_DUMP=1 only",
    "uuid_arm64": uuids[0], "changed_payload_files_from_public_r22": changed,
    "unchanged_payload_files": len(after)-len(changed), "unsigned_macho_files": machos,
    "original_fex_windows_engines_preserved": True, "microsoft_runtime_redistributed": False,
    "validation": "Host ASan/UBSan production argv/Dock and timezone tests, 513 parser parity cases, regression suites and optimized Release compilation/package verification; no new game or iPhone acceptance claimed.",
    "tests": json.loads((root / ".build/r23-audit/host-tests.json").read_text()),
    "combase_optimization": "-O2, stripped ARM64EC PE",
    "audio_compatibility": "r22 COM/audio DLL preserved byte for byte",
    "wineserver_archive": json.loads((root / ".build/r23-audit/wineserver-members.json").read_text()),
    "timezone_consistency": "actual host DST bias cached outside server loop; shared High2/Low/High1 publication",
    "custom_launch_arguments": "per-game; direct/Dock; Windows quoting; <4096 bytes and <=64 tokens; no shell expansion",
    "native_ntdll_archive": {"unchanged_from_r22": True, "sha256": "4d9f5a520f2caedefcd4d7ac7a9d00658042ad3ece006d9925c5fe58c6eca08a"},
}
for artifact in (ipa, symbols):
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    Path(str(artifact)+".sha256").write_text(digest+"  "+artifact.name+"\n")
    report[artifact.suffix[1:]] = {"filename": artifact.name, "bytes": artifact.stat().st_size, "sha256": digest}
(output / "verification.json").write_text(json.dumps(report, indent=2)+"\n")
print(json.dumps({"ipa": str(ipa), "uuid": uuids[0], "changed": changed}, indent=2))
