# r33 — WinRT dependency for game input startup

The supplied r32 device log shows Supermarket Together (Steam app 2709570)
presenting its startup screen, then loading `Rewired_WindowsGamingInput.dll`.
The plugin requests `Windows.Foundation.Metadata.ApiInformation` through
`RoGetActivationFactory`. Wine resolves the registered class to
`C:\windows\system32\wintypes.dll`, but that module is absent from the
64-bit DLL farms. The call fails with `0x8007007e`, followed by an unhandled
C++ exception `0xe06d7363` and termination of the game's process.

Steam reports the game ended. The Wine desktop remains alive while the frame
count stops at 365, explaining why the app appears stuck on its last image.
The missing module is the concrete dependency failure preceding the exception;
the log does not establish that adding it resolves every later game requirement.

## Change

Build and include Wine's existing, unmodified `wintypes.dll` from the pinned
Wine source `c3d1cf8f8163281ce6227d9887aa90a1a4da9e26` for ARM64EC and native
ARM64. The bundled prefix already registers the activation class correctly,
and the app's existing farm-link refresh makes the DLL available after an
update without replacing the user's prefix. The existing i386 module is retained.

The builtin build helper now accepts `ARCH=arm64ec` (default), `aarch64` and
`i386`, with the corresponding compiler, build directory and destination.
Its default modules include `wintypes`:

```sh
bash build/wine-pe/build-modules.sh wintypes
ARCH=aarch64 bash build/wine-pe/build-modules.sh wintypes
```

No Wine source modification is required. The FEX, DXMT, D3D12, Dock and all
previous Windows runtime files remain byte-identical to the published r32 IPA.
Current native archives are reused byte-for-byte. Application/helper metadata
advances to build 18, with the `r33-winrt-input-startup` diagnostic marker.

## DLSS via MetalFX payload audit

The app contains the ARM64EC `nvngx.dll` and `nvapi64.dll` bridges, DXMT's
D3D11/DXGI/WineMetal frontends, and Madeira's D3D12/D3D12Core engine. NGX exports
the init, capability, scratch, create, evaluate, release and shutdown entry points
for D3D11 and D3D12. The D3D12 engine supplies the four
`MadeiraD3D12Temporal{Supported,Create,Record,Release}` exports NGX resolves.
Their imported DLLs are present in the farm; API sets use Wine's API-set schema.

The native app links `/System/Library/Frameworks/MetalFX.framework/MetalFX`,
provided by iOS, and includes the temporal-scaler implementation, Metal shader
resources and the D3D12 shader converter. No proprietary NVIDIA neural network
runtime or model is required by this replacement bridge.

Enable the game's **DLSS via MetalFX (experimental)** profile and choose DLSS
in the game itself. Existing restrictions remain: 64-bit local rendering, device
support for temporal MetalFX and supported texture/motion-vector formats. The
supplied Supermarket Together log has the DLSS profile disabled and does not
exercise reconstruction. Payload integrity and host ABI tests do not establish
actual game compatibility, image quality or a frame-rate improvement.

## Validation and distribution

`tests/test_wintypes_payload.py` inspects the registered activation class, module
exports, hybrid/native/32-bit PE architectures and import availability, with
negative fixtures for the missing module and COM dependency. Wine's ARM64EC
builtin header intentionally presents AMD64 compatibility; the test identifies
its hybrid architecture from load-config CHPE metadata.

`tests/test_dlss_payload.py` verifies both NGX backends, NVAPI, D3D12 temporal
exports and imported modules. On the final IPA it also verifies native MetalFX
linkage, temporal-scaler code and shader/converter resources. Existing host
tests cover NGX parameters, D3D11/D3D12 dispatch, temporal resource ownership,
profile application and failure paths without a real GPU or game.

All 118 host suites pass, including the existing 116 and both new payload checks.
Optimized Release, version 0.1.3, build 18. The release verifier compares against
the SHA-256-verified published r32 package and permits exactly two new DLLs;
previous Windows resources and Wine Mono remain intact. Public artifacts exclude
Microsoft VC runtime binaries and Apple signatures, preserve the JIT helper and
licence texts, and include matching external dSYMs and recursive corresponding
source. A separate personal IPA retains the owner's unmodified local VC runtime.

Physical-device acceptance remains pending: retest Supermarket Together startup
and, separately, DLSS creation/evaluation in a game that supports it. This release
removes the identified missing dependency; it does not claim confirmed gameplay.
