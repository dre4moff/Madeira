# r25 diagnosis and validation

Based on official Madeira 0.1.1 and fork r23/r24, with AI-assisted changes in
the Madeira host and D3D12 code only. No FEX edits or FEX contribution.

## What the supplied r24 log demonstrates

The configured JIT request is 896 MiB, but the successful executable allocation
is only 544 MiB. A sub-MiB mapping blocks the old single early reservation
address. Later PE image relocation reaches the pool head/tail limit while
loading D3D12/D3D11 and logs `EXHAUSTED`. The engine's generic D3D11 feature-level
warning is therefore not evidence that MetalFX lacks the required GPU feature.
The host reports nominal thermal state, but this particular log never reaches
gameplay, so it cannot establish a current CPU/GPU FPS bottleneck.

r25 scans actual free holes in [0x119000000, 0x200000000), rounds to native
page/16 MiB boundaries and holds the largest usable run (256–1152 MiB) before
SwiftUI/Metal initialization. Reservations use fixed no-overwrite allocation,
PROT_NONE and bounded retries; they do not commit physical memory. Requested
pool size, executable ownership checks and debugger allocation remain intact.
Actual capacity remains dependent on the OS address map and debugger.

## Audio contract

The existing driver had real render output but no capture endpoints and empty
capture-buffer stubs. The new snapshot enumerates current actual output ports
and permission-gated available input ports. iOS owns global routing; the system
picker handles outputs, and `setPreferredInput` selects an actual available
input. Settings and session menu expose these controls.

One RemoteIO unit per process supplies microphone samples to lock-free client
rings. No allocations, Wine calls or locks run in the callback. Capture supports
1–2 channels, PCM16/PCM32/float32 and 8–192 kHz with a streaming rate converter.
Mono input is duplicated when the Windows client requests stereo; this is not
a promise of independent stereo microphone channels. Overflow drops new samples
without overwriting held packets and reports discontinuity. Games receive
actual samples, not wall-clock-generated silent capture. Permission is opt-in,
and unavailable devices/formats fail explicitly. There are no recorded files
or sample-content logs. OS route changes refresh the native snapshot; cached
Windows endpoint lists may require a game restart.

## Synthetic verification

30 suites pass, including production early-constructor execution with mocked
Mach VM boundaries, ASan/UBSan microphone ring/packet/format/endpoint tests,
production D3D12 barrier recorder tests, a deliberately blocked cache scan to
verify UI reads remain immediate and launch still waits safely, clock/timezone,
513 launch-parser parity cases, controller, VC runtime, MetalFX/DX12 and FEX
restoration regressions. Physical input/output and gameplay remain device tests.
Only `audio_null_ios.o` changes in the native ntdll archive relative to r24;
all other object members and the entire r24 wineserver archive are unchanged.
Windows graphics payload changes only the two identical D3D12 PE DLL copies.
Optimized Release (`-O2` native, `-O` Swift), no testability, Debug support dylib
or bundled dSYM. Matching symbols are supplied separately.

## Performance and remaining online issue

Read-only transition omission removes redundant recorded commands/encoder
breaks while preserving producer hazards. Disabling per-buffer audio sample
analysis removes unnecessary native work. These changes do not establish a
phone FPS gain. Do not describe synthetic success as an in-map speedup.

MECCHA CHAMELEON (Steam AppID 4704690) still reports a manually changed device
time and returns no server list, even with Crossplay off and iOS automatic
time enabled. r24's log proves an advancing Q24 shared tick multiplier and
plausible real host UTC/local bias; it does not contain the successful online
request or backend rejection that would identify the root cause. Windows
TimeAdjustmentDisabled is not a reliable indicator of manually set iOS time.
No clock spoof or online-service check bypass was added. This issue is **not
resolved** by r25 and must not be advertised as fixed.

For a targeted next capture, use Custom Launch Arguments to enable the game's
Unreal online logging if supported:

```text
-LogCmds="LogOnline VeryVerbose,LogEOS VeryVerbose,LogHttp Verbose"
```

Start the game, attempt server search once, note elapsed time, then export the
Madeira log and the game's `Saved/Logs` file. Redact account IDs, authorization
headers/tickets and server addresses before sharing. Compare one attempt with
Crossplay on and one off. This is an optional diagnostic pass, not a required
new setting for normal play.

## Primary API references

- [Apple availableInputs](https://developer.apple.com/documentation/avfaudio/avaudiosession/availableinputs)
- [Apple setPreferredInput](https://developer.apple.com/documentation/avfaudio/avaudiosession/setpreferredinput(_:))
- [Microsoft D3D12 resource barriers](https://learn.microsoft.com/en-us/windows/win32/direct3d12/using-resource-barriers-to-synchronize-resource-states-in-direct3d-12)
- [Microsoft GetSystemTimeAdjustment](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getsystemtimeadjustment)
