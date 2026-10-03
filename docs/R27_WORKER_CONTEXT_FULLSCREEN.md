# r27 — worker context and Dock game presentation

The supplied r26 device log gets past the previous voice-worker kernel-stack
allocation failure. There is no JIT-pool exhaustion or first fatal
`std::system_error` in this run. The first terminal failure is instead two
Mono worker threads accessing address 1 in an emitted helper-return epilogue.

## Observed failure and host correction

The Wine Mach-thread registry reached its 512-entry capacity after hundreds
of worker starts, with only about 72 emulator workers still live. Registration
was append-only except when Mach port names happened to repeat; four pinned
port references kept exited names from recycling. New workers were omitted,
and exception lookup substituted the first registered thread's TEB. The supplied
log explicitly shows the full registry and that foreign context on the faulting
workers. Using another thread's TEB supplies the wrong CPUArea, exception
stack and pseudo-process dispatcher.

The host registry now serializes writers, reuses entries only after Mach
confirms the previous thread is dead, balances its own pinned references, and
publishes entries with an atomic generation guard for signal-safe readers.
Unknown thread-info failures retain the entry. A genuinely full live registry
stays bounded and a missing lookup returns no context; it never borrows another
thread's TEB. This removes the demonstrated cumulative-start failure without
raising a lifetime thread limit or disabling voice.

The log's exact helper-return sequence is `blr x4; ldr x11,[x18,#0x1788];
strb wzr,[x11,#1]`. Mono's emitted return still reads the CPUArea through x18,
which iOS does not preserve across all native calls. A narrow host recovery
matches all three instructions, the address-1 fault, a zero x11, the owning
CPUArea's x28 StateFrame, and its active callback flag. It restores only x11
and x18 and retries the original store. It neither skips the callback flag nor
changes guest registers or the FEX source/Windows engines. This covers the
specific epilogue even if x18 is cleared independently of registry exhaustion.

The old reclaim diagnostic claimed pages had been zero-filled even when
`mprotect` succeeded and no replacement mapping occurred; all five reported
pages in this run have `mmap=0`. That is not evidence of heap zeroing. The
recovery now reports protection restoration accurately and never uses
`MAP_FIXED` fresh zero pages to replace memory whose ownership is unknown.
Wine's absence of a committed view does not establish disposable FEX cache
ownership.

## Game presentation

Dock keeps a Windows desktop for Steam's authenticated launch. The supplied
run's game creates a Metal layer inside a smaller decorated Windows window,
so fitting the desktop alone retains the caption and borders.

The existing owner-path census now tracks the session through completion.
After it identifies the visible game's Metal window, the compositor presents
that client surface above a black backdrop in the game presentation area.
The guest's HWND, client geometry, launch arguments, authentication and saved
display settings stay intact. Touch and cursor maps use the same fitted client
rectangle, including independent X/Y scales for Stretch. Rotation/layout
changes refit the surface; hidden/destroyed windows and session end restore
normal desktop ownership. Steam and installer windows are not selected.

## Verification and remaining acceptance

`tests/test_thread_registry.py` compiles production host functions under
ASan/UBSan. Its unchanged r26 fixture reproduces the incorrect context after
600 cumulative starts with 64 live workers. The patched registry handles 4,000
starts, exact/missing lookups, 512 simultaneously live entries, unknown and
terminal Mach failures, reference balancing, purge, publication guards, and
positive/negative matching of the observed Mono return.

`tests/test_dock_fullscreen.py` drives production placement/input functions
with host CALayers: a smaller client inside the desktop fills the presentation
area, excludes chrome, maps center/edges correctly, handles Stretch and hidden
windows, ignores other windows, and restores layers at session end. The
existing Dock starting-screen tests also pass under ASan and TSan. All 31 r26
regression suites plus the two new suites pass. An optimized unsigned iOS
Release build uses build 11 and separate matching symbols.

These are synthetic host checks and build/package evidence. Successful game
startup, speech recognition, visible iPhone output, multiplayer and FPS still
require a fresh physical-device run. No game or authenticated Steam session
was executed on the development Mac.
