# Local r12: upstream 0.1.1 integration

Base: official tag `v0.1.1`, commit `ca3183e`. This is a merge of upstream
into the local r11 fork, with a recoverable source/archive checkpoint at
`.build/checkpoints/r11-before-v0.1.1`. This document describes r12; r13 supersedes it (see R13_DLSS_PERFORMANCE.md). Old IPAs are removed from `dist` after validating r13.

Included upstream changes: JIT readiness checks and actionable launch failures,
RW alias retry for the 63 GB address map, private mapping of shared PE sections
unaligned to the host page, executable-window access for small fixed-base
images, the running user's AppData/LocalLow folder, Steam error 29 explanation,
Appearance settings and the new default Liquid Glass, gentler card highlights,
and privacy-preserving startup device diagnostics. The project supplies version
0.1.1 and build 2 to Info.plist.

Preserved local features: per-game native VC++ runtime and its five DLL overrides,
Force DirectX 11, touch/physical controller publication and early player-1 slot,
full display resolution and the experimental D3D11 DLSS-to-MetalFX bridge,
JIT reservation recovery, quiet profiling, texture staging and persistent shader
caches. Storage maintenance keeps recent shaders and never runs during gameplay;
existing library/configuration paths and the bundle identifier are unchanged.

Upstream reorganized the source tree: DXMT, Madeira Dock and Madeira D3D12 are
now top-level components; host tests moved to `tests/host`. Local build scripts
and tests follow those paths. Existing Meson build trees have local compatibility
symlinks under `research`; those are not distributed in the IPA.

The 1,012 runtime farm files are byte-identical between the official 0.1.0 and
0.1.1 IPAs. The local fork keeps its four rebuilt farm files (Dock host/notices,
D3D11, FEX ARM64EC) and two added NVEXT modules. The native ntdll virtual-memory
object was rebuilt for upstream's loader fixes. Other native archives remain
byte-identical to r11, preserving the shader-converter cache identity.

Validation is synthetic only: host tests of production profile serialization,
JIT readiness and kernel-error alias retry using mocked Mach calls, memory-window
policies, controller publication, cache ownership/age protection, texture upload,
NGX/MetalFX descriptor boundaries, Steam library/download fixtures, unsigned iOS
build and IPA resource/version/signature inspection. No game, Wine session,
simulator, physical device or real GPU workload is run.

This integration does not establish an FPS improvement or enable a new D3D12 NGX
bridge. Madeira D3D12 remains the existing D3D12 engine; r11's temporal bridge is
still D3D11-only. The separate D3D12/CPU-bottleneck investigation remains open.

Rebuild native virtual memory with `build/ntdll-unix/build.sh` (or compile only its
`virtual` object to preserve all unrelated objects). Build the app with
`CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO ENABLE_DEBUG_DYLIB=NO` and package
with `build/tools/package-local-ipa.py --upstream /path/to/Madeira-0.1.1.ipa`.
