# r34 — Per-game texture memory saving

Madeira 0.1.3 fork r34, optimized Release build 19, adds **Texture memory saving**
in each game's **Compatibility & performance** section. The menu has **Off**,
**4 GB** and **2 GB**. Try it only when loading a game or map with large textures
makes the app close. Reducing texture detail can help a game fit in memory;
it cannot guarantee that every game stays below the iOS process limit.

## What the values mean

4 GB and 2 GB are approximate app-memory-use triggers (internally 4096 and
2048 MiB), not hard limits on app RAM or the total texture allocation. The
2 GB setting starts the same reduction earlier. Eligible textures created
under pressure lose one top mip, usually halving each dimension and removing
roughly three quarters of that texture's storage. Already allocated textures
are not resized. Device memory pressure can start reduction before the chosen
trigger: both modes retain a 1536 MiB headroom guard.

For example, with an 8192 MiB process budget, the 4 GB mode sets DXMT's
headroom threshold to 4096 MiB; 2 GB sets it to 6144 MiB. Lower remaining
headroom means more memory is used, so the larger headroom threshold acts
sooner. The budget uses current process footprint plus available memory,
capped by physical RAM minus the existing `ram-reserve-mb` setting. It never
changes the iOS limit, swap tier, reported GPU budget or JIT reservation.

## Renderers and resource safety

DXMT (DirectX 11) uses the existing automatic BC mip clamp. The game menu
writes `texture-memory-start-mb = 4096` or `2048` to the game's existing config
and derives `d3d11.mipClampAuto=1;d3d11.mipClampAutoMB=<headroom>` at launch.
Off removes the preset and its legacy DXMT options, leaving renderer defaults
and other advanced settings. The existing 32-bit pressure guard is retained.

Madeira DirectX 12 reads the same per-game trigger and uses the existing
WineMetal headroom query. Eligible resources are committed, private, sampled
2D BC textures, at least 1024 pixels in one dimension, with multiple mips,
block-aligned retained dimensions, no special flags and one sample. The
logical resource description and copy footprints stay intact. Uploads,
readback and texture copies translate logical mip indices to retained physical
mips; copies targeting a removed top mip are skipped. SRV ranges translate
similarly, with a removed-only range falling back to the first retained mip.
Array and cube slices are preserved. Render targets, depth, UAV, shared,
placed and reserved resources are excluded. Memory reports count the physical
texture size. Remote rendering or an unavailable memory budget skips reduction.

The tested r33 Supermarket profile is recognized as 4 GB and extended to
D3D12 at launch without changing the saved library schema. Switching modes
preserves unrelated DXMT options, comments, launch settings and MetalFX.
Changes apply at the next game launch.

## Validation and limits

The user confirmed that Supermarket Together entered its map on an iPhone
17 Pro Max with the r33 DXMT profile `mipClampAuto=1;mipClampAutoMB=4096`.
The diagnostic run began reduction near 4102 MiB of process footprint,
reduced at least 1792 large textures and ended at 7181 MiB, with a sampled
peak of 7190 MiB. This demonstrates that particular game/run; it is not a
hard memory cap or a promise about other maps.

19 focused host suites verify profile serialization, legacy recognition,
Off/4 GB/2 GB transitions, per-game isolation, config precedence, frontend
contracts, VC++/DX11/MetalFX coexistence, D3D12 mip eligibility and actual copy
recording, array slices, cropped upload pitches, SRV ranges, tiled resource
exclusions, lifetime, NGX and existing memory policy. The ARM64EC D3D12 DLL
and optimized iOS app compile successfully. Final IPA checks verify resources,
architectures, external symbols, JIT extension and unchanged runtime payloads
outside the app and the two D3D12 DLLs.

The r34 menu, new 2 GB mode and D3D12 rendering have not yet been accepted
with a physical-device gameplay test. Games using different texture formats,
large CPU allocations or placed/reserved resources can still exceed memory.
