# RV There Yet? — r18 live-device profiling

Recorded on 2 October 2026, Europe/Rome, on the user's iPhone 17 Pro Max,
iOS 27.0.1. This is a local diagnostic report, not a claim of an FPS improvement.

## Result

The measurements support a **mixed execution and dependency limit**, rather
than a GPU continuously saturated by resolution alone. CPU activity remains
near four core equivalents during both movement and stationary play. During
the short moving Metal recording, Madeira's active GPU execution covers less
of the recording and submission-to-execution latency has a longer tail.

There is also a concrete movement-related host cost: the native UI thread
uses approximately **0.21–0.28 of one core while moving**, compared with
**0.018–0.019 while stationary**. AttributeGraph and SwiftUI account for much
of this activity. This is a useful optimization candidate outside FEX, but
does not establish that removing this cost would double the game's FPS.

The largest unresolved part remains translated/guest execution with partial
stacks. These captures do not identify one guest function or prove a single
critical-path bottleneck. No new runtime patch, engine replacement or settings
change was made during this profiling session.

## Conditions and preservation

- Already-running Madeira r18 profiling Release build, based on 0.1.1.
- DX11, native VC runtime overrides, DLSS bridge off; logged spatial factor 1.
- Last readable configuration: 1408×648, JIT allocation 896 MB, swap 2048 MB.
- Low Power Mode off. The comparison captures report thermal state **Fair**.
  The first, earlier probe was under different thermal conditions and is not
  an equivalent performance baseline.
- Attached to the same running native process throughout; no reinstall,
  termination, relaunch or JIT reset was performed.
- Controller and compatibility implementations were preserved. Movement was
  confirmed by the user; this session did not separately establish physical
  Xbox controller acceptance.
- FEX tracked source remains clean at Madeira's pin
  `26859e184ad90f0e811d7f8bbd943a4b1573a2c3`. No FEX source was edited here.
  The official ARM64EC DLL and native archive qualification are documented in
  `R18_PROFILING.md`; the entire native engine must not be described as
  byte-identical to the official IPA.

The matching host dSYM UUID is `1CF35DF8-E963-3552-9D51-9AC495028862`.
The build is optimized Release with separate symbols, not an unoptimized Debug
build. No official-build device A/B comparison was performed, so these results
cannot certify performance parity with the official release.

## Recorded runs

The trace filenames describe their first intended capture, not every contained
run. **Both useful documents contain two runs**; selecting the correct run is
essential.

| Trace | Run | Phase | Local start | Duration |
| --- | ---: | --- | --- | ---: |
| `cpu-moving.trace` | 1 | Moving, user confirmed | 21:42:53.488 | 61.421535 s |
| `cpu-moving.trace` | 2 | Stationary, user confirmed | 21:45:41.600 | 61.257924 s |
| `gpu-short-stationary.trace` | 1 | Stationary requested; no direct phone observation | 21:50:44.264 | 11.627544 s |
| `gpu-short-stationary.trace` | 2 | Moving, user confirmed | 21:56:13.045 | 21.569250 s |

The initial `cpu-ui.trace` sampled waiting threads. It is preserved, but its
weights must **not** be used as physical CPU consumption. Subsequent useful
CPU and Metal recordings explicitly disabled waiting-thread sampling.

No in-app phase marker was selected in these runs; phase identification comes
from the user's replies. The default Points of Interest instrument did not
capture the app's `Profiling` category, so this is not a frame-aligned phase
signpost analysis.

## CPU comparison

Values below are estimated running-sample weight divided by elapsed time.
One core equivalent means one CPU-second per wall second, not a clock-normalized
measure of performance. The export includes samples with unknown/empty stacks;
the Instruments call-tree total excludes some of those, hence its smaller sum.
The aggregate passes a six-core physical-capacity sanity check.

