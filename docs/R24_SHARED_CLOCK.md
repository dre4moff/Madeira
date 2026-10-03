# r24: Windows shared-clock compatibility (local Release)

## Scope

This local build follows r23 and changes only the native shared-clock multiplier,
one launch diagnostic, and the build identification. Graphics, performance
settings, controllers, launch arguments, audio fixes, DLSS/MetalFX, cache policies
and the original FEX Windows engines are retained. Nothing has been published to
GitHub. The proposed D3D12 read-barrier experiment was withdrawn, including its
rebuilt DLLs.

## Evidence and correction

The supplied r23 log reports:

```text
GetTickCount64()=280100661 ms (TickCountMultiplier=0x0) — ticking
```

Wine's `kernelbase/sync.c` deliberately ignores `TickCountMultiplier`: its shared
`TickCount` is already in milliseconds. A Windows implementation reading the
shared page and applying the multiplier, however, obtains zero when that field
is zero. A working Wine API therefore does not prove that a direct reader sees
a working clock. Wine's own fallback shared-page initialization in
`ntdll/unix/virtual.c` uses `1 << 24` for this millisecond representation.

`build/wineserver/fd_ios.c` now publishes the same Q24 identity multiplier,
`0x01000000`, along with the existing advancing tick count. The units, monotonic
source, interrupt time, real UTC system time and actual cached timezone bias
remain unchanged. The update adds one scalar atomic store, with no logging,
allocation, timezone calculation or filesystem work in the server loop.

`WineProcessBridge.m` emits one `[clock-compat]` diagnostic after launch logging
is configured. It records host Unix seconds and UTC-minus-local bias. Its
multiplier value describes the configured publication; the existing guest
`[usd-clock]` diagnostic is the check of the mapped page actually observed by
Windows. The `MADEIRA_USD_TIME=0` troubleshooting opt-out remains available.

This corrects a demonstrated clock inconsistency. It does **not** establish that
the game's matchmaking warning is caused by this field. The supplied log lacks
the game's detailed clock-check or matchmaking response. Completed TLS
handshakes are not proof of successful matchmaking authentication. This build
does not change the phone's date/time, forge server time, bypass matchmaking
validation or change Windows' time-adjustment flag.

## Synthetic validation and packaging

- The host harness compiles the actual production `set_current_time()` body
  under ASan/UBSan. It verifies raw and Windows-scaled tick equality, including
  32-bit rollover and larger counts, UTC/interrupt/timezone publication and the
  null-page guard.
- The existing timezone suite covers UTC, DST, fractional positive/negative
  offsets, concurrent readers and publication ordering.
- Regression suites cover launch arguments (513 Swift/native parity cases),
  Force DX11, original FEX, COM/audio compatibility, controller publication,
  shader caching, cache maintenance and D3D12 mesh behavior.
- The native archive is rebuilt with `build/wineserver/build.sh timezone` at
  `-O2`. Only `fd_ios.o` changes; all 46 other archive members retain their r23
  SHA-256 hashes.
- Xcode uses optimized `Release`, native `-O2`, Swift `-O`, no testability and no
  debug support dylib. Build number: 8. Symbols are kept outside the IPA.
- Packaging starts from the SHA-256-verified public r23 IPA and replaces only
  `Madeira` and `Info.plist`. All other payload files, including FEX, D3D12,
  DX11, Dock and audio DLLs, must remain byte-identical. The IPA is unsigned.
- The personal IPA additionally preserves the existing unmodified Microsoft
  runtime DLLs and their license. It is a local test artifact.

No new gameplay, matchmaking or performance acceptance is claimed.

## Device acceptance

Install the personal unsigned Release using the existing signing/JIT workflow.
Keep Date & Time automatic and use the same game configuration as r23. In the
new log, confirm the `r24-shared-clock` build marker and that the actual guest
`[usd-clock]` reports `TickCountMultiplier=0x1000000` with an advancing count.
Then retry Search Public Servers. If the warning remains, capture the new log
and any game/EOS logs; the next investigation must identify the game's failing
validation rather than presume that the phone clock is wrong.

Performance is intentionally unchanged. The last supplied log moves from a
fair to a serious thermal state, so it does not support attributing its later
FPS drop to a new clock fix or promising an FPS gain from this build.

Machine-readable build, archive-member and synthetic-test results are retained
in `dist/local-r24/verification.json`.
