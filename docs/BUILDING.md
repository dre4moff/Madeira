# Current fork build (0.1.3 r29)

The fork is synchronized with official v0.1.3 and published submodule pins.
Use [FORK_RELEASE.md](FORK_RELEASE.md) for the optimized Release build and
unsigned packaging, [R29_TEXTURE_STREAMING.md](R29_TEXTURE_STREAMING.md) for the
current changes and [R28_UPSTREAM_013.md](R28_UPSTREAM_013.md) for upstream integration.
Build `build/rppairing-ios/build.sh` before Xcode; the app links that library
and embeds its separate StikJIT helper. Preserve app extensions during sideloading.
The historical record below predates this fork; its unpushed-pin and Debug-only
remarks do not describe the current release. Clean-machine relinking and device
acceptance remain separate from the local build verified here.

# Building Madeira from a clean checkout (reproducibility record, 2026-09-16)

This is the "scripts to control compilation and installation" record the
LGPL relink obligation depends on (docs/LICENSING.md). Each step says
whether it has been re-executed from a clean checkout. A fresh recursive
clone of the repository at commit 8a8cabe was tested on 2026-09-16 (with
the submodule URLs redirected to the local forks, since nothing is pushed):
the app target does NOT build from the clone alone, because the inputs
marked "not in the repository" below are absent. Two further findings:
`app/Madeira/x86_64-vcruntime` is required by the project but ignored, and
the submodule commits (FEX, its nested rpmalloc fork, wine branch
`madeira-lgpl`, dxmt) exist only locally: the forks named in `.gitmodules`
(all under github.com/willfaust) do not yet carry them, so a recipient's
recursive clone fails at the first submodule until every fork is pushed. This document is the
remediation; steps marked UNVERIFIED have not yet been re-run from scratch.

## Inputs that are not in the repository