| Thread / role | Moving core equivalents | Stationary core equivalents |
| --- | ---: | ---: |
| Entire Madeira process | 3.922 | 4.008 |
| GameThread | 0.631 | 0.714 |
| RenderThread | 0.555 | 0.610 |
| RHIThread | 0.355 | 0.417 |
| Native Wine server thread | 0.445 | 0.406 |
| Foreground Worker #1 | 0.314 | 0.349 |
| Foreground Worker #0 | 0.273 | 0.307 |
| Background Worker #2 | 0.178 | 0.202 |
| Background Worker #1 | 0.173 | 0.190 |
| Background Worker #0 | 0.169 | 0.186 |
| DXMT encode thread | 0.157 | 0.172 |
| Native UI main thread | **0.211** | **0.018** |

The shorter Metal captures independently show aggregate CPU values of 3.940
stationary and 3.739 moving, with UI-thread values of 0.019 and 0.284 respectively.
These are sequential observations of different views, not an identical-scene
benchmark or statistically established effect size.

### Native UI

In the 61-second moving recording, the UI thread has 2.845 sampled seconds in
AttributeGraph, 2.616 in SwiftUICore and 2.529 in Swift's runtime. In the moving
Metal recording the same pattern recurs. `AG::Graph::propagate_dirty` and
`AG::Graph::UpdateStack::update` are prominent leaves.

Movement may cause control-state publications and view invalidations. The
trace does not isolate one publisher as the sole cause. The corresponding
source review targets are `ContentView.swift` control state and observed
models, `FPSOverlay.swift`, and `LogStore.swift`. Existing log-display
suppression already exists; simply claiming to disable it would duplicate
existing behavior. Any change must preserve virtual stick responsiveness,
button transitions, physical input and the controller publisher fix.

### Wine server

The native Wine server consumes 27.314 sampled CPU-seconds during movement.
Its stack leads through `wineserver_thread_func`, `wineserver_main`, `main_loop`
and request polling. Device symbols resolve prominent syscall leaves to
`read`, `poll` and `__recvmsg`; `read` alone accounts for 13.148 sampled seconds
on this thread. This is significant sampled activity, **not a measurement of
13 seconds of game-thread blocking**. Syscall sample attribution cannot by
itself establish the frame's dependency or request latency.

The server already has request wakeups and poll-descriptor reuse in this local
version. Adding those again is not an optimization. Before changing it, measure
request types/counts and the latency of requests that the game actually waits
for, using bounded diagnostics outside FEX.

### Guest execution and CPU placement

About 60% of the long moving trace's running sample weight has unresolved leaf
attribution. Some PCs lie in the logged JIT RX region; other unknown frames do
not. Neither all unknown samples nor all partial stacks can be called FEX
translation overhead. Logged PE aliases allow partial offline symbolization;
nearest COFF text symbols are candidates unless function bounds are verified.

Resolved self samples in `libarm64ecfex.dll` represent about 8.6% moving and
9.4% stationary. These percentages **exclude translated guest instructions**
and are not the total cost of FEX. Official transition/translation helpers are
visible, but this does not justify removing upstream counters or changing FEX.

GameThread samples occur on both core classes. In the long pair, approximately
52.6% of its sampled running time is on efficiency cores during movement,
versus 40.5% stationary; the short pair shows the same direction. This is a
scheduling observation, not proof of a scheduler defect. The log already has
`MADEIRA_PROMOTE=1`; another generic priority switch would not establish a new
fix. A scheduling capture must distinguish runnable delay from execution before
attempting a bounded priority experiment. Do not force every worker to the
highest priority or bypass Apple's scheduler.

## Metal comparison

GPU activity is the union of Madeira's **Active execution intervals**, clipped
to the interior windows and merged across channels. It is not shader occupancy,
hardware utilization or an additive Compute + Vertex + Fragment total.

| Measure | Stationary probe | Moving probe |
| --- | ---: | ---: |
| Interior analysis window | 1–10 s | 2–19 s |
| Active execution union | 7.416 / 9 s | 12.277 / 17 s |
| Active execution coverage | **82.4%** | **72.2%** |
| CPU submission → GPU start, median | 13.44 ms | 16.35 ms |
| CPU submission → GPU start, p95 | 18.12 ms | 31.31 ms |

