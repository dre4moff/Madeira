#!/usr/bin/env python3
"""Package and inspect the local 0.1.1 r17 iOS build without launching it."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import plistlib
import shutil
import struct
import subprocess
import zipfile

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--upstream', type=Path, required=True)
args = parser.parse_args()
dist = root / 'dist'
name = 'Madeira-0.1.1-VC-Runtime-DX11-MetalFX-unsigned-r17.ipa'
ipa = dist / name
staging = dist / 'r17-staging'
if staging.exists():
    shutil.rmtree(staging)
app = staging / 'Payload/Madeira.app'
app.parent.mkdir(parents=True)
subprocess.run(['ditto', str(root / '.build/Build/Products/Release-iphoneos/Madeira.app'), str(app)], check=True)
for path in [app / 'Madeira', app / 'd3d12/libmetalirconverter.dylib']:
    result = subprocess.run(['codesign', '--remove-signature', str(path)], capture_output=True, text=True)
    if result.returncode and 'not signed at all' not in result.stderr:
        raise RuntimeError(result.stderr)
for path in app.rglob('_CodeSignature'):
    if path.is_dir():
        shutil.rmtree(path)
for path in app.rglob('embedded.mobileprovision'):
    path.unlink()
info = plistlib.loads((app / 'Info.plist').read_bytes())
assert info['CFBundleShortVersionString'] == '0.1.1'
assert info['CFBundleVersion'] == '2'
assert info['CFBundleIdentifier'] == 'com.willfaust.madeora'
assert '0.1.1 r17' in info['MadeiraBuild']
subprocess.run(['ditto', '-c', '-k', '--keepParent', 'Payload', str(ipa)], cwd=staging, check=True)
spec = importlib.util.spec_from_file_location('resources', root / 'tests/test_ipa_resources.py')
resources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resources)
counts = resources.verify(args.upstream, ipa, root / 'app/Madeira')
machos = []
with zipfile.ZipFile(ipa) as archive:
    assert archive.testzip() is None
    assert all(n.startswith('Payload/') for n in archive.namelist())
    for path in archive.namelist():
        if path.endswith('/'):
            continue
        data = archive.read(path)
        if data[:4] != b'\xcf\xfa\xed\xfe':
            continue
        assert struct.unpack_from('<I', data, 4)[0] == 0x100000c, path
        count = struct.unpack_from('<I', data, 16)[0]
        position = 32
        for _ in range(count):
            command, size = struct.unpack_from('<II', data, position)
            assert command != 0x1d, f'Apple code signature: {path}'
            if command == 0x2c:
                assert struct.unpack_from('<I', data, position + 16)[0] == 0, path
            position += size
        machos.append(path)
    assert len(machos) == 2
    executable = archive.read('Payload/Madeira.app/Madeira')
    for marker in [b'[dlss-metalfx]', b'MADEIRA_GAME_METALFX_DLSS', b'[cache-cleanup]',
                   b'[rw-alias]', b'[shared-section]', b'MADEIRA_EXE_WINDOW_SMALL_FIXED',
                   b'AppData/LocalLow', b'[jit-debugger]', b'[device]', b'[jit-budget]',
                   b'[wmt-shared-port]', b'MADEIRA_RUNTIME_PROFILING', b'DXMT_IOS_CACHE_DIR', b'[perf-bottleneck]', b'[perf-work]', b'DXMT_RESOURCE_BATCH', b'MADEIRA_BOTTLENECK_STATS', b'[srv-poll-live]', b'[dock-auth-stall]', b'session-auth-step', b'[build-mode] native-optimization=on', b'DXMT_WAIT_ON_ADDRESS', b'DXMT_QUERY_POLL_YIELD']:
        assert marker in executable, marker
    assert b'[build-mode] native-optimization=off' not in executable
    d3d11 = archive.read('Payload/Madeira.app/arm64ec-windows/d3d11.dll')
    assert b'DXMT_QUERY_POLL_YIELD' in d3d11 and b'query_yield_max=' in d3d11
    wininet = archive.read('Payload/Madeira.app/arm64ec-windows/wininet.dll')
    assert b'[wininet-index] grew' in wininet and b'[cache-full]' not in wininet
    runtimes = list((root / 'app/Madeira/x86_64-vcruntime').glob('*.dll'))
    assert len(runtimes) == 12
    for path in runtimes:
        data = archive.read('Payload/Madeira.app/x86_64-vcruntime/' + path.name)
        assert data == (root / 'toolchains/vcruntime-x64' / (path.name + '_amd64')).read_bytes()

sha = hashlib.sha256(ipa.read_bytes()).hexdigest()
Path(str(ipa) + '.sha256').write_text(sha + '  ' + name + '\n')
report = {
    'ipa': name, 'version': '0.1.1', 'build': '2', 'local_build': 'r17', 'configuration': 'Release', 'native_optimization': '-O2', 'swift_optimization': '-O',
    'bytes': ipa.stat().st_size, 'sha256': sha,
    'upstream_tag': 'v0.1.1', 'upstream_commit': subprocess.check_output(['git', 'rev-parse', 'v0.1.1'], cwd=root).decode().strip(),
    'upstream_ipa_sha256': resources.UPSTREAM_SHA256,
    'byte_identical_upstream_farm_files': sum(counts.values()),
    'verified_rebuilt_farm_files': 6, 'added_nvext_modules': 2,
    'byte_identical_microsoft_x64_runtime_dlls': 12, 'unsigned_arm64_macho_files': machos,
    'native_archives': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (root / 'app/Madeira').glob('*.a')},
    'validation': 'Synthetic tests, unsigned iOS compilation, IPA version, runtime resource identity, linked fix markers and Apple signature inspection only. No app/game/device/simulator/GPU execution.',
    'limitations': 'The supplied r16 log and user comparison show no sustained gain. r17 fixes ARM64EC WinINet index growth and reuses its mapped view; no device FPS gain has been measured. CPU/GPU samples do not establish a sole bottleneck. The experimental MetalFX DLSS bridges for D3D11 and Madeira D3D12 remain unchanged; no NGX evaluation appears in the supplied run. No frame generation or module signature bypass.',
}
(dist / 'verification-r17.json').write_text(json.dumps(report, indent=2) + '\n')
for source in ['UPSTREAM_0_1_1.md', 'VC_RUNTIME_SWITCH.md', 'R13_DLSS_PERFORMANCE.md', 'R14_STEAM_AUTH.md', 'R15_PERFORMANCE.md', 'R16_PERFORMANCE.md', 'R17_PERFORMANCE.md']:
    shutil.copyfile(root / 'docs' / source, dist / ('r17-' + source))
patch = subprocess.check_output(['git', 'diff', '--binary', 'v0.1.1', '--', 'app', 'build', 'docs', 'tests', 'madeira-d3d12', '.gitignore'], cwd=root)
(dist / 'Madeira-local-v0.1.1-r17.patch').write_bytes(patch)
for directory, filename, new_files in [
    ('dxmt', 'Madeira-DXMT-r17.patch', ['src/dxmt/dxmt_texture_upload.hpp', 'src/util/util_metalfx_profile.hpp', 'include/madeira_dlss_abi.h', 'src/nvngx/nvngx_d3d12.hpp', 'src/winemetal/unix/wmt_resource_batch.h']),
    ('FEX', 'Madeira-FEX-r17.patch', []), ('wine', 'Madeira-Wine-r17.patch', []),
    ('madeira-dock', 'Madeira-Dock-r17.patch', []),
]:
    patch = subprocess.check_output(['git', 'diff', '--binary', 'HEAD'], cwd=root / directory)
    for relative in new_files:
        result = subprocess.run(['git', 'diff', '--no-index', '--binary', '/dev/null', relative], cwd=root / directory, capture_output=True)
        assert result.returncode in (0, 1)
        patch += result.stdout
    (dist / filename).write_bytes(patch)
shutil.rmtree(staging)
print(json.dumps({'ipa': str(ipa), 'bytes': report['bytes'], 'sha256': sha}, indent=2))
