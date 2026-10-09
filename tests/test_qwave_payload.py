#!/usr/bin/env python3
"""Check QoS exports, architecture, stripped sections and runtime import closure."""
from pathlib import Path
import struct
import subprocess
import tempfile
import sys
import zipfile

root = Path(__file__).resolve().parents[1]
def pe(data):
    off = struct.unpack_from('<I', data, 0x3c)[0]
    assert data[off:off+4] == b'PE\0\0'
    machine, count = struct.unpack_from('<HH', data, off+4)
    opt = off+24
    dd = opt+(112 if struct.unpack_from('<H', data, opt)[0] == 0x20b else 96)
    section_start = opt+struct.unpack_from('<H', data, off+20)[0]
    sections = [struct.unpack_from('<8sIIII', data, section_start+i*40) for i in range(count)]
    def raw(rva):
        for _, vs, va, size, ptr in sections:
            if va <= rva < va+max(vs,size): return ptr+rva-va
        raise AssertionError('RVA outside sections')
    def string(rva):
        start = raw(rva); return data[start:data.index(b'\0', start)].decode('ascii')
    imports = []
    rva, size = struct.unpack_from('<II', data, dd+8)
    if rva:
        pos = raw(rva)
        while any(struct.unpack_from('<5I',data,pos)):
            imports.append(string(struct.unpack_from('<I',data,pos+12)[0]).lower());pos+=20
    exports = set()
    rva, size = struct.unpack_from('<II', data, dd)
    if rva:
        pos=raw(rva);num=struct.unpack_from('<I',data,pos+24)[0]
        if num:
            names=raw(struct.unpack_from('<I',data,pos+32)[0])
            exports={string(struct.unpack_from('<I',data,names+4*i)[0]) for i in range(num)}
    return machine,sections,imports,exports

payload = {}
if len(sys.argv)>1:
    with zipfile.ZipFile(sys.argv[1]) as z:
        prefix='Payload/Madeira.app/'
        payload={n.removeprefix(prefix):z.read(n) for n in z.namelist() if n.startswith(prefix) and not n.endswith('/')}
else:
    for farm in ('arm64ec-windows','aarch64-windows','i386-windows'):
        for p in (root/'app/Madeira'/farm).iterdir():
            if p.is_file():payload[farm+'/'+p.name]=p.read_bytes()
for farm,machine in (('arm64ec-windows',0x8664),('aarch64-windows',0xaa64),('i386-windows',0x14c)):
    data=payload[farm+'/qwave.dll'];m,sections,imports,exports=pe(data)
    assert m==machine,(farm,hex(m))
    if farm=="arm64ec-windows":
        with tempfile.TemporaryDirectory(prefix="madeira-qwave-") as tmp:
            p=Path(tmp)/"qwave.dll";p.write_bytes(data)
            headers=subprocess.check_output([str(root/"toolchains/llvm-mingw-20260421-ucrt-macos-universal/bin/llvm-readobj"),"--file-headers",str(p)],text=True)
            assert "Format: COFF-ARM64EC" in headers,headers
    assert {'QOSCreateHandle','QOSAddSocketToFlow','QOSCloseHandle'} <= exports,(farm,exports)
    assert not any(s[0].startswith(b'.debug') for s in sections),farm
    assert b'[import-retry]' in payload[farm+'/ntdll.dll'],farm
    files={n.split('/')[-1].lower() for n in payload if n.split('/')[0]==farm}
    missing=[];checked=0
    for name,data in payload.items():
        if name.split('/')[0]!=farm or data[:2]!=b'MZ':continue
        checked+=1
        for imported in pe(data)[2]:
            if imported.startswith(('api-ms-','ext-ms-')):continue
            if imported not in files:missing.append((name,imported))
    assert not missing,missing
    print(f'PASS: {farm}: QoS exports, stripped PE, retry marker, {checked} modules, no missing imports')
