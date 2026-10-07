# Complete fork changes — Madeira 0.1.3 / r33

This unofficial fork is based on Will Faust's official `v0.1.3`
(`4e9d45a74294cd820120791c4b3f2b79adf4fc70`). Original copyright and licenses
are retained. Fork changes were prepared with AI assistance and are offered
for inspection, not as an upstream endorsement or a guaranteed FPS increase.
The final FEX gitlink and source tree remain original; the earlier custom
FEX performance/diagnostic gate was removed before this release.

## r33 — WinRT input startup dependency

- Include stock Wine `wintypes.dll` for ARM64EC and native ARM64, matching the
  existing registration of `Windows.Foundation.Metadata.ApiInformation`.
- Address the missing module immediately before Supermarket Together's Rewired
  input plugin throws an unhandled C++ exception in the supplied r32 log.
- Make the builtin build helper accept ARM64EC, ARM64 and i386; add `wintypes`
  to its default module list. Preserve the existing 32-bit module and all r32 engines.
- Verify activation-class registration, DLL exports, PE architecture and imported
  DLL availability in both the source farms and final IPA, including negative fixtures.
- Optimized Release build 18; on-device game startup remains to be retested.
  See [r33 diagnosis and validation](R33_WINRT_INPUT_STARTUP.md).

## r32 — Every original upstream update, with fork features preserved

- Merge all 207 missing original commits through `48f9764`, including the
  original Wine/FEX/DXMT/Dock pins. Keep all 14 original fork commits in history.
- Include Wine Mono and the original patch, save backups/shortcuts, library
  groups, offline Steam, original launch keys, spatial MetalFX, frame generation,
  NVIDIA reporting, AVX, HID output, 40 FPS and the full D3D12/runtime changes.
- Preserve fork controls and fixes; combine NVIDIA/spatial settings with the
  opt-in DLSS profile, and selected Steam launch keys with bounded arguments.
- Rebuild current native/PE components, retain the complete 32-bit farm and
  rebuild changed Wine/XInput and graphics frontends for both architectures.
- Optimized Release build 17, 116 passing host suites and complete final-resource
  verification. Physical-device acceptance and the existing stutter issue remain
  separate. See [r32 evidence](R32_UPSTREAM_SYNC.md).

## r31 — Explicit shader cache purge and movement-stutter evidence

- Fix the manual cache button: explicitly purge recent DXMT databases/custom
  Metal artifacts and Files `shadercache` D3D12 entries, regardless of the soft
  storage budget. Remove empty generated roots, retain foreign files and links,
  and keep launch/cleanup serialization. Automatic cleanup still protects warm caches.
- Restore normal shader cache defaults after the local cache-disabled A/B trial
  produced no perceived improvement. Keep the existing explicit DXMT cache opt-out;
  the native guard now skips path resolution, SQLite and custom Metal setup too.
- Record cumulative dynamic-buffer releases, bytes and immediate fresh allocations
  after a trim in the existing 64-frame log cadence, including when detailed
  profiling is off. Preserve resource ownership, GPU fences and all pool policies.
- Publish a sanitized performance report for developers: movement stutters remain
  unresolved, footprint drops alone do not prove texture eviction, and the supplied
  trial has no evidence justifying another speculative memory-policy change.
- Optimized Release, build 16. 83 host suites; device FPS/rendering acceptance remains
  separate. See [r31 report](R31_PERFORMANCE_REPORT.md).

## r30 — Restore batching and execute texture copies natively

- Revert r29 compact 8 MiB upload rings, additional retention/completion policy,
  and automatic 64 MiB initialization submissions to the complete r28 policy.
  The user reports shorter but more frequent stutters and confirms transient
  memory peaks were never a problem to solve.
- Replace guest-side texture memcpy loops with one native WineMetal operation
  for each local initial/streamed upload. Copies retain padded row and depth
  strides, BC handling, original staging ownership and GPU dependencies. No
  extra image allocation, submission, wait or cache purge is introduced.
- Append Unix-call slot 151 without renumbering existing slots; preserve remote
  explicit uploads, WoW64 pointer translation and the existing opt-out.
- Existing 64-frame Present summaries now count gaps above 50 and 100 ms to
  distinguish recurring spikes from a single long loading frame.
