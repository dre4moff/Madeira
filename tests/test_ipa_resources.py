"""Compare a locally built IPA with the verified v0.1.1 release; no app launch.

Usage: python3 tests/test_ipa_resources.py upstream.ipa candidate.ipa [rebuilt_bundle]
"""
import hashlib
import plistlib
import sys
import zipfile
from collections import Counter
from pathlib import Path

UPSTREAM_SHA256 = "045aeb8fd4c71c2e6a78fb4511f94c56f8ed7af14c47a3b0ea2937a4fc8bfcee"
PREFIX = "Payload/Madeira.app/"
FARMS = {"aarch64-windows", "arm64ec-windows", "i386-windows"}


def verify(upstream_path, candidate_path, rebuilt_dock_bundle=None):
    assert hashlib.sha256(Path(upstream_path).read_bytes()).hexdigest() == UPSTREAM_SHA256
    with zipfile.ZipFile(upstream_path) as upstream, zipfile.ZipFile(candidate_path) as candidate:
        original_info = plistlib.loads(upstream.read(PREFIX + "Info.plist"))
        candidate_info = plistlib.loads(candidate.read(PREFIX + "Info.plist"))
        assert original_info["CFBundleIdentifier"] == candidate_info["CFBundleIdentifier"]
        names = set(candidate.namelist())
        counts = Counter()
        rebuilt = 0
        # Debug support libraries are deliberately linked into the main binary
        # instead (ENABLE_DEBUG_DYLIB=NO); an unsigned IPA has no CodeResources.
        permitted_absences = {"_CodeSignature/CodeResources", "Madeira.debug.dylib", "__preview.dylib"}
        for name in upstream.namelist():
            if not name.startswith(PREFIX) or name.endswith("/"):
                continue
            relative = name[len(PREFIX):]
            if relative not in permitted_absences:
                assert name in names, f"Missing release resource: {relative}"
            if relative.split("/", 1)[0] not in FARMS:
                continue
            assert name in names, f"Missing release resource: {relative}"
            if rebuilt_dock_bundle and relative in {"arm64ec-windows/dockhost.exe", "arm64ec-windows/dock-notices.txt", "arm64ec-windows/d3d11.dll", "arm64ec-windows/d3d12.dll", "arm64ec-windows/xtajit64.dll", "arm64ec-windows/wininet.dll"}:
                assert candidate.read(name) == (Path(rebuilt_dock_bundle) / relative).read_bytes(), f"Wrong rebuilt resource: {relative}"
                rebuilt += 1
                continue
            assert candidate.read(name) == upstream.read(name), f"Changed release resource: {relative}"
            counts[relative.split("/", 1)[0]] += 1
        assert set(counts) == FARMS
        assert candidate.read(PREFIX + "arm64ec-windows/dockhost.exe")[:2] == b"MZ"
        assert not any("/_CodeSignature/" in name or name.endswith("embedded.mobileprovision") for name in names)
        if rebuilt_dock_bundle:
            assert rebuilt == 6
            for relative in ["arm64ec-windows/nvapi64.dll", "arm64ec-windows/nvngx.dll"]:
                source = Path(rebuilt_dock_bundle) / relative
                if source.exists():
                    assert candidate.read(PREFIX + relative) == source.read_bytes(), f"Wrong added NVEXT resource: {relative}"
        print(f"PASS: bundle identity and {sum(counts.values())} byte-identical release resources: {dict(counts)}; {rebuilt} verified rebuilt Dock/DXMT/FEX/WinINet files")
        return counts


if __name__ == "__main__":
    assert len(sys.argv) in (3, 4), __doc__
    verify(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) == 4 else None)
