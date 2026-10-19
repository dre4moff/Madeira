#!/usr/bin/env python3
"""Package r39 and verify its unsigned code, runtime resources and symbols."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'Payload/Madeira.app/'
FARMS = ('arm64ec-windows', 'aarch64-windows', 'i386-windows')
BASE = 'Madeira-0.1.3-Fork-r39'
UPSTREAM = '279fd0f83170425db002fe25d6bd62f6355f497d'

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()

def payload(path):
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        assert len(z.namelist()) == len(set(z.namelist()))
        return {n[len(PREFIX):]: z.read(n) for n in z.namelist()
                if n.startswith(PREFIX) and not n.endswith('/')}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--products', type=Path, required=True)
    p.add_argument('--previous', type=Path, required=True)
    p.add_argument('--output-directory', type=Path, required=True)
    a = p.parse_args()
    products, previous, output = a.products.resolve(), a.previous.resolve(), a.output_directory.resolve()
    audit = ROOT / '.build/r39-audit'
    assert digest(previous) == 'ebe277effbb7bf572e5691cdfe7062572bd523520fcd45fd536c24ffe34e7ae1'
    assert '** BUILD SUCCEEDED **' in (audit / 'xcode-release-final.log').read_text()
    tests = json.loads((audit / 'host-tests.json').read_text())
    assert sum(t['passed'] is True for t in tests) >= 198
    assert all(t['passed'] is True or t.get('skipped') for t in tests)
    for source in ('ntdll-native.log', 'dxmt-native.log'):
        assert '0 failed' in (audit / source).read_text(), source
    for pin, path in ((UPSTREAM, '.'),
                      ('9129e9684daaeae70da9435e7c6060e59392634e', 'wine'),
                      ('128b297c6e9a00014408dc68b4c2c2373b5813de', 'dxmt')):
        subprocess.run(['git', '-C', str(ROOT / path), 'merge-base', '--is-ancestor', pin, 'HEAD'], check=True)
    fex = git('-C', 'FEX', 'rev-parse', 'HEAD')
    assert fex == 'f59cab95659e8add0c88f0c76ec1cf483c536dbf'
    assert not git('-C', 'FEX', 'status', '--porcelain', '--untracked-files=no')
    output.mkdir(parents=True, exist_ok=True)
    ipa, symbols = output / (BASE + '-Release-unsigned.ipa'), output / (BASE + '-symbols.zip')
    assert not ipa.exists() and not symbols.exists(), 'Refusing to overwrite release files'
    unsigned, uuids = [], {}
    with tempfile.TemporaryDirectory(prefix='madeira-r39-package-') as temporary:
        stage = Path(temporary)
        app = stage / 'Payload/Madeira.app'
        shutil.copytree(products / 'Madeira.app', app, symlinks=True)
        for name in ('x86_64-vcruntime', 'MICROSOFT-LICENSE.rtf'):
            target = app / name
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
        for target in app.rglob('_CodeSignature'):
            if target.is_dir():
                shutil.rmtree(target)
        for target in app.rglob('embedded.mobileprovision'):
            target.unlink()
        for target in app.rglob('*'):
            if not target.is_file():
                continue
            with target.open('rb') as source:
                magic = source.read(4)
            if magic != b'\xcf\xfa\xed\xfe':
                continue
            r = subprocess.run(['codesign', '--remove-signature', str(target)], capture_output=True, text=True)
            assert r.returncode == 0 or 'not signed at all' in r.stderr, r.stderr
            data = target.read_bytes()
            assert struct.unpack_from('<I', data, 4)[0] == 0x100000c, target
            offset = 32
            for _ in range(struct.unpack_from('<I', data, 16)[0]):
                command, length = struct.unpack_from('<II', data, offset)
                assert command != 0x1d and length >= 8
                offset += length
            assert b'__DWARF' not in data[:offset]
            unsigned.append(str(target.relative_to(app)))
        info = plistlib.loads((app / 'Info.plist').read_bytes())
        assert info['CFBundleVersion'] == '24' and info['CFBundleShortVersionString'] == '0.1.3'
        assert info['MadeiraProfileBuild'] is False and 'r39 /' in info['MadeiraBuild']
        extension = app / 'PlugIns/MadeiraJITHelper.appex'
        helper = plistlib.loads((extension / 'Info.plist').read_bytes())
        assert helper['CFBundleVersion'] == '24'
        assert helper['CFBundleIdentifier'] == info['CFBundleIdentifier'] + '.JITHelper'
        assert helper['NSExtension']['NSExtensionPointIdentifier'] == 'com.apple.ar.viewer'
        for relative in ('Frameworks/StikJIT.framework/StikJIT', 'Madeira JIT.shortcut',
                         'legal/LICENSE-StikJIT-MPL-2.0.txt', 'legal/LICENSE-idevice-MIT.txt',
                         'legal/LICENSES-rppairing-crates.txt'):
            assert (app / relative).is_file(), relative
        assert not list(app.rglob('*.dSYM')) and not list(app.rglob('*debug.dylib'))
        symstage = stage / 'Symbols'
        symstage.mkdir()
        for exe, dsym in ((app / 'Madeira', products / 'Madeira.app.dSYM'),
                          (extension / 'MadeiraJITHelper', products / 'MadeiraJITHelper.appex.dSYM')):
            text = subprocess.check_output(['xcrun', 'dwarfdump', '--uuid', str(exe), str(dsym)], text=True)
            ids = re.findall(r'UUID: ([A-F0-9-]+) \(arm64\)', text)
            assert len(ids) == 2 and ids[0] == ids[1]
            uuids[str(exe.relative_to(app))] = ids[0]
            shutil.copytree(dsym, symstage / dsym.name)
        subprocess.run(['ditto', '-c', '-k', '--norsrc', '--noextattr', '--keepParent', 'Payload', str(ipa)], cwd=stage, check=True)
        subprocess.run(['ditto', '-c', '-k', '--norsrc', '--noextattr', '--keepParent', str(symstage), str(symbols)], check=True)
    before, after = payload(previous), payload(ipa)
    assert not before.keys() - after.keys(), sorted(before.keys() - after.keys())
    for name in after:
        assert 'x86_64-vcruntime/' not in name and not name.endswith('MICROSOFT-LICENSE.rtf')
        assert '_CodeSignature' not in name and not name.endswith('embedded.mobileprovision')
        assert '..' not in Path(name).parts and not name.startswith('/')
    farm_counts = {}
    for farm in FARMS:
        source = ROOT / 'app/Madeira' / farm
        files = [p for p in source.iterdir() if p.is_file()]
        assert files, farm
        farm_counts[farm] = len(files)
        for path in files:
            assert after[farm + '/' + path.name] == path.read_bytes(), path.name
    original_runtime = [name.removeprefix('app/Madeira/') for name in
                        git('ls-tree', '-r', '--name-only', UPSTREAM, '--', 'app/Madeira').splitlines()
                        if name.removeprefix('app/Madeira/').split('/')[0] in FARMS]
    assert original_runtime and not set(original_runtime) - after.keys()
    for name in ('arm64ec-windows/xtajit64.dll', 'aarch64-windows/xtajit.dll'):
        pristine = subprocess.check_output(['git', 'show', UPSTREAM + ':app/Madeira/' + name], cwd=ROOT)
        assert after[name] == pristine, 'FEX Windows engine differs from original: ' + name
    assert hashlib.sha256(after['wine-mono/lib/mono/4.5/mscorlib.dll']).hexdigest() == 'cfc4fb50c0e4f93d6e2c5fd827e2d7b3f215d3b183df024db68d6784c5388bc6'
    assert after['wine-mono/COPYING'] == (ROOT / 'build/wine-mono/COPYING').read_bytes()
    assert after['arm64ec-windows/d3d12.dll'] == after['arm64ec-windows/madeira_d3d12.dll']
    assert git('-C', 'madeira-dock', 'rev-parse', 'HEAD').encode() in after['arm64ec-windows/dock-notices.txt']
    for name in ('test_qwave_payload.py', 'test_wintypes_payload.py', 'test_dlss_payload.py'):
        subprocess.run([sys.executable, str(ROOT / 'tests' / name), str(ipa)], check=True)
    report = {
        'version': '0.1.3', 'fork_revision': 'r39', 'build': '24',
        'source_commit': git('rev-parse', 'HEAD'), 'upstream_commit': UPSTREAM,
        'configuration': 'optimized Release; native -O2, Swift whole-module -O; no testability, profiling build or debug dylibs',
        'unsigned_macho_files': unsigned, 'uuids_arm64': uuids,
        'previous_r38_ipa_sha256': digest(previous),
        'changed_payload_files_from_r38': sorted(n for n in before if before[n] != after[n]),
        'added_payload_files_from_r38': sorted(after.keys() - before.keys()),
        'runtime_farm_counts': farm_counts,
        'all_original_upstream_runtime_resources_present': True,
        'fex_original_source_and_windows_engines_preserved': True,
        'microsoft_runtime_redistributed': False,
        'host_suites_passed': sum(t['passed'] is True for t in tests),
        'host_suites_skipped': [t for t in tests if t.get('skipped')],
        'native_archives': [{'path': str(p.relative_to(ROOT)), 'sha256': digest(p)}
                            for p in sorted((ROOT / 'app/Madeira').glob('lib*.a'))],
        'component_pins': {m: git('-C', m, 'rev-parse', 'HEAD') for m in ('wine', 'dxmt', 'FEX', 'madeira-dock')},
        'device_acceptance': 'Not performed: iPhone startup, rendering, FPS, thermals, JIT pairing, Steam authentication and multiplayer.'
    }
    for artifact in (ipa, symbols):
        sha = digest(artifact)
        Path(str(artifact) + '.sha256').write_text(sha + '  ' + artifact.name + '\n')
        report[artifact.suffix[1:]] = {'filename': artifact.name, 'bytes': artifact.stat().st_size, 'sha256': sha}
    (output / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'ipa': str(ipa), 'runtime_farms': farm_counts, 'host_suites': report['host_suites_passed']}, indent=2))

if __name__ == '__main__':
    main()
