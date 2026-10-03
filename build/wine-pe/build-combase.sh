#!/bin/bash
# Rebuild only ARM64EC combase; do not replace ntdll, FEX, audio or graphics.
set -eu
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TC="$R/toolchains/llvm-mingw-20260421-ucrt-macos-universal/bin"
export PATH="$TC:/opt/homebrew/opt/bison/bin:$PATH"
B="$R/wine/build-arm64ec"
if [ ! -f "$B/config.status" ]; then
    mkdir -p "$B"
    cd "$B"
    ../configure --enable-archs=arm64ec --without-x --disable-tests --enable-winegstreamer
fi
make -C "$B" -j "${MADEIRA_BUILD_JOBS:-6}" dlls/combase/arm64ec-windows/combase.dll
OUT="$R/app/Madeira/arm64ec-windows/combase.dll"
cp "$B/dlls/combase/arm64ec-windows/combase.dll" "$OUT.tmp"
"$TC/arm64ec-w64-mingw32-strip" "$OUT.tmp"
mv "$OUT.tmp" "$OUT"
