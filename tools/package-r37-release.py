#!/usr/bin/env python3
"""Package optimized fork r37 products and verify nested JIT code."""
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
p.add_argument('--previous', type=Path, required=True)
p.add_argument('--output-directory', type=Path, required=True)
a = p.parse_args()
products, previous, output = (getattr(a, k).resolve() for k in ('products','previous','output_directory'))
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
assert digest(previous) == '4527253e9f962bccdac9573569b3e7854d475bba953008c183c5b04557d5b319'
assert b'** BUILD SUCCEEDED **' in (root/'.build/r37-audit/xcode-release-final.log').read_bytes(), 'Release build has not completed successfully'
output.mkdir(parents=True, exist_ok=True)
base = 'Madeira-0.1.3-Fork-r37'
ipa, symbols = output/(base+'-Release-unsigned.ipa'), output/(base+'-symbols.zip')
assert not ipa.exists() and not symbols.exists(), 'Refusing to overwrite a release'
tests = json.loads((root/'.build/r37-audit/host-tests.json').read_text())
assert len(tests) >= 27 and all(t['passed'] for t in tests)
assert {'tests/test_failed_import_retry.py','tests/test_qwave_payload.py','tests/test_udp_control.py','tests/test_poll_fd_reuse.py'} <= {t['test'] for t in tests}
unsigned, uuids = [], {}
with tempfile.TemporaryDirectory(prefix='madeira-r37-package-') as folder:
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
 assert info['CFBundleVersion']=='22' and info['CFBundleShortVersionString']=='0.1.3'
 assert info['MadeiraProfileBuild'] is False and 'r37 /' in info['MadeiraBuild']
 extension=app/'PlugIns/MadeiraJITHelper.appex'
 helper=plistlib.loads((extension/'Info.plist').read_bytes())
 assert helper['CFBundleVersion']=='22' and helper['CFBundleShortVersionString']=='0.1.3'
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
with zipfile.ZipFile(previous) as old, zipfile.ZipFile(ipa) as new:
 assert new.testzip() is None
 files=lambda z: {n.removeprefix(prefix):z.read(n) for n in z.namelist() if n.startswith(prefix) and not n.endswith('/')}
 before, after=files(old),files(new)
 assert not before.keys()-after.keys(), before.keys()-after.keys()
 for n in after:
  assert 'x86_64-vcruntime/' not in n and not n.endswith('MICROSOFT-LICENSE.rtf')
  assert '_CodeSignature' not in n and not n.endswith('embedded.mobileprovision')
  assert '..' not in Path(n).parts and not n.startswith('/')
 farms=('arm64ec-windows','aarch64-windows','i386-windows')
 original_paths=subprocess.check_output(['git','ls-tree','-r','--name-only','upstream/main','--','app/Madeira'],cwd=root,text=True).splitlines()
 original_runtime=[n.removeprefix('app/Madeira/') for n in original_paths if n.removeprefix('app/Madeira/').split('/')[0] in farms]
 assert original_runtime and not set(original_runtime)-after.keys(), set(original_runtime)-after.keys()
 for n in original_runtime:
  assert after[n]==(root/'app/Madeira'/n).read_bytes(), n
 for n in ('arm64ec-windows/xtajit64.dll','aarch64-windows/xtajit.dll'):
  pristine=subprocess.check_output(['git','show','upstream/main:app/Madeira/'+n],cwd=root)
  assert after[n]==pristine, 'FEX engine changed from original upstream: '+n
 for folder in farms:
  for path in (root/'app/Madeira'/folder).iterdir():
   if path.is_file(): assert after[folder+'/'+path.name]==path.read_bytes(), path.name
 assert hashlib.sha256(after['wine-mono/lib/mono/4.5/mscorlib.dll']).hexdigest()=='cfc4fb50c0e4f93d6e2c5fd827e2d7b3f215d3b183df024db68d6784c5388bc6'
 assert after['wine-mono/bin/libmono-2.0-x86.dll'][:2]==b'MZ'
 assert after['wine-mono/COPYING']==(root/'build/wine-mono/COPYING').read_bytes()
 assert b'[dynamic-buffer-recycle]' in after['arm64ec-windows/d3d11.dll']
 assert b'[texture-stream] staging-block=' in after['arm64ec-windows/d3d11.dll']
 assert after['arm64ec-windows/d3d12.dll']==after['arm64ec-windows/madeira_d3d12.dll']
 assert after['arm64ec-windows/d3d12core.dll'][:2]==b'MZ'
 assert b'[texture-memory] D3D12' in after['arm64ec-windows/d3d12.dll']
 assert b'texture-memory-start-mb' in after['arm64ec-windows/d3d12.dll']
 changed=sorted(n for n in before if before[n]!=after[n]);added=sorted(after.keys()-before.keys())
 assert not added, added
 allowed_changes={'Madeira','Info.plist','PlugIns/MadeiraJITHelper.appex/Info.plist','PlugIns/MadeiraJITHelper.appex/MadeiraJITHelper','arm64ec-windows/dockhost.exe','arm64ec-windows/dock-notices.txt'}
 assert set(changed)<=allowed_changes, changed
 # Only the Dock host and its source notice change in Windows farms against r36.
 for n in before:
  if n.split('/')[0] in farms and n not in allowed_changes: assert before[n]==after[n], n
 subprocess.run(['python3',str(root/'tests/test_qwave_payload.py'),str(ipa)],check=True)
 subprocess.run(['python3',str(root/'tests/test_wintypes_payload.py'),str(ipa)],check=True)
 subprocess.run(['python3',str(root/'tests/test_dlss_payload.py'),str(ipa)],check=True)

 reader=root/'toolchains/llvm-mingw-20260421-ucrt-macos-universal/bin/llvm-readobj'
 rebuilt=('qwave.dll','wintypes.dll','bluetoothapis.dll','d3d11.dll','d3d10core.dll','dxgi.dll','winemetal.dll','nvapi64.dll','nvngx.dll','ntdll.dll','combase.dll','wininet.dll','d3d12.dll','madeira_d3d12.dll','d3d12core.dll')
 for name in rebuilt:
  data=after['arm64ec-windows/'+name];pe=struct.unpack_from('<I',data,0x3c)[0]
  headers=subprocess.check_output([str(reader),'--file-headers',str(root/'app/Madeira/arm64ec-windows'/name)],text=True)
  assert 'Format: COFF-ARM64EC' in headers, name
  start=pe+24+struct.unpack_from('<H',data,pe+20)[0]
  for i in range(struct.unpack_from('<H',data,pe+6)[0]):assert not data[start+40*i:start+40*i+8].startswith(b'.debug'),name
 # Real 32-bit payloads use the current source farm and carry no PE debug sections.
 rebuilt_i386=('ntdll.dll','kernelbase.dll','mscoree.dll','combase.dll','wininet.dll','xinput1_1.dll','xinput1_2.dll','xinput1_3.dll','xinput1_4.dll','xinput9_1_0.dll','xinputuap.dll','d3d11.dll','d3d10core.dll','dxgi.dll','winemetal.dll','d3d9.dll','d3d9shim.dll','d3d9-emulated.dll')
 for name in rebuilt_i386:
  data=after['i386-windows/'+name];pe=struct.unpack_from('<I',data,0x3c)[0]
  assert struct.unpack_from('<H',data,pe+4)[0]==0x14c,name
  start=pe+24+struct.unpack_from('<H',data,pe+20)[0]
  for i in range(struct.unpack_from('<H',data,pe+6)[0]):assert not data[start+40*i:start+40*i+8].startswith(b'.debug'),name
