# r22: audio device discovery crash during asset loading

## What the supplied r21 log establishes

MECCHA CHAMELEON (`PenguinHotel-Win64-Shipping.exe`) passes the mesh pipeline
failure corrected in r21. It converts shaders and presents its loading screen.
The first relevant guest exception occurs on `FAsyncLoadingThread`, immediately
after Wine reports `com_get_class_object apartment not initialised`.
The HRESULT is `0x800401F0` (`CO_E_NOTINITIALIZED`), followed by a null-pointer
read at module RVA `0x654a474`. Later crash-handler exceptions and continuing
shader compilation are consequences of this first failure, not proof of a JIT
or GPU failure. The last loading frame can remain visible after the guest fails.

Read-only inspection of the locally installed executable identified the call
preceding the null dereference. Its CLSID is
`{BCDE0395-E52F-467C-8E3D-C4579291692E}` (MMDeviceEnumerator), its IID is
`{A95664D2-9614-4F35-A746-DE8DB63617E6}` (IMMDeviceEnumerator), and its class
context is `CLSCTX_INPROC_SERVER`. The constructor ignores the result of
`CoCreateInstance` and immediately calls through the null interface. No game
files were patched; the executable and private phone records are not included
in source or release assets.

Microsoft describes [MMDeviceEnumerator as the audio endpoint discovery entry
point](https://learn.microsoft.com/en-us/windows/win32/coreaudio/mmdevice-api).
[Normal COM initialization is per thread](https://learn.microsoft.com/en-us/windows/win32/learnwin32/initializing-the-com-library).
This is a narrowly enabled game compatibility workaround, not a claim that
Wine's standard rejection of an uninitialized caller is incorrect.

## Correction

The launcher defaults `MADEIRA_MMDEVICE_IMPLICIT_MTA` to `1`, without overwriting
an existing environment/config override. In Wine's ARM64EC `combase.dll`, the
normal apartment lookup runs first. Only if there is no explicit apartment or
existing implicit MTA, the requested class is exactly MMDeviceEnumerator, the
context includes an in-process server, and the policy is exactly `1`, the
compatibility path retains an implicit MTA using Wine's existing thread-local
`implicit_mta_cookie`.

The real class factory, audio endpoint enumeration, interface validation and
COM failures still run normally. No successful HRESULT or fake audio interface
is substituted. Existing STA/MTA callers and unrelated classes bypass the
workaround. The worker's explicit initialization count and apartment field are
not changed. Existing Wine thread-detach and explicit apartment teardown paths
release the same cookie. Concurrent requests use Wine's apartment lock and
reference counting; the MTA is not an unbounded process-wide leak. Allocation
failure remains a failure, with a null object; an existing unchecked MTA
allocation is also guarded before its cookie is linked.

The narrow path logs `[madeira-audio-com] MMDeviceEnumerator implicit MTA
retained until worker teardown` when it actually allocates a cookie, not every
frame. Healthy initialized callers perform the same apartment lookup as before.
It applies to audio discovery through this ARM64EC COM path with either DX11 or
DX12; it is not a graphics-engine or FEX change. Other games with this same
missing-apartment/audio-enumerator failure may benefit, but are not tested here.

To disable the compatibility path for comparison, add this to `madeira.cfg` and
restart the app:

```ini
env.MADEIRA_MMDEVICE_IMPLICIT_MTA = 0
```

## Microphone limitation

The existing native iOS backend (`build/ntdll-unix/audio_null_ios.c`) currently
returns zero endpoints for capture. Its microphone methods are placeholders,
and the app activates a playback AVAudioSession. Consequently, fixing COM
discovery does **not** implement microphone recording or voice chat. Those need
a separate native capture path, iOS permission handling, appropriate session
routing and real device validation. r22 deliberately preserves current audio
output behavior rather than advertising a nonfunctional input device.

## Validation, packaging and next test

- Host ASan/UBSan test executes the production helper and MTA cookie allocation/
  release functions with controlled platform boundaries: exact CLSID/context/
  policy, initialized callers, repeated calls, allocation/TLS failure and retry,
  sixteen concurrent workers, unchanged init count and balanced resources.
- Existing regression suites cover protected shader caches, disabled JIT dumps,
  original FEX, DX11, native VC runtime, controllers and mesh depth selection.
- ARM64EC combase is compiled with `-O2`, then debug sections are stripped.
- App is unsigned optimized **Release**, build 6. App symbols stay in a separate
  dSYM archive; Debug helpers, testability and profiling phase controls are off.
- The package verifies byte-for-byte preservation of every r21 public payload
  resource except the app executable, Info.plist and ARM64EC combase.dll.
  Both D3D12 DLLs, DXMT, native audio/ntdll, Dock and original FEX stay identical.

No synthetic test proves that the full game will reach its menu or that FPS
will improve. This addresses the precisely identified crash; other blockers may
surface next. Update with the same signing identity/bundle ID, without
uninstalling, restart Madeira, keep Native VC++ Runtime enabled when needed,
and retain warm shader caches. For a DX12 attempt leave Force DirectX 11 off.
If the loading screen still stays visible, export a fresh log after the attempt.
The policy marker and activation line distinguish the new build's behavior.

## Rebuild

Run `build/wine-pe/build-combase.sh`, then build the app with the Release command
in [FORK_RELEASE.md](FORK_RELEASE.md), build 6. Only combase must be rebuilt for
this correction; do not rebuild/replace original FEX engines. Run
`python3 tests/test_audio_com_compat.py` for the isolated synthetic test.
`tools/package-r22-release.py` packages against the SHA-pinned public r21 IPA.
The personal runtime helper adds only your locally supplied unmodified Microsoft
DLLs and terms; those are never included in the public package.
