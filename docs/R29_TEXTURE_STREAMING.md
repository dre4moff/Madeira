# Madeira 0.1.3 r29 — texture upload memory and streaming overhead

The supplied r28 log and the user's report establish that games now start,
including YAPYAP. The request concerns transient memory/FPS spikes when looking
at a new area, and possible termination above the app's memory limit.

## What the log establishes

- The run uses Direct3D 11 at 1568x720, with both MetalFX modes disabled.
  Heavy runtime profiling is off. The device is already thermally serious at
  app opening and fair at game launch and the performance sampling windows.
- Recorded conversion-cache reports reach 256 hits, zero misses and zero read
  errors. This proves observed conversion reuse, not universal Metal pipeline
  cache hits or the absence of new shader work.
- Scene/loading changes include long gaps between presents; time inside the
  sampled Present call is usually 0.0–0.1ms. Gameplay windows vary substantially.
  GPU completed-buffer interval coverage and aggregate background completion
  waits are not hardware occupancy or removable game-thread stall time.
- The largest recorded footprint is 7110 MiB, with up to 585 MiB compressed.
  A 200 MiB rise appears in the regular footprint samples, but those sparse
  samples cannot identify every brief spike or its sole cause.
- No matched previous-version route/settings/thermal benchmark is supplied;
  this log cannot prove a regression caused by the official 0.1.3 merge.

Only sanitized numerical records are included in `r29-log-analysis.json`.
The original device log, sandbox paths and account/session details are private.

## Changes

D3D11 `UpdateSubresource` texture uploads now use the existing local shared
staging pointer and texture-copy helper, extending the creation-time optimization
to streamed data. Both immediate and deferred contexts keep their original
allocation and command-list ownership. Row/depth strides, valid bytes, BC decode,
mip translation, GPU blits and command ordering are preserved. Remote handles
still require explicit delivery and never expose this pointer. The existing
`env.DXMT_DIRECT_TEXTURE_UPLOAD=0` restores the old copy path.

Only the iOS 64-bit D3D11 CPU upload rings change their normal block capacity
from 32 to 8 MiB. Private copy buffers, argument buffers, the native D3D9
frontend and the 32-bit policy are preserved. One small transfer consequently
reserves 24 MiB less capacity; this is not a measured reduction in physical
device residency. Completion watermark equality can reuse a finished upload
block immediately, provided the caller has advanced to a later sequence.
Current-batch and in-flight blocks remain protected.

Up to two completed medium-size upload blocks (at most 32 MiB each) can stay
warm with the existing expiry. This prevents compact blocks from causing fresh
allocations for every repeated 16/32 MiB upload. Completed undersized FIFO entries
cannot strand a usable block behind them. Larger one-off blocks still retire;
`env.DXMT_RING_OVERSIZE_REUSE=0` disables medium-size retention.

Creation-time initialization submits pending copies at 64 MiB boundaries,
after the complete upload command has been assembled. The existing two-buffer
upload queue and shared-event dependencies remain. The API returns the sequence
that actually owns the copy, including when that batch is submitted immediately.
Pending bytes are bounded by the threshold plus one individual upload, rather
than indirectly by the 1 MiB CPU command-description heap. In-flight resources
are still retained until GPU completion; this does not cap total game memory.

The low-volume `[texture-stream]` device-creation line identifies the block size,
direct-copy policy, completed reuse and initializer batch limit. No per-upload
logging or full resource scan is added.

## Swap and the 8 GiB report

The supplied log has swap enabled with a 2048 MiB cap and `classic` coverage.
It records up to 331 MiB file-backed, zero refused allocations and no swap
mapping/open/truncation errors. Classic coverage deliberately backs eligible
private writable guest commits of at least 8 MiB in the guest address band.
It does not cover all small guest heaps, native/JIT allocations or Metal resources.
`blocks` and `wide` remain existing explicit coverage choices; their I/O costs
are why they are not forced on globally for a performance investigation.

The log's reported process budget is 8192 MiB. Swap capacity is not an increase
of that physical footprint limit. Apple documents that exceeding a process's
memory limit can cause [jetsam termination](https://developer.apple.com/documentation/xcode/identifying-high-memory-use-with-jetsam-event-reports).
The described >8 GiB termination is compatible with that limit even while the
tier works. This supplied run ends below it and has no JetsamEvent report for
the separate termination, so its exact cause is unverified. Swap code, defaults,
capacity and coverage are retained; no defect requiring a swap change was found.

## Verification and preservation

The production copy branch, ring template and batch-submission helper run in
host tests under ASan/UBSan. Tests cover padded rows, volumes, byte guards,
remote/opt-out delivery, equal completion watermarks, current/in-flight safety,
preallocation, 10,000 medium uploads with one allocation, bounded retention,
expiry and large-block release. A 900-upload creation model submits at the
64 MiB threshold and preserves every returned owning sequence. This checks
operations and memory capacity; it is not a GPU rendering or FPS benchmark.

The full 81 host suites, including real sparse-file swap bookkeeping and WMA
decoding, optimized ARM64EC D3D11 compilation, Xcode Release and unsigned IPA/
matching external dSYM verification are checked before publishing. Only the
D3D11 DLL changes in the Windows farms. All native archives, shader converter
cache identity, FEX sources/original Windows engines, Dock, D3D12, VC runtime
support, controller/input, microphone and official 0.1.3 features are preserved.

For device acceptance, update without uninstalling or purging shader caches.
Compare the same map, graphics settings and route with Low Power Mode off and
the device cool: first traversal versus second traversal, then the same warm
route across builds. Actual r29 FPS, rendering and transient physical-memory
improvement remain to be measured on the phone.
