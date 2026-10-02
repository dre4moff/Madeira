# r21: PS-less D3D12 mesh pipeline startup correction

## Evidence and root cause

The latest supplied log identifies r20 and reports a requested 896 MB JIT pool
successfully allocated at 880 MB. The game executable is
`PenguinHotel-Win64-Shipping.exe` (MECCHA CHAMELEON). It now progresses past the
device-probe failures corrected in r20 and converts many vertex/pixel shaders.
It also creates geometry pipelines, including a `WriteToSliceMainGS` pipeline
whose pixel bytecode length is zero.

The first terminating graphics error is:

```text
Mesh Render Pipeline Descriptor Validation
fragmentFunction must not be nil.
```

Metal raises this while constructing a rasterizing mesh pipeline without a
fragment function. The process then exits and other guest threads fault during
teardown. Those subsequent exceptions do not justify changing FEX. The Metal
SDK's `MTLMeshRenderPipelineDescriptor.fragmentFunction` contract explicitly
requires either a non-nil fragment function or disabled rasterization. See
[Apple's mesh pipeline descriptor](https://developer.apple.com/documentation/metal/mtlmeshrenderpipelinedescriptor).

## Correction and rendering semantics

A D3D12 graphics pipeline may intentionally omit its pixel shader for
depth/stencil-only rendering. Disabling rasterization to appease Metal would
also suppress its depth/stencil work. The fix supplies a tiny no-output fragment
**only to PS-less mesh pipelines**, keeping rasterization and depth/stencil
formats, tests, writes and sample count intact. It suppresses color writes,
blending and alpha-to-coverage when no game pixel shader exists.

`mesh_null_fragment.metal` has no inputs, color/depth outputs, discard,
resources or side effects. The rasterizer supplies depth normally. Both iOS 18
and macOS 15 versions are compiled ahead of time by `build-pe.sh`; the engine
selects the actual rendering backend's version. The library/function are owned
by the PSO, loaded once per PS-less mesh PSO and reused across its variants.
There is no per-frame shader compilation and no new disk cache format.

`mad_mesh_fragment` covers all three paths: DXIL geometry emulation, DXBC
geometry (list/strip variants), and DXBC tessellation. Existing game pixel
shaders retain their functions and pipeline state. A failed real pixel-shader
conversion remains an error; the fallback never substitutes for it. If the
tiny shader cannot load, pipeline creation is refused before sending an invalid
descriptor to Metal, with an explicit log message.

## JIT dump and shadercache in Files

`Documents/fex-jit-dump.bin` was a diagnostic snapshot of the entire executable
pool, roughly 900 MB with these settings. It is not the runtime's JIT storage.
r20 disabled automatic snapshots and cleans the exact obsolete dump at startup
unless `env.MADEIRA_JIT_DUMP = 1` explicitly requests diagnostics. General
profiling does not enable it. The pool is still allocated in memory and enabled
through the existing JIT workflow; the supplied r20 log confirms 880 MB.

`Documents/shadercache` stores reusable converted D3D12 shaders and reflection.
It is useful persistent data, not a replacement for the dump. Cache maintenance
recognizes owned `.mdxc`/`.mdsc` entries and abandoned temporary fragments;
recent shader entries remain protected even above the soft size target.
Obsolete entries are evicted only after 30 days and above that target. Steam,
games and saves remain untouched. The Storage & caches explanation now names
both the folder and the diagnostic file so their different roles are clear.
Do not purge warm shaders between comparable performance tests.

## Validation and limitations

- Production helper tested under ASan/UBSan with fake Metal boundaries: actual
  pixel shader preservation, no-output selection, iOS/macOS selection, per-PSO
  reuse, allocation/function failure, color suppression, retained depth/stencil
  formats and 4x sample count, resource lifetime and all three creation paths.
- A real **host Metal GPU synthetic test** loads the exact macOS metallib
  embedded in the DLL. It creates 1x and 4x mesh pipelines with and without a
  color attachment, rasterizes a triangle and reads back depth `0.25` in every
  pixel. A bound color attachment keeps its red clear value unchanged.
- Relevant r20 regression suites passed for device lifetime, dump policy,
  protected caches, original FEX, D3D12 MetalFX, forced DX11, native VC runtime
  and virtual/physical controller publication.
- Optimized unsigned Release, build 5; separate dSYM, no Debug support dylib or
  profiling phase controls. Native Wine/DXMT/Dock archives and both original
  FEX Windows DLLs remain unchanged from r20. Only the main executable, plist
  and two identical D3D12 DLLs change in the public IPA.

No game, Wine process, simulator or physical-iPhone session was run for r21.
This fixes the specific invalid pipeline demonstrated by the supplied log;
full game startup and FPS gains are not claimed. Other unsupported D3D12
features may still be encountered after this blocker. Update without
uninstalling, restart Madeira, leave Force DirectX 11 off for a D3D12 attempt,
retain Native VC++ Runtime when required, and export a fresh log if it fails.

## Rebuilding

Run `build/madeira-d3d12/build-pe.sh --dll-only` to regenerate both platform
metallibs and both DLL names. Use the optimized Release command in
[FORK_RELEASE.md](FORK_RELEASE.md), build 5. `tools/package-r21-release.py`
packages against the SHA-pinned public r20 payload and verifies exact retention
of every other resource. Microsoft runtimes remain personal-only; use the
existing helper with your locally supplied, unmodified runtime files.
