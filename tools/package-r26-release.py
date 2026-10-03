#!/usr/bin/env python3
"""Package r26 without losing r26 runtime resources; no app/Wine execution."""
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
parser.add_argument("--baseline", type=Path, required=True, help="Verified public r26 unsigned IPA")
parser.add_argument("--products", type=Path, required=True, help="Release-iphoneos products directory")
parser.add_argument("--output-directory", type=Path, required=True)
args = parser.parse_args()
baseline = args.baseline.resolve()
products = args.products.resolve()
output = args.output_directory.resolve()
assert hashlib.sha256(baseline.read_bytes()).hexdigest() == "2b7c0abd80510d4f59b8ca03c6d95e0cb5f17d967a918dc540eb5b63a8a58d77"
output.mkdir(parents=True, exist_ok=True)
name = "Madeira-0.1.1-Fork-r26-Release-unsigned"
ipa = output / (name + ".ipa")
symbols = output / "Madeira-0.1.1-Fork-r26-symbols.zip"
assert not ipa.exists() and not symbols.exists(), "Refusing to overwrite a release"
prefix = "Payload/Madeira.app/"
replacements = {
    "Madeira": products / "Madeira.app/Madeira",
    "Info.plist": products / "Madeira.app/Info.plist",
}
with tempfile.TemporaryDirectory(prefix="madeira-r26-package-") as folder:
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
    assert info["CFBundleVersion"] == "10" and info["CFBundleShortVersionString"] == "0.1.1"
    assert info["CFBundleIdentifier"] == "com.willfaust.madeora"
    assert info["MadeiraProfileBuild"] is False and "r26-voice-thread-stacks" in info["MadeiraBuild"]
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
    for relative in ("arm64ec-windows/xtajit64.dll", "aarch64-windows/xtajit.dll",
                     "arm64ec-windows/dockhost.exe", "arm64ec-windows/dock-notices.txt"):
        assert new.read(prefix+relative) == old.read(prefix+relative)
    assert new.read(prefix+"arm64ec-windows/d3d12.dll") == new.read(prefix+"arm64ec-windows/madeira_d3d12.dll")
report = {
    "configuration": "Release", "native_optimization": "-O2", "swift_optimization": "-O whole-module",
    "build": "10", "debug_support_dylibs": False, "testability": False,
    "profiling_phase_controls": False, "jit_dump_default": "disabled; explicit MADEIRA_JIT_DUMP=1 only",
    "uuid_arm64": uuids[0], "changed_payload_files_from_public_r25": changed,
    "unchanged_payload_files": len(after)-len(changed), "unsigned_macho_files": machos,
    "original_fex_windows_engines_preserved": True, "microsoft_runtime_redistributed": False,
    "baseline_ipa_sha256": hashlib.sha256(baseline.read_bytes()).hexdigest(),
    "validation": "31 synthetic suites: production voice-worker stack failure replay before/after (ASan/UBSan), plus all r25 audio/JIT/D3D12/cache/clock/controller/launch/FEX regressions. Optimized Release compiled. No game was executed for this validation.",
    "tests": json.loads((root / ".build/r26-audit/host-tests.json").read_text()),
    "native_archive_members": json.loads((root / ".build/r26-audit/native-members.json").read_text()),
    "native_ntdll_archive": {"changed_object_from_r25": "virtual.o", "sha256": hashlib.sha256((root / "app/Madeira/libntdll_unix.a").read_bytes()).hexdigest()},
    "yapyap": {"app_id": 3834090,
        "supplied_log_renderer": "Force DX11 enabled; user reports the same startup failure without forcing it",
        "first_failure": "1 MiB kernel-stack STATUS_NO_MEMORY during thread creation, followed by libvosk/libstdc++ std::system_error and exit(3)",
        "fix": "Keep the iOS native 0x100010000 floor at 64-bit process boot; retain existing advisory-ceiling fallback for the 4 GiB kernel/emulator-stack lower bound",
        "microphone": "actual input and permission present in the supplied log; r25 real capture unchanged; voice recognition is not disabled",
        "device_acceptance": "pending; successful startup and spoken spell recognition are not yet established"},
    "retained": ["original FEX/source/Windows DLLs", "all graphics DLLs and MetalFX bridges", "real microphone capture and route selection", "controller", "VC runtime switch and Force DX11", "custom launch arguments", "warm shader cache and cleanup gate", "shared clock/timezone"],
    "matchmaking_acceptance": "MECCHA CHAMELEON manual-time warning remains unresolved; no online or time-check bypass",
    "performance_acceptance": "No measured FPS improvement claimed",
}
assert all(t["passed"] for t in report["tests"]) and len(report["tests"]) == 31
for artifact in (ipa, symbols):
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    Path(str(artifact)+".sha256").write_text(digest+"  "+artifact.name+"\n")
    report[artifact.suffix[1:]] = {"filename": artifact.name, "bytes": artifact.stat().st_size, "sha256": digest}
(output / "verification.json").write_text(json.dumps(report, indent=2)+"\n")
print(json.dumps({"ipa": str(ipa), "uuid": uuids[0], "changed": changed}, indent=2))
