# r18: official Madeira FEX restoration and optimized profiling

Local preparation dated 2026-10-02. Nothing has been uploaded, forked on GitHub,
or sent to the upstream developer. This document supersedes earlier reports
where they describe our FEX diagnostic gate. Existing compatibility and
controller changes are retained.

## FEX provenance and the actual restoration

The baseline is **Madeira v0.1.1**, root commit
`ca3183ea3dfb0fd706aff1bea2abb871b5d27aec`, with its own pinned FEX fork at
`26859e184ad90f0e811d7f8bbd943a4b1573a2c3`. This is not a substitution with
vanilla FEX-Emu.

Before restoration, two tracked FEX files differed: `Core.cpp` and `Arm64.cpp`
(39 insertions, 5 deletions). Our nonessential changes cached a quiet/profiling
choice, gated diagnostic counters and reports, and separated the allocator
snapshot reporting cadence. They did not implement the VC runtime fix, DX11
selection or controller support. Those diagnostic changes have been removed.

Both tracked source files are restored verbatim to the pin; the FEX tracked
diff is empty. The ARM64EC `xtajit64.dll` was taken directly from the verified
official v0.1.1 IPA, SHA-256
`dc5c980c2882922775978b030954d245ace82801667599e8457b3b978508fb82`.
The WoW64 `xtajit.dll` was already byte-identical to the official release.
The upstream IPA SHA-256 is
`045aeb8fd4c71c2e6a78fb4511f94c56f8ed7af14c47a3b0ea2937a4fc8bfcee`.

**Native archive qualification:** the linked native FEX Core archive has no
custom diagnostic gate, but retains three existing compiler portability guards
around platform-specific diagnostics: iOS callback capture arrays, a Windows
rpmalloc snapshot, and Windows `VirtualQuery` diagnostics with a native fallback.
The unguarded pinned source does not compile in the Apple native target. The
exact guards are recorded in `dist/Madeira-FEX-native-build-portability.patch`.
They do not introduce a new translation or scheduling optimization. This native
archive is not certified byte-identical to an official native static archive;
upstream does not publish that archive. The source checkout contains none of
these local edits. A clean rebuild of that native archive still needs this
documented portability accommodation or an upstream-approved equivalent.

FEX's `AGENTS.md` says: “AI must not be used to generate code for contributions
to this project.” No new FEX source implementation or FEX contribution was
created for r18. The source restoration is exact. The private native build
qualification above must be disclosed before any future public contribution;
do not describe the entire native engine as byte-identical to official binaries.
Previous modified objects and the pre-restoration diff remain in the ignored
`.build/checkpoints/r18-fex/` directory for recovery, not as current patches.
Future FEX rebuilds must use restored sources, not a stale cached ARM64EC DLL.

Official FEX counters are now independent of `MADEIRA_RUNTIME_PROFILING`.
Disabling that switch still controls our existing Wine/DXMT diagnostic gates,
but cannot suppress the original FEX counters. This may affect measurement
overhead compared with r17; it is not a proven FPS improvement.

## What stays in this build

The current library and Steam integration, per-game native VC runtime overrides
(`msvcp140`, `msvcp140_1`, `msvcp140_2`, `vcruntime140`, `vcruntime140_1`), forced
DX11 option, controller publisher/early slot fix, physical and virtual input,
Steam authentication and WinINet fixes, MetalFX options for D3D11/Madeira D3D12,
cache policy, JIT budget and all other existing non-FEX native archives remain.
The MetalFX DLSS bridges remain experimental; retaining them does not establish
that this game's DLSS selector works.

Package verification compares every file against r17: only the main executable,
`Info.plist` and the restored ARM64EC FEX DLL differ. All other bundled resources,
including controller/Wine/Dock/graphics binaries and the Microsoft runtime DLLs,
are byte-identical to r17. The non-FEX static archives also match the recorded
pre-restoration hashes. This is stronger resource evidence than merely checking
that an input source file has not changed, but does not replace a device test.

## What the supplied log actually establishes

The latest supplied log is r17, running DX11 at 1408×648 with native VC runtime,
896 MB JIT allocation and 2048 MB swap. Spatial MetalFX factor is 1.0 and the
DLSS bridge is off. The reported device is iPhone 17 Pro Max / iOS 27.0.1.
`dist/r18-log-analysis.json` contains sanitized numeric samples and the original
log hash; the original device log is not included in the release or a patch.

Of 36 ten-second windows, 33 have complete GPU timestamps, averaging about
25.15 FPS. The first three windows have missing timestamps; the early 86.2 FPS
sample cannot be used to infer GPU utilization. Chronological complete groups:

