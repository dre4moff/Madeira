# Local 0.1.1 r13 — DLSS / MetalFX and performance investigation

The official 0.1.1 merge and existing local VC++ runtime, per-game DX11 switch,
Steam library, controllers, full-resolution output and safe storage maintenance
are preserved. This release changes NGX/D3D11, adds NGX supersampling entry points
to the existing Madeira D3D12 engine, and measures the remaining bottleneck.

## Startup and reconstruction

DXMT's NGX GetScratchBufferSize previously called abort(). It now returns success
with zero scratch bytes for supersampling, because MetalFX owns its temporary
resources. Null parameters and unsupported features return errors. Evaluate uses
feature dimensions when the game's optional subrect dimensions are absent;
missing/zero pre-exposure defaults to 1. D3D11 now propagates MetalFX creation
failure through a new COM interface IID, preserving the original Ext/Ext1 ABI,
and resets temporal history on the first successful evaluation. Mobile optimal
settings and dynamic minimum render dimensions no longer request 3x reconstruction
when the existing iOS factory supports at most 2x.

This is an identified startup defect, not proof that it caused this user's failed
launch: the supplied latest device log was explicitly from a later DLSS-OFF run.
A DLL-load message and feature/init/error messages distinguish discovery,
creation and evaluation in the next DLSS-ON log. Game-specific NGX module signature
checks can still affect discovery; see the upstream
[DXMT vendor-extension documentation](https://github.com/3Shain/dxmt/wiki/Vendor-Extensions).
The implemented NGX lifecycle follows the
[NVIDIA SDK API contract](https://github.com/NVIDIA/DLSS/blob/main/include/nvsdk_ngx.h).
No proprietary NGX implementation or neural network model is copied into the app.

The D3D12 bridge resolves four private exports from the d3d12.dll already loaded
by the game. The shipped DLL IS the Madeira D3D12 engine. The Settings canary is
not a backend selector and is not forced on. Init/capability/scratch/create/
evaluate/release/shutdown entry points are provided; original ID3D12Resource
pointers cross a versioned 96-byte ABI, and the backend validates device ownership,
texture formats, dimensions, single-sample 2D resources and output UAV usage.

Evaluation appends a temporal command to the game's Direct/Compute command list;
it does not reconstruct immediately during recording. Replay ends open encoders,
joins pending mode-6 fences, reconstructs and orders later writes. Display-resolution
motion vectors are downsampled with DXMT's existing iOS Metal kernel before MetalFX;
low-resolution vectors go directly to reconstruction. Scalers are cached in two
entries per feature. Feature resources survive list replay; native completion
retains each evaluation's scaler/textures until the GPU completes. Reset/Release
free owned recording references. First use and scaler changes reset history.

Enable **DLSS via MetalFX** on a 64-bit game's card, then select DLSS in its graphics
settings. This works as a bridge for D3D11 and Madeira D3D12 supersampling; it does
not lower the desktop resolution. Jittered-vector mode, frame generation, ray
reconstruction, multisample/array textures and unsupported native texture formats
are rejected. Reconstruction is limited to 2x on this mobile profile. The D3D12
high-resolution-vector path requires a full input viewport; an active subrect is
rejected rather than feeding cropped motion into MetalFX. Actual compatibility/quality still requires the user's device test.

## What the latest device log establishes

The supplied run is r12, full output 1408x648, DLSS OFF and runtime profiling OFF,
with the full 896 MB JIT pool. Device startup reports low-power OFF and nominal
thermal state. Steady scene reports show roughly 6–10 command buffers and dozens
of render passes per frame, encoding preparation around 1–3 ms and flushing around
3–6 ms. Steady drawable acquisition is usually around 0.05–0.08 ms. These timings
are not total GPU time; commit_avg is submission cost, not GPU duration.

The log contains 1,950 FD-send diagnostic lines, 1,794 poll-registration lines,
and 1,161 Wininet cache-index refusals. The successful wineserver FD/poll logs
performed formatted, mutex-protected file writes and fflush on a hot path even
with quiet mode. They are now omitted when profiling is off, while protocol
failures remain logged and explicit profiling restores the diagnostics. No IPC,
polling, fastsync/madsync, thread priority, frame pacing, FEX semantics or cache
limit was changed to claim an unmeasured FPS gain. Wininet's refusals concern its
HTTP index, not a full JIT or shader cache; its protective behavior is retained.

Resolution-insensitive FPS remains consistent with a CPU/translation or
synchronization limit, but this log cannot identify the dominant cause. It has no
real GPU execution measurements or sampled CPU/thread utilization.

r13 adds optional bounded sampling, **CPU and GPU performance sampling** in All
Settings (`env.MADEIRA_BOTTLENECK_STATS = 1`, default; `0` disables it for comparisons).
Every 10 seconds `[perf-bottleneck]` reports process CPU cores, busiest continuously
sampled thread (100% is one core), completed-buffer GPU busy, queue depth/peak,
CPU waits per presented frame, thermal and low-power state. GPU intervals are
unioned across queues rather than double-counted. The GPU busy value is a lower
bound for completed buffers: missing timestamps, overflows and pending buffers
are explicitly reported. Thread sampling is bounded to 512, releases every Mach
send right and the returned array, never suspends threads, and does not enable
FEX counters or scan guest memory. GPU storage is bounded to 8,192 intervals.
There is no synthetic result that establishes an on-device FPS increase.

## Storage and reproducible build

The shader converter archive member is byte-identical to r12, preserving its
DATE/cache identity. Only winemetal_unix.o changes in the native DXMT archive;
only request_ios.o/fd_ios.o change in wineserver. Existing recent shader caches
remain protected and no cleanup runs during gameplay. Temporary/swap cleanup and
closed log compaction retain their existing tested policy.

Synthetic tests exercise real NGX methods, D3D12 recording/replay with fake
COM/Metal boundaries, resource ownership/lifetime, high-resolution motion ordering,
failure propagation, CPU/GPU interval accounting and Mach-right cleanup under
ASan/UBSan. Existing controller, library/configuration, JIT, runtime, cache and
Steam content-fixture checks remain in the validation set. No game, Wine process,
simulator, physical device or real GPU workload was started.

Rebuild the changed components, preserving unrelated shader compiler objects:

```sh
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer MADEIRA_ONLY=winemetal_unix bash build/dxmt-ios/build.sh
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer bash build/wineserver/build.sh diagnostics
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer bash build/dxmt-ios/build-nvext.sh
bash build/madeira-d3d12/build-pe.sh --dll-only
```

Then build with Xcode, `CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO
ENABLE_DEBUG_DYLIB=NO`, and package using `build/tools/package-local-ipa.py` against
the SHA-pinned official 0.1.1 IPA. The distribution contains an unsigned arm64
app, the rebuilt D3D11/NGX/Madeira-D3D12 ARM64EC modules and all 12 unmodified
Microsoft x64 runtime DLLs. The final package verification and cleanup inventories
are stored alongside the IPA. Historical source checkpoints/patches are preserved;
old IPAs, staging bundles and owned disposable build caches are removed only after
validating the new package. Source, toolchains, assets, and device data are retained.
