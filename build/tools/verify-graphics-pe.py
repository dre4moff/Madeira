#!/usr/bin/env python3
"""Inspect graphics DLL ABI and imports against shipped Wine modules; no execution."""
from pathlib import Path
import json
import re
import subprocess
root = Path(__file__).resolve().parents[2]
reader = root/'toolchains/llvm-mingw-20260421-ucrt-macos-universal/bin/llvm-readobj'
farm = root/'app/Madeira/arm64ec-windows'
checks = {}
export_cache = {}
for dll in ['d3d11.dll', 'd3d12.dll', 'nvngx.dll', 'nvapi64.dll', 'wininet.dll']:
    path = farm/dll
    output = subprocess.check_output([str(reader), '--file-headers', '--coff-load-config', '--coff-exports', '--coff-imports', str(path)], text=True)
    assert 'COFF-ARM64EC' in output and re.search(r'CHPEMetadataPointer: 0x[1-9A-Fa-f]', output), dll
    builtin = b'Wine builtin DLL' in path.read_bytes()[:200]
    # Preserve upstream native D3D DLLs; only NVEXT shims use builtin-only overrides.
    assert builtin == (dll in ['nvngx.dll', 'nvapi64.dll', 'wininet.dll']), dll
    if dll == 'd3d12.dll':
        for name in ['MadeiraD3D12TemporalSupported', 'MadeiraD3D12TemporalCreate', 'MadeiraD3D12TemporalRecord', 'MadeiraD3D12TemporalRelease']:
            assert 'Name: '+name+'\n' in output, name
        for ordinal, name in [(101, 'D3D12CreateDevice'), (102, 'D3D12GetDebugInterface')]:
            assert re.search(r'Ordinal: '+str(ordinal)+r'\s+Name: '+name, output), name
    if dll == 'nvngx.dll':
        for api in ['Init', 'Init_Ext', 'Init_ProjectID', 'Init_with_ProjectID', 'GetParameters', 'GetCapabilityParameters', 'AllocateParameters', 'DestroyParameters', 'GetFeatureRequirements', 'GetScratchBufferSize', 'CreateFeature', 'EvaluateFeature', 'ReleaseFeature', 'Shutdown', 'Shutdown1']:
            assert 'Name: NVSDK_NGX_D3D12_'+api+'\n' in output, api
    unresolved = []
    imports = 0
    for section in re.findall(r'Import \{(.*?)\n\}', output, re.S):
        name = re.search(r'Name: (\S+)', section).group(1).lower()
        target = farm/name
        if not target.exists() and name.startswith('api-ms-win-crt-'):
            # Shipped apisetschema forwards CRT API sets to the Wine UCRT module.
            schema = (farm/'apisetschema.dll').read_bytes()
            assert name.removesuffix('.dll').encode('utf-16le') in schema, name
            assert 'ucrtbase.dll'.encode('utf-16le') in schema, name
            target = farm/'ucrtbase.dll'
        assert target.exists(), (dll, name)
        if target not in export_cache:
            exports = subprocess.check_output([str(reader), '--coff-exports', str(target)], text=True)
            export_cache[target] = set(re.findall(r'Name: (\S+)', exports))
        for symbol in re.findall(r'Symbol: (\S+) \(', section):
            imports += 1
            if symbol not in export_cache[target]: unresolved.append((name, symbol))
    assert not unresolved, (dll, unresolved)
    checks[dll] = {'arm64ec': True, 'chpe_metadata': True, 'wine_builtin': builtin, 'resolved_named_imports': imports}
print(json.dumps(checks, indent=2))
