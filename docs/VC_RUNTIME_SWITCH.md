# Current build: 0.1.1 / r12

Upstream 0.1.1 integrated with all local r11 implementations retained.
See [UPSTREAM_0_1_1.md](UPSTREAM_0_1_1.md) for changes and validation.

# Historical build: r11

r11 replaces the earlier spatial MetalFX picker with experimental **DLSS via
MetalFX** for 64-bit DirectX 11 games. It preserves the selected virtual display
size, fixing r10's 704x324 launch rejection, and uses the game's own DLSS quality
selection. Old spatial preferences still decode but are inactive. See
[`PERFORMANCE_R11.md`](PERFORMANCE_R11.md) for scope, validation and device checks.

# Per-game native VC++ Runtime

**Historical build: r10.** The user's r9 log revealed that Steam's explorer desktop
still used the saved output resolution, undoing the reduced virtual monitor.
Dock now uses the common session render resolution. D3D11 also bounds MetalFX
output and bypasses scaling when the game already renders at the target size.
Remaining heap/VM and Wine wait/event-history diagnostics now respect quiet
mode; JIT warming, footprint sampling and orphan-lock recovery are retained.
See [PERFORMANCE_R10.md](PERFORMANCE_R10.md). An actual device FPS gain is not
established by these synthetic tests, and the user reports no r9 improvement
even with MetalFX disabled.

The **r9 unsigned IPA** adds per-game **MetalFX upscaling (DirectX 11)**,
local shared-memory texture uploads and safe storage maintenance. Existing
Steam/library resources, controls and compatibility switches are retained.
See [PERFORMANCE_R9.md](PERFORMANCE_R9.md) for the log findings, validation,
build details and limits. MetalFX is opt-in; select Balanced (1.5x) or
Performance (2x) on the game's card and retain Force DirectX 11 for RV.
Games with a saved resolution may need their resolution reduced in-game too.

Storage settings provide a soft shader-cache target of 512 MB, 1 GB or 2 GB.
Only obsolete caches unused for 30 days can be evicted, before Wine starts;
recent caches survive even above the target. Owned abandoned runtime staging
folders and leftover swap files are cleaned. New swap backing remains mapped
but is unlinked after opening, so the OS reclaims it on exit/crash. Only a
closed previous-session log above 64 MB is compacted, keeping its header and
last 8 MB; active session logging is preserved. Game files, saves and Steam
download caches are outside the cleanup scope.

The remaining notes describe earlier builds and their validation. In r9 only
four guest-farm resources differ from the upstream release: rebuilt Dock host
and notices, `d3d11.dll` and `xtajit64.dll`. The other 1,008 runtime resources
are compared byte for byte; the two new DLLs have unchanged exports/ordinals
and no new imported Windows APIs. Do not overwrite them with older binaries
when restoring upstream generated resources.

## Earlier builds

The r8 unsigned IPA follows the user's r7 confirmation: virtual controls work
and device gameplay reaches approximately 25-30 FPS. Further changes target
diagnostic overhead and shader-cache persistence, with no reduction in image
quality or changes to game files, renderer flags, synchronization engine or
JIT allocation.

- Runtime profiling: r7's quiet mode still starts the task sampler, the 250 ms
  performance probe and the W-thread profiler. The latter can suspend running
  guest threads 3,000 times per burst. The app compositor also walks every
  thread's stack every 20 seconds. r8 makes these diagnostic workers respect
  quiet mode, through `build/ntdll-unix/runtime_profiling.h`. Explicit
  `env.MADEIRA_RUNTIME_PROFILING=1` restores them for diagnosis; 0 disables
  them even without quiet mode. This gates creation, not just log output.
  Fault handling, present counters, JIT pool residency protection, memory
  pressure responses and the lightweight ten-second present log remain active.
- Cache persistence: the native DXMT cache resolver has an iOS sandbox path
  correction that defaults only to 32-bit callers. The previous device log
  reports failed cache-path resolution for the x64 game. r8 defaults
  `DXMT_IOS_CACHE_DIR=1` so relative shader database/Metal cache paths resolve
  below the app's Caches directory for x64 as well. Cache keys, schema version,
  shader output and explicit absolute paths remain unchanged. Inherited or
  configured opt-outs win, and a path-creation failure retains the existing
  fallback. Warm cache benefits apply after the relevant shaders have been
  seen; steady gameplay FPS gains are not measured by the host tests.