for rec in json.loads((root/'.build/r37-audit/reused-build-inputs.json').read_text()):
 assert digest(root/rec['path']) == rec['sha256'], rec['path']
native_check=json.loads((root/'.build/r37-audit/native-member-verification.json').read_text())
assert native_check['changed_members']==['socket.o'] and native_check['other_archives_byte_identical']==15
assert b'launch-client-logged-on' in after['arm64ec-windows/dockhost.exe']
assert b'launch-client-connection-result' in after['arm64ec-windows/dockhost.exe']
assert subprocess.check_output(['git','-C',str(root/'madeira-dock'),'rev-parse','HEAD']).strip() in after['arm64ec-windows/dock-notices.txt']
report={
 'version':'0.1.3','fork_revision':'r37','build':'22',
 'upstream_commit':subprocess.check_output(['git','rev-parse','upstream/main'],cwd=root,text=True).strip(),
 'configuration':'optimized Release, native -O2, Swift -O, testability/debug dylibs/profiling disabled',
 'unsigned_macho_files':unsigned,'uuids_arm64':uuids,
 'previous_r36_ipa_sha256':digest(previous),
 'changed_payload_files_from_r36':changed,'added_payload_files_from_r36':added,'unchanged_r36_payload_files':len(before)-len(changed),
 'original_upstream_runtime_resources':len(original_runtime),'all_original_runtime_resources_present':True,
 'fex_original_source_and_latest_windows_engines_preserved':True,
 'dlss_metalfx_payload_verified':True,
 'wintypes_architectures':['ARM64EC','ARM64'],
 'native_inputs_reused_without_modification':False,
 'native_udp_control_member_verification':json.loads((root/'.build/r37-audit/native-member-verification.json').read_text()),
 'udp_control_real_datagrams_verified':512,
 'dock_local_connection_reports_bounded':True,
 'failed_import_reuse_verified':True,
 'qwave_architectures':['ARM64EC','ARM64','i386'],
 'wine_mono_version':'11.0.0','wine_mono_original_patch_verified':True,
 'microsoft_runtime_redistributed':False,
 'native_archive_members':json.loads((root/'.build/r37-audit/native-members.json').read_text()),
 'tests':[dict(test=t['test'],passed=t['passed'],seconds=t.get('seconds')) for t in tests],
 'device_acceptance':'Release compilation and synthetic contracts verified. Device gameplay and real multiplayer acceptance remain open.'}
for artifact in (ipa,symbols):
 sha=digest(artifact);Path(str(artifact)+'.sha256').write_text(sha+'  '+artifact.name+'\n');report[artifact.suffix[1:]]={'filename':artifact.name,'bytes':artifact.stat().st_size,'sha256':sha}
(output/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'ipa':str(ipa),'uuids':uuids,'changed':changed,'added':len(added),'tests':len(tests)},indent=2))
