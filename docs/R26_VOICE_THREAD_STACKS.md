# r26 — YAPYAP voice-worker startup allocation

This is a narrow host Wine VM correction on the existing official-0.1.1-based
r25 fork. AI-assisted implementation is confined to Madeira's host code; the
original FEX gitlink, source tree and Windows engines are unchanged.

## Evidence from the supplied r25 log

The game is [YAPYAP, Steam AppID 3834090](https://store.steampowered.com/app/3834090/).
Voice is part of its gameplay, so disabling audio/recognition is not a fix.
The supplied run has Force DirectX 11 enabled; the tester separately reports
the same failure without it. We do not have a second DX12 log for comparison.

The log exposes an actual microphone input and granted permission. The 896 MiB
JIT request obtains 752 MiB; there is no `jit-pool EXHAUSTED` event in this run.
During voice initialization, creation of thread 01cc fails while allocating a
1 MiB kernel stack in [0x100000000, 0x73ffff0000). Its allocator returns
STATUS_NO_MEMORY without attempting the existing unclamped fallback. Immediately
afterwards, the main thread raises GNU C++ `std::system_error` with
`libstdc++-6.dll` and `libvosk.dll` exception handlers, then exits with code 3.
The native exception storm occurs later, during shutdown; it is not the first
failure. No private log, ticket, account ID or game binary is redistributed.

## Root cause and patch

`build/ntdll-unix/virtual_ios.c` initializes `address_space_start` to
0x100010000, above the native iOS PAGEZERO region. However, the generic desktop
Wine branch in `virtual_set_large_address_space()` resets it to 0x10000 whenever
a 64-bit pseudo-process boots. A kernel/emulator stack's 4 GiB lower bound then
looks like an additional restrictive caller bound. `map_view()` consequently
disables both its usable scan floor and its advisory furniture-ceiling fallback.
If the preferred high window is full, that becomes a hard allocation failure,
even though an unconstrained native allocation can still succeed.

r26 retains 0x100010000 at 64-bit iOS process boot; other platforms keep the
desktop value. The existing fallback can now serve a native stack whose lower
bound is already satisfied by the native floor. No arbitrary thread-count cap,
audio disablement, global allocator retry loop or increase in reserved stack
size is introduced. Explicit restrictive low/high limits still fail within
their requested windows. WoW32 process windows and fixed-address validation
are unchanged. The partial native build replaces only `virtual.o`; the entire
wineserver archive and all other native archive members are byte-identical to
r25. All packaged PE engines and resources remain byte-identical to r25.

## Verification

`python3 tests/test_native_stack_floor.py` compiles the production process-boot,
`map_view()` and thread-stack functions with a synthetic allocator. It first
replays the former boot reset and reproduces the fatal 1 MiB stack failure with
no anonymous fallback. With the patch, 160 consecutive native stack requests
recover successfully. It also checks emulator and guarded stack sizing,
explicit caller bounds, 2/4 GiB WoW windows, fixed mappings, genuine OS
allocation failures and cleanup after view creation failure, under ASan/UBSan.
This demonstrates the diagnosed allocator defect; it does not simulate the
whole voice engine or prove that a phone has enough physical memory.

All 30 r25 synthetic suites also pass, including actual capture packets/rings,
route discovery, JIT reservation, D3D12/MetalFX, controller, cache serialization,
clock and launch argument regressions. The release uses optimized native -O2
and Swift -O, build 10, no testability, Debug support dylib or profiling controls.
Matching symbols are separate. Only Madeira and Info.plist differ in the IPA
relative to public r25. Public assets contain no Microsoft runtime DLLs.

## Phone acceptance

Before launching YAPYAP, enable **Settings → Audio devices → Enable microphone
for games**, allow iOS access, select the connected input and choose it in the
game if offered. Restart Madeira before changing microphone access after a
Wine session. Keep custom arguments empty unless needed; `-noaudio` defeats
this game's voice functionality. The log already shows permission/input, so
these instructions are not a claim that missing permission caused this crash.

Verify startup into gameplay and recognition of spoken spells on the phone.
If it still fails, export a fresh complete r26 log; an early native memory
failure and a speech-model failure require different follow-up. Voice capture,
successful YAPYAP startup, multiplayer and FPS remain unverified on-device.
The previously reported MECCHA CHAMELEON matchmaking warning is still open.
