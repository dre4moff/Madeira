#!/bin/bash
# Build PE ntdll from the wine submodule (ARCH=arm64ec, aarch64 or i386).
# Post-process the ARM64EC output the way
# the app needs: strip, then pad with zeros to SizeOfImage + 0x50000 (the loader
# maps the file image; the padding is the slack the iOS mapping path relies on).
# Other PE modules: build/wine-pe/build-modules.sh (the same build tree; it
# strips them with --strip-debug and does not pad). Requires the llvm-mingw
# toolchain (docs/BUILDING.md).
# --enable-winegstreamer keeps winegstreamer's PE rules although GStreamer is
# absent (its unix side is build/ntdll-unix/winegstreamer_unixlib_ios.c); build
# it as `make dlls/winegstreamer/arm64ec-windows/winegstreamer.dll`, never as
# `make -C dlls/winegstreamer`, which would also try the GStreamer-based .so.
set -eu
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TC="$R/toolchains/llvm-mingw-20260421-ucrt-macos-universal/bin"
export PATH="$TC:$PATH"
if command -v brew >/dev/null 2>&1; then
    BISON_BIN="$(brew --prefix bison 2>/dev/null)/bin"
    [ -x "$BISON_BIN/bison" ] && export PATH="$BISON_BIN:$PATH"
fi
ARCH="${ARCH:-arm64ec}"
case "$ARCH" in
    arm64ec|aarch64) TRIPLE="$ARCH-w64-mingw32" ;;
    i386) TRIPLE=i686-w64-mingw32 ;;
    *) echo "Unsupported PE architecture: $ARCH" >&2; exit 1 ;;
esac
B="$R/wine/build-$ARCH"
if [ ! -f "$B/config.status" ]; then
    mkdir -p "$B" && cd "$B" && ../configure --enable-archs="$ARCH" --without-x --disable-tests --enable-winegstreamer
fi
cd "$B" && make -j"${JOBS:-8}" "dlls/ntdll/$ARCH-windows/ntdll.dll"
SRC="$B/dlls/ntdll/$ARCH-windows/ntdll.dll"; OUT="$R/app/Madeira/$ARCH-windows/ntdll.dll"
cp "$SRC" "$OUT.tmp"
if [ "$ARCH" != arm64ec ]; then
    "$TC/$TRIPLE-strip" --strip-debug "$OUT.tmp"
    mv "$OUT.tmp" "$OUT"
    ls -l "$OUT"
    exit 0
fi
"$TC/$TRIPLE-strip" "$OUT.tmp"
python3 - "$OUT.tmp" <<'PY'
import struct, sys
p = sys.argv[1]; d = open(p, 'rb').read()
pe = struct.unpack_from('<I', d, 0x3c)[0]
soi = struct.unpack_from('<I', d, pe + 24 + 56)[0]     # OptionalHeader.SizeOfImage
# ml1004: PAD UP TO the target, do not blindly append.
#
# The old code asserted `len(d) == soi` and then appended 0x50000. Stripping
# removes sections and debug data, so the stripped file is SMALLER than
# SizeOfImage (measured: 0x120000 stripped vs 0x140000 SizeOfImage) and the
# assert failed on every single run -- this script has never completed, and the
# file was being padded by hand instead. Appending a fixed 0x50000 would also
# have produced the wrong total even if the assert had passed.
#
# The header comment states the intent: pad to SizeOfImage + 0x50000. Compute
# that target and fill up to it, which reproduces the known-good hand-built
# size exactly (0x140000 + 0x50000 = 0x190000 = 1,638,400 bytes).
target = soi + 0x50000
if len(d) > target:
    raise SystemExit("stripped ntdll is %d bytes, already larger than the "
                     "target SizeOfImage(%d) + 0x50000 = %d -- the padding "
                     "assumption no longer holds, do not guess"
                     % (len(d), soi, target))
pad = target - len(d)
with open(p, 'ab') as f:
    f.write(b'\0' * pad)
final = len(open(p, 'rb').read())
if final != target:
    raise SystemExit("padding produced %d bytes, expected %d" % (final, target))
print("ntdll.dll: stripped %d + pad %d = %d bytes (SizeOfImage %d + 0x50000)"
      % (len(d), pad, final, soi))
PY
mv "$OUT.tmp" "$OUT"; ls -l "$OUT"
