# Complete fork changes — Madeira 0.1.1 / r19

This unofficial fork is based on Will Faust's official `v0.1.1`
(`ca3183ea3dfb0fd706aff1bea2abb871b5d27aec`). Original copyright and licenses
are retained. Fork changes were prepared with AI assistance and are offered
for inspection, not as an upstream endorsement or a guaranteed FPS increase.
The final FEX gitlink and source tree remain original; the earlier custom
FEX performance/diagnostic gate was removed before this release.

## Compatibility and controls

- **Per-game Native VC++ Runtime:** saves an independent preference and applies
  `native,builtin` overrides for `msvcp140`, `msvcp140_1`, `msvcp140_2`,
  `vcruntime140`, `vcruntime140_1`. Other overrides are retained. Unmodified x64
  runtime files supplied by the user are staged in the architecture-correct
  child farm even when Steam/Dock starts from an ARM64 desktop. Turning the
  option off restores Wine's default library routing. Public IPAs contain no
  Microsoft runtime binaries; see [personal setup](FORK_RELEASE.md).
- **Per-game Force DirectX 11:** sends `-dx11` to a direct executable or Steam's
  actual game launch, rather than to explorer. Session-specific environment is
  cleared for other profiles. This is a request understood by compatible games,
  not an implementation of DX11 for games that only support DX12.
- **Controller fixes:** reserve the first XInput slot before a library game
  initializes when touch mappings or a physical gamepad are available. Preserve
  physical/touch arbitration, buttons/sticks/triggers, independent finger holds,
  explicit disable switches, foreground ownership and release on interruption.
  Stick feedback now uses UIKit without repeated SwiftUI glass invalidations.
  The user confirmed working virtual input in RV There Yet?; the Xbox path has
  synthetic publisher/transport coverage, not a separate new physical-device
  acceptance claim for r19.
- **Original library and Steam preserved:** game cards, owned-library downloads,
  saved preferences and bundle identifier remain. Official 0.1.1 loader/JIT,
  LocalLow, appearance and launch-error changes are inherited, not credited to
  this fork. Native local-resolution output is preserved.

## Graphics and runtime

- **Experimental DLSS via MetalFX, DX11 and DX12:** opt-in card switch, NGX
  supersampling discovery/lifecycle and temporal reconstruction using the
  game's color/depth/motion/jitter/exposure data. DX12 uses Madeira's native
  D3D12 backend and ordered command-list replay. Unsupported inputs and failed
  scaler creation propagate errors; resource lifetime is retained until GPU
  completion. Frame generation, ray reconstruction and module-signature bypass
  are not provided. This does not lower the virtual desktop resolution.
- **Mobile reconstruction bounds:** avoid requesting unsupported 3x scaling,
  validate dimensions/formats and reset history on first successful use/scaler
  changes. Scratch-size queries no longer abort supersampling initialization.
- **iOS shared-port registry:** same-process Metal shared resources/fences can
  be registered and resolved without relying on a system bootstrap service
  unavailable to this sandbox. Reference ownership and failure cleanup are tested.
- **Texture staging:** same-process, owned shared-memory upload path avoids
  repeated transport copies, with size/lifetime checks and original fallbacks.
- **JIT memory recovery:** reservation/alias retries and executable-window
  accounting retain the requested pool within the actual mapped layout.
  Residency warming and memory-pressure handling remain. Official 0.1.1 fixes
  are retained; no relaxed FEX memory model or guest instruction shortcuts are used.

## Steam, networking and synchronization

- Fix poll socket-family cache invalidation when a slot/FD number is reused.
  An IPv4 socket reusing a cached Unix descriptor was incorrectly classified;
  allocation failure now preserves the previous cache and uses a safe fallback.
- Preserve FD-handoff errno before diagnostics and avoid successful-protocol
  hot logging in quiet mode.
- Add bounded numeric sign-in checkpoints and a visible recovery message for
  an unresponsive wait. Actual Steam authentication, subscriptions and DRM remain
  mandatory; no offline entitlement bypass, fake login or credential replay.
- Restore bounded WinINet cache-index growth and retain its mapped view under
  the existing mutex. Growth explicitly persists entries and handles partial/
  failed writes; normal lookups avoid repeated map/unmap and unchanged limits
  prevent unbounded index growth. [Details and failure tests](R17_PERFORMANCE.md).
