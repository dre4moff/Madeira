# Fork release and personal runtime setup

Release: `v0.1.1-fork-r21`, based on official Madeira `v0.1.1`. This is an
unofficial, experimental prerelease. The app is optimized Release (`-O2` native,
`-O` whole-module Swift), build 5, with external symbols outside the IPA. Profiling phase controls and Debug support dylibs are disabled.
The public IPA is unsigned; it needs personal signing/sideloading and JIT.

## Install

1. Download `Madeira-0.1.1-Fork-r21-Release-unsigned.ipa` from
   [this fork's releases](https://github.com/dre4moff/Madeira/releases).
2. For games needing Microsoft native VC++ runtime, first prepare your personal
   IPA as below. Microsoft binaries are deliberately absent from public assets.
3. Sideload/sign with your usual tool and Apple ID. Preserve the same bundle ID
   if updating an existing installation; do not uninstall merely to update.
4. Enable JIT through Madeira's existing button/StikDebug and check Memory+.
5. On the game's card enable **Native VC++ Runtime** and **Force DirectX 11**
   when needed. RV There Yet? was tested this way. For a DX12 game, leave Force
   DirectX 11 off; the opt-in DLSS/MetalFX bridge supports Madeira D3D12 too.

The bridge switch only makes NGX/MetalFX available. The game must expose and
select DLSS and reach feature evaluation; it is not a universal upscaling toggle.

## Supply the Microsoft runtime locally

Obtain Microsoft's official x64 Visual C++ redistributable and extract its
unmodified files and accompanying terms; [upstream instructions](../tools/fetch-vcruntime.md).
The local folder needs all twelve DLLs listed there and `MICROSOFT-LICENSE.rtf`.
Their Microsoft license is separate from this project. They are not downloaded
or redistributed by the helper. Do not strip their certificate payloads.

Run on macOS with Python 3:

```sh
python3 tools/prepare-vcruntime-ipa.py \
  --ipa /path/to/Madeira-0.1.1-Fork-r21-Release-unsigned.ipa \
  --runtime-dir /path/to/your/unmodified-x64-runtime \
  --output /path/to/Madeira-r21-personal-unsigned.ipa
```

The helper checks x64 PE headers and intact certificate ranges, preserves DLL
bytes and the existing app payload, and refuses to overwrite files or patch a
signed/already-runtime-bundled IPA. Certificate presence is not a cryptographic
signature verification. Sign/sideload the **personal** output and enable the
runtime card switch. These personal files are not public release assets.

## Source and rebuilding

```sh
git clone --recurse-submodules --branch v0.1.1-fork-r21 \
  https://github.com/dre4moff/Madeira.git
```

Wine, DXMT and Dock are pinned to this fork's published dependency commits.
FEX and its original nested dependencies remain upstream. A recursive source
archive is provided alongside the release for inspecting the complete sources.

[BUILDING.md](BUILDING.md) is upstream's historical build record; its remarks
about unpushed submodules and Debug-only builds predate this fork release.
Its dependency/toolchain recipes are still relevant. This release used Xcode
with an iOS 27 SDK. An end-to-end rebuild on a clean machine was not performed.
The public source includes the existing native-FEX build portability patch and
its provenance; there is no FEX source fork or performance gate.

Rebuild the native Wine/DXMT components, ARM64EC graphics/NVEXT modules and Dock
from the pinned sources as described in the component reports, preserving
unrelated shader converter objects when making a partial rebuild. Restore the
unmodified i386 farm from the SHA-pinned official 0.1.1 IPA when needed. The
upstream package SHA-256 is
`045aeb8fd4c71c2e6a78fb4511f94c56f8ed7af14c47a3b0ea2937a4fc8bfcee`.
Do not build/repackage modified FEX Windows DLLs; use the original official ones.

For the application:

```sh
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild \
  -project app/Madeira.xcodeproj -scheme Madeira -configuration Release \
  -destination 'generic/platform=iOS' -derivedDataPath .build/release \
  CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO ENABLE_DEBUG_DYLIB=NO \
  GCC_OPTIMIZATION_LEVEL=2 SWIFT_OPTIMIZATION_LEVEL=-O \
  DEBUG_INFORMATION_FORMAT=dwarf-with-dsym CURRENT_PROJECT_VERSION=5 ENABLE_TESTABILITY=NO build
```

The historical r17/r18/r19 packagers consume local prior artifacts/checkpoints;
they are audit records, not a promise of one-command clean reproducibility.
For a public package remove Microsoft DLLs, personal terms, provisioning files
and Apple signatures from a **staging copy**, retain license notices, zip its
`Payload` directory and verify resources against the pinned official release.
Do not alter your locally supplied runtime or the source checkout to do so.

## Verification and performance

The release's verification manifest contains the public asset digest, native
UUID, unsigned Mach-O inspection, original FEX identities, resource comparison,
optimization evidence and tests. Native and dSYM UUIDs match.
See the current `verification.json` and `dwarfdump --uuid` output; symbols remain outside the IPA.
r21 rebuilds the app and the two D3D12 DLLs; all other public r20 payload files
are verified byte-identical. See [r21 diagnosis and remaining limits](R21_MESH_DEPTH.md).

[Complete changes](FORK_CHANGELOG.md) distinguish observed gameplay, synthetic
operation counts and unverified FPS/graphics outcomes. Compare the same map,
settings, warm cache and thermal state when testing; do not purge shader caches
between runs. Raw phone logs, IDs, credentials and private traces are not shipped.
