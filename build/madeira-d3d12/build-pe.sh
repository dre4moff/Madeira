#!/bin/bash
# Build madeira_d3d12.dll as ARM64EC, plus the x64 test executable.
#
# --dll-only stages the existing Madeira D3D12 engine into the local app.
# Without it, also compile the synthetic Windows probes (never run them here).
set -eu
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DIR/../.." && pwd)"
MINGW="$REPO_ROOT/toolchains/llvm-mingw-20260421-ucrt-macos-universal/bin"
SRC="$REPO_ROOT/madeira-d3d12/src/pe"
TESTS="$REPO_ROOT/madeira-d3d12/tests/windows"
OUT="${OUT:-$REPO_ROOT/build/madeira-d3d12/out-pe}"
mkdir -p "$OUT"

# A partial graphics rebuild also works after generated DXMT outputs were
# cleaned. Recreate only the import library from the already bundled bridge;
# never relink or replace that bridge to build this DLL.
IMPORT_DIR="$REPO_ROOT/dxmt/build-arm64ec/src/winemetal"
if [ ! -f "$IMPORT_DIR/libwinemetal.dll.a" ]; then
    IMPORT_DIR="$OUT/imports"
    mkdir -p "$IMPORT_DIR"
    "$MINGW/llvm-readobj" --coff-exports "$REPO_ROOT/app/Madeira/arm64ec-windows/winemetal.dll" > "$IMPORT_DIR/exports.txt"
    python3 - "$IMPORT_DIR" <<'PY'
from pathlib import Path
import re, sys
p = Path(sys.argv[1])
names = re.findall(r'^  Name: (\S+)$', (p / 'exports.txt').read_text(), re.M)
assert names and len(names) == len(set(names)), 'Missing/duplicate bridge exports'
(p / 'winemetal.def').write_text('LIBRARY winemetal.dll\nEXPORTS\n' + '\n'.join(names) + '\n')
PY
    "$MINGW/arm64ec-w64-mingw32-dlltool" -d "$IMPORT_DIR/winemetal.def" -l "$IMPORT_DIR/libwinemetal.dll.a"
fi

SHADER_DIR="$REPO_ROOT/build/dxmt-ios/shader-headers"
if [ ! -f "$SHADER_DIR/dxmt_command.h" ]; then
    mkdir -p "$SHADER_DIR"
    xcrun -sdk macosx metal -o "$SHADER_DIR/dxmt_command.air" -c "$REPO_ROOT/dxmt/src/dxmt/dxmt_command.metal"
    xcrun -sdk macosx metallib -o "$SHADER_DIR/dxmt_command.metallib" "$SHADER_DIR/dxmt_command.air"
    xxd -n dxmt_command -i "$SHADER_DIR/dxmt_command.metallib" > "$SHADER_DIR/dxmt_command.h"
fi

# Mesh pipelines cannot rasterize with a nil fragment function, even for
# depth-only passes. Embed a tiny no-output shader for each rendering backend.
# This is built ahead of time, never compiled on a game's frame path.
for PLATFORM in ios macos; do
    if [ "$PLATFORM" = ios ]; then
        SDK=iphoneos; TARGET=air64-apple-ios18.0
    else
        SDK=macosx; TARGET=air64-apple-macos15.0
    fi
    xcrun -sdk "$SDK" metal -target "$TARGET" -O2 -c \
        "$REPO_ROOT/madeira-d3d12/shaders/mesh_null_fragment.metal" \
        -o "$SHADER_DIR/mesh_null_$PLATFORM.air"
    xcrun -sdk "$SDK" metallib "$SHADER_DIR/mesh_null_$PLATFORM.air" \
        -o "$SHADER_DIR/mesh_null_$PLATFORM.metallib"
    xxd -n "madeira_mesh_null_$PLATFORM" -i "$SHADER_DIR/mesh_null_$PLATFORM.metallib" \
        > "$SHADER_DIR/mesh_null_$PLATFORM.h"
done

# Regenerate the stub tables so a toolchain header update cannot silently leave
# the vtables the wrong length.
python3 "$SRC/gen_vtables.py" \
    "$REPO_ROOT/toolchains/llvm-mingw-20260421-ucrt-macos-universal/generic-w64-mingw32/include/d3d12.h" \
    "$SRC/madeira_d3d12_stubs.h" >/dev/null

echo "=== madeira_d3d12.dll (arm64ec) ==="
"$MINGW/arm64ec-w64-mingw32-clang" -shared -O2 -Wall \
    -o "$OUT/madeira_d3d12.dll" "$SRC/madeira_d3d12.c" "$SRC/d3d12.def" \
    -I"$SRC" -I"$REPO_ROOT/build/dxmt-ios/shader-headers" -I"$REPO_ROOT/dxmt/include" -I"$REPO_ROOT/madeira-d3d12/src" -I"$REPO_ROOT/dxmt/src/winemetal" \
    -L"$IMPORT_DIR" -lwinemetal \
    -luuid -lole32
echo "  built $(ls -l "$OUT/madeira_d3d12.dll" | awk '{print $5}') bytes"
# The same binary also ships as d3d12.dll (ml849): the engine reaches it through
# the standard entry points, while the tests keep loading it by the old name.
cp "$OUT/madeira_d3d12.dll" "$OUT/d3d12.dll"
echo "  exports: $("$MINGW/llvm-objdump" --private-headers "$OUT/d3d12.dll" 2>/dev/null | grep -cE '^ +[0-9]+ +0x[0-9a-f]+ +D3D12|^ +[0-9]+ .*D3D12')  (ordinal 101/102 pinned by d3d12.def)"

if [ "${1:-}" = "--dll-only" ]; then
    cp "$OUT/d3d12.dll" "$REPO_ROOT/app/Madeira/arm64ec-windows/d3d12.dll"
    cp "$OUT/madeira_d3d12.dll" "$REPO_ROOT/app/Madeira/arm64ec-windows/madeira_d3d12.dll"
    exit 0
fi

echo "=== d3d12-m2-x64.exe (x86_64 guest) ==="
"$MINGW/x86_64-w64-mingw32-clang" -O2 -Wall \
    -o "$OUT/d3d12-m2-x64.exe" "$TESTS/m2_abi.c" -luuid -lole32
echo "  built $(ls -l "$OUT/d3d12-m2-x64.exe" | awk '{print $5}') bytes"

echo "=== d3d12-vfetch-x64.exe (x86_64 guest, vertex-path differential test, ml906) ==="
"$MINGW/x86_64-w64-mingw32-clang" -O2 -Wall \
    -o "$OUT/d3d12-vfetch-x64.exe" "$TESTS/vfetch_test.c" -I"$TESTS" -luuid -lole32
echo "  built $(ls -l "$OUT/d3d12-vfetch-x64.exe" | awk '{print $5}') bytes"

echo "=== d3d12-cube-x64.exe (x86_64 guest, visible) ==="
"$MINGW/x86_64-w64-mingw32-clang" -O2 -Wall -mwindows \
    -o "$OUT/d3d12-cube-x64.exe" "$TESTS/cube_window.c" -I"$TESTS" -luuid -lole32
echo "  built $(ls -l "$OUT/d3d12-cube-x64.exe" | awk '{print $5}') bytes"
