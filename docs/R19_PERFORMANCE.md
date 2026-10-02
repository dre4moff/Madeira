# Madeira 0.1.1 r19 — performance changes and cache audit

This optimized Release builds on the tested r18 version. No new device FPS gain
is claimed: the changes have host synthetic tests, compiler, resource and binary
verification, but have not yet been measured in a new game session on the phone.
The running phone session was preserved while preparing this build.

## CPU cores: the app is not limited to four

The previous live running-sample captures covered every CPU index from 0 to 5.
The process used approximately 3.922 core equivalents while moving and 4.008
while stationary. Four core equivalents means approximately four CPU-seconds
of work per second across the machine, not four selected or enabled cores.

| CPU index / Instruments label | Moving sampled CPU seconds | Stationary sampled CPU seconds |
| --- | ---: | ---: |
| 0 / E Core | 37.161 | 35.807 |
| 1 / E Core | 37.950 | 35.641 |
| 2 / E Core | 38.667 | 35.641 |
| 3 / E Core | 39.462 | 35.714 |
| 4 / S Core | 43.160 | 51.656 |
| 5 / S Core | 44.467 | 51.072 |

The windows lasted 61.422 and 61.258 seconds respectively. These figures are
sample-based estimates, not clock-normalized throughput. All six cores have
substantial activity. Additional worker threads cannot parallelize a serial
GameThread dependency automatically. Existing foreground priority promotion is
preserved; there is no new core affinity, blanket QoS boost, guest CPU count or
engine modification in r19.

