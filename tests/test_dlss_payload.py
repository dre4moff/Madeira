#!/usr/bin/env python3
"""Inspect the shipped DLSS-to-MetalFX bridge; never start a game or GPU workload."""
from pathlib import Path
import struct
import sys
from test_wintypes_payload import PE, files_from_ipa

ROOT = Path(__file__).resolve().parents[1]
FARM = "arm64ec-windows/"


def verify(files, native=False):
    for name in ("nvngx.dll", "nvapi64.dll", "d3d11.dll", "dxgi.dll", "winemetal.dll", "d3d12.dll", "d3d12core.dll"):
        module = PE(files[FARM + name])
        assert module.machine == 0xA641, "Incorrect bridge architecture: " + name
        for dependency in module.imports():
            if dependency.startswith(("api-ms-", "ext-ms-")):
                continue  # Wine resolves API sets through its apisetschema, not loose DLLs.
            assert FARM + dependency in files, "Missing bridge import: " + dependency
    exports = PE(files[FARM + "nvngx.dll"]).exports()
    for backend in ("D3D11", "D3D12"):
        for call in ("Init", "GetCapabilityParameters", "GetScratchBufferSize", "CreateFeature", "EvaluateFeature", "ReleaseFeature", "Shutdown"):
            assert "NVSDK_NGX_" + backend + "_" + call in exports, (backend, call)
    assert "nvapi_QueryInterface" in PE(files[FARM + "nvapi64.dll"]).exports()
    exports = PE(files[FARM + "d3d12.dll"]).exports()
    for call in ("Supported", "Create", "Record", "Release"):
        assert "MadeiraD3D12Temporal" + call in exports, call
    assert files[FARM + "d3d12.dll"] == files[FARM + "madeira_d3d12.dll"]
    if native:
        code = files["Madeira"]
        assert code[:4] == b"\xcf\xfa\xed\xfe"
        pos = 32
        libraries = []
        for _ in range(struct.unpack_from("<I", code, 16)[0]):
            command, size = struct.unpack_from("<II", code, pos)
            if command in (0xC, 0x80000018):
                name = pos + struct.unpack_from("<I", code, pos + 8)[0]
                libraries.append(code[name:code.index(b"\0", name)].decode())
            pos += size
        assert "/System/Library/Frameworks/MetalFX.framework/MetalFX" in libraries
        assert b"MTLFXTemporalScalerDescriptor" in code
        assert b"[dlss-metalfx] enabled=" in code
        assert files["default.metallib"][:4] == b"MTLB"
        assert files["d3d12/libmetalirconverter.dylib"][:4] == b"\xcf\xfa\xed\xfe"


if __name__ == "__main__":
    if len(sys.argv) == 2:
        files = files_from_ipa(sys.argv[1])
        verify(files, native=True)
    else:
        app = ROOT / "app/Madeira"
        files = {FARM + p.name: p.read_bytes() for p in (app / FARM).iterdir() if p.is_file()}
        verify(files)
    print("PASS: ARM64EC NGX/NVAPI, D3D11/D3D12 exports and imports; native IPA links system MetalFX and contains temporal scaler plus shader resources" if len(sys.argv) == 2 else
          "PASS: ARM64EC NGX/NVAPI, D3D11/D3D12 bridge exports and imported DLL availability")
