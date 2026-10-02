# Local 0.1.1 r15 — release optimization and graphics scheduling

## Evidence from the supplied r14 log

The game now reaches sustained gameplay. The late segment from log lines
20188–28485 contains 17 native sampling windows spanning 169.9 seconds. It is
selected from the first 25.4 FPS window to the first `menu=1` marker; transitions
may be included. The sanitized numerical report is `r15-log-analysis.json`.

- FPS average 26.89, range 19.5–31.9; the earlier menu reaches 90.1 FPS.
- CPU use averages 4.24 core equivalents across all process threads; the busiest
  individual thread averages 64%, peaking at 69%. Roles and P/E-core residency
  are not measured, so this does not exclude a CPU critical path.
- Completed Metal command-buffer interval coverage averages 75%, reaches 90%,
  and has no missing timestamps, overflow or GPU errors in this segment. This
  is a timing proxy, **not hardware shader occupancy**: synchronization/idle
  inside a command-buffer interval cannot be separated by these counters.
- Native buffer-completion waits average 28 ms per presented frame. These sum
  waits across threads, including DXMT's background retirement worker; they are
  **not 28 ms of removable game-thread stalls**. Buffer lifetimes/fences remain
  intact. The log now explicitly labels these two measurement kinds.
- Typically 7–9 command buffers and many render passes are submitted per frame.
  Sampled encoding preparation/flush work takes several milliseconds, while
  drawable acquisition is roughly 0.1 ms. Sampled frame-latency and staging
  synchronization times are zero; there is no evidence of a fixed 30 FPS cap.
- There are bursts of up to 299326 pending-query polls in a sampled frame
  window in this late segment (higher counts also occur during transitions).
  `event_stall_max` is a **count**, not milliseconds. Ordinary frames often
  have only 12–17 polls. Repeated `Flush` after submission is mostly a no-op,
  but the caller can continuously poll while the real event watermark is pending.
- JIT request/allocation both equal 896 MB; no allocation shortage is shown.
  Footprint peaks at 7016 MB, with about 929 MB compressed. The app swap tier
  is not enabled in the exported configuration; compressed memory still exists.
  The log cannot quantify decompression's cost or isolate the swap-off gain.
- Thermal state is nominal and Low Power Mode is off in all selected windows.

The evidence points to substantial graphics submission/synchronization work
alongside game/emulation CPU work. It does not uniquely establish either a
CPU-only or shader-only bottleneck. FPS being insensitive to resolution is
consistent with fixed per-frame work, but is not sufficient to locate it.

## Changes

The local packaging script previously copied `Debug-iphoneos`. Those Xcode
builds compiled app/bridge Objective-C/C++ at `-O0` and Swift at `-Onone`.
r15 packages **Release** with explicit native `-O2`, Swift `-O` and whole-module
compilation. Prebuilt FEX/Wine/DXMT archives were already optimized; this change
does not claim to newly optimize the entire emulator. A compile-time beacon
`[build-mode] native-optimization=on` and package inspection prevent accidentally
shipping another unoptimized bridge build. Developer Debug remains available.

The app opts 64-bit DXMT into its **existing own-address wait backend**:
`DXMT_WAIT_ON_ADDRESS=1`. The queue atomics then use Wine's existing
`RtlWaitOnAddress/RtlWakeAddress*` primitives directly rather than the generic
libc++ contention table and API-set discovery. The native Darwin backend is
unchanged; all fences, ring bounds, memory order and real completion checks remain.
This is an avoidable handoff cost identified in source, not proof of a measured
device gain.

`DXMT_QUERY_POLL_YIELD=1` lets a thread cooperate during long event/timestamp
query polls. The first 64 pending calls use the current fast path. Thereafter,
one in every 64 still-pending polls calls `SwitchToThread`, using Wine's existing
adaptive-yield policy. There is no new fixed per-frame sleep. Completed/invalid
queries and query reissue reset/skip the budget. GetData's output, flush flags,
real shared-event watermark and S_FALSE/S_OK decision are preserved. A bounded
`query_yield_max` field in the existing FRAME_STATS line records whether the
path is used. Explicit `env.DXMT_WAIT_ON_ADDRESS=0` or
`env.DXMT_QUERY_POLL_YIELD=0` in the config restores each previous policy; defaults
are exported before user config, so user overrides win.

## Verification and limits

Production atomic-wait templates are exercised in a host compare/enqueue/wake
model, including four atomic widths, 8000 producer/consumer exchanges, spurious
wakes, 16 concurrent waiters and explicit fallback. The real event-query class
is exercised with 500000 pending polls, completion, reissue, invalid state,
short polls and opt-out. ASan/UBSan run on these tests. The host address-wait model
does not execute Wine's kernel/alert primitives or prove iOS scheduling latency.

ARM64EC graphics compilation, existing regression checks, optimized unsigned
iOS compilation and IPA contents/signatures are verified separately. No app,
Wine session, game, GPU, simulator or live Steam service is executed. No r15
FPS gain is measured; the device comparison remains necessary at the same map,
resolution and settings, preferably with warm caches and swap still off.

Shader converter/native graphics archives and shader-cache identity are retained.
The D3D11 frontend changes query scheduling; D3D12 and both DLSS MetalFX bridges,
VC runtime overrides, controllers, library and Steam authentication remain present.
Cache policy is unchanged: no gameplay cache purge or tighter limits. Generated
build caches and superseded local release outputs are cleaned after verification;
source, toolchains and recoverable patch/checkpoint evidence are retained.
