# Madeira 0.1.3 Fork r31: remaining movement stutters

This report accompanies the unofficial experimental r31 release, based on official
v0.1.3 (`4e9d45a74294cd820120791c4b3f2b79adf4fc70`). It documents an unresolved
performance issue; it does not claim an FPS fix. Raw device logs are private.
The attached numeric `r31-log-analysis.json` excludes account details and paths.

## User observations and supplied log

Across games, standing still is relatively smooth; moving or turning quickly
introduces recurring stutters and rapid footprint drops. Reducing transient
memory peaks was never the user's goal. r29's smaller staging/batching policy
made stutters shorter but more frequent and was completely reverted in r30.
The local r30 cache-disabled trial also produced no perceived improvement.

The trial log confirms `DXMT-disk=off custom-Metal-path=off` and has no persistent
cache reader reports. The normal cache is therefore restored in r31. System
Metal driver caching was still managed by iOS during the trial; this experiment
cannot rule out every driver-cache effect or compilation bottleneck.

The 12 ten-second FPS windows are 54.6, 75.8, 23.3, 17.8, 19.4, 23.4, 26.7,
26.3, 29.9, 30.2, 24.5 and 26.8. These include startup/menu/loading phases;
there are no synchronized movement or route markers. Across 3,968 sampled
Present intervals, 365 exceed 50 ms and 34 exceed 100 ms, including loading.
All performance windows report nominal thermal state, low-power off and no
GPU completion errors. Completed-buffer busy interval coverage reaches 80–87%
in several later windows; it is not hardware occupancy. Aggregate GPU completion
waits are not measurements of the game thread's blocking time.

Reported footprint peaks at 6,981 MiB. For example, consecutive samples at cycles
53–54 fall from 6,792 to 6,680 MiB. Footprint, internal/compressed/external bytes
are distinct OS accounting metrics. A footprint decrease alone does not establish
texture destruction, resource eviction, reloading or a renderer allocator bug.
One JIT code-buffer allocation falls back from 128 to 8 MiB under pool pressure;
correlation with gameplay pauses is unknown.

## Confirmed cache-button defect and correction

The manual button previously called the automatic soft-budget cleanup: caches
used within 30 days were protected even when the user explicitly pressed Clear.
It now removes recent generated DXMT groups in `Library/Caches/dxmt` and recognized
D3D12 conversion entries in `Documents/shadercache`, including `.mdsc`, `.mdxc`
and their temporary fragments. Empty generated roots are removed. Foreign files,
symlinks, games, saves, Steam data and the system-managed Metal driver cache are
preserved. Automatic cleanup remains soft and protects recently used shaders.
Cleanup is serialized before launch and refused once Wine has launched; restart
Madeira before using the button. The next game launch may compile shaders again.
This storage cleanup does not execute while the game is running.

## Allocator findings and bounded evidence added in r31

- `dxmt_dynamic.cpp`: retired dynamic buffers above a reserve of 64 are released
  only after their GPU fence completes. This policy already exists in the merged
  official DXMT pin `35a4db11bd`; the fork's earlier optimization reduced diagnostic
  scanning without changing retirement decisions. r31 leaves the policy unchanged.
- `dxmt_ring_bump_allocator.hpp`: the original 32 MiB staging policy and expiry
  threshold of 300 completed sequence/cleanup ticks remain. These are command
  sequences, not frames or milliseconds. At several submissions per frame,
  retained staging blocks may age faster than a casual reading suggests. Whether
  this causes the reported pauses requires correlated block reuse/expiry and
  upload timings; changing the threshold without evidence risks memory pressure.
- `build/ntdll-unix/virtual_ios.c`: JIT pool freelist reuse/warming is preserved.
  Despite historical sweep comments, the current sweep does not call MADV_FREE
  on JIT ranges; it marks accounting state after live-overlap checks. Guest
  explicit decommit zeroing is required behavior and is not evidence that Madeira
  is unconditionally evicting live game memory. FEX sources and engine DLLs,
  swap behavior, native Wine memory allocator and r27 crash fixes are unchanged.

Heavy resource census was off in the supplied run, so dynamic trim statistics
were unavailable. r31 adds `[dynamic-buffer-recycle]` alongside existing 64-frame
summaries: `trimmed`, `bytes` and `fresh-after-trim` are cumulative process totals.
The first two count actual surplus retired dynamic-buffer releases; the third
counts a fresh allocation when the immediately preceding call on that same
buffer performed a trim. These are not texture eviction counters, do not include
staging blocks/JIT/game heaps and cannot prove causality alone. Only constant-cost
atomic updates on actual trim events and three loads per summary are added;
no retained-set census or allocation policy changes are introduced.

## Suggested developer investigation

Reproduce a fixed standing/turning/movement route with the same device, game,
resolution, rendering settings, thermal state and cache state. Add timestamped
phase markers, compare Present gaps and deltas in recycling counters, then
instrument staging-block expiry/reuse, upload allocation/copy, shader compile
latency and guest page faults if trim deltas do not track pauses. Distinguish
CPU/JIT translation, GPU saturation, game asset streaming and actual allocator
churn. Compare r28/r30/r31 with identical routes; unmatched ten-second windows
cannot establish a regression's magnitude or identify its cause.

## Verification boundary

83 host suites pass, including ASan/UBSan execution of production allocator code
against the pinned original across 6,000 fenced-resource cases, quiet-mode trim
counters, warm reserve and in-flight preservation. Actual cleanup Swift code is
exercised with automatic/manual paths, recent cache entries, WAL/SHM/custom Metal
artifacts, empty roots, symlinks and foreign/user/Steam data. Native cache entry
points are exercised for enabled behavior and 3,000 disabled calls.
ARM64EC/iOS Release builds, exact dependency pins, preserved original engine
binaries, unsigned public/personal IPA payloads and matching external symbols
are verified separately. Physical-device rendering/FPS acceptance is pending;
movement stutters remain an open issue in this release.