| Input | Why absent | How to obtain | Verified from clean |
|---|---|---|---|
| `toolchains/llvm-mingw-20260421-ucrt-macos-universal/` | 122 MB third-party toolchain | `llvm-mingw-20260421-ucrt-macos-universal.tar.xz` from https://github.com/mstorsjo/llvm-mingw/releases/tag/20260421, SHA-256 `bd85a3975723815cef28dbbd2ca2cb0c926f6b348a12a0453f39f7af273cb3f7`, extracted under `toolchains/` | tarball hash recorded; download UNVERIFIED |
| `toolchains/llvm-project/` + `toolchains/llvm-ios-build/` + `toolchains/llvm-host-build/` | LLVM built for iOS (hours) | upstream llvm-project at commit `8dfdcc7b7` ("[libc++] Fix memory leaks when throwing inside std::vector constructor"); configure `llvm-ios-build` with `-DCMAKE_SYSTEM_NAME=iOS -DCMAKE_OSX_ARCHITECTURES=arm64 -DCMAKE_OSX_SYSROOT=iphoneos -DCMAKE_BUILD_TYPE=Release -DLLVM_HOST_TRIPLE=arm64-apple-ios17.0 -DLLVM_DEFAULT_TARGET_TRIPLE=arm64-apple-ios17.0 -DLLVM_TARGET_ARCH=host -DLLVM_TARGETS_TO_BUILD= -DLLVM_ENABLE_PROJECTS= -DLLVM_BUILD_TOOLS=Off -DLLVM_INCLUDE_TESTS=Off -DLLVM_ENABLE_ZLIB=Off` (values read back from the existing CMakeCache); a host build for tablegen lives in `llvm-host-build` | recipe reconstructed; UNVERIFIED |
| `research/GPTK/Metal Shader Converter 4.0 beta 2.pkg` | Apple installer, 30 MB, licence-bound | Apple developer downloads; SHA-256 `1acc33c87ea663933df89721a998d066106685473020bcbe007cee7a16155734` (pinned in `build/madeira-d3d12/deps.sh`). Only needed to REBUILD the converter fetch; the library itself is tracked | n/a |
| `app/Madeira/x86_64-vcruntime/` | Microsoft Visual C++ 2015-2022 x64 runtime DLLs (concrt140, msvcp140*, vcamp140, vccorlib140, vcruntime140*), redistributable under Microsoft's terms, not under this repository's licence | extract from Microsoft's `vc_redist.x64.exe` (or copy from `C:\Windows\System32` of a licensed Windows install) into that folder | UNVERIFIED |
| `build/wine-mono/wine-mono-11.0.0/` (optional) | Wine Mono, the .NET Framework runtime Wine's mscoree loads (not Microsoft code; licences in `build/wine-mono/COPYING` and `THIRD-PARTY-NOTICES.md`), 41.6 MB download, 228 MB unpacked | `bash build/wine-mono/fetch.sh` downloads `wine-mono-11.0.0-x86.tar.xz` from https://dl.winehq.org/wine/wine-mono/11.0.0/ and checks its SHA-256; `--source` also fetches the matching source tarball. Version and hashes are pinned in `build/wine-mono/pin.sh`, which does not follow `WINE_MONO_VERSION` in `wine/dlls/mscoree/mscoree_private.h`. The Xcode phase "Bundle Wine Mono" runs `build/wine-mono/bundle.sh`, which copies it into `Madeira.app/wine-mono` without the `lib/mono/*-api` reference assemblies and patches the bundled `mscorlib.dll`: **a dirty hack** (4 IL bytes: `GC.Collect` with `GCCollectionMode.Optimized` returns, for Terraria), pinned to the exact file by SHA-256 so the build stops on any other mscorlib; TODO: replace it with a Wine Mono built from source or an upstream fix (see the TODO in `bundle.sh`). Without the folder the app builds without Mono, and .NET Framework programs fail with "Wine Mono is not installed". **Release builds leave Wine Mono out** (2026-10-06): the packaging step deletes `Madeira.app/wine-mono`, and the app downloads it from WineHQ on first use (setup or Settings › .NET Framework, `app/Madeira/WineMono.swift`) | fetch + bundle run on the development machine 2026-10-05; not from a clean checkout |
| A free Apple ID; StikDebug or a pairing file plus LocalDevVPN | signing and JIT runtime requirements | see `docs/JIT.md` | n/a |

## Native build chains (all in the repository)

Run in this order after the inputs above are in place. Outputs are
git-ignored and consumed by the app project.

