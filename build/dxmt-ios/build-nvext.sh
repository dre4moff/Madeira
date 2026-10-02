#!/bin/bash
# Build DXMT's D3D11 DLSS -> MetalFX bridge for the pinned ARM64EC Wine port.
set -eu
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DXMT_ROOT="$REPO_ROOT/dxmt"
DXMT_BUILD="$DXMT_ROOT/build-arm64ec"
MESON="$REPO_ROOT/toolchains/build-python/bin/meson"
CROSS="$REPO_ROOT/build/dxmt-ios/arm64ec-nvext-generated.ini"
python3 - "$REPO_ROOT" "$CROSS" <<'PY'
from pathlib import Path
import json,sys
root=Path(sys.argv[1]);prefix=root/'toolchains/llvm-mingw-20260421-ucrt-macos-universal/bin'
binaries={'c':'clang','cpp':'clang++','ar':'ar','strip':'strip','windres':'windres'}
out=['[binaries]']+[k+' = '+json.dumps(str(prefix/('arm64ec-w64-mingw32-'+v))) for k,v in binaries.items()]
out += ['[properties]','needs_exe_wrapper = true','[host_machine]',"system = 'windows'","cpu_family = 'aarch64'","cpu = 'aarch64'","endian = 'little'"]
Path(sys.argv[2]).write_text('\n'.join(out)+'\n')
PY
"$MESON" setup --reconfigure "$DXMT_BUILD" "$DXMT_ROOT" --cross-file "$CROSS" \
    --buildtype=release -Dwine_build_path="$REPO_ROOT/wine/build-arm64ec" \
    -Denable_nvapi=true -Denable_nvngx=true
ninja -C "$DXMT_BUILD" src/nvapi/nvapi64.dll src/nvngx/nvngx.dll.postproc src/d3d11/d3d11.dll
DEST="$REPO_ROOT/app/Madeira/arm64ec-windows"
cp "$DXMT_BUILD/src/nvapi/nvapi64.dll" "$DEST/nvapi64.dll"
# Use Wine's ARM64EC-aware builtin path for both shim modules.
"$REPO_ROOT/wine/build-arm64ec/tools/winebuild/winebuild" --builtin "$DEST/nvapi64.dll"
cp "$DXMT_BUILD/src/nvngx/nvngx.dll" "$DEST/nvngx.dll"
cp "$DXMT_BUILD/src/d3d11/d3d11.dll" "$DEST/d3d11.dll"
cp "$DXMT_ROOT/external/nvapi/License.txt" "$REPO_ROOT/app/Madeira/legal/NVIDIA-NVAPI-MIT.txt"
