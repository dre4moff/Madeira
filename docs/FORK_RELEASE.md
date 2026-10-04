# Fork release and personal runtime setup

Release: `v0.1.3-fork-r30`, based on official Madeira `v0.1.3`. This is an
unofficial, experimental prerelease. The app is optimized Release (`-O2` native,
`-O` whole-module Swift), build 14, with external symbols outside the IPA. Profiling phase controls and Debug support dylibs are disabled.
Texture copy changes and the r29 regression are explained in [the r30 report](R30_NATIVE_TEXTURE_UPLOADS.md).
The public IPA is unsigned; it needs personal signing/sideloading and JIT.

## Install

1. Download `Madeira-0.1.3-Fork-r30-Release-unsigned.ipa` from
   [this fork's releases](https://github.com/dre4moff/Madeira/releases).
2. For games needing Microsoft native VC++ runtime, first prepare your personal
   IPA as below. Microsoft binaries are deliberately absent from public assets.
3. Sideload/sign with your usual tool and Apple ID. Preserve the same bundle ID
   if updating an existing installation; do not uninstall merely to update.
4. Keep app extensions during sideloading, then configure built-in JIT or
   StikDebug as described in [JIT.md](JIT.md). Check Memory+ before launching.
5. On the game's card enable **Native VC++ Runtime** and **Force DirectX 11**
   when needed. RV There Yet? was tested this way. For a DX12 game, leave Force
   DirectX 11 off; the opt-in DLSS/MetalFX bridge supports Madeira D3D12 too.

Use **Custom Launch Arguments** in the game’s card for options such as
`-noaudio` or `-windowed`. Keep **Force DirectX 11** as the separate renderer
choice. Double-quote argument values containing spaces. These values reach
the actual game executable in both direct and Steam/Dock starts.

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
  --ipa /path/to/Madeira-0.1.3-Fork-r30-Release-unsigned.ipa \
  --runtime-dir /path/to/your/unmodified-x64-runtime \
  --output /path/to/Madeira-r30-personal-unsigned.ipa
```

The helper checks x64 PE headers and intact certificate ranges, preserves DLL
bytes and the existing app payload, and refuses to overwrite files or patch a
signed/already-runtime-bundled IPA. Certificate presence is not a cryptographic
signature verification. Sign/sideload the **personal** output and enable the
runtime card switch. Keep **MadeiraJITHelper.appex** when the sideloader asks
about app extensions; built-in JIT requires it. See [JIT setup](JIT.md). These personal files are not public release assets.

## Source and rebuilding

```sh
git clone --recurse-submodules --branch v0.1.3-fork-r30 \
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
  DEBUG_INFORMATION_FORMAT=dwarf-with-dsym CURRENT_PROJECT_VERSION=13 ENABLE_TESTABILITY=NO build
```

The historical r17/r18/r19 packagers consume local prior artifacts/checkpoints;
they are audit records, not a promise of one-command clean reproducibility.
For a public package remove Microsoft DLLs, personal terms, provisioning files
and Apple signatures from every nested executable in a **staging copy**, retain license notices, zip its
`Payload` directory and verify resources against the pinned official release.
Do not alter your locally supplied runtime or the source checkout to do so.

## Verification and performance

The release's verification manifest contains the public asset digest, native
UUID, unsigned Mach-O inspection, original FEX identities, resource comparison,
optimization evidence and tests. Native and dSYM UUIDs match.
See the current `verification.json` and `dwarfdump --uuid` output; symbols remain outside the IPA.
r30 retains the official 0.1.3 app and native changes with all retained fork
fixes. The native WineMetal object gains the upload operation; every other
native object matches r29, preserving the r27 thread/signal engine and the
shader converter cache identity. See [r30 analysis](R30_NATIVE_TEXTURE_UPLOADS.md).

[Complete changes](FORK_CHANGELOG.md) distinguish observed gameplay, synthetic
operation counts and unverified FPS/graphics outcomes. Compare the same map,
settings, warm cache and thermal state when testing; do not purge shader caches
between runs. Raw phone logs, IDs, credentials and private traces are not shipped.

## r25 audio and validation

Before starting a game, open **Settings → Audio devices → Enable microphone
for games**, grant iOS permission and choose an available input. The session
menu also provides the input selector and system output route picker. Windows
receives the real iOS port names/UIDs and captured microphone samples (mono or
duplicated stereo, PCM16/PCM32/float32), not a fake silent capture endpoint.

iOS has one current output route and one shared input route; multiple Windows
clients cannot independently use different physical microphones. Connecting a
new device updates the native route snapshot; a game that caches its Windows
endpoint list may need a restart to enumerate newly connected ports. Bluetooth
microphone use can change the output profile/quality. Microphone access is off
by default and cannot be enabled after Wine has launched without restarting.
No microphone recordings or audio sample dumps are written.

This release addresses the observed JIT placement failure, removes a UI wait
on cache scanning, and omits conservative D3D12 read-only transition commands.
These are verified source/build and synthetic results, **not a measured FPS
improvement on a phone**. FEX source and both official Windows engine DLLs
remain unchanged.

**MECCHA CHAMELEON matchmaking remains unresolved.** The user reports the same
manual-time warning with Crossplay disabled; r24 already publishes the real UTC
time, local DST bias and a valid advancing shared tick multiplier. We do not
fake service/device time or bypass the game's online checks. See
[R25 validation and remaining issues](R25_JIT_AUDIO.md) for reproduction details.

## r26 YAPYAP startup

The native stack allocation fix retains the iOS address floor during 64-bit
process boot; it preserves the real microphone path and every r25 engine.
31 synthetic suites pass, including a before/after production allocator replay.
Phone acceptance must cover startup and actual spoken spell recognition; neither
is claimed from the synthetic run. See [r26 details](R26_VOICE_THREAD_STACKS.md).