1. `build/gnutls-ios/build.sh`: GMP 6.3.0, Nettle 3.10.1, GnuTLS 3.8.9 from
   the tracked tarballs in `build/gnutls-ios/src` (SHA256SUMS there) ->
   `app/Madeira/lib{gmp,nettle,hogweed,gnutls}.a` (these four outputs are
   also tracked). Verified: built on the development machine; not re-run
   from a clean checkout.
   `build/ffmpeg/build.sh`: FFmpeg 7.1.1 in an LGPL-only configuration (WMA,
   MPEG audio and PCM decoders; mp3/wav/mov demuxers; no H.264/HEVC/AAC),
   built from the tracked, unmodified release tarball in `build/ffmpeg/src`
   after verifying it against `build/ffmpeg/src/SHA256SUMS` -> headers in `toolchains/ffmpeg-ios/include`
   (read by `build/ntdll-unix/build.sh` for winegstreamer's unix side) and
   `app/Madeira/lib{avformat,avcodec,swresample,avutil}.a` (ignored; the app
   target links them together with VideoToolbox, CoreMedia, CoreVideo,
   AudioToolbox and CoreFoundation). The configure arguments are the ones the
   port was built and device-tested with on the WSL toolchain; the macOS form
   of the script is UNVERIFIED.
2. FEX (submodule, branch ios-port-2607):
   - `FEX/build-ios`: `build/fex-ios/build.sh` (same options as the development CMakeCache) -> `FEX/build-ios/FEXCore/Source/lib{FEXCore,FEXCore_Base,JemallocLibs}.a` and the `External/{cephes,fmt,SoftFloat-3e,xxhash}` archives. Verified from a clean r32 build with explicit aarch64 processor, generic CPU tuning and LTO off; no FEX source patch is required by the current original pin.
   - `FEX/build-arm64ec`: `build/fex-arm64ec/build.sh` (configures with `FEX/Data/CMake/toolchain_mingw.cmake` and the recorded options on first run, builds target `arm64ecfex`, copies `Bin/libarm64ecfex.dll` to `app/Madeira/arm64ec-windows/xtajit64.dll`). The build step was verified this session; the first-run configure in the script is reconstructed from CMakeCache and UNVERIFIED.
3. Wine (submodule, branch madeira-lgpl):
   - unix side: `build/ntdll-unix/build.sh`, `build/wineserver/build.sh`,
     `build/win32u-unix/build.sh` -> `app/Madeira/lib{ntdll_unix,wineserver,win32u_unix}.a`. Verified on the development machine.
   - PE side: `build/wine-pe/build-ntdll.sh` (configures `wine/build-arm64ec` with `--enable-archs=arm64ec --without-x --disable-tests --enable-winegstreamer` on first run, builds `dlls/ntdll`, strips, pads to SizeOfImage + 0x50000, copies to the app). Other PE modules: `build/wine-pe/build-modules.sh <name>...` (same tree; it builds each module's DLL target `dlls/<name>/arm64ec-windows/<name>.dll`, strips it with `--strip-debug` like every shipped builtin and installs it into `app/Madeira/arm64ec-windows/`, or into `$DEST`). Building the DLL target rather than `make -C dlls/<name>` is also what winegstreamer needs (enabled by `--enable-winegstreamer` although GStreamer is absent, since its unix side is `build/ntdll-unix/winegstreamer_unixlib_ios.c`). Without arguments the script rebuilds the stock builtins added for games: `cryptsp`, `d3dx11_43`, `msvcp110`, `msvcr110` and `xaudio2_7` (committed in `app/Madeira/arm64ec-windows/` like every other builtin). It needs bison 3 for `tools/wrc` (macOS ships 2.3; Homebrew's is used when installed). The strip/pad step was verified this session; the configure step is UNVERIFIED from clean; build-modules.sh reproduced the five default DLLs at their shipped sizes on the development machine (2026-10-03).
   - `app/Madeira/arm64ec-windows/` is the DLL farm: every file in it is linked into the prefix (`system32` for x64 sessions, and `sysx64`), so a Wine module is only available if it was built and copied there. The native D3D12 path needs two stock modules in addition to the existing ones: `dcomp.dll` (`make -C dlls/dcomp`; a 64-bit Godot 4 engine loads it before it creates its D3D12 device, and gives up on D3D12 without it) and `ktmw32.dll` (`make -C dlls/ktmw32`; an optional import the same engine probes).
4. DXMT (submodule, branch ios-port):
   - unix side: `build/dxmt-ios/build.sh` (needs `toolchains/llvm-ios-build`) -> `app/Madeira/libdxmt_combined.a` (ignored; the app links it). Verified this session.
   - PE side: `meson setup dxmt/build-arm64ec dxmt -Dbuildtype=release -Dwine_build_path=../../wine/build-arm64ec --cross-file=dxmt/build-arm64ec-win.txt` then `ninja -C dxmt/build-arm64ec src/winemetal/winemetal.dll` (and d3d11.dll) -> copied to `app/Madeira/arm64ec-windows/`. Verified this session (winemetal.dll).
4b. In-app pairing (Built-in StikJIT on iOS 27): `build/rppairing-ios/build.sh`
   (Rust with the `aarch64-apple-ios` target; crates from crates.io at the
   versions in `build/rppairing-ios/Cargo.lock`) -> `app/Madeira/libmadeira_rppairing.a`
   (ignored; the app links it) and the bundled crate notices
   `app/Madeira/legal/LICENSES-rppairing-crates.txt` (tracked). `cargo test`
   in that folder runs its host tests. Verified on the development machine.
5. Native D3D12 runtime: `build/madeira-d3d12/build-pe.sh` -> `d3d12.dll`, `madeira_d3d12.dll` and the test executables in `app/Madeira/arm64ec-windows/` (tracked). Verified this session. `build/madeira-d3d12/fetch-converter.sh` re-verifies the converter library; `build/stage-licenses.sh` refreshes the bundled licence copies (the Xcode build fails if they are stale).
6. App: `xcodebuild -project app/Madeira.xcodeproj -scheme Madeira -destination 'generic/platform=iOS' -allowProvisioningUpdates build` (Debug is the configuration that runs the games; Release builds have crashed the guest), then zip `Payload/Madeira.app` into an IPA and sideload. Verified this session on the development machine.
7. WoW64 (32-bit programs, optional): `build/wine-i386/build.sh` (i386 Wine farm
   -> `app/Madeira/i386-windows/`), `build/fex-wow64/build.sh` (FEX WOW64 module
   -> `app/Madeira/aarch64-windows/xtajit.dll`) and the aarch64 `wow64.dll` /
   `wow64win.dll`; see docs/WOW64.md, "Building". UNVERIFIED on macOS.

## Status of the LGPL relink question

A recipient of a built package can obtain the complete corresponding
source of every LGPL library (Wine fork, GnuTLS, Nettle, GMP, FFmpeg) from the
repository, and the application source and build scripts above. Whether
they can actually relink depends on assembling the "not in the repository"
inputs and re-executing the UNVERIFIED steps; that end-to-end clean-machine
rebuild, signing and installation has NOT been performed. Until it is,
docs/LICENSING.md keeps the relink capability marked unverified. The
alternative the LGPL offers, shipping the application's object files, is
not currently done.

## Fork r32 release build

Use full Xcode (`DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer`).
The native Wine config uses the configured ARM64EC tree's generated headers,
with `HAVE_GNUTLS_CIPHER_INIT=1` and `SONAME_LIBGNUTLS="libgnutls.dylib"`
for the static iOS crypto shim. Keep the PE configuration separate. Build all
three Wine unix archives and retain FreeType in win32u. Rebuild the fork Wine
`ntdll`, `combase` and `wininet` DLLs; the other original Wine farm additions
come from the upstream sync. Rebuild all six DXMT PE libraries and the full
native DXMT/converter archive, then D3D12 plus its new `d3d12core` forwarder.

Fetch the pinned Mono runtime and matching source with
`build/wine-mono/fetch.sh --source`; Xcode bundles the runtime and verifies
the original mscorlib patch. Run `build/stage-licenses.sh` before Xcode.
Build `Release` with `CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO`
and `ENABLE_TESTABILITY=NO ENABLE_DEBUG_DYLIB=NO`. The optimized build is
verified for compilation, resources and host contracts; gameplay/rendering
acceptance still belongs to a physical device. Package with
`tools/package-r32-release.py`; it compares both the r31 payload and every
current original/fork runtime resource rather than freezing the r31 DLL list.

The ignored i386 farm must contain the complete built runtime before Xcode:
use `build/wine-i386/build.sh` (or seed unchanged resources from the verified
previous release, then rebuild changed modules). r32 verified the macOS
selected-module path for ntdll, kernelbase, mscoree, combase, wininet and all
six XInput variants, and rebuilt/staged all seven i386 DXMT frontend files.
The original WoW64 service executables must also remain in aarch64-windows.
A final PE import scan covers all three farms; r32 supplies bluetoothapis.dll
for the existing bthprops.cpl dependency.
