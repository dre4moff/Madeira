#!/usr/bin/env python3
"""Archive committed sources and recursive source dependencies at exact pins."""
import argparse
import io
import json
from pathlib import Path
import shutil
import stat
import subprocess
import tarfile
import zipfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--prefix', default='Madeira-r38')
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
modules = []
optional_binaries = {'External/fex-posixtest-bins', 'External/fex-gvisor-tests-bins', 'External/fex-gcc-target-tests-bins'}

def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args])

def archive(repo, revision, prefix, target):
    process = subprocess.Popen(['git', '-C', str(repo), 'archive', '--format=tar', revision], stdout=subprocess.PIPE)
    with tarfile.open(fileobj=process.stdout, mode='r|') as source:
        for entry in source:
            if not (entry.isfile() or entry.issym()):
                continue
            assert '..' not in Path(entry.name).parts and not entry.name.startswith('/')
            name = prefix + '/' + entry.name
            info = zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = ((stat.S_IFLNK if entry.issym() else stat.S_IFREG) | entry.mode) << 16
            if entry.issym():
                target.writestr(info, entry.linkname)
            else:
                with source.extractfile(entry) as original, target.open(info, 'w', force_zip64=True) as destination:
                    shutil.copyfileobj(original, destination)
    assert process.wait() == 0
    for record in git(repo, 'ls-tree', '-rz', revision).split(b'\0'):
        if not record:
            continue
        meta, path = record.split(b'\t', 1)
        mode, kind, commit = meta.decode().split()
        if mode != '160000':
            continue
        name = path.decode()
        relative = str((repo / name).relative_to(root))
        row = {'path': relative, 'commit': commit, 'included': name not in optional_binaries}
        modules.append(row)
        if not row['included']:
            row['reason'] = 'Optional precompiled upstream test binaries; not runtime/source dependencies.'
            continue
        assert (repo / name / '.git').exists(), 'Missing source submodule: ' + relative
        archive(repo / name, commit, prefix + '/' + name, target)

a.output.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(a.output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as target:
    revision = git(root, 'rev-parse', 'HEAD').decode().strip()
    archive(root, revision, a.prefix, target)
    target.writestr(a.prefix + '/SUBMODULES.json', json.dumps(modules, indent=2) + '\n')
    target.writestr(a.prefix + '/SOURCE_README.txt',
        'Root commit: ' + revision + '\nAll tracked sources and recursive source dependencies are included at their exact pins.\n'
        'Optional precompiled FEX test suites are represented by their original pins. No runtime feature is omitted.\n'
        'Wine Mono corresponding source is supplied as wine-mono-11.0.0-src.tar.xz alongside this archive.\n'
        'See docs/BUILDING.md and docs/R38_SHARED_CA_ROOTS.md for the verified build and validation.\n')
with zipfile.ZipFile(a.output) as target:
    assert target.testzip() is None
print(json.dumps({'file': str(a.output), 'root_commit': revision, 'modules': len(modules), 'bytes': a.output.stat().st_size}))