- Optimized Release, build 14. Host/ASan/UBSan checks and packaging are separate
  from physical-device FPS acceptance. See [r30 report](R30_NATIVE_TEXTURE_UPLOADS.md).

## r29 — Texture streaming overhead and upload memory

- Extend direct local shared-memory copies to streamed D3D11 texture updates,
  preserving row/depth data and remote fallback in immediate/deferred contexts.
- Use 8 MiB blocks for iOS 64-bit CPU upload rings, reuse completed upload
  sequences immediately and retain at most two medium-size blocks with expiry.
- Submit creation-time upload batches at 64 MiB boundaries with the original
  owning shared-event sequence and two-buffer GPU queue.
- Retain shader cache identity, native archives, FEX, Dock, D3D12 and all r28
  fixes/features. Swap is working in the supplied log and remains unchanged;
  its capacity does not raise iOS's process footprint limit.
- Optimized Release, build 13. See [r29 analysis and verification](R29_TEXTURE_STREAMING.md).
  Host tests prove the changed operations; phone FPS and rendering acceptance
  remain separate.

## r28 — Official Madeira 0.1.3 integration

- Merge official v0.1.3 and its DXMT dependency: built-in StikJIT helper,
  in-app pairing on iOS 27 / pairing-file import on iOS 26, automatic JIT
  before Play, optional Madeira JIT shortcut, Steam Cloud synchronization
  with conflict choices and replacement backups, controller keyboard/mouse
  mappings and per-game DirectInput choice.
- Recompile the native .NET process, anonymous guest RWX heap / V8 holdback
  allocator and wineserver readiness changes. Include the upstream D3D12
  ResolveSubresource correction and escaped Steam metadata strings.
- Retain every fork feature below, the real microphone path and both r27
  fixes. FEX's source pin and both Windows engine DLLs remain original.
- Rebuild DXMT/D3D12 with the merged fork sources. Pin all embedded command
  and no-output fragment shaders to Metal 3.1; correct the ARM64EC cross-file
  toolchain path after DXMT moved to the repository root. Native command-only
  rebuilding preserves the shader converter cache identity.
- Physical keyboard/mouse mode suspends the fork's early physical XInput
  reservation; touch input remains available. Changed bindings release all
  previous keys before resampling; unchanged bindings do not interrupt a hold.
- Optimized Release, build 12, with a Release JIT extension and separate
  matching dSYMs. See [r28 integration evidence](R28_UPSTREAM_013.md).
  Device gameplay, JIT pairing, Steam Cloud account access and FPS still need
  device acceptance; host builds and tests do not establish those outcomes.

## r27 — Worker context and Dock fullscreen presentation

- Reuse dead Mach-thread registry slots safely instead of exhausting the
  fixed registry after cumulative worker starts. Signal readers use coherent
  snapshots; missing threads never borrow another thread's TEB.
- Recover only the exact observed Mono callback return sequence when the
  owning TEB, CPUArea, callback flag and frame validate. Retry the original
  store with its owning registers; no FEX code or guest code is patched.
- Remove destructive anonymous replacement of unknown occupied mappings and
  correct the reclaim diagnostic; successful mprotect does not zero memory.
- Present a recognized Dock game's client CAMetalLayer over a black fullscreen
  backdrop, preserving guest geometry and inverse cursor/touch mapping.
  Keep the game-window census active throughout the session.
- 33 host suites passed before the upstream merge, including production
  thread-registry and fullscreen-layer replays under ASan/UBSan.
  See [r27 diagnosis](R27_WORKER_CONTEXT_FULLSCREEN.md).

## r26 — YAPYAP voice-worker native stack allocation

- Preserve the iOS native address floor at 64-bit process boot. The old desktop
  reset made a kernel/emulator stack's 4 GiB lower bound disable the existing
  advisory allocation fallback; YAPYAP's voice initialization then failed a
  1 MiB stack request and terminated through `libvosk`/`std::system_error`.
- Keep real microphone capture and voice recognition available. No `-noaudio`,
  thread-count cap, larger stack reservation or FEX change is introduced.
- Retain caller low/high constraints, WoW windows and all unrelated r25 engine
  objects and resources. Only native `virtual.o` changes; only Madeira and
  Info.plist differ in the IPA. Partial rebuilds can select this VM object.
