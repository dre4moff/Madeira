# r20: Direct3D 12 startup and crash-dump corrections

This optimized, unsigned Release update preserves all r19 compatibility,
controller, DX11/DX12 MetalFX and cache changes, and the original Madeira 0.1.1
FEX pin. It does not replace Madeira D3D12 with CrossOver's implementation.

## Findings in the supplied log

The title is MECCHA CHAMELEON (Steam app 4704690), running
`PenguinHotel-Win64-Shipping.exe`. This log contains a launch without `-dx11`;
it has no separate DX11 attempt. Madeira D3D12 loads and creates 11_0/12_0
devices. The old message about the `d3d12` gate refers to an optional diagnostic
canary, not to enabling the game backend. r20 clarifies that message.

The first native fault is `objc_msgSend` from `_MTLSharedEvent_signaledValue`.
Inspection reveals a deterministic ordering bug: `device_Release` releases
`gpu_event`, then `mad_mheap_reclaim` queries that freed event, even during
destruction of an empty adapter-probe device. r20 keeps the event alive until
reclamation finishes. Unconditional teardown no longer queries GPU progress;
normal reclamation still uses the timeline and its existing retirement delay.
Teardown drains all retired heaps in batches of 64 and releases pooled/retired
argument-ring buffers.

Later the log names the stub `ID3D12Device10::GetDeviceRemovedReason`, followed
by guest faults and process exit. A healthy device must return `S_OK`, not
`E_NOTIMPL`. r20 installs the actual vtable method: healthy is `S_OK`, the
existing device-lost flag reports `DXGI_ERROR_DEVICE_REMOVED`, and a recorded
failed GPU serial reports `DXGI_ERROR_DEVICE_HUNG`. Recorded failures remain
visible; no optional device capabilities are fabricated.

Unsupported optional interfaces, features, formats and
`OpenExistingHeapFromAddress` also appear. They remain unsupported: their
memory/aliasing semantics cannot safely be replaced with a successful stub.
A new device run is needed to determine whether one becomes the next blocker.
CrossOver success does not establish feature parity with this iOS backend.
The phone already reported serious thermal pressure at launch. No FPS gain or
successful full-game boot is claimed from this log or host tests.

## Release overhead and storage

- Native application code and the D3D12 DLL use `-O2`; Swift uses `-O` with
  whole-module optimization. Debug support dylibs and testability are disabled.
  dSYM files are separate assets outside the IPA.
- Profiling phase controls are hidden (`MadeiraProfileBuild = false`). Quiet
  runtime mode remains the default; explicit diagnostics and fault logs remain.
- Both Mach/illegal-instruction fault paths now require the exact explicit
  setting `env.MADEIRA_JIT_DUMP = 1` to write the entire JIT pool. Previously
  they automatically wrote 896 MB in this log. General profiling alone does
  not enable this dump. This changes the Wine iOS bridge, not FEX.
- Startup/manual maintenance removes only the exact old generated
  `Documents/fex-jit-dump.bin` when capture is not explicitly enabled. Symlinks
  are refused. Maintenance is serialized before launch. Warm shader caches,
  active Wine files, Steam files and saves are preserved.

## Rebuilding

`build/madeira-d3d12/build-pe.sh --dll-only` reconstructs a missing import
library from the bundled, unchanged ARM64EC `winemetal.dll` and regenerates the
internal shader header if cleanup removed it. Both `d3d12.dll` and
`madeira_d3d12.dll` receive the same compiled output. No DXMT/FEX rebuild is
needed for the PE fixes.

For the dump gate, `MADEIRA_ONLY=signal_arm64 build/ntdll-unix/build.sh` rebuilds
only `signal_arm64_ios.c` and replaces its member in the existing
`libntdll_unix.a`. `MADEIRA_WINE_CONFIG_DIR` may select a regenerated native
Wine configuration directory. The other 36 archive objects were verified byte-identical.
Wine configuration headers were regenerated locally; no complete Wine engine
rebuild or FEX changes were made.

Build the app with the Release command in `FORK_RELEASE.md`, build number 4,
`ENABLE_TESTABILITY=NO` and `ENABLE_DEBUG_DYLIB=NO`. Public packaging retains the
r19 payload and replaces the executable, plist and two D3D12 DLLs. Microsoft
runtime DLLs remain personal-only resources; the public helper is unchanged.

## Validation and acceptance

The new host test compiles the production destructor/reclaimer/status functions
against fake Metal/Win32 boundaries under ASan/UBSan. It covers empty-device
teardown, 130 retired heaps, ring lifetime, GPU-gated normal retirement and
healthy/removed/failed status. Dump tests verify default-off, exact opt-in and
both fault paths. Cache tests cover old-dump deletion, explicit preservation,
symlink safety and warm shader protection. Relevant prior controller,
compatibility and MetalFX suites were rerun.

No game, Wine process, simulator or physical-device session was executed for
this update. Restart Madeira, retain the VC runtime switch when needed, disable
Force DirectX 11 to test D3D12, and export a fresh log after the attempt. Do not
clear warm shader caches between comparable runs. A separate DX11 log is needed
to investigate the reported splash hang. Full-game startup and FPS acceptance
remain open.

References: [device removal status contract](https://learn.microsoft.com/en-us/windows/win32/api/d3d12/nf-d3d12-id3d12device-getdeviceremovedreason),
[diagnostic heap contract](https://learn.microsoft.com/en-us/windows/win32/api/d3d12/nf-d3d12-id3d12device3-openexistingheapfromaddress).