Apple documents [CPU bottleneck analysis](https://developer.apple.com/documentation/xcode/addressing-cpu-bottlenecks)
and [efficient CPU scheduling](https://developer.apple.com/documentation/xcode/scheduling-cpu-work-efficiently).
The useful next question is which frame dependency delays the game, rather
than whether all cores can be forced to run at 100%.

## GPU cores: activity is not occupancy

The previous Metal recordings showed active execution covering approximately
82.4% of the stationary interior window and 72.2% while moving. That measures
the union of execution intervals. It does not report the number of active GPU
cores, shader occupancy, ALU saturation, bandwidth or texture unit utilization.
There is no evidence in those captures of a disabled GPU core limit.

Apple's [GPU counter statistics guide](https://developer.apple.com/documentation/xcode/analyzing-apple-gpu-performance-using-counter-statistics)
explains the separate hardware measurements needed for this analysis. Adding
CPU workers or changing a compute dispatch cannot universally improve vertex,
fragment and compute workloads. The current evidence points to mixed guest
execution, scheduling/dependency and graphics supply costs; it does not establish
one CPU-only cause or justify speculative changes to game shaders.

## Changes implemented

### Virtual sticks and native UI

The touch input lifetime and gamepad publisher are preserved. The moving stick
knob and LS/RS label are now UIKit subviews; every analog input event is still
sent to the guest, while knob movement does not invalidate the surrounding
SwiftUI glass graph. Layout editing retains its SwiftUI preview. Button feedback,
multiple fingers, release, cancellation, remapping, resize and backgrounding
remain supported. Physical controller arbitration and the early XInput slot
fix are unchanged.

The FPS overlay still samples presents every 100 ms, but the sample buffer no
longer publishes SwiftUI state at that cadence. The visible readout updates at
250 ms. Present counting, adaptive FPS calculation and frame pacing are preserved.

LogStore assembles each batch in a local snapshot and publishes the entries once.
A repeated signature whose row is still pending is now correctly retained and
collapsed, rather than becoming an ignored negative-index update. Suppressed
log display and on-disk capture remain available.

### Wine request wakes, outside FEX

The request semaphore now represents pending work instead of counting every
notification. An atomic claim permits one wake token while work is pending.
The consumer clears the claim only after consuming that token and **before**
the next complete descriptor scan. A new producer during the scan can therefore
schedule the next wake. Timeouts never clear an unconsumed producer claim.
Request data, polling readiness, timers and Steam protocol processing are unchanged.

This removes the mechanism by which queued wake notifications can cause repeated
immediate semaphore returns and redundant polling. It is a performance candidate,
not a measured improvement in guest request latency. `MADEIRA_SRV_COALESCE=0`
restores the counting wake behavior for an A/B comparison. No sleep floor,
network timeout or request-dropping shortcut was introduced.

### Shader cache reuse and cleanup

A read-only inventory of the connected phone found 7,361,904 bytes in the game's
DXMT shader database, WAL and SHM files. Its WAL had been updated during use.
This demonstrates persisted cache files, not proof that every shader lookup was
a hit. The phone inventory itself is private and is not part of public patches.

The app already enabled the correct iOS DXMT cache directory for 64-bit games.
r19 keeps that resolver and cache version (15) unchanged. Reader diagnostics
are now enabled by default, with lookup hit, miss and SQLite read-error counts.
Output occurs at lookup 1, 64, 256 and each multiple of 1,024. `DXMT_CACHE_STATS=0`
disables the counters/output. A cache miss and a database read error can now be
distinguished. These are conversion-cache counters; they do not measure every
Metal driver's pipeline cache or total game shader compilation.

The cleanup UI reports retained shader bytes and recently used bytes separately
from removed files. “No obsolete files to remove” is therefore distinguishable
from “No saved shader cache files found yet”. The Metal driver's cache under the
signed bundle ID is measured separately and left to system management.

Owned D3D12 conversion entries in `Documents/shadercache` are included in startup
and manual housekeeping. Only 16-digit hexadecimal `.mdsc`/`.mdxc` entries and
abandoned matching temporary fragments are eligible. Wine, Steam downloads,
saves and other Documents files are not traversed. Symlinked roots and entries
are excluded. Manual cleanup still requires a fresh app session and is serialized
before launch; it never cleans open game databases during gameplay.

D3D12 cache pruning no longer runs after every over-budget shader write on the
shader compilation thread. Startup maintenance enforces a **soft** size target:
entries reused in the last 30 days survive even above the target. DXBC conversion
cache hits refresh age at most once a day; DXIL already refreshes reuse age.
Newly created cache data can exceed the target during a long active session and
is reconsidered at a later startup. This deliberately avoids deleting working
shaders merely to enforce a strict limit and then paying recompilation costs.

Rebuilding the D3D12 native conversion service changes its existing build-stamp
cache identity. The first D3D12 launch on r19 may therefore reconvert old entries;
subsequent launches of this same service can reuse them. D3D11's shader cache
identity is preserved. Cache key correctness checks were not weakened.

## Preservation and verification

- FEX tracked source is unchanged at Madeira's pin
  `26859e184ad90f0e811d7f8bbd943a4b1573a2c3`.
- Both Windows FEX DLLs match the official 0.1.1 release byte for byte.
- The native FEXCore archive matches r18, SHA-256
  `364966c9ac3d31ac865bd6a4aa6ebd971ab497c4d174024a3357f3e10fd8553d`.
  Its pre-existing native compiler portability qualification is documented in
  `R18_PROFILING.md`; the entire native engine is not certified byte-identical
  to the unpublished official static archive.
- Only `cache.o` and `madeira_ir_unix.o` changed in the combined graphics archive;
  1,063 other object members match the r18 checkpoint. Only `fd_ios.o` changed in
  the Wine server archive; 45 other members match. Other app static archives
  retain their recorded r18 hashes.
- Against the r18 IPA, only `Madeira` and `Info.plist` change. The other 1,077
  bundle files match. VC runtime, forced DX11, existing DX11/DX12 MetalFX bridge,
  Steam/auth behavior, controller resources and original FEX DLLs are retained.
- 21 host synthetic test suites pass. They include 10,000 delivered analog
  movements without SwiftUI movement publications; real Combine batching with
  20,000 retained repeated events; real Mach semaphore producer/consumer races;
  100,000 pending notifications reduced to one wake; 80,000 concurrent work items
  delivered; counting-mode opt-out; real SQLite cold/warm/reopen and version
  isolation; and 101 DXIL cache checks including warm-over-budget and symlinks.
- Xcode Release succeeds with native `-O2`, Swift `-O` and whole-module optimization.
  The IPA contains no Apple signing load commands, provisioning profile, signature
  directory or debug support dylib. Matching external dSYM symbols are exported.
- Native arm64 UUID: `1A1FB6D3-F16E-3A37-8D0D-1B5C630C0320`.

Synthetic checks do not establish physical Xbox acceptance, rendering appearance,
game launch or higher FPS on r19. Existing minimum-OS linker warnings remain;
this work does not extend platform compatibility. No files were uploaded and
no developer notification was sent.

## Next device comparison

Install/sign r19 using the established method and re-enable JIT after relaunch.
Keep resolution, DX11, graphics preset, DLSS setting, overlay, swap tier and route
identical to r18. Compare at the same thermal state with Low Power Mode off.
Do not press cleanup between warm-cache runs. Allow a first warmup, then record
one minute stationary and one minute walking the same route twice. Save the log
and the displayed FPS windows; mark phases if using the profiling controls.

Look for `[shader-cache] r19 reader-open`, `hits`, `misses`, `read-errors` and
`[wineserver-fd] ... coalesced=1`. Repeated-route/second-launch shader hits and
lower main-thread CPU during movement are useful outcomes. If FPS remains similar,
repeat with `MADEIRA_SRV_COALESCE=0` to isolate the Wine wake change. The next
critical-path trace should include scheduler/runnable delay and supported GPU
hardware counters; the existing ~60% unresolved guest/JIT samples limit what
can honestly be attributed to an individual game function.
