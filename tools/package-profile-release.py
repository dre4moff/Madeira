#!/usr/bin/env python3
"""Package the optimized r18 diagnostic build; never executes Madeira or Wine."""
import hashlib
import importlib.util
import json
from pathlib import Path
import plistlib
import re
import shutil
import struct
import subprocess
import zipfile

root = Path(__file__).resolve().parents[1]
dist = root / "dist"
products = root / ".build/r18-profile/Build/Products/Release-iphoneos"
name = "Madeira-0.1.1-FEX-Original-profile-unsigned-r18"
ipa = dist / (name + ".ipa")
symbols = dist / (name + "-symbols.zip")
stage = root / ".build/r18-package"
if stage.exists():
    raise RuntimeError("Staging directory exists; inspect it before reusing this packager")
if ipa.exists() or symbols.exists():
    raise RuntimeError("Refusing to overwrite a diagnostic release")
app = stage / "Payload/Madeira.app"
app.parent.mkdir(parents=True)
subprocess.run(["ditto", str(products / "Madeira.app"), str(app)], check=True)
for relative in ["Madeira", "d3d12/libmetalirconverter.dylib"]:
    result = subprocess.run(["codesign", "--remove-signature", str(app / relative)], capture_output=True, text=True)
    if result.returncode and "not signed at all" not in result.stderr:
        raise RuntimeError(result.stderr)
for path in app.rglob("_CodeSignature"):
    shutil.rmtree(path)
for path in app.rglob("embedded.mobileprovision"):
    path.unlink()
info = plistlib.loads((app / "Info.plist").read_bytes())
assert info["CFBundleShortVersionString"] == "0.1.1"
assert info["CFBundleIdentifier"] == "com.willfaust.madeora"
assert info["CFBundleVersion"] == "2" and info["MadeiraProfileBuild"] is True
assert "r18-profile" in info["MadeiraBuild"]
subprocess.run(["ditto", "-c", "-k", "--keepParent", "Payload", str(ipa)], cwd=stage, check=True)
subprocess.run(["ditto", "-c", "-k", "--keepParent", str(products / "Madeira.app.dSYM"), str(symbols)], check=True)
spec = importlib.util.spec_from_file_location("resources", root / "tests/test_ipa_resources.py")
resources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resources)
counts = resources.verify("/tmp/Madeira-0.1.1-upstream.ipa", ipa, root / "app/Madeira")
prefix = "Payload/Madeira.app/"
changed = []
machos = []
with zipfile.ZipFile(ipa) as candidate, zipfile.ZipFile(dist / "Madeira-0.1.1-VC-Runtime-DX11-MetalFX-unsigned-r17.ipa") as previous, zipfile.ZipFile("/tmp/Madeira-0.1.1-upstream.ipa") as official:
    assert candidate.testzip() is None
    files = {n for n in candidate.namelist() if not n.endswith("/")}
    before = {n for n in previous.namelist() if not n.endswith("/")}
    assert files == before, {"added": sorted(files - before), "removed": sorted(before - files)}
    for path in sorted(files):
        data = candidate.read(path)
        if data != previous.read(path):
            changed.append(path.removeprefix(prefix))
        if data[:4] != b"\xcf\xfa\xed\xfe":
            continue
        assert struct.unpack_from("<I", data, 4)[0] == 0x100000c
        position = 32
        for _ in range(struct.unpack_from("<I", data, 16)[0]):
            command, size = struct.unpack_from("<II", data, position)
            assert command != 0x1d, "Apple signature still present: " + path
            position += size
        machos.append(path)
    assert set(changed) == {"Info.plist", "Madeira", "arm64ec-windows/xtajit64.dll"}, changed
    assert len(machos) == 2
    for relative in ["arm64ec-windows/xtajit64.dll", "aarch64-windows/xtajit.dll"]:
        assert candidate.read(prefix + relative) == official.read(prefix + relative)
    binary = candidate.read(prefix + "Madeira")
    for marker in [b"[perf-context]", b"[perf-phase]", b"Gameplay phase", b"Performance sample", b"[build-mode] native-optimization=on", b"[cache-cleanup]", b"MADEIRA_GAME_METALFX_DLSS", b"[jit-budget]", b"[dock-auth-stall]"]:
        assert marker in binary, marker
    assert b"[build-mode] native-optimization=off" not in binary
    for path in (root / "app/Madeira/x86_64-vcruntime").glob("*.dll"):
        assert candidate.read(prefix + "x86_64-vcruntime/" + path.name) == (root / "toolchains/vcruntime-x64" / (path.name + "_amd64")).read_bytes()

uuid_output = subprocess.check_output(["xcrun", "dwarfdump", "--uuid", str(app / "Madeira"), str(products / "Madeira.app.dSYM")], text=True)
uuids = re.findall(r"UUID: ([A-F0-9-]+) \(arm64\)", uuid_output)
assert len(uuids) == 2 and uuids[0] == uuids[1]
subprocess.run(["python3", str(root / "tests/test_fex_restoration.py")], check=True)
restoration = json.loads((root / ".build/checkpoints/r18-fex/restoration.json").read_text())
for archive, expected in restoration["preserved_non_fex_archives"].items():
    assert hashlib.sha256((root / "app/Madeira" / archive).read_bytes()).hexdigest() == expected, archive
response_files = list((root / ".build/r18-profile/Build/Intermediates.noindex/Madeira.build/Release-iphoneos/Madeira.build/Objects-normal/arm64").glob("*common-args.resp"))
assert response_files and all("-O2" in p.read_text().split() for p in response_files)
buildlog = Path("/tmp/madeira-r18-profile-build.log").read_text()
assert "BUILD SUCCEEDED" in buildlog and "-O -whole-module-optimization" in buildlog
report = {
    "ipa": ipa.name, "symbols": symbols.name, "configuration": "Release, optimized profiling with dSYM",
    "optimization": {"native": "-O2", "swift": "-O -whole-module-optimization"},
    "uuid_arm64": uuids[0], "changed_bundle_files_from_r17": changed,
    "unchanged_bundle_files_from_r17": len(files) - len(changed),
    "unsigned_macho_files": machos, "upstream_identical_farm_files": sum(counts.values()) + 1,
    "fex_restoration": restoration,
    "validation": "Synthetic host checks and compilation/resource/signature/UUID inspection only. No game, Wine, simulator or physical device execution.",
    "performance": "No device FPS gain claimed; phase-aligned traces still required.",
}
for artifact in [ipa, symbols]:
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    Path(str(artifact) + ".sha256").write_text(digest + "  " + artifact.name + "\n")
    report[artifact.suffix.removeprefix(".")] = {"filename": artifact.name, "bytes": artifact.stat().st_size, "sha256": digest}
(dist / "verification-r18.json").write_text(json.dumps(report, indent=2) + "\n")
shutil.copyfile("/tmp/madeira-r18-profile-build.log", dist / "r18-xcode-build.log")
shutil.rmtree(stage)
print(json.dumps({"ipa": str(ipa), "symbols": str(symbols), "uuid": uuids[0], "changed_from_r17": changed}, indent=2))
