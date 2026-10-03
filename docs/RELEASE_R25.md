# Madeira 0.1.1 Fork r25 — JIT startup, audio devices and responsive settings

Unofficial experimental fork based on official Madeira 0.1.1. Optimized **Release**, build 9; unsigned IPA, no Debug support dylib, no profiling controls or bundled debug symbols. AI-assisted changes are documented; original FEX source and official Windows FEX DLLs remain untouched.

## Changes in r25 (including the local r24 clock correction)

- **JIT startup:** reserve the largest free safe native address interval early instead of one often-blocked address. The supplied r24 log requested 896 MiB, obtained only 544 MiB and exhausted its code pool while loading graphics DLLs, producing the generic D3D11 GPU warning. No mappings belonging to other components are overwritten. Actual pool capacity still depends on iOS/debugger allocation.
- **Responsive settings:** cache-status checks no longer wait for background filesystem scans. Cleanup and launch remain serialized; recently used shader caches remain protected for reuse.
- **Real microphone/input selection:** explicitly enable microphone access in Settings before launching. Connected inputs and the current actual output route are exposed to Windows. The native driver now returns real microphone samples through WASAPI capture packets; Settings and the session menu provide input selection and the iOS output route picker. No fake silent capture device or audio recording files. Bluetooth input can affect output quality. Device/game acceptance is still required.
- **Less unnecessary work:** remove continuous legacy output sample analysis/raw sample logging; omit known D3D12 read-only transition commands while preserving writes, COMMON/PRESENT, UAV, aliasing, split, unknown-state and previously queued fences. `read-barrier-elision=0` restores recording of these transitions.
- **Shared Windows timer:** publish the Q24 identity multiplier for the existing advancing millisecond clock, preserving actual UTC and local timezone behavior.

## Retained fork functionality

Per-game Native VC++ Runtime and Force DirectX 11 switches; Custom Launch Arguments for direct and Steam/Dock launches; controller fixes; opt-in DLSS via MetalFX for DX11 and Madeira D3D12; prior D3D12 startup/mesh fixes; MMDevice worker COM initialization; upstream 0.1.1 fixes; shader reuse and conservative cache cleanup. See [the complete fork changelog](https://github.com/dre4moff/Madeira/blob/v0.1.1-fork-r25/docs/FORK_CHANGELOG.md).

## Validation and limits

30 synthetic suites passed, including ASan/UBSan tests of actual microphone ring/packet code, Mach-boundary JIT constructor and D3D12 recorder; blocked-scan UI concurrency; 513 launch-parser parity cases; clock/timezone, controller, VC runtime, MetalFX, shader cache and original FEX regressions. The IPA payload differs from public r23 in exactly four files: Madeira, Info.plist and the two identical D3D12 DLL copies. Only the audio object changes in native ntdll relative to r24; unrelated native objects are retained.

**No measured phone FPS improvement is claimed. MECCHA CHAMELEON matchmaking remains unresolved**, including the manual-time warning with Crossplay disabled. The latest log fails before gameplay and contains no backend rejection establishing its cause. No device/server time spoofing or online-check bypass is included. See [diagnosis, audio behavior and next diagnostic capture](https://github.com/dre4moff/Madeira/blob/v0.1.1-fork-r25/docs/R25_JIT_AUDIO.md).

The public IPA contains **no Microsoft runtime DLLs**. Supply your own unmodified Microsoft runtime locally using `tools/prepare-vcruntime-ipa.py` before signing if needed. Installation/rebuild instructions are in [FORK_RELEASE.md](https://github.com/dre4moff/Madeira/blob/v0.1.1-fork-r25/docs/FORK_RELEASE.md). Matching symbols and complete corresponding source with pinned submodules are separate assets; checksums and verification results accompany the IPA.
