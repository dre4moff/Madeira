# Local 0.1.1 r16 — buffer recycling and native Metal submission

## What the supplied r15 log establishes

The user reports no sustained performance gain over the previous builds.
The late gameplay sample at lines 22579–26522 contains nine sampling windows:
26.81 FPS average, 23.7–34.2 range, 4.21 CPU core equivalents on average.
Transitions may be included; this is not a matched-scene benchmark. The menu
reaches about 96 FPS, so a fixed 30 FPS ceiling is not demonstrated.
The sanitized numerical evidence is `r16-log-analysis.json`.

Native command preparation and flushing still take several milliseconds per
frame, with many render passes and command buffers. Completed GPU buffer
interval coverage is not hardware occupancy. Aggregate completion waits
include background retirement and must not be read as removable game-thread
stall time. These measurements do not establish a single CPU/GPU bottleneck.
JIT allocation matches the requested 896 MB; GPU errors are zero. Late samples
report nominal thermal state and Low Power Mode off. The initial device state
is fair, so this does not claim the whole session was thermally identical.

The log reports runtime profiling off but reaches 2,972,127 buffer renames.
Source inspection found a complete diagnostic FIFO walk on every dynamic
buffer allocation, regardless of quiet/profiling settings. This is a concrete
avoidable CPU cost; r15 did not measure its duration. The cumulative rename
counter cannot by itself establish how much of the frame time it consumes.

## Changes and preserved behavior

Quiet D3D11 buffer recycling now skips the diagnostic inventory. Small reserves
need no scan; larger queues examine only their completed prefix. The existing
64-entry warm reserve, ordering, allocation fallback and GPU completion fence
checks are retained. In-flight buffers are never released to meet a size limit.
Moving the front entry avoids an unnecessary temporary reference-count cycle.
Detailed buffer/site census atomics and reports follow the cached explicit
profiling gate. `env.MADEIRA_RUNTIME_PROFILING=1` restores the detailed census.
These D3D11 frontend changes do not rebuild the native Direct3D 9 substrate.

Native render and compute command execution combines adjacent resource
declarations only when usage and stage masks match. Each group holds at most
64 handles and uses Metal's equivalent bulk `useResources` method. Order,
duplicates, resource ownership and all draw/dispatch/fence boundaries remain.
`env.DXMT_RESOURCE_BATCH=0` restores the individual calls for comparison. Remote
command packing is unchanged. No draw merging or pass reordering is introduced.

Quiet Objective-C object release also skips the diagnostic retain-count/class
inventory. Actual object release is unconditional; explicit runtime profiling
or the existing stale-resource probe restores that inventory.

The bounded ten-second `[perf-work]` report records coarse CPU roles, native
render/compute batch wall time, declaration counts and saved Metal calls.
Thread names are mapped to fixed labels rather than emitted. Unknown or
unavailable names are accounted for; name mapping does not measure P/E-core
residency. Native batch timing is wall time, not CPU time. One clock pair and
one counter update per command batch avoid per-command timing/locking.

## DLSS check

The latest log has the card bridge enabled and NVAPI initialized, but contains
no NGX capability/creation/evaluation activity. MetalFX DLSS consequently does
not upscale this game in that run. The game also failing to expose DLSS on
CrossOver is useful context, but does not prove that the game alone is at fault.
The existing app staging loop links both native-extension modules into
`system32` and the ARM64EC child farm, including when Steam uses an ARM64 host.
Synthetic staging checks cover these paths and stale-link repair. The IPA
includes both modules. Their bytes are retained
from r15; there is no evidence in this log of a failed NGX load.

DXMT documents that some games reject unsigned NGX modules and that enabling
NVIDIA extensions globally can select unsuitable NVIDIA-specific paths:
https://github.com/3Shain/dxmt/wiki/Vendor-Extensions
No signature/capability bypass is added. The existing MetalFX DLSS interfaces
for Direct3D 11 and Madeira's Direct3D 12 engine remain available per game.

## Synthetic verification and limitations

The real old/new recycling functions are exercised against 6,000 deterministic
queues and fence positions, with profiling on/off and diagnostic table overflow.
Returned allocations, retained entries and trims match. A synthetic 10,000-entry
in-flight queue reduces scan visits from 10,000 to one; 64-entry reserves need
zero scan visits. These are operation counts, not game FPS measurements.

Actual render/compute command cases and the collector are checked across 520
sequences with varying masks, duplicates, fences, draws and opt-out. A homogeneous
256-declaration model makes four method calls instead of 256, preserving every
resource record. ASan/UBSan check both tests. CPU-role tests retain bounded
sampling and Mach-right cleanup coverage. Existing regression checks, ARM64EC
graphics compilation and optimized unsigned iOS Release packaging are verified
separately. No app, game, Wine session, GPU, simulator or live Steam is executed.

There is no measured r16 device FPS gain yet. Compare the same map and settings
with warm caches and DLSS disabled in the card if it remains unavailable in-game.
The next log can show whether bulk calls are being used and whether game, render,
RHI or native encoding dominates the sampled CPU work.

Only the native WineMetal object is rebuilt in the combined graphics archive;
shader compiler/converter objects and shader-cache keys are retained. Cache
cleanup policy is unchanged: no gameplay purge or tighter limits. Build caches
and superseded local IPA outputs are removed only after artifact verification;
source, toolchains, private supplied logs and recoverable patch evidence remain.
