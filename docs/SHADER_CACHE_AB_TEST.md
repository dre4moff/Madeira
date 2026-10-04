# Local r30 shader-cache-off comparison

This is an unsigned local test build, version 0.1.3 / build 15. It is not a
GitHub release and does not establish a cache-caused slowdown or an FPS gain.
The control is the published r30, version 0.1.3 / build 14.

The supplied log uses Direct3D 11. The folder the user removed in Files,
`Madeira/shadercache`, is the separate D3D12 converter cache. D3D11's DXMT
conversion and configured Metal cache paths use `Library/Caches/dxmt` instead.
The log records up to 256 conversion-cache hits and zero reported misses/read
errors. Later 10-second FPS windows are approximately 23–28 at nominal thermal
state. Neither those counts nor a fluid first few seconds establish causation.

The SQLite shader cache and iOS path resolver already exist upstream. The fork
enabled that resolver for 64-bit games too, added low-volume lookup diagnostics
and retained recently used cache directories. This experiment bypasses DXMT
persistent conversion-cache reads/writes and setting its custom Metal cache
path. The automatic internal Metal driver cache and in-memory shader/pipeline
reuse remain. D3D12's separate converter cache is unchanged because it is not
used by this DX11 run.

The trial forces `DXMT_SHADER_CACHE=0`, `DXMT_USE_DEFAULT_METAL_CACHE=1` and
`DXMT_CACHE_STATS=0` after user config
and before game-renderer startup. Three native cache entry points return before
reading a path, resolving a directory, opening SQLite or calling the Metal path
API. This also covers native callers and explicit paths. Existing files are
preserved. The log must show:

```
[shader-cache-test] r30-cache-off-test DXMT-disk=off custom-Metal-path=off driver-cache=system-managed
```

There should be no DXMT `reader-open` or hit/miss reports for this trial. Other
settings, renderer DLLs, texture-upload policy, FEX, audio, fullscreen and native
archives/objects are checked against r30. Only `cache.o`, the app bridge/test
version metadata and the matching executable/symbols change.

The production reader, writer and Metal path entry points run under ASan/UBSan.
An enabled cache first persists synthetic data, then 3,000 disabled operations
are checked for no path dereference, no new files, unchanged database contents
and modification time, no legacy resolution and no Metal path API call. The
actual app override is exercised after a simulated user-config value of 1.
This validates the bypass, not on-device frame stability.

## Device comparison

1. Install the personal cache-off test IPA over Madeira using the same bundle
   ID and usual signing/JIT method. Do not uninstall or delete other data.
2. Use the same DX11 game, resolution, graphics, swap, FPS overlay and map/route
   as r30. Keep Low Power Mode off and compare at similar thermal state.
3. Allow initial loading/shader compilation, then remain at the same position
   for one minute and traverse the same route twice. Keep a two-to-three-minute
   log rather than only the first seconds. Reopen the game once without cleanup
   and repeat; persistent cache remains off but each session's in-memory reuse
   can still warm during the run.
4. Compare to r30 on that same route. Check `[PRESENT_GAP]` average/max and
   `over_50ms`/`over_100ms` counts, plus the 10-second performance/thermal records.
   File clearing and different scene/load phases are not a controlled comparison.

The existing r30 public/personal IPAs remain available for returning to the
control. No remote branch, tag or release is updated for this experiment.

## Outcome and final r31

The user reports no perceived improvement with the cache-disabled IPA. The new
log confirms the off beacon and lacks persistent reader activity. This is a
negative qualitative result, not a matched-route performance benchmark. r31
restores normal cache defaults, fixes explicit manual purge of recent caches,
and documents remaining movement stutters in R31_PERFORMANCE_REPORT.md.
