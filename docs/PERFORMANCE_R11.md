# Madeira r11: D3D11 DLSS Super Resolution via MetalFX Temporal

The supplied r10 log is a failed launch with the old spatial Performance mode:
`[dock-display] desktop=704x324 output=1408x648`, followed by zero presents. The
screenshot reports "The current resolution is too low to run this game."
That mode lowered the virtual display itself; it was not an integration with
the game's DLSS menu. The user's separate MetalFX-off comparisons still show
unchanged performance. This failed launch has no gameplay frame timings and
cannot establish a CPU, GPU or synchronization bottleneck.

r11 replaces the spatial picker with **DLSS via MetalFX (experimental)**, a new
per-game opt-in. Existing library files still decode, including the retired
`metalFX` string, but that setting no longer lowers the display or implicitly
enables NVIDIA vendor extensions. Library and Dock keep the saved resolution,
including 1408x648. New field `metalFXDLSS` is optional. Desktop, 32-bit and
unsupported/remote sessions keep the option disabled. DLSS quality is chosen
inside a compatible game's own graphics menu, with no game-file modifications.

DXMT's pinned source already implements a D3D11 NGX bridge: capabilities,
optimal internal render dimensions, feature creation/evaluation, depth and
motion vectors, jitter, reset and exposure are sent to its temporal scaler
context. The ARM64EC `nvngx.dll` and `nvapi64.dll` are now built and packaged.
The existing DXGI implementation enables its NVIDIA extension only for this
opt-in (`DXMT_ENABLE_NVEXT=1`), and the bridge applies builtin overrides for
the two modules after global configuration. Other override names are retained;
the app restores its own overrides on the next launch. Final spatial scaling
is disabled, avoiding a second upscale of the DLSS output.

The iOS temporal factory preserves Wine/FEX signal handlers instead of applying
the upstream macOS workaround. It checks hardware support, bounds the dynamic
scale range to the device's supported range and respects synchronous scaler
initialization. A null scaler is logged and rejected before GPU submission.
NGX evaluation retains/releases its queried COM interface on every return path
and rejects missing input textures. A creation log identifies actual use:
`[dlss-metalfx] temporal scaler active input=... output=...`.
An `enabled=1` startup line alone does not prove that the game selected DLSS.

## Scope and device check

- This is experimental **64-bit DirectX 11 DLSS Super Resolution** support.
  It does not provide D3D12 DLSS, frame generation, ray reconstruction or
  compatibility with every game's NGX/Streamline/version/signature checks.
- Keep Force DirectX 11 enabled for RV There Yet?, enable the new toggle, and
  select DLSS Super Resolution **Quality** in the game if it becomes available.
  Leave the display at 1408x648 or your prior working resolution. Performance
  now reduces internal targets, rather than the visible virtual display.
- If DLSS is absent, or no temporal-scaler creation appears, the new route was
  not accepted/used by the game; that needs device evidence. Some integrations
  reject unsigned NGX implementations. The app does not patch game signatures
  or replace a game's own DLL files.
- No FPS improvement is claimed. Previous quiet/JIT/controller changes remain;
  warm shader caches, cache cleanup policy and shader converter keys are kept.
  There is no new profiling worker, per-frame logging or disk cache budget.

The intended CrossOver behavior is documented by
[CodeWeavers](https://support.codeweavers.com/en_US/advanced-settings-in-crossover-mac-26).
The underlying bridge is described by
[DXMT's vendor-extension documentation](https://github.com/3Shain/dxmt/wiki/Vendor-Extensions).
Those sources describe desktop implementations, not iPhone acceptance.

## Validation and reproduction

Only synthetic checks were run: production NGX parameters, capability/quality
callbacks, creation/evaluation with fake COM interfaces, and production native
descriptor setup with a fake MetalFX device/factory. Depth/motion/jitter/reset
mapping, unsupported hardware, COM reference cleanup, mobile range limits,
same-resolution direct/Dock launches, optional Codable fields, override reset,
and no double spatial upscaling are covered. These checks do not render a frame
or simulate hardware performance. The new modules' 312 named imports resolve
against the shipped DLL exports and the pinned Wine CRT API-set aliases.

`bash build/dxmt-ios/build-nvext.sh` reproducibly enables the two pinned Meson
targets, builds ARM64EC modules and D3D11, marks vendor modules Wine builtins
and stages resources/license. Native winemetal is rebuilt with the existing
port flags; the linked archive member is verified. The native shader converter
is retained, preserving its date/cache key. An unsigned arm64 Xcode IPA build,
resource comparison with v0.1.0 and bundle/signature/checksum checks complete
packaging. No Wine, game, simulator, iPhone or real GPU workload is run.
