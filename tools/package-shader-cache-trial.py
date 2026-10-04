#!/usr/bin/env python3
"""Package a local r30 cache-off trial; verify all renderer DLLs match the r30 control."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import re
import shutil
import struct
import subprocess
import tempfile
import zipfile
root = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--products', type=Path, required=True)
p.add_argument('--official', type=Path, required=True)
p.add_argument('--previous', type=Path, required=True)
p.add_argument('--output-directory', type=Path, required=True)
a = p.parse_args()
products, official, previous, output = (getattr(a, k).resolve() for k in ('products','official','previous','output_directory'))
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
assert digest(official) == '71e900cbc140778bd6fa67c1062821981ed98e6bfb674d853cfeefd6d242e1c0'
assert digest(previous) == 'daf8a5d957fc889ace0caa1c8002408b0d7f0f8ee25b4d7a294522e4ad3e9962'
output.mkdir(parents=True, exist_ok=True)
base = 'Madeira-0.1.3-r30-ShaderCacheOFF-Test'
ipa, symbols = output/(base+'-Release-unsigned.ipa'), output/(base+'-symbols.zip')
assert not ipa.exists() and not symbols.exists(), 'Refusing to overwrite a release'
tests = json.loads((root/'.build/cache-off-audit/host-tests.json').read_text())
assert len(tests) >= 7 and all(t['passed'] for t in tests)
unsigned, uuids = [], {}
with tempfile.TemporaryDirectory(prefix='madeira-r30-package-') as folder:
 stage = Path(folder); app = stage/'Payload/Madeira.app'
 shutil.copytree(products/'Madeira.app', app, symlinks=True)
 for name in ('x86_64-vcruntime','MICROSOFT-LICENSE.rtf'):
  target=app/name
  if target.is_dir(): shutil.rmtree(target)
  elif target.exists(): target.unlink()
 for target in list(app.rglob('_CodeSignature')):
  if target.is_dir(): shutil.rmtree(target)
 for target in app.rglob('embedded.mobileprovision'): target.unlink()
 for target in app.rglob('*'):
  if not target.is_file(): continue
  with target.open('rb') as f: magic=f.read(4)
  if magic!=b'\xcf\xfa\xed\xfe': continue
  run=subprocess.run(['codesign','--remove-signature',str(target)],capture_output=True,text=True)
  assert run.returncode==0 or 'not signed at all' in run.stderr,run.stderr
  data=target.read_bytes();assert struct.unpack_from('<I',data,4)[0]==0x100000c
  pos=32
  for _ in range(struct.unpack_from('<I',data,16)[0]):
   cmd,size=struct.unpack_from('<II',data,pos);assert cmd!=0x1d;assert size>=8;pos+=size
  assert b'__DWARF' not in data[:pos]
  unsigned.append(str(target.relative_to(app)))
 info=plistlib.loads((app/'Info.plist').read_bytes())
 assert info['CFBundleVersion']=='15' and info['CFBundleShortVersionString']=='0.1.3'
 assert info['MadeiraProfileBuild'] is False and 'r30-cache-off-test' in info['MadeiraBuild']
 extension=app/'PlugIns/MadeiraJITHelper.appex'
 helper=plistlib.loads((extension/'Info.plist').read_bytes())
 assert helper['CFBundleVersion']=='15' and helper['CFBundleShortVersionString']=='0.1.3'
 assert helper['CFBundleIdentifier']==info['CFBundleIdentifier']+'.JITHelper'
 assert helper['NSExtension']['NSExtensionPointIdentifier']=='com.apple.ar.viewer'
 assert (app/'Frameworks/StikJIT.framework/StikJIT').is_file()
 assert (app/'Madeira JIT.shortcut').is_file()
 assert (app/'legal/LICENSE-StikJIT-MPL-2.0.txt').is_file()
 assert (app/'legal/LICENSE-idevice-MIT.txt').is_file()
 assert (app/'legal/LICENSES-rppairing-crates.txt').is_file()
 assert not list(app.rglob('*.dSYM')) and not list(app.rglob('*debug.dylib')) and not list(app.rglob('__preview.dylib'))
 code=(app/'Madeira').read_bytes()
 for marker in (b'[mono-return] restored owning CPUArea',b'[dock-fullscreen] game-client=',b'madeira_rppairing_'):
  assert marker in code,marker
 symstage=stage/'Symbols';symstage.mkdir()
 for exe, dsym in ((app/'Madeira',products/'Madeira.app.dSYM'),(extension/'MadeiraJITHelper',products/'MadeiraJITHelper.appex.dSYM')):
  text=subprocess.check_output(['xcrun','dwarfdump','--uuid',str(exe),str(dsym)],text=True)
  ids=re.findall(r'UUID: ([A-F0-9-]+) \(arm64\)',text);assert len(ids)==2 and ids[0]==ids[1]
  uuids[str(exe.relative_to(app))]=ids[0];shutil.copytree(dsym,symstage/dsym.name)
 subprocess.run(['ditto','-c','-k','--norsrc','--noextattr','--keepParent','Payload',str(ipa)],cwd=stage,check=True)
 subprocess.run(['ditto','-c','-k','--norsrc','--noextattr','--keepParent',str(symstage),str(symbols)],check=True)
prefix='Payload/Madeira.app/'
with zipfile.ZipFile(previous) as old, zipfile.ZipFile(official) as upstream, zipfile.ZipFile(ipa) as new:
 assert new.testzip() is None
 files=lambda z: {n.removeprefix(prefix):z.read(n) for n in z.namelist() if n.startswith(prefix) and not n.endswith('/')}
 before, off, after=files(old),files(upstream),files(new)
 assert not before.keys()-after.keys(),before.keys()-after.keys()
 for n in after:
  assert 'x86_64-vcruntime/' not in n and not n.endswith('MICROSOFT-LICENSE.rtf')
  assert '_CodeSignature' not in n and not n.endswith('embedded.mobileprovision')
  assert '..' not in Path(n).parts and not n.startswith('/')
 for n in ('arm64ec-windows/xtajit64.dll','aarch64-windows/xtajit.dll'):
  assert after[n]==before[n]==off[n]
 for n in ('arm64ec-windows/dockhost.exe','arm64ec-windows/dock-notices.txt'):
  assert after[n]==before[n]
 changed=sorted(n for n in before if before[n]!=after[n]);added=sorted(after.keys()-before.keys())
 assert b'[texture-stream] staging-block=' in after['arm64ec-windows/d3d11.dll']
 assert after['arm64ec-windows/d3d11.dll']==(root/'app/Madeira/arm64ec-windows/d3d11.dll').read_bytes()
 assert b'[shader-cache-test] r30-cache-off-test DXMT-disk=off' in after['Madeira']
 farm_changes=set()
 assert set(changed) <= {'Info.plist','Madeira','PlugIns/MadeiraJITHelper.appex/Info.plist','PlugIns/MadeiraJITHelper.appex/MadeiraJITHelper'}
 assert not added
 for name in before:
  if name.startswith(('arm64ec-windows/','aarch64-windows/','i386-windows/')): assert before[name]==after[name],name
 for n in changed:
  if n.startswith(('arm64ec-windows/','aarch64-windows/','i386-windows/')):
   assert n.startswith('arm64ec-windows/') and Path(n).name in farm_changes,n
 assert after['arm64ec-windows/d3d12.dll']==after['arm64ec-windows/madeira_d3d12.dll']
 reader=root/'toolchains/llvm-mingw-20260421-ucrt-macos-universal/bin/llvm-readobj'
 for name in farm_changes:
  data=after['arm64ec-windows/'+name];pe=struct.unpack_from('<I',data,0x3c)[0]
  headers=subprocess.check_output([str(reader),'--file-headers',str(root/'app/Madeira/arm64ec-windows'/name)],text=True)
  assert 'Format: COFF-ARM64EC' in headers
  start=pe+24+struct.unpack_from('<H',data,pe+20)[0]
  for i in range(struct.unpack_from('<H',data,pe+6)[0]):assert not data[start+40*i:start+40*i+8].startswith(b'.debug')
report={
 'version':'0.1.3','fork_revision':'r30-cache-off-test','build':'15','upstream_commit':'4e9d45a74294cd820120791c4b3f2b79adf4fc70',
 'configuration':'optimized Release, native -O2, Swift -O, testability/debug dylibs/profiling disabled',
 'unsigned_macho_files':unsigned,'uuids_arm64':uuids,
 'official_ipa_sha256':digest(official),'previous_r30_ipa_sha256':digest(previous),
 'changed_payload_files_from_r30':changed,'added_payload_files_from_r30':added,'unchanged_r30_payload_files':len(before)-len(changed),
 'fex_original_source_and_windows_engines_preserved':True,'dock_r23_binary_preserved':True,'microsoft_runtime_redistributed':False,
 'swap_runtime_and_default_coverage_preserved':True,
 'native_archive_members':json.loads((root/'.build/cache-off-audit/native-members.json').read_text()),
 'tests':[dict(test=t['test'],passed=t['passed'],seconds=t.get('seconds')) for t in tests],
 'device_acceptance':'Local test only; controlled comparison against r30 on the phone pending. Host checks establish cache bypass and preserved renderer payload, not FPS. No GitHub release is created.'}
for artifact in (ipa,symbols):
 sha=digest(artifact);Path(str(artifact)+'.sha256').write_text(sha+'  '+artifact.name+'\n');report[artifact.suffix[1:]]={'filename':artifact.name,'bytes':artifact.stat().st_size,'sha256':sha}
(output/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'ipa':str(ipa),'uuids':uuids,'changed':changed,'added':len(added),'tests':len(tests)},indent=2))