| Windows | FPS | CPU core equivalents | Completed GPU intervals | Aggregate completion waits/frame |
| --- | ---: | ---: | ---: | ---: |
| First 13 | 21.78 | 3.67 | 35% | 17.07 ms |
| Next 12 | 28.79 | 4.13 | 77% | 27.19 ms |
| Last 8 | 25.16 | 4.20 | 81% | 32.21 ms |

These groups are **not labeled stationary or moving**. Thermal state is nominal,
low power mode is off, and the complete windows show no recorded GPU errors or
sample overflows. The late resource footprint reaches about 6.8 GB, including
about 0.52 GB compressed; that alone does not prove memory pressure.

The previous classifier puts actual Unreal foreground/background workers,
asynchronous loading and I/O threads under `other`, which accounts for much of
the measured CPU. A zero worker subtotal therefore was misleading. GPU busy
here means the union of completed command-buffer execution intervals, not
hardware utilization. Waits are summed across threads and buffers, not a
game-thread critical-path stall. Native rendering batch times are overlapping
wall scopes, not an additive frame budget. Query poll/yield counts are not
durations. The log does not uniquely distinguish CPU simulation, streaming,
translation, shader compilation, GPU backpressure or scheduling waits.

Movement-sensitive FPS and limited resolution sensitivity make a CPU/streaming
constraint plausible, but this is an inference from the user's observations.
It does not justify another speculative FEX or renderer change.

## Measurement changes outside FEX

The existing bounded ten-second sampler now recognizes Unreal worker, loading
and I/O names, including truncated thread names. Existing role indexes stay
unchanged; loading and I/O are appended. A separate `[perf-context]` report
contains those totals, monotonic time, cumulative frames and a fixed phase label.

The in-game menu has four profiling-only markers: stationary, camera turn,
moving and repeat route. It records `[perf-phase]` and an OS signpost. A reporting
window containing a phase change is marked `mixed` and must be excluded from
phase comparisons. There is one signpost per marker and one per ten-second
sample; no new per-frame profiler or additional sampling timer was added.
The controller pipeline and input ownership logic are unchanged.

`MadeiraProfileBuild=true` exposes these buttons only in this diagnostic build.
The runtime profiling setting text now explicitly excludes the original FEX
counters. No shader/game cache cleanup is triggered by the measurements.

## Build and validation

The app is built as **Release**, native `-O2`, Swift `-O` with whole-module
optimization, with a matching separate `dwarf-with-dsym` bundle. This supplies
symbols for profiling without the timing distortion of an unoptimized Debug
build. It contains no `Madeira.debug.dylib` or preview library. The IPA has no
Apple code signature or provisioning profile; Microsoft-authored PE runtime
signatures are not stripped. Development signing and JIT still happen on the
user's side.

`dist/verification-r18.json` records hashes, the matching arm64 UUID, exact
resource preservation, original FEX DLL identity and optimization checks.
`dist/r18-synthetic-tests.json` records host-only checks of classification,
phase transitions, bounded sampling, existing diagnostic gates, actual
physical/touch publisher, VC runtime profiles and DX11 forwarding.
Compilation succeeded. At packaging time, no game, Wine process, simulator,
live GPU or physical device execution had been performed. Subsequent live
device captures on 2 October 2026 are documented in `R18_LIVE_PROFILING.md`.
They do not establish an FPS improvement or official-build regression parity.

## Next evidence and future publication

Use `dist/Guida-Profiling-r18.md` and `tools/capture-profile.py` to attach to an
already-running host after JIT setup. Capture CPU and Metal traces separately
on the same route, with marked stationary/camera/movement/repeat phases and
warm caches. OS sampling can resolve native host code using the dSYM; dynamically
translated guest instructions and Windows PE symbols need separate mapping and
may remain unresolved. Unknown frames must not be presented as proof of a
particular guest function.

The actionable distinction is whether the slow frames show CPU execution,
workers/streaming/I/O, or runnable threads waiting for GPU/dependencies. Apple
documents CPU/GPU timelines and scheduling in its
[Metal performance analysis guide](https://developer.apple.com/documentation/xcode/analyzing-the-performance-of-your-metal-app/).
That is the evidence needed before changing synchronization, translation or
cache behavior. An optimized profiling build follows Apple's
[Instruments workflow](https://developer.apple.com/tutorials/instruments/executing-work-asynchronously?changes=_3).

Current patches and reports are local review material only. Keep raw logs,
device identifiers, Steam credentials, user prefixes and redistributable
runtime binaries out of a future source contribution. Preserve the pinned
FEX gitlink and disclose the native archive qualification. A GitHub fork and
message to the original developer are deferred until the user requests upload.
