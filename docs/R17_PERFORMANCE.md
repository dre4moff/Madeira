# Local 0.1.1 r17 — WinINet cache index and CPU accounting

## Evidence from the supplied r16 run

The user reports unchanged game performance. The new log identifies r16 and
shows resource batching operating, with hundreds of thousands of saved native
Metal declarations in ten-second windows. Late gameplay reports roughly
21–27 FPS; native render plus compute batch wall time is around 2–3 ms per
frame. Continuing to tune that measured work alone does not explain the full
frame time. The menu reaches 84 FPS; a fixed 30 FPS ceiling is not established.

Late CPU samples total approximately 4.1–4.4 core equivalents. Game, render and
RHI threads account for around 0.6, 0.6 and 0.4 respectively. The large `other`
category cannot be attributed solely to Steam: DXMT's Windows thread-name
buffer truncates `dxmt-encode-thread` and `dxmt-finish-thread`, so the r16 exact
name comparison incorrectly placed these threads in `other`. r17 recognizes
both full and truncated names, without recording arbitrary thread names. This
is an accounting correction, not an FPS optimization or a P/E-core measurement.

The supplied log contains 909 `[cache-full]` failures and 2,636 section-removal
notifications, including repeated removal of the same 32 KB data mapping while
Steam's HTTP workers report a full Internet cache index. WinINet is loaded from
the ARM64EC farm. In the shipped source, index growth was unconditionally
refused after leaked-entry cleanup. Every ordinary cache access also mapped and
unmapped the index. FEX's section-removal path acquires its context-wide exclusive
code-invalidation lock and visits thread code caches even for data sections.
These are concrete avoidable operations; the log does not measure their exact
contribution to game frame time or prove a sole CPU bottleneck.

JIT allocation matches the requested 896 MB. Recorded gameplay windows have
nominal thermal state, Low Power Mode off and zero GPU errors. Completed GPU
buffer interval coverage varies substantially and is not hardware occupancy.
Completion waits are aggregate background waits, not removable game-thread
stall time. These quantities alone do not prove that the GPU has spare capacity.
Sanitized counts and sampling windows are in `r17-log-analysis.json`.

## Cache fix

The ARM64EC WinINet index now retains one mapped view per cache container under
its existing named mutex. Lookups borrow that view; growth, explicit reset and
container teardown release it. Configuration queries acquire the same mutex
before closing a retained view, so an active borrowed pointer cannot be unmapped
by a concurrent query. Other APIs retain their existing locking and reset paths.

Growth snapshots the entire current index, explicitly persists that snapshot
before reopening a larger section, copies existing entries into the new view,
zeros only its added tail and persists the completed larger index. This handles
iOS shadow mappings without relying on unmap to flush modified bytes. The old
view and handle remain alive until success. Publishing the new size makes a
peer container refresh its old view at its next lock. Allocation, mapping and
write failures retain the old live index and attempt to restore disk; a failed
rollback write is reported rather than concealed. Short writes are handled.
There are no writes added to ordinary lookups or per-frame rendering.

The original index ceiling remains 16,187,392 bytes per container (approximately
15.44 MiB). Growth reaches that bound and then returns the original capacity
error. It does not create an unbounded cache, reset Steam credentials, change
HTTP payload-cache quotas, evict warm shaders or lower image quality. Existing
app cleanup policy is retained, with no gameplay purge or tighter shader limits.
Normal index persistence outside growth is unchanged; this is not a guarantee
that every pending cache mutation survives process termination.

Only the WinINet ARM64EC module used in this log is rebuilt. Native ARM64/i386
farms, FEX, Dock, D3D11/D3D12/NVAPI/NGX binaries and native graphics/compiler
archives retain their r16 bytes. Existing controller, library, authentication,
VC runtime and DirectX 11 controls remain. The experimental MetalFX DLSS bridges
for Direct3D 11 and Madeira D3D12 remain available. The supplied run contains
NVAPI initialization but no NGX feature creation/evaluation; no in-game DLSS
upscaling is demonstrated by that log.

## Verification and practical limit

A host test extracts the actual old and new Wine lock/unlock functions, plus
the new growth/write/close functions, and supplies Win32 shadow-mapping and I/O
mocks. Across 50,000 unchanged-index lookups, the old functions perform 50,000
maps and unmaps; the new functions perform one map and no unmaps or writes.
This is an operation-count comparison, not a game benchmark. ASan/UBSan check
entry preservation, zeroed tail, explicit persistence, peer refresh, initial
mapping failure and retry, eight injected growth failure paths, partial/zero
writes, original bounded growth and balanced mutex/view lifetimes. CPU-role
checks cover full and truncated encode/finish names and bounded Mach accounting.

The 31 scoped synthetic tests and ten existing release host checks pass.
An additional broad historical audit has seven harness failures: missing Linux
Glibc/falloc/atomic dependencies, macOS ASan leak-detection incompatibility and
frontend test stubs missing previously added library helpers. Those unrelated
harnesses are not changed or presented as passing; their output is retained in
`r17-extended-host-audit.json`. The affected production paths were not changed
by r17. The release also verifies optimized unsigned iOS compilation,
ARM64EC CHPE metadata and imports, IPA resources, version and Apple-signature
absence. No app, game, Wine session, live Steam login, simulator or GPU is run.
There is no measured r17 device FPS gain. This fixes an observed cache failure
and repeated mapping cost; it cannot honestly guarantee that the game's limiting
path is removed. Compare the same map/settings and warm caches on the phone.

Superseded IPA and disposable build caches are removed only after verification.
Source, toolchains, small historical evidence, supplied logs and app/game data
are preserved.
