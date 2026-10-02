# Madeira r10: effective MetalFX sizing and remaining native diagnostics

The user reports essentially unchanged performance with r9, including subsequent
MetalFX-off comparisons at their previous resolution. The supplied log itself
is a MetalFX Balanced session; it cannot establish CPU/GPU attribution for those
separate off sessions.

## Concrete r9 launch defect

The profile requests input 1280x720, output 1920x1080 and scale 1.5. But the
Wine argv still contains `/desktop=madeira,1920x1080`. Explorer changes the
monitor back to 1920x1080 before starting the game. The swapchain then logs
`[metalfx] active input=1920x1080 output=2880x1620`: input pixels have not been
reduced and the scaler processes a larger output. This is a launcher defect,
not evidence that the user failed to set a game option.

r10 uses `LibraryEntry.sessionRenderResolution` for the Dock desktop argument,
screen environment and compositor default, matching direct-launch sizing.
The saved output preference is preserved. `[dock-display]` records both sizes.
The bridge exports an output bound after global configuration. DXMT bounds
the scaler's actual output to that size, updates drawable/contents scale, and
bypasses scaling if either input dimension already reaches the output target.
It does not silently resize a game's own backbuffer. A game that restores a
larger saved resolution still needs an in-game adjustment; the log will say
`[metalfx] bypass` rather than scaling it to an even larger texture. Subsequent
smaller swapchain resizes restore the requested factor. Off/unsupported/desktop
profiles retain their prior sizing. No new Unreal or other engine flags are
injected, and no game configuration file is edited.

## Overhead that also exists with MetalFX off

The r9 log has zero CB_SUMMARY, HOTRIP or BC-stream reports: the r9 diagnostic
gates were active. It nevertheless contains sixteen full physical-map scans,
with around 117,000 regions, a repeated whole-host-heap validation, 1,303
srv-stuck lines, 1,475 event-lifetime lines and 483 event-history lines.
The memory monitor mixes JIT residency work with forensic probes, so gating
only the diagnostic workers in r8/r9 did not remove those probes.

r10 gates the full VM-region census, heap validation, CoreAnimation allocation
probes, periodic pool protection census, optional beacon/lock stack sampling,
and server message-queue/stuck-wait dumps on the existing profiling choice.
Native wait histories skip their fences, state copies and timestamp calls;
event history skips its rings/lifetime diagnostic counters. A constant-initialized
cached atomic policy avoids getenv on each hot hook. Explicit
`env.MADEIRA_RUNTIME_PROFILING=1` restores them at the next launch.
The launch establishes quiet/profiling choices from the configuration (or the
legacy environment file) before JIT allocation and wineserver startup, so early
event creation cannot cache a policy that ignores the user's diagnostic opt-in.

The JIT warmer still touches used RX and RW pages, retains its existing cadence,
samples task footprint, and invokes the existing orphan-lock recovery. Actual
Wine event state changes, fastsync cells/generations, wait/alert delivery,
timeouts, APCs and fault handling are unchanged. Memory safety mechanisms are
not exchanged for speed. Cache cleanup/persistence remains exactly the r9 policy
and does not run while playing.

The available map samples show median encode preparation about 2.59 ms, flush
about 4.88 ms and drawable blocking about 0.06 ms. Present gaps remain about
35–52 ms, with little time inside Present. These sampled CPU scopes do not sum
to a complete frame measurement and do not measure GPU duration. The log shows
the full requested 896 MB JIT pool; it does not justify increasing that setting
or relaxing FEX's memory-ordering rules. No claim is made that these diagnostic
costs are the dominant limiter or that r10 will improve steady gameplay FPS.

## Synthetic checks and packaging

- Production Dock sizing branch: Balanced 1920x1080 output produces a 1280x720
  desktop, Performance produces 960x540; off, unsupported hardware, desktop,
  no-profile defaults and saved output are preserved.
- Production output-bound helper: r9's 1920x1080 input no longer creates
  2880x1620 output, lower inputs upscale normally, aspect/rounding is bounded,
  larger game buffers remain unmodified, and malformed limits are rejected.
- Production native wait hooks, with fake TEB/clock: 100,000 quiet waits produce
  zero history stores/timestamp calls; diagnostic opt-in restores records.
  Production event history similarly skips all records in quiet mode and
  restores them when opted in. Actual heap-check block runs with a mock checker.
- Source checks ensure VM/allocation scans are gated while RX/RW warming and
  orphan-lock recovery remain; this does not simulate real Mach execution.
- VC++/DX11, JIT-window, controller, shared-port, cache, profiling, texture and
  generated-catalog regression tests; Xcode Debug iOS arm64 build.
- Native virtual/server/signal-arm64 and server event/fd objects are rebuilt
  with the existing port flags, including wineserver's Mach-O symbol renames,
  and compared with the exact members in the archives linked by the app.
  The D3D11 PE DLL is rebuilt from the pinned tree; export names/ordinals and
  imports are checked against the prior working module. Native FEX and DXMT
  shader converter remain the r9 artifacts, preserving converter cache keys.
- Unsigned IPA verifies bundle identity, 1,008 unchanged upstream runtime
  resources, four rebuilt Dock/DXMT/FEX resources, native VC DLL identity and
  checksum. Native binaries are unsigned; no Wine/game/device/simulator/GPU
  workload is executed.

For a comparable device check, first use MetalFX Off with the same resolution,
map and preset as the previous run to isolate diagnostic removal. Then enable
Balanced and confirm the log shows 1280x720 -> 1920x1080 for a 1080p profile.
If it says bypass, reduce the game's own saved resolution before evaluating
upscaling. Device evidence is still needed to establish a performance gain.