`[performance-policy]` records the final census/cache/profiling settings after
configuration export. Synthetic tests exercise actual profiling gates with
mocked worker and timer dispatch, and actual Objective-C cache resolver and
SQLite reader/writer classes with synthetic bytes in a temporary host directory.
They cover cold miss, write/read, reopening, version separation, absolute paths,
opt-out, unavailable directories and a mocked Metal cache-path fallback. No
Metal shader, game, Wine session, simulator or device is executed.
Only the native `server.o` archive member and application are rebuilt; the DXMT
native archive and guest farms remain those delivered in r7. The extracted
server member is checked against the newly compiled object before linking.

Research compared the pinned port to the upstream
[DXMT configuration](https://github.com/3Shain/dxmt/blob/main/dxmt.conf) and
[FEX configuration documentation](https://wiki.fex-emu.com/index.php/Development:Configuring_FEX).
Upstream DXMT exposes frame pacing and spatial-upscaling controls, but these
are not automatically changed here: the current device workload is not yet
separated into CPU/GPU time. No untested FEX memory-model relaxation or large
upstream engine update is applied to the functioning iOS port.

For a native rebuild, use the `compile_one` command/flags from
`build/ntdll-unix/build.sh` on `build/ntdll-unix/server_ios.c`, then replace only
the `server.o` member with `xcrun ar r app/Madeira/libntdll_unix.a
build/ntdll-unix/obj/server.o` and run `xcrun ranlib` on that archive before
building the app. Preserve the other members.

The r7 unsigned IPA follows the user's successful r6 gameplay test and the
reported approximately 15 FPS. Its device log contains 2,839 resource-census
reports (roughly nine per second), producing over 90,000 diagnostic lines on
the DXMT encode thread. r7 defaults `DXMT_CENSUS_THROTTLE=1` before Wine starts,
using the gate already present in the unchanged guest renderer. It scans and
prints at most once per ten seconds; the first report and memory warnings
remain immediate. An explicit environment value or `madeira.cfg` setting wins.
Resource budgets, shader compilation, renderer settings and trimming are unchanged.
The existing session timer now logs ten-second present-counter averages as
`[present-rate]`; these measure submission cadence, not GPU frame duration.
The observed memory footprint peaks near 7.1 GiB and the FEX reuse rate reaches
99%; neither proves which hardware stage limits frame rate. No FPS improvement
is asserted without a new device measurement.

r7 also investigates the user's nonresponsive virtual controls and Xbox Series
S controller. The supplied log enables both input sources and loads the host-
aware XInput DLL, but contains no physical-controller connection beacon.
Library game sessions now reserve player 1 at rest before Wine starts when
controller mappings or a paired gamepad are available. Previously this was
opt-in, and hidden startup controls could leave the slot absent during game
initialization. The serial publisher is drained synchronously before returning,
and physical profiles are refreshed at launch. Developer/desktop sessions keep
the opt-in default; an explicit `env.MADEIRA_PAD_EARLY_SLOT=0` disables reservation.
No control layouts are replaced and no Steam Input settings are modified.

Bounded `[xinput-source]` and `[xinput-host]` beacons distinguish detected iOS
profiles, visible touch mappings, published slot connections, and the first
connected/nonneutral snapshots read by the native Wine query. They do not log
every input event or polling call. Synthetic tests run the actual Swift
publisher against fake GameController/UIKit sources, plus the production C
snapshot transport and win32u query: buttons, sticks, triggers, source merge,
frontend ownership, explicit disabling, early publication, inactive clearing,
disconnect and concurrent reads. They cannot confirm Bluetooth detection or
RV There Yet?'s input handling on the user's device.

The r6 unsigned IPA follows the next device log, which confirms the r5 layout
now allocates the full requested 896 MB and loads the previously excluded
images. There is no pool-exhaustion marker. After 136 presents, the renderer
reports `DeviceTexture: Failed to register mach port for shared texture`;
the RHI thread immediately emits an Unreal D3D11 fatal report. Subsequent
access violations occur during crash handling. The fatal text in the shipped
guest logger is truncated, so it does not expose the complete HRESULT/line.

The failure path in DXMT returns `E_FAIL` when `bootstrap_register2` fails.
r6 uses an iOS-only, native-process-local shared-port registry instead of the
system bootstrap service. Madeira's Wine pseudo-processes run as threads of
one native process, so textures and shared fences can register and resolve
their actual Mach ports there. The registry retains one send right for each
name and supplies an additional right for a successful lookup; failed
registrations/lookups retain no extra right. It refuses duplicate, empty,
unterminated, null-port and dead-port entries, synchronizes concurrent access,
and retains names until native process exit because the guest interface has no
unregister operation. Existing Metal texture import and D3DKMT sharing remain
in use; no shared texture is silently replaced by an unshared one. The macOS
bootstrap path and the remote-backend guard remain unchanged.

The log adds `[wmt-shared-port] register local=1` and `lookup local=1` when
the corresponding operations succeed. Synthetic tests execute the actual
iOS native wrappers with mocked Mach rights, including creator release,
texture/fence lookup, concurrent clients, allocation/retain failures and
balanced ownership at shutdown. Real Metal/IOSurface import, rendering and
gameplay still require device testing. No guest PE binary is rebuilt in r6;
only the native Winemetal object and the application are updated.

The r5 unsigned IPA addresses the JIT address-space shortage exposed by the
latest device log. The requested pool is 896 MB, but the available contiguous
hole only permits 560 MB. Image copies reach roughly 477 MB and FEX tail
reservations consume another 80 MB. `d3d12.dll` (about 18 MB) and
`EOSSDK-Win64-Shipping.dll` (about 19 MB) cannot obtain their pool copies;
the latter subsequently faults during a writable-memory operation while the
present counter remains at 34. DirectX 11 and the native VC overrides are
confirmed enabled in that log.

For a library launch with either compatibility switch enabled, r5 inspects
the installed game's executables (including nested launchers) before allocating
the pool. If every executable that overlaps the fixed-image window supports
ASLR and has a valid supported relocation table, the allocator releases only
its own 128 MB reservation at `0x140000000`. The released space can join the
early pool hole, allowing a larger pool without changing image copies or FEX
cache sizes. Missing, unreadable, malformed, fixed-base or unsupported files,
directory links and incomplete scans retain the previous protected layout.
Games starting outside that window do not require that reservation. The
inspection never changes game files, Steam configuration or the saved library.

When the reservation is borrowed, another session requires an app restart,
including when the optional usual session guard is disabled. The log records
`[jit-window]` eligibility/release results and `[jit-budget]` with requested
and actually allocated MB. Allocation can still shrink if a sufficiently
large contiguous hole is unavailable; the settings value is a request.
The captured budget fits both failed images after adding 128 MB, but this
is a synthetic geometry check, not evidence of successful device allocation
or of gameplay. Keep both game switches enabled for the next device check.

The r4 unsigned IPA also provides **Force DirectX 11** beside the VC++ switch.
It is off by default, saved per game as optional `forceDirectX11`, and requests
`-dx11` at the next launch. It requires a game with a DirectX 11 renderer.
Direct launches preserve existing arguments and quoted values while removing
conflicting standalone renderer flags. Steam Dock passes `-dx11` as Valve's
user-arguments parameter for both the initial launch and launch retries;
the default Steam launch option and game files remain unchanged. Disabling
restores the original arguments/default renderer.

The second supplied device log confirms native Microsoft DLLs loaded, then
the game selects Madeira's DirectX 12 backend and remains on its splash screen
with the game/render threads waiting. This motivates a selectable DirectX 11
path, matching the user's more stable CrossOver configuration; it does not
establish that every DirectX 12 refusal in the log causes the wait, or that
DirectX 11 has already been verified on the device.

Open a game's card, then **Compatibility & performance → Native VC++ Runtime**.
The switch is available for every library entry, including Steam games. It is
off by default and applies to the next launch. The optional `nativeVCRuntime`
field in `Documents/madeira-library.json` preserves compatibility with v0.1.0
libraries.

When enabled, Wine receives:

```
WINEDLLOVERRIDES=msvcp140,msvcp140_1,msvcp140_2,vcruntime140,vcruntime140_1=n,b
```

This means native first, builtin fallback. Unrelated overrides are preserved,
including DLLs in a comma-separated clause shared with a VC++ DLL. The game's
choice is applied after `madeira.cfg` and inherited by Steam/Dock child
processes. Turning it off restores the prior environment. No DLL override is
written to Wine's shared registry.

Bundled Microsoft x64 DLLs are linked into `sysx64` while enabled. This is the
path used by x64 games spawned through an ARM64 explorer/Steam Dock session.
Direct ARM64EC sessions also link them into `system32`. The ARM64 host retains
its own `system32` libraries, and `sysaa64`/`syswow64` stay architecture-correct.
Madeira removes its own native-runtime symlinks from both managed paths before
refreshing the Wine DLL farms, so switching off restores the original Wine
implementations and removes supplemental DLLs without a Wine counterpart. For 32-bit games,
the same load order applies to native x86 DLLs supplied with the game or
installed in the prefix; the bundled x64 DLLs are not installed in syswow64.

The x64 runtime used for this local IPA is Microsoft's 14.44.35211 package,
downloaded from https://aka.ms/vs/17/release/vc_redist.x64.exe, SHA-256
`cc0ff0eb1dc3f5188ae6300faef32bf5beeba4bdd6e8e445a9184072096b713b`.
The twelve DLLs were copied byte for byte from the package's x64 minimum-runtime
cabinet, with certificate payloads intact. Microsoft's license is included in
`x86_64-vcruntime/MICROSOFT-LICENSE.rtf`; these files are outside Madeira's GPL
license and are not committed to Git.

## Synthetic validation

- C tests under AddressSanitizer and UndefinedBehaviorSanitizer: merging,
  existing overrides, mixed clauses, repeated activation, config precedence,
  on/off transitions, absent versus empty environment, and per-session isolation.
- Swift PE fixtures: valid relocations, fixed-base/helper executables, missing
  and damaged headers, bounded reads, path containment and links; the actual
  reservation-release block also runs against a mocked Mach allocator for
  opt-out, ownership, failure and success cases. No executable memory is used.
- Winemetal shared-port tests under AddressSanitizer/UndefinedBehaviorSanitizer:
  the actual iOS register/lookup wrappers with mocked Mach references, concurrent
  clients, creator release, malformed requests, duplicate names, memory/right
  failures, missing lookups and balanced cleanup. No real Mach port is created.
- Swift Codable tests: old-library decoding, persisted on/off choices and
  independent game profiles; structural checks for direct and Steam launch wiring.
- DirectX 11 profile tests: persistence, disabling, argument preservation,
  conflicting renderer flags, actual Dock launch and retry calls through a
  fake client callback, and export/reset after global configuration.
- Dock's own host sanitizer tests: client layout, entitlement/launch-result,
  lifecycle and transfer parsing. The modified x64 host is cross-compiled
  from the pinned Dock submodule; no client library or real Steam login runs.
- Objective-C staging blocks run against a temporary synthetic prefix:
  Steam's ARM64 host with an x64 child, direct ARM64EC sessions, repeated
  activation, disabling, supplemental-DLL removal, stale-link repair and
  preservation of user DLLs and ARM64/x86 libraries.
- Full Debug iOS arm64 build with Xcode 27, signing disabled and the Debug dylib
  disabled. Release optimization is not used, per `docs/BUILDING.md`.
- IPA structure, Mach-O dependencies, signature removal, runtime binary identity
  and archive checksum.
- All three Windows resource farms compared byte for byte with the verified
  v0.1.0 release, including Dock, the generated i386 farm and Wine services.
  `python3 tests/test_ipa_resources.py upstream.ipa candidate.ipa` catches
  missing generated resources before delivery. Without `dockhost.exe`,
  `MadeiraDock.enabled` is false and the existing UI hides Steam game sections.
  For r4, supply `app/Madeira` as a third argument: only `dockhost.exe` and its
  generated notices are compared to the rebuilt source outputs instead.
  All other 1,010 farm resources must still match the original byte for byte.

No simulator, device, Wine session or game was launched. Actual game
compatibility remains to be tested on the user's device; the original source
records earlier ARM64EC/FEX exception-handling issues with native VC++ DLLs.

The r3 staging fix follows the supplied device log: the override is enabled,
but the root executable is ARM64 `explorer.exe`; the x64 game then resolves
`msvcp140.dll` and `vcruntime140.dll` through `C:\\windows\\sysx64`, where r2
still linked the Wine implementations. The expanded prefix test reproduces
this route and fails against the actual r2 bridge source, then passes with r3.
All guest binaries except the r4 rebuilt Dock host remain identical to the
original release. Its separate `Madeira-Dock-DirectX11.patch` is included.

## Native prerequisite build notes

The checkout is v0.1.0 (`3ccbf9b8bc97f7a59727d10bb9e98717d2c91d64`).
Wine, FEX and DXMT use their pinned submodule revisions. LLVM 15 is built from
`8dfdcc7b7bf66834a761bd8de445840ef68e4d1a`, freetype from `VER-2-13-3`, and
llvm-mingw 20260421 matches the hash in `docs/BUILDING.md`.

FEX's native CMake build uses `CMAKE_SYSTEM_PROCESSOR=aarch64`, generic CPU
tuning, `CMAKE_MACOSX_BUNDLE=OFF`, and builds `JemallocLibs` as well as
`FEXCore` and `FEXCore_Base`. `FEX_IOS_HOST` is a Windows-guest define and is
not defined in the native iOS build. Two small FEX source guards restrict
Windows-only diagnostics to their platform; their patch is delivered alongside
the application patch. Guest PE DLLs remain those of v0.1.0. r4 rebuilds only
the Dock host executable to forward the selected DirectX 11 argument; its
layout pins are unchanged.

Wine's host configuration and widl produce the generated headers. Its native
config includes `HAVE_GNUTLS_CIPHER_INIT=1` and
`SONAME_LIBGNUTLS="libgnutls.dylib"` so the existing static iOS crypto shim is
compiled. The wineserver base archive is built from the unmodified server
sources not replaced by `build/wineserver/build.sh`, using that script's flags,
then the existing script applies the iOS replacements and symbol renames.

DXMT shader headers are generated using its Meson recipe. Xcode 27's Metal
intrinsic requires the explicit fifth `__METAL_MEMORY_FLAGS_NONE__` argument in
`air_tessellation.metal`; only the temporary build copy is adapted. The DXMT
source tree and guest PE DLLs are unchanged. The resulting unix archive is
merged with the required LLVM iOS archives into `libdxmt_combined.a`.

Final application build:

For r6, apply `Madeira-DXMT-Shared-Ports.patch` in the pinned DXMT checkout and
include the root `build/dxmt-ios/shared_port_registry.h` from the application
patch. Recompile Winemetal and update the exact archive linked by the app:

```sh
MADEIRA_ONLY=winemetal_unix bash build/dxmt-ios/build.sh
xcrun ar r app/Madeira/libdxmt_combined.a build/dxmt-ios/obj/winemetal_unix.o
xcrun ranlib app/Madeira/libdxmt_combined.a
```

The Winemetal member extracted from `app/Madeira/libdxmt_combined.a` must match
the rebuilt object byte for byte before linking. `MADEIRA_ONLY` currently
filters the core compile helpers; the script also recompiles its native D3D9
objects, which are not needed for this change. Preserve the other members of
the existing combined archive, including LLVM and the shader converter.

Before building, restore the generated resources from the official v0.1.0 IPA
(SHA-256 `29054bb5d167382f004ba3ae04d3995e31070e67f4c0acf7eb4f180280f93335`)
into their matching `app/Madeira/` directories: `dockhost.exe` and
`dock-notices.txt` in `arm64ec-windows`, all files in `i386-windows`, and
`plugplay.exe`, `svchost.exe`, `winedevice.exe` in `aarch64-windows`.
These generated resources are not committed upstream. A source-only checkout
does not contain the complete released runtime.
For r4, apply the delivered Dock source patch and run
`bash build/madeira-dock/build.sh --check` to replace only Dock's generated
executable and notices. The patch leaves the pinned client method signature
intact and changes its existing final string argument; the older
[Open Steamworks interface](https://github.com/SteamRE/open-steamworks/blob/master/Open%20Steamworks/IClientAppManager.h)
also identifies that string as user arguments, although its historical ABI
must not be used in place of Madeira's pinned client layouts.

```sh
bash build/stage-licenses.sh
xcodebuild -project app/Madeira.xcodeproj -scheme Madeira \
  -configuration Debug -destination 'generic/platform=iOS' \
  -derivedDataPath .build CODE_SIGNING_ALLOWED=NO \
  CODE_SIGNING_REQUIRED=NO ENABLE_DEBUG_DYLIB=NO build
```

The unsigned IPA has no Apple code signatures or provisioning profile. Use
the accompanying `Madeira.entitlements` when signing for sideloading, preserving
the upstream JIT, debugger and increased-memory entitlements.
