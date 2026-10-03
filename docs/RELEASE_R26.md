# Madeira 0.1.1 Fork r26 — YAPYAP voice-worker stack fix

Unofficial experimental fork, optimized **Release**, build 10. Unsigned IPA;
matching symbols are separate. No Debug support dylib, testability or profiling
controls. This release retains the existing official-0.1.1-based r25 engines.

YAPYAP's supplied log fails to allocate a native thread stack during voice
initialization, then raises `std::system_error` through `libvosk` and exits.
r26 fixes a boot-time reset that mistakenly disables the native allocator's
existing advisory-ceiling fallback. It preserves the iOS native address floor
and all explicit caller bounds; it does not disable the microphone, voice
recognition or worker threads. Only the native `virtual.o` archive member
changes. All other native objects, Windows engine DLLs, FEX and resources are
retained from r25.

**31 synthetic suites passed**, including a before/after replay of the actual
production allocator/stack functions under ASan/UBSan, 160 consecutive worker
stack allocations, constrained/WoW allocation refusals and genuine failure
cleanup. The IPA changes only Madeira and Info.plist relative to public r25.
Successful startup and spoken spell recognition still require phone testing;
no FPS increase or new online-matchmaking fix is claimed.

Before launching, enable **Settings → Audio devices → Enable microphone for
games**, grant permission and select your real input. The supplied log already
has an input and permission. `-noaudio` is not a workaround for this game.

All existing VC runtime, Force DX11, custom argument, controller, real audio,
DLSS/MetalFX DX11/DX12 and cache features remain. Public IPA assets exclude
Microsoft DLLs: supply your own unmodified runtime with the provided helper
before signing if needed.

- [Diagnosis and patch details](https://github.com/dre4moff/Madeira/blob/v0.1.1-fork-r26/docs/R26_VOICE_THREAD_STACKS.md)
- [Installation and rebuild](https://github.com/dre4moff/Madeira/blob/v0.1.1-fork-r26/docs/FORK_RELEASE.md)
- [Complete fork changelog](https://github.com/dre4moff/Madeira/blob/v0.1.1-fork-r26/docs/FORK_CHANGELOG.md)

MECCHA CHAMELEON's manual-time matchmaking warning remains unresolved. FEX
source/official Windows DLLs remain original. Source, external symbols,
verification, synthetic results and SHA-256 checksums accompany the public IPA.
