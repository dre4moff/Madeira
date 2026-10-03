#!/usr/bin/env python3
"""Package the r27 host fix over the verified r26 resources, without app execution."""
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
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline',type=Path,required=True)
p.add_argument('--products',type=Path,required=True)
p.add_argument('--output-directory',type=Path,required=True)
a=p.parse_args()
baseline=a.baseline.resolve(); products=a.products.resolve(); output=a.output_directory.resolve()
assert hashlib.sha256(baseline.read_bytes()).hexdigest()=='bc376dce49568afd282edc96c3de8ca15604345eb325421f42041b222e6a9c05'
output.mkdir(parents=True,exist_ok=True)
ipa=output/'Madeira-0.1.1-Fork-r27-Release-unsigned.ipa'
symbols=output/'Madeira-0.1.1-Fork-r27-symbols.zip'
assert not ipa.exists() and not symbols.exists(), 'Refusing to overwrite a release'
prefix='Payload/Madeira.app/'
with tempfile.TemporaryDirectory(prefix='madeira-r27-package-') as folder:
 stage=Path(folder)
 with zipfile.ZipFile(baseline) as old:
  assert old.testzip() is None
  assert all(not n.startswith('/') and '..' not in Path(n).parts for n in old.namelist())
  old.extractall(stage)
 app=stage/'Payload/Madeira.app'
 for name in ('Madeira','Info.plist'):shutil.copyfile(products/'Madeira.app'/name,app/name)
 executable=app/'Madeira'
 r=subprocess.run(['codesign','--remove-signature',str(executable)],capture_output=True,text=True)
 assert r.returncode==0 or 'not signed at all' in r.stderr,r.stderr
 info=plistlib.loads((app/'Info.plist').read_bytes())
 assert info['CFBundleVersion']=='11' and info['CFBundleShortVersionString']=='0.1.1'
 assert info['CFBundleIdentifier']=='com.willfaust.madeora'
 assert info['MadeiraProfileBuild'] is False and 'r27-worker-context-fullscreen' in info['MadeiraBuild']
 uuidtext=subprocess.check_output(['xcrun','dwarfdump','--uuid',str(executable),str(products/'Madeira.app.dSYM')],text=True)
 uuids=re.findall(r'UUID: ([A-F0-9-]+) \(arm64\)',uuidtext)
 assert len(uuids)==2 and uuids[0]==uuids[1]
 data=executable.read_bytes()
 assert b'[mono-return] restored owning CPUArea' in data and b'[dock-fullscreen] game-client=' in data
 assert not list(app.rglob('*.dSYM')) and not list(app.rglob('*debug.dylib'))
 subprocess.run(['ditto','-c','-k','--norsrc','--noextattr','--keepParent','Payload',str(ipa)],cwd=stage,check=True)
 subprocess.run(['ditto','-c','-k','--norsrc','--noextattr','--keepParent',str(products/'Madeira.app.dSYM'),str(symbols)],check=True)
changed=[]
with zipfile.ZipFile(baseline) as old,zipfile.ZipFile(ipa) as new:
 assert new.testzip() is None
 before={n for n in old.namelist() if not n.endswith('/')};after={n for n in new.namelist() if not n.endswith('/')}
 assert before==after
 for n in sorted(after):
  data=new.read(n)
  if data!=old.read(n):changed.append(n.removeprefix(prefix))
  assert '/x86_64-vcruntime/' not in n and not n.endswith('MICROSOFT-LICENSE.rtf')
  assert '_CodeSignature' not in n and not n.endswith('embedded.mobileprovision')
  if data[:4]==b'\xcf\xfa\xed\xfe':
   assert struct.unpack_from('<I',data,4)[0]==0x100000c
   pos=32
   for _ in range(struct.unpack_from('<I',data,16)[0]):
    cmd,size=struct.unpack_from('<II',data,pos);assert cmd!=0x1d;pos+=size
   assert b'__DWARF' not in data[:pos]
 assert set(changed)=={'Madeira','Info.plist'},changed
report={
 'build':'11','configuration':'optimized Release','uuid_arm64':uuids[0],
 'baseline_r26_sha256':hashlib.sha256(baseline.read_bytes()).hexdigest(),
 'changed_payload_files_from_public_r26':changed,'unchanged_payload_files':len(after)-len(changed),
 'original_fex_windows_engines_preserved':True,'microsoft_runtime_redistributed':False,
 'tests':json.loads((root/'.build/r27-audit/host-tests.json').read_text()),
 'native_archive_members':json.loads((root/'.build/r27-audit/native-members.json').read_text()),
 'device_acceptance':'Pending: successful game startup, speech recognition, visible fullscreen iPhone output and performance require a fresh device run.'
}
assert len(report['tests'])==33 and all(t['passed'] for t in report['tests'])
for artifact in (ipa,symbols):
 digest=hashlib.sha256(artifact.read_bytes()).hexdigest()
 Path(str(artifact)+'.sha256').write_text(digest+'  '+artifact.name+'\n')
 report[artifact.suffix[1:]]={'filename':artifact.name,'bytes':artifact.stat().st_size,'sha256':digest}
(output/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'ipa':str(ipa),'uuid':uuids[0],'changed':changed},indent=2))
