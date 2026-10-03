# r23 — custom launch arguments and consistent Windows local time

## What changed

Based on the complete r22 fork. Official Madeira 0.1.1 remains the upstream
base; original FEX source and Windows engines stay unchanged.

Each non-desktop game card now exposes **Custom Launch Arguments**. The
existing `arguments` field is reused, so the library schema and saved profiles
are preserved. Examples: `-noaudio`, `-windowed`, or `-path "Maps Folder"`.
The independent **Force DirectX 11** toggle still applies `-dx11`; when enabled
it removes conflicting standalone renderer flags from the assembled user
arguments. Disabling it restores the saved custom arguments. This does not
rewrite Steam's selected default launch option.

Direct local starts decode Windows double quotes/backslash rules into argv,
then use Wine's existing command-line encoder. Direct Steam program starts
combine Steam's program arguments with the saved custom arguments once.
Steam/Dock starts use the selected Steam launch option and pass the complete
custom UTF-8 command line to the actual game's LaunchApp call, on both the
first attempt and the configuration retry. Arguments never execute as a host
shell command. The host command line and the game's arguments remain separate.

Bounds: fewer than 4096 UTF-8 bytes in the assembled arguments, at most 64
arguments, balanced double quotes, no NUL or line breaks. Invalid profiles are
rejected before launch; the native decoder and Dock also fail on overflow.
Only counts/byte lengths are logged, never the raw custom arguments. Values
are reset for each selected profile and desktop to avoid cross-game leakage.
Authentication, entitlement, the original client and original game DRM remain
unchanged. `-noaudio` is an optional diagnostic argument, not an FMOD fix.

## Why local-time consistency needed a correction

In the iOS wineserver, `set_current_time()` updated the Windows shared page's
UTC/monotonic clocks but deliberately left `TimeZoneBias` at its initialized
UTC value (zero). Wine's separate timezone-information path computed the
actual host local timezone. Consequently, a Windows local-time conversion
could disagree with the reported timezone when the iPhone was outside UTC.

The bridge now snapshots the real host offset, including DST, outside the
server event loop. Windows bias is UTC minus local time, stored in 100 ns
units. Startup, post-config launch setup and iOS timezone/significant-time
notifications refresh the cached atomic value. The server reads it and
publishes High2/Low/High1 with the existing shared-time atomic sequence.
No libc timezone calculation, allocation, logging or file I/O was added to
the steady-state clock publication path. The existing MADEIRA_USD_TIME opt-out
still applies. Neither wall-clock UTC nor QueryPerformanceCounter nor device
date/time settings are changed. No game check is patched or bypassed.

The supplied gameplay report says the device uses automatic date/time and the
server list remains empty with a manual-time warning. The log does not prove
a server clock-skew rejection. This fix addresses the actual API inconsistency;
whether it removes that game's matchmaking warning needs on-device testing.
Other network/auth/service causes remain possible. No successful matchmaking
or additional FPS gain is claimed for r23.

## Build and synthetic verification

- Production Swift profile assembly/persistence and native Windows quoting
  decoder: 513 corpus cases including quoted spaces, UTF-8, backslashes,
  empty arguments, malformed quotes and limits; round trips through Wine’s
  actual command-line encoder; ASan/UBSan on the C path.
- Actual Dock reader and both LaunchApp call sites: complete custom forwarding,
  legacy DX11 fallback, empty/reset values and conversion/size failures.
- Production timezone helper: UTC, Rome/New York winter and summer DST,
  India/Nepal fractional offsets, local/UTC round trips and concurrent cached
  readers/refresh; shared-page write ordering and off-loop refresh wiring.
- Existing audio COM, D3D12 mesh depth, cache, JIT policy, original FEX,
  controller, VC runtime and Steam auth regression suites.
- Dock's bootstrap/launch, ownership/CEG/service, handoff and layout suites.
- Optimized iOS Release compilation and unsigned package inspection. Matching
  dSYM symbols are separate assets; no Debug support dylib or profiling UI.

The native server rebuild replaces only `fd_ios.o` in the actual shipped
archive; all other archive members are verified unchanged. No FEX, graphics,
controller, audio COM, native ntdll or shader-cache binary is replaced. The
packager compares every file with public r22; permitted replacements are the
main executable, Info.plist, stripped Dock executable and its source notices.

Rebuild this increment from a complete r22 artifact/input set:

```sh
# A configured Wine host include/config.h is required; native build details
# are recorded in BUILDING.md. Configure only: do not rebuild unrelated DLLs.
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
  bash build/wineserver/build.sh timezone
bash build/madeira-dock/build.sh --check
python3 tests/test_launch_arguments.py
python3 tests/test_timezone_bias.py
# App Release command and personal runtime preparation: FORK_RELEASE.md
```

The corresponding-source ZIP retains the pinned full dependency trees. The
partial packager requires the SHA-verified r22 public IPA; it is an incremental
artifact tool, not a promise of a clean-machine one-command rebuild.
