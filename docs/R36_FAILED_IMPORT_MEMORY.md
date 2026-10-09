# r36: bounded failed-import retries and Wine QoS dependency

Repeated `LoadLibrary` attempts after a missing import previously left the failed
PE image, module record, TLS and JIT copy behind, then mapped another image on the
next attempt. The supplied r35 device log contains 345 attempts for an approximately
11.75 MiB plugin with a missing `qwave.dll` import, followed by JIT exhaustion and
an 8,161 MiB footprint. The log does not include the OS termination report.

r36 includes Wine's stock `qwave.dll` in the ARM64EC and ARM64 farms; the existing
i386 copy is preserved. Wine's QoS exports remain their upstream implementations,
including unsupported-service responses. This adds a loadable dependency, not a
promise that every QoS or online-service operation is supported.

On an import failure the loader now retains one image per file identity in a
private list, removes it from public module lookups and clears the lookup cache.
Another attempt reuses that image and retries only unresolved import descriptors.
It therefore does not allocate another image, executable copy, TLS slot,
activation context or reference to already resolved imports. This also works when
`OriginalFirstThunk` is absent: already bound IAT entries are never parsed again
as import names. A dependency supplied later can complete the same image; a new
file identity maps the replacement normally. An unresolved dependency fails
initialization, including when reached through a circular dependency.

The first failed image and its graph are intentionally retained for the Windows
process lifetime, or until the retry succeeds and normal unload applies. Existing
circular references and translated code pointers make immediate unmapping or JIT
pool recycling unsafe. This change removes growth with repeated attempts; it does
not cap allocations by the game or retain at most one image across *different*
failed files. No emulator invalidation API or native executable recycling behavior
is changed. Direct, Steam and manually added Dock games share this loader fix.

The 2 GB / 4 GB texture options retain their r34 behavior: they trigger reductions
in eligible texture detail and are not hard RAM caps.

## Build and verification

- Rebuild `ntdll.dll` for ARM64EC, ARM64 and i386 with
  `ARCH=<arch> bash build/wine-pe/build-ntdll.sh` (ARM64EC is the default).
- Build the added dependency with `bash build/wine-pe/build-modules.sh qwave` and
  `ARCH=aarch64 bash build/wine-pe/build-modules.sh qwave`.
- `tests/test_failed_import_retry.py` compiles the production resolver, private
  retention, retry and native-load functions with AddressSanitizer and UBSan.
  10,345 retries use one image/TLS/context, preserve the resolved IAT and reference
  count, recover when the missing dependency appears, distinguish file identities
  and survive bitmap allocation failure and incoming graph references.
- `tests/test_qwave_payload.py [IPA]` checks exports, architecture, stripped PE
  sections, loader markers and import closure in all three runtime farms.
- Package with `tools/package-r36-release.py` against the SHA-256-verified public
  r35 IPA. It permits only the three loader binaries, two added QoS modules and
  application build metadata/code to differ. Original engines, graphics modules,
  Wine Mono and existing resources remain in the payload.

23 selected host suites pass, including the loader sanitizer regression, local
Dock, texture-memory behavior and image-lifetime checks.

Optimized unsigned iOS Release, build 21. Compilation, sanitizer contracts and
payload integrity can be verified on the host; reproducing the menu session,
actual phone memory stability and multiplayer requires device acceptance.
