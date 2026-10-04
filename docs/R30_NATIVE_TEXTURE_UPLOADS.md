# Madeira 0.1.3 r30 — native texture copies and restored upload scheduling

## Why r29 is superseded

The user tested r29 and reports shorter but more frequent stutters, including
small map movements. They explicitly confirm that transient memory peaks were
never a problem. Reducing staging capacity does not satisfy that request and is
not retained as a performance objective.

The supplied r29 log records nominal thermal states throughout its performance
samples. Among 149 later 64-frame windows (frame 2432 onward), 118 have at least
one gap above 50 ms, and six have a gap above 100 ms. Median window-average gap
is 36.5 ms; the largest sampled time inside Present in these windows is 4.8 ms.
Intervening time includes both game work and graphics API calls such as uploads,
resource creation and shader work. It cannot be attributed exclusively to the
game. Window maxima cannot reconstruct individual frame percentiles or count
all stalls. No matched route isolates the cost of each r29 change.

## Changes and scope

The normal iOS 64-bit D3D11 staging block returns to 32 MiB. The complete r28 ring
allocation, reclamation and completion policy is restored. Initialization returns
to its original batching and two-buffer upload queue, with no forced 64 MiB
submission boundary. No new memory cap, streaming throttle or buffer eviction
policy is imposed. Deferred command-list ownership and all GPU fences remain.

Local initial and streamed texture uploads now send their layout to a new native
WineMetal entry. The native function copies rows/depth slices straight into the
already allocated staging suballocation, using a single contiguous memcpy where
possible. It allocates no temporary image and creates no GPU command, submission
or wait. This replaces r29 streamed copies performed by guest-side memcpy and
also avoids repeated row-by-row guest/native boundary crossings. The existing
BC decode, mip translation, blit commands and texture ownership are unchanged.
Destination bounds and arithmetic overflow are checked before copying.

Unix-call slot 151 is appended to both dispatch tables. The original 151 entries
remain byte-for-byte in their original order; reserved slots stay reserved. The
WoW64 wrapper translates/restores the source pointer. Remote handles continue
to use explicit upload delivery and never reach Objective-C. The normal remote
caller retains its original row/slice path, and the new entry also preserves that
ordering if called remotely. `env.DXMT_DIRECT_TEXTURE_UPLOAD=0` restores the
original row/slice update path for comparison.

Two integer counters added to the existing 64-frame Present report show gaps
above 50 and 100 ms. They add no per-frame log, resource scan, extra timing call
or submission. These are absolute thresholds, not a claim that every such gap
is a distinct perceived stutter.

## Verification and limitations

The actual production native entry, streamed branch and WoW64 wrapper run under
ASan/UBSan with Foundation mock buffers. Tests cover padded rows, volumes,
boundary guards, overflow rejection, source-pointer restoration, opt-out and
remote delivery without dereferencing remote handles. A 257-row, three-slice
fixture replaces 771 original Wine crossings with one native crossing. This is
an operation-count result, not a latency or FPS benchmark. The initial-upload
branch is also checked against the original data layout.

82 host suites, ARM64EC D3D11/WineMetal compilation, the optimized iOS Release,
external dSYM UUIDs and complete unsigned IPA payload are verified before
publication. Only the native WineMetal object and two ARM64EC renderer DLLs are
intentionally changed. Other native objects, shader converter/cache identity,
FEX source and original Windows engines, fullscreen/YAPYAP fixes, input, audio,
Dock, D3D12 and official 0.1.3 functionality are preserved.

The classic 2048 MiB swap tier in this supplied log has no observed refused
allocations or mapping failures. Swap defaults and implementation remain.

r30 is a corrective prerelease awaiting physical-device rendering and frame
stability acceptance. The user report establishes the r29 regression, but this
host cannot validate the improvement in the same game/map. Install without
uninstalling or clearing shader caches, and compare the same map/settings and
route. r28 remains available as the baseline. No claimed FPS gain is inferred
from these host checks.
