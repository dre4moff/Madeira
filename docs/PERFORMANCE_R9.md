# Madeira r9: graphics, dispatch overhead and temporary storage

## Supplied device log

The latest `madeira-log.txt` is an r8 session. The JIT pool allocates its full
requested 896 MB; no pool-exhaustion evidence appears. Present-counter windows
range from roughly 17 to 50 presents/s, so the captured session does not show
a fixed 30 FPS cap. In map, average gaps between Present calls reach 55–62 ms,
while time inside the measured Present scope is about 0–0.1 ms. This locates
the delay before that scope but cannot separate CPU work from GPU backpressure
earlier in rendering. There is no new CPU/GPU overlay in this change.

FEX logs about 16.7 million CompileBlock callbacks versus 197,490 compilations:
roughly 98% reuse. Logged L1 pointers are nonzero and match their LookupCache
pointers; this does not support the existing comment's zero-L1 hypothesis.
Quiet r8 still executes global atomic diagnostic counters on each callback,
plus call/return tracking and hot-RIP statistics. r9 gates those diagnostics
before touching their counters; the compile/cache paths and rare rpmalloc
safety snapshot remain. Explicit `MADEIRA_RUNTIME_PROFILING=1` restores them.
The user's approval applies to this local FEX build, not an upstream contribution.

BC compression is hardware supported and logged software-decode bytes are zero.
The renderer's cumulative allocation totals are not live memory: the log shows
about 2.2 GB live private textures and a 72 MB staging ring (104 MB peak).
These observations do not prove a texture leak. r9 retains compressed textures,
checks BC hardware support once per initializer, and skips detailed BC census
COM queries/locks and stream counters in quiet sessions.

The private Metal cache-path setter still reports fallback to its default.
Enabling the SQLite shader cache does not prove that this private setter works
or increase steady-state FPS by itself. No such FPS claim is made here.

## MetalFX and texture loading

Every game card exposes Off, Balanced (1.5x) and Performance (2x), default Off.
The saved resolution remains the output preference. On a supported local Metal
device, the virtual monitor defaults to a smaller input mode: 1408x648 becomes
939x432 or 704x324. Profiles persist independently and legacy libraries decode.
Desktop profiles and unsupported devices keep their original monitor size.
This targets the existing D3D11 spatial-scaler path; enable DirectX 11 as needed.
If the game restores its own resolution, select the lower resolution in-game.
The actual swapchain dimensions appear in `[metalfx] active input=… output=…`.
Output allocation/scaler creation failure falls back to ordinary presentation
without dereferencing a missing scaler. It retains the lower input resolution.
Balanced's rounding can make the scaled output differ by one pixel.

Local iOS texture initialization writes directly into the CPU-visible shared
staging ring rather than crossing the Wine boundary for every row or slice.
Contiguous textures use one memcpy; padding and 3D slice pitches are handled,
and missing destination padding is zeroed. Existing GPU blits, reference
lifetimes and completion fences remain. Remote handles and unavailable pointers
use the previous explicit updateContents path. Set
`env.DXMT_DIRECT_TEXTURE_UPLOAD=0` to compare against that original path.

## Storage policy

Startup/manual cleanup serializes before opening Wine or shader databases;
after any launch it is disabled until restart. No scanner or eviction runs
during gameplay. Only NSCachesDirectory/dxmt per-game groups are budgeted.
The target is deliberately soft: any cache used in the last 30 days is kept,
even if all warm caches exceed it. Cache-directory use dates are refreshed when
opened, including read-only shader hits. Unused groups are removed oldest first
only when above the target. This avoids repeated shader compilation due to a
hard limit. Switching a graphics profile does not deliberately change shader
cache keys or delete warm cache databases.

Cleanup also handles the owned temporary swap filename and valid-UUID runtime
staging directories older than 24 hours, with symlink/ancestor checks. It does
not enter the Wine prefix, Steam depot downloads, saves, login data or library.
New app-owned swap files are detached after successful open/truncate; descriptor
and mappings stay valid, and termination releases the storage automatically.
Closed previous logs above 64 MB keep their first 64 KB and last 8 MB. The
current log is preserved in full until the next launch; a long explicitly
profiled session can still make it large. Custom absolute DXMT cache locations
are preserved and outside the automatic cleanup scope.

## Build and synthetic evidence

Native FEX and its ARM64EC module are rebuilt. `build/fex-arm64ec/build.sh`
records the Windows-host define for C/C++/ASM, arm64ec triple, allocator options,
generic tuning, bundled fmt and no LTO. LLVM-mingw's thin-LTO ARM64EC symbol
mangling failed in the fresh build; the non-LTO module links and preserves all
30 exports and imported APIs. The D3D11 module similarly retains 7 exports and
its imports. Both use the pinned source/toolchain, not a newer engine version.

DXMT ARM64EC was configured with its arm64ec Meson cross file, resolved project
root, Release build type, DXMT_IOS=1, and Wine's build-arm64ec import libraries.
Only the rebuilt d3d11.dll is staged. Native DXMT's D3D9 substrate is rebuilt
as well because staging-block/initializer layouts changed. The combined
archive retains LLVM and the existing shader converter object (whose build
date is part of the cache key). Cache and Winemetal objects are updated in the
archive actually linked by the app. Wine's native virtual.o is rebuilt with
the existing iOS build flags and replaces only that archive member.

Tests compile production code with mocked framework boundaries, using only
synthetic data and owned temporary fixtures:

- MetalFX sizing, legacy Codable persistence, isolation and environment reset.
- Actual texture upload branch matches original output for contiguous, padded,
  short rows and 3D slices under ASan/UBSan; direct writes avoid update calls,
  remote/opt-out keep them, and fences/ownership are retained.
- Actual FEX diagnostic gate and summary block, plus texture diagnostics gate:
  200,000 quiet callbacks perform zero summary atomic updates; opt-in restores
  counters and reporting. This is a behavior check, not an FPS benchmark.
- Cache age/budget behavior, warm protection above budget, abandoned/active
  staging, unrelated user/Steam data, links and launch serialization.
- Swap detachment with an actual synthetic POSIX mapping: contents remain
  writable/readable after unlink, wrong inode/link/opt-out cases are rejected.
- Closed-log compaction preserves head/tail and leaves current logs untouched.
- Regression coverage for VC++ overrides/staging, DX11 direct/Steam retries,
  JIT window, shared ports, controls, census gate, SQLite shader persistence,
  runtime profiler gates and generated Settings catalog.
- Xcode Debug iOS arm64 build, unsigned Mach-O/IPA checks, exact resource and
  staged DLL comparison, PE export/import comparison and SHA-256.

No Wine, game, simulator, device or real GPU workload is executed. Performance,
image quality, actual MetalFX activation and thermal behavior need an iPhone
run. Increasing the JIT pool or relaxing FEX memory-ordering is not justified
by this log and is not part of r9.

The lower-input/larger-output approach follows Apple's
[spatial scaler API](https://developer.apple.com/documentation/metalfx/mtlfxspatialscalerdescriptor).