The GPU is doing substantial work, but is not active continuously. A lower
active fraction during movement and a longer latency tail are consistent with
changing CPU supply, queued work and dependency behavior. They do not uniquely
separate CPU starvation, frame pacing, synchronization and GPU backpressure.
The latency statistic is per exported GPU interval, not per game frame; queued
work itself can increase this latency.

System display-swap counters are deliberately excluded from game FPS: touch
controls and system composition can present additional surfaces. Their higher
values during movement are **not** a performance improvement.

## Log correlation

The last successful current-log copy includes five complete interior windows
within the long moving CPU capture, reporting FPS of 32.8, 23.3, 27.7, 21.2 and
27.0 (mean 26.4). CPU telemetry agrees approximately with the profiler at
3.85–4.11 core equivalents. These windows contain no recorded missing GPU
timestamps, overflows or GPU errors. Loading and I/O role totals round to zero;
there is no evidence here for those named threads being the dominant load.
This does not rule out streaming tasks on workers.

Alignment uses the preceding timestamped heartbeat and a two-second boundary
guard. Samples have no selected app phase marker; alignment is approximate.
There is no equivalent successfully transferred log for the later stationary
or Metal captures. Therefore a precise paired FPS improvement or regression
must not be computed from these recordings.

Later current-log transfers failed in Xcode's device file service with a socket
closure/timeout. Read-only file listing and a small previous-log copy still
worked. The CPU/Metal traces were saved and exported successfully. The failed
transfer must not be mistaken for a game crash or a missing profiler capture.

## Next changes worth testing

1. **Isolate UI invalidation during held/moving controls.** Keep immediate input
   delivery separate from visual updates and update only the affected control.
   Confirm the actual publisher with focused host stacks first. Target the
   measured extra 0.19–0.26 core of UI work; do not promise a corresponding FPS
   percentage. Compare virtual and physical controller movement separately.
2. **Measure Wine request/dependency cost.** Use bounded request aggregates and
   short scheduling captures to identify blocking request types. Do not replace
   real waits with spins or weaken correctness to reduce sample weight.
3. **Resolve the guest frame critical path.** Map the hottest generated PCs to
   guest modules/functions with engine-supported diagnostics or upstream help.
   Keep original Madeira FEX. If guest simulation dominates, resolution and
   MetalFX alone cannot remove that CPU work; a renderer-only patch cannot be
   advertised as its cure.

Each candidate needs one change at a time, the same warmed route/settings,
matching thermal conditions, and repeated moving/stationary measurements.
Accept it only with an FPS/frame-time improvement and retained compatibility
and input behavior. This session completed profiling, not that implementation
or acceptance cycle. No new faster IPA is claimed or exported.

## Local evidence and cleanup

Private traces, exports, log copies and symbols remain in:

```
.build/profiling-captures/live-20261002-211205
```

Useful summaries are `cpu-moving.analysis.json`, `cpu-stationary.analysis.json`,
`metal-cpu-run1.analysis.json`, `metal-cpu-run2.analysis.json`,
`gpu-short.analysis.json`, `moving-gpu-short.analysis.json`, and
`moving-log-alignment.json`. They retain limitations and the measurement method.

An initial Metal attempt inherited an unintended long recording limit and
Instruments failed during analysis as temporary storage grew. Its raw data is
preserved as `gpu-raw.ktrace.gz`, **not a validated usable trace**, with verified
decompressed SHA-256 in `gpu-raw-preservation.json`. Do not use it in the tables
above. The subsequent short captures completed and are the actual evidence.

Removed only six identified, unopened temporary GPU analysis arrays belonging
to that failed capture: 11,579,752,448 bytes. The raw capture was reduced from
6,277,824,512 to 732,456,616 bytes by gzip, with complete hash-verified readback
before deleting the redundant uncompressed copy. The cleanup inventory is
`temporary-cache-cleanup.json`. After closing the completed Instruments
documents, another 4,789,894,112 bytes of identified, unopened raw scratch inputs
were removed; the corresponding saved and exported traces remain. That inventory
is `completed-capture-temporary-cleanup.json`. Saved traces, symbols, builds and source remain.
No iPhone shader/game cache, Wine prefix, save or Steam installation was cleared.
No public upload, GitHub fork or upstream notification was performed.
