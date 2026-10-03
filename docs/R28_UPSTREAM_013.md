# r28 — Official Madeira 0.1.3 with retained fork fixes

The release merges official `v0.1.3` at
`4e9d45a74294cd820120791c4b3f2b79adf4fc70`, from the official v0.1.1 merge
base, into the preserved r27 fork. DXMT merges official
`35a4db11bd1bda380c5176a3bc6c1878f7192101` with the fork's compatibility and
performance changes, plus the relocated ARM64EC cross-file path correction.
The original FEX pin remains `26859e184ad90f0e811d7f8bbd943a4b1573a2c3`;
Wine remains `14c361b646f539f237050d6e3e4585b6aa835e8b` and Dock remains
`09c98ba5998cf873d7e0c9363ec26ff2acf193e5`.

## Integrated official changes

Built-in StikJIT runs in the bundled MadeiraJITHelper extension. The pairing
library is built from the locked Rust dependencies, with the upstream MIT/MPL
notices retained. In-app pairing requires iOS 27; iOS 26 accepts an imported
pairing file. StikDebug remains available. Automatic JIT and the optional
Madeira JIT shortcut use the official flow.

Steam Cloud synchronization retains upstream conflict choices and replacement
backups. Physical controller keyboard/mouse mappings and the per-game
DirectInput choice are integrated. The native build includes official .NET
native-ready process routing, guest anonymous RWX heap policy, V8 holdback
release, wineserver readiness and D3D12 ResolveSubresource corrections.

## Retained fork behavior and integration corrections

The fork keeps the worker registry/Mono return fix, native stack floor, early
JIT reservation, real microphone capture and device routes, Dock fullscreen
presentation, custom launch arguments, native VC++ opt-in, Force DX11,
DLSS/MetalFX bridges, read barrier elision, cache maintenance, shared Windows
clock, controller publishing and bounded diagnostics.

Controller keyboard/mouse mode suspends an early reservation that came only
from a physical controller; touch-controller reservations are retained.
Changing bindings releases old keys before the new sample, including a stick
changed from keys to mouse. Reapplying identical bindings preserves holds.

All embedded command and mesh no-output fragment shaders are pinned to Metal
3.1. The ARM64EC cross file resolves its toolchain relative to its own location
instead of the DXMT project root. Targeted native rebuilds use the shipped
archive as their base and replace only their selected members.

## Verification

- Optimized Xcode Release build succeeds for the main app and JIT extension,
  build 12 / version 0.1.3. Native code uses -O2 and Swift uses -O; debug support
  dylibs, preview dylibs, testability and profiling phase controls are disabled.
- 80 host suites pass, including all 33 r27 suites, all upstream host checks,
  Rust pairing tests, Swift Steam Cloud rules and production VM policy checks.
  Tests that depended on Linux-only harness APIs now use Darwin equivalents
  on macOS, while retaining their Linux path. Profile fixtures include the
  actual ControlAction type required by 0.1.3's new saved controller fields.
- Native archive comparison changes only `process.o`, `virtual.o`,
  `main_ios.o`, `request_ios.o` and `dxmt_command.o`. The r27 signal/thread
  object and all unrelated members are byte-identical; the shader converter
  cache identity is preserved.
- Every r27 payload resource is retained. Eight existing files change: the
  main executable, Info.plist, five rebuilt ARM64EC graphics DLLs and the
  notices. Seventeen resources are added for built-in JIT and its licenses.
  Both FEX Windows engines are byte-identical to r27 and official 0.1.3;
  the Dock executable and notices remain identical to r27.
- The package has four unsigned arm64 Mach-O files, no provisioning profiles,
  no debug dylibs or dSYMs inside the IPA, and no Microsoft runtime binaries.
  Main-app and helper dSYM UUIDs match their shipped binaries. Source,
  symbols, SHA-256 checksums and a compact verification manifest accompany it.

The public IPA SHA-256 is
`ac65afc7643d641588013767df91e8060169e679796c269a5cd867ffd233f810`.
The downloaded official IPA was verified against GitHub's release digest
`71e900cbc140778bd6fa67c1062821981ed98e6bfb674d853cfeefd6d242e1c0`.

Host tests do not establish phone gameplay, JIT pairing, authenticated Steam
Cloud access, visible fullscreen rendering, spoken recognition, online
matchmaking or higher FPS. Those require device acceptance. The previously
reported MECCHA CHAMELEON manual-time warning remains unresolved.

## Building these changed components

Use the full dependency recipes in BUILDING.md for a fresh build. On a
prepared checkout, the native updates can use:

```sh
MADEIRA_WINE_CONFIG_DIR=/path/to/configured-wine MADEIRA_ONLY=virtual build/ntdll-unix/build.sh
MADEIRA_WINE_CONFIG_DIR=/path/to/configured-wine MADEIRA_ONLY=process build/ntdll-unix/build.sh
MADEIRA_WINE_CONFIG_DIR=/path/to/configured-wine build/wineserver/build.sh startup
MADEIRA_ONLY=dxmt_command build/dxmt-ios/build.sh
build/rppairing-ios/build.sh
build/madeira-d3d12/build-pe.sh --dll-only
```

Rebuild DXMT's ARM64EC d3d11, dxgi and winemetal DLLs with Meson/Ninja from
the merged source; stage the resulting DLLs before the app Release build.
The r28 packager consumes verified Release products and the SHA-pinned official
and prior r27 IPAs. It strips signatures only in its disposable staging copy,
checks the nested helper, compares resources and keeps dSYMs separate.
