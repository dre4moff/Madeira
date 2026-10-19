# r39 — Complete upstream synchronization

Madeira 0.1.3 Fork r39, optimized unsigned Release build 24, merges every
upstream superproject change through `279fd0f83170425db002fe25d6bd62f6355f497d`.
The r38 history had 24 fork commits and lacked 212 commits from upstream's
history. The upstream wave changes 286 files; its history includes both
individual development commits and squashed integrations.

## Integrated components

| Component | Original upstream revision | Release source |
|---|---|---|
| Madeira | `279fd0f83170425db002fe25d6bd62f6355f497d` | Complete merge with the r38 fork |
| FEX | `f59cab95659e8add0c88f0c76ec1cf483c536dbf` | Original source, rebuilt native iOS archives; original upstream Windows engines |
| Wine | `9129e9684daaeae70da9435e7c6060e59392634e` | Complete merge preserving fork runtime fixes |
| DXMT | `128b297c6e9a00014408dc68b4c2c2373b5813de` | Complete merge preserving fork graphics features |
| Dock | `72558e416a390f3669457930f09a389e54f49556` | Existing fork `006e8b10fcacf8d302ea4dd538b4784137143685`; no newer original Dock pin |

The source archive and `verification.json` give the final merged dependency
commits. FEX source has no fork code changes. No original runtime feature or
source dependency is dropped; optional precompiled upstream FEX test suites
remain represented by their original pins in the source archive.

## Original improvements included

- Per-executable configuration and launch preferences, built-in recommended
  game profiles, Reset to Recommended and screen-shaped 720-line resolutions.
- JIT-pool layouts and reclaiming exited programs' FEX buffers, larger thread
  populations, optional stack spill and small stacks, Chromium/Social Club
  launcher support and revised virtual-memory diagnostics.
- D3D12 persistent shader caches keyed by converter identity and switch set,
  optional packed caches and pipeline warm-up, command batching and state
  deduplication, indirect tessellation, typed views, MIN/MAX samplers and
  rendering/fault diagnostics. Optional switches retain their upstream defaults.
- Wineserver doorbells, coalesced wake-ups, optional direct requests, descriptor
  reply paths, storage information and timer fairness.
- One-time installers in their own sessions, shared-depot ownership, per-game
  controller settings, native MFC runtime support when the user supplies those
  DLLs, profile folders, Game Mode declaration and thermal/battery diagnostics.

## Fork behavior retained

Native VC++ and DirectX 11 controls, quoted custom launch arguments, local
executables through Dock, DLSS/MetalFX temporal bridges, texture-memory
presets and native uploads, real microphone capture, worker-context and
fullscreen fixes, native-stack/JIT safety, cache maintenance, failed-import
reclamation, QoS modules, Darwin UDP controls and shared trusted CA roots
remain included.

The two runtime controls are mutually exclusive. Enabling Native VC++ Runtime
clears Wine's C++ runtime preference; enabling Wine's option clears the native
choice. A saved explicit native choice takes precedence over a recommended
Wine preference. An explicit `MADEIRA_WINE_VCRT=1` in the final game environment
disables the native overlay and its DLL overrides. MFC follows `MADEIRA_MFC`.

Local Dock sessions reset installer-session state and never acquire a Steam
App ID or run a Steam game's installation plan. Normal Steam sessions retain
the new original installer workflow, ownership checks and selected launch keys.

The original doorbell is combined with the fork's tested wake claim/consume
gate: only consuming a signal releases its claim, so a producer paused between
claim and signal cannot lose ownership to a timeout. The doorbell stress test
delivers 1.6 million requests, including partial reads; the independent Mach
semaphore test retains its timeout-race and counting-mode checks.

Heavy diagnostic workers still respect the fork's profiling control. Upstream
lean-diagnostics and warmer cadence settings apply within that control.

## Build and verification

- Native FEX, ntdll, wineserver, win32u/FreeType and the DXMT/converter archive
  were rebuilt for iOS. Wine uses an iPhoneOS-configured native header, the
  bundled GnuTLS shim, and the checked-in Darwin vnode/device-type shims.
- Changed Wine modules were rebuilt for ARM64EC, ARM64 and i386; DXMT was
  rebuilt for ARM64EC and i386; D3D12 and its forwarding library were rebuilt.
  The complete previous architecture farms are retained alongside new modules.
- 198 applicable host suites pass. Six GNU/Linux x86-64 ELF fixtures, one
  4 KiB-page fixture on this 16 KiB host and one superseded historical allocator
  fixture are explicitly excluded in `synthetic-tests.json`. They are not
  counted as passes. Existing allocator/JIT/native-floor tests cover the current
  implementation on this host.
- Xcode 27.1 builds optimized Release build 24 with native `-O2`, whole-module
  Swift `-O`, testability and debug dylibs disabled. Symbols stay outside the IPA.
- The release packager verifies all current source-farm resources, retention of
  previous resources, original upstream FEX Windows engines, Wine Mono's exact
  patched assembly, JIT helper/framework, matching arm64 dSYM UUIDs and absence
  of Apple signatures/provisioning profiles in all nested Mach-O files.
- The personal unsigned IPA adds the twelve supplied Microsoft DLLs and their
  terms byte-for-byte to the public payload; these files are not public assets.

See `tools/package-r39-release.py`, `verification.json`, the corresponding
source archive and the local verification directory for the exact evidence.
End-to-end rebuilding on a clean machine was not performed. iPhone gameplay,
startup, rendering, FPS, thermals, JIT pairing, authenticated Steam and actual
multiplayer require device testing; this release makes no new measured FPS claim.

## Native header preparation

Configure the ARM64EC Wine build first to provide host Wine tools and generated
IDL headers. Configure a separate native tree with `--host=aarch64-apple-darwin`,
`--with-wine-tools=<ARM64EC build>`, the iPhoneOS clang/clang++ SDK target,
`--enable-archs=arm64ec --without-x --without-freetype --without-gnutls
--disable-tests --enable-winegstreamer`. Its config enables
`HAVE_GNUTLS_CIPHER_INIT`, `SONAME_LIBGNUTLS="libgnutls.dylib"`,
`HAVE_SYS_CONF_H` and `HAVE_SYS_VNODE_H` for the bundled shims. Populate missing
generated headers from the ARM64EC tree without replacing the native config.
Use `MADEIRA_WINE_CONFIG_DIR=<native tree>` for all three native Wine scripts.

After `build/dxmt-ios/build.sh`, refresh every newly compiled object in the
combined DXMT/LLVM archive and stage that archive in `app/Madeira`; updating
only `libdxmt_unix.a` does not update what the application links. The current
build retains the original LLVM archives and replaces all rebuilt DXMT members.
