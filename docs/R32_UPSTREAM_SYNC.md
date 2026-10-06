# r32 — Complete upstream sync

The fork branch was 14 commits ahead and 207 behind `willfaust/Madeira:main`.
This release merges every original change through
`48f976429c189f8396e23d251d8a82f43c705922`, without rebasing away the fork history.

The original pins are retained as ancestors of the merged component forks:

| Component | Original upstream pin | r32 source |
|---|---|---|
| FEX | `3bec2ac498bf78156ab47c0c194b0e8cb2849756` | Original source, no fork changes |
| Wine | `257f271cfffed9f22f7987cac53bc00095d092fe` | Original runtime changes plus fork COM/cache fixes |
| DXMT | `db546ee466ad50ec6463edb5fa183de11db43761` | Original graphics updates plus native uploads, cache policy and DLSS |
| Madeira Dock | `72558e416a390f3669457930f09a389e54f49556` | Original offline/launch behavior plus bounded custom arguments |

## Original features included

Wine Mono and its hash-checked mscorlib patch; save backups and Home Screen
shortcuts; library groups; original Steam launch-entry keys and offline
support; display-shape resolution choices; spatial MetalFX on D3D11/D3D12;
frame generation; NVIDIA reporting; AVX controls; HID controllers and output;
40 FPS choices; the original JIT, Wine runtime, swap and D3D12 improvements.
The full original source changes and resources are included rather than
selectively cherry-picked.

Existing fork controls and fixes remain: per-game VC runtime and DX11,
bounded custom launch arguments, experimental DLSS via MetalFX, microphone
capture and route selection, native stack floor, worker context and Dock
fullscreen, cache maintenance and native texture uploads. The NVIDIA/spatial
options are no longer cleared by an inactive fork DLSS profile. Dock forwards
the selected original launch key and bounded arguments on initial/retry paths.
D3D12's healthy-device result retains both the original device-loss handling
and the fork's GPU-hang reporting; teardown retains both scratch and ring
buffer ownership fixes.

## Build and evidence

Optimized Release, version 0.1.3, build 17. Full Wine native archives, DXMT
native/converter archive and six PE libraries, original FEX native archives,
fork Wine ntdll/combase/wininet and D3D12/d3d12core are rebuilt. The entire
729-file i386 farm is retained; changed Wine runtime/XInput DLLs and the
i386 DXMT D3D9/10/11, DXGI and WineMetal frontends are also rebuilt, so
32-bit games retain their resources and receive the new graphics/pad work. FEX Windows
engines are byte-identical to the latest original upstream files. No FEX source
portability patch is needed by the current original revision. The Metal AIR
support shaders are generated from source; the tessellation atomic uses the
public Metal intrinsic with the same relaxed threadgroup operation.

All 116 original/fork host suites pass, including sanitizers, Wine Mono,
launch selection/offline contracts, HID output, audio, resource lifetime,
shader cache, launch arguments and memory policies. Older synthetic harnesses
were extended for the current production interfaces; historical before/after
comparisons use actual pre-fix revisions instead of a moving HEAD. No suite
was dropped. The new package verifier checks that the previous r31 payload
resources and all current original runtime resources remain, and verifies the
Mono patch, stripped ARM64EC libraries, unsigned ARM64 code and matching dSYMs.

Wine Mono 11.0.0 is bundled with its COPYING and matching source asset. The
app's original download fallback remains available. Public artifacts exclude
Microsoft VC runtime files; a personal IPA can include the owner's unmodified
local runtime through the existing preparation tool.

Compilation and host contracts do not establish device gameplay, rendered
frames, live Steam authentication or an FPS improvement. Those checks require
physical-device acceptance. No game or account was launched during this work.
The existing r31 movement-stutter limitation remains documented.