- Coalesce pending Wine wake notifications while preserving request data,
  polling, deadlines and producer races. `MADEIRA_SRV_COALESCE=0` supports
  comparison. Original synchronization-engine choices remain available.

## Avoidable overhead and storage

- Quiet runtime mode suppresses expensive census, stack-sampling, wait-history,
  VM/heap and retain-count diagnostics while preserving functional release,
  fault handling, lightweight presentation counts and explicit diagnostic opt-ins.
- D3D11 completed-buffer recycling avoids redundant diagnostic and full-queue
  scans while retaining warm buffers, ordering and GPU completion checks.
- Adjacent compatible Metal resource declarations use equivalent bounded bulk
  calls without draw/pass/fence reordering; `DXMT_RESOURCE_BATCH=0` opts out.
- Event-aware graphics waits/query polling are available with explicit gates;
  correctness/ownership and scheduling checks use synthetic fixtures.
- FPS readout and log display publish fewer UI updates; repeated pending log
  signatures retain their counts. On-disk capture remains available.
- Enable persistent iOS DXMT shader caches for x64 callers; preserve schema/key
  correctness. Bounded hit/miss/read-error diagnostics distinguish reuse from
  failures. The phone contained a persisted ~7 MB game database plus WAL/SHM.
- Clean owned abandoned runtime staging and swap leftovers before launch. New
  swap backing is unlinked after opening so it cannot remain as a file after exit.
- Bound only the closed previous-session log; never truncate the active log.
- DX11/DX12 shader caches use soft targets and protect recently used entries
  even above the target. D3D12 eviction is outside the shader compilation write
  path. No cleanup runs during gameplay or touches games, saves, Steam downloads
  or login data. Cleanup reports kept cache bytes rather than an ambiguous 0 MB.

## Evidence and honest limits

The user confirmed that RV There Yet? starts and reaches a playable map after
native VC runtime routing and DX11 were enabled, and that virtual controls work.
Early tests reported ~15 FPS, later modified builds ~25–30 FPS. These are user
reports across different builds/settings, not a controlled attribution to one
patch. Later changes often produced little or no FPS gain.

Live r18 captures on iPhone 17 Pro Max / iOS 27.0.1 showed ~3.9–4.0 CPU core
equivalents with activity on all six cores. Moving FPS windows were 21.2–32.8;
~26.4 is the mean of five complete recorded windows, not a universal benchmark.
Main-thread cost increased from ~0.018–0.019 to ~0.21–0.28 core equivalents
while moving. GPU active execution coverage of 72–82% is not GPU core occupancy.
Guest/JIT stacks remain partly unresolved. [Live report](R18_LIVE_PROFILING.md).

RV There Yet? did not expose selectable DLSS in the user's tests, including
CrossOver; NGX evaluation was not observed in its supplied logs. That does not
prove the game is solely responsible. Both backend bridges are implemented and
synthetically tested, but no in-game DLSS or DX12 quality/performance success
is claimed for that title.

r19 has 21 relevant host suites, plus a new personal-package helper suite,
optimized Release compilation and binary/resource/signature verification.
Synthetic operation-count results (fewer cache mappings, scans, resource calls
and wake tokens) establish reduced work, not higher device FPS. r19 itself has
not yet had a controlled on-device FPS comparison. [r19 changes](R19_PERFORMANCE.md).

## FEX and provenance

`FEX` remains `26859e184ad90f0e811d7f8bbd943a4b1573a2c3`; both Windows FEX DLLs
match the official 0.1.1 IPA. No FEX fork or upstream FEX contribution is made.
The native static archive retains three existing compiler/platform guards and
is unchanged from r18. Its unpublished official counterpart cannot be compared
byte-for-byte. The [existing build-only portability patch](provenance/FEX_NATIVE_PORTABILITY.patch)
is supplied transparently for reproducing that native archive in an isolated
build copy; the checked-out FEX source remains original. It is not an FPS patch.
The archived qualification is detailed in [R18_PROFILING.md](R18_PROFILING.md).

Wine, DXMT and Madeira Dock changes are in separate fork commits pinned by
`.gitmodules`. All original third-party notices and license terms are retained.