- Optimized Release, build 10; 31 synthetic suites pass, including production
  allocator/stack replay showing the r25 failure and 160-worker recovery with
  ASan/UBSan. Successful phone startup/spoken spell recognition, FPS and online
  matchmaking remain unverified. See [r26 diagnosis](R26_VOICE_THREAD_STACKS.md).

## r25 — Native JIT placement, responsive settings and real microphone

- Reserve the largest actual free hole in the bounded native executable band
  at image load, rather than retry one blocked address. Never overwrite or
  release someone else's mapping; fixed-base executable reservation retained.
- UI cache-availability reads use a short lock rather than waiting behind a
  filesystem scan. Launch/cleanup serialization and warm shader cache retention
  are unchanged.
- Expose actual iOS audio route endpoints, request microphone access explicitly,
  persist preferred input, add settings/session route controls and implement
  real RemoteIO capture with WASAPI packets, PCM conversion and resampling.
  Denied/unavailable capture fails instead of returning a fabricated device.
- Remove legacy continuous output sample analysis and raw sample-word logging.
- D3D12 records no command for known read-only→read-only transitions. Retain
  COMMON/PRESENT, writes, UAV, aliasing, split and unknown-state hazards plus
  every previously recorded fence. Config `read-barrier-elision=0` opts out.
- Include the locally tested r24 Q24 shared-tick multiplier correction.
- Optimized Release, build 9; 30 synthetic suites pass. FEX/source/DLLs and all
  unrelated native archive objects retained. No device FPS uplift or successful
  online matchmaking claimed; manual-time warning is still under investigation.

## r23 launch and clock consistency

- Add **Custom Launch Arguments** to each game's card using the existing saved
  `arguments` field. Direct games, direct Steam starts and Steam/Dock launches
  receive the user arguments; direct Steam starts also keep their default
  program arguments. **Force DirectX 11** remains independent and removes
  conflicting standalone renderer flags when enabled. Quoted values are kept.
- Replace the direct-start space splitter with bounded Windows quoting decode.
  Steam/Dock forwards the complete UTF-8 value to the real game's LaunchApp
  call, including its retry. Empty choices reset across games. No shell
  expansion or raw argument logging is added.
- Correct an iOS Wine clock inconsistency: the shared page kept timezone bias
  at UTC zero while the timezone API used the host's local zone. Publish the
  cached actual offset (including DST) with the standard three-store sequence.
  Refresh outside the server loop at startup/launch and on timezone/significant
  time changes. System UTC, monotonic clocks and device settings are untouched.
- The tester reports that the preceding audio fix allows the affected game to
  start and run. The new timezone correction addresses a proven API mismatch;
  its effect on the empty matchmaking list remains unverified on the phone.
- No new FEX, graphics, controller, shader-cache or performance-policy changes.
  No new FPS increase is claimed. See [r23 details](R23_LAUNCH_CLOCK.md).

## Compatibility and controls

- **r22 audio device discovery compatibility:** the supplied r21 log and
  read-only executable inspection identify a failed MMDeviceEnumerator creation
  on the game's uninitialized asset worker, followed by a null dereference.
  A narrowly enabled implicit-MTA TLS cookie allows the real audio class factory
  to run; existing apartments and unrelated classes keep their behavior. Thread
  teardown releases the cookie. No FEX/graphics/audio backend change; microphone
  capture remains unsupported. Synthetic tests pass; full game startup remains
  unverified. See [r22 evidence and limits](R22_AUDIO_COM.md).
- **r21 PS-less mesh pipeline correction:** provide a precompiled no-output
  fragment when a geometry/tessellation pipeline has no game pixel shader.
  Preserve depth/stencil rasterization and prevent Metal's fatal nil-fragment
  validation. Existing pixel shaders remain intact. A synthetic host Metal
  GPU test verifies actual depth writes and unchanged color; on-device game
  startup remains unverified. Clarify the diagnostic JIT dump and reusable
  shadercache folder in Storage & caches.
  [Diagnosis, implementation and validation](R21_MESH_DEPTH.md).

- **r20 D3D12 startup corrections:** repair Metal event lifetime during device
  destruction, report real device-removal status, reclaim all retired heaps and
  ring buffers, and make full JIT crash dumps explicitly opt-in. Startup cleanup
  removes obsolete dumps while preserving shader caches. The r20 IPA is an
  optimized Release with separate symbols and hidden profiling controls.
  [Diagnosis, validation and remaining limitations](R20_D3D12_STARTUP.md).

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
