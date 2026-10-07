from library_host_fixture import texture_memory_profile_fields, madeira_config_parser
from library_host_fixture import resolution_choices, control_action
"""Actual saved-profile sizing and renderer settings; host-only fixtures."""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parents[1]
s=(root/'app/Madeira/Library.swift').read_text()
helper=s[s.index('enum LibraryMetalFX {'):s.index('\nstruct LibraryEntry:')]
fields=s[s.index('struct LibraryEntry:'):s.index('    var displayMode: DisplayMode')] + texture_memory_profile_fields()
swift='import Foundation\nstruct TouchControl: Codable {}\n'+control_action()+helper+fields+'}\n'+r'''
let size = LibraryMetalFX.renderResolution
assert(size("1408x648", "balanced", true) == "1408x648")
assert(size("1408x648", "performance", true) == "1408x648")
for mode: String? in [nil, "off", "invalid"] { assert(size("1408x648", mode, true) == "1408x648") }
assert(size("1408x648", "performance", false) == "1408x648")
assert(size("640x480", "performance", true) == "640x480")
assert(size("320x240", "performance", true) == "320x240")
assert(size("bad", "balanced", true) == "bad")
var game = LibraryEntry(title: "RV", relativePath: "Ride.exe", bits: 64)
game.resolution = "1408x648"
let other = game
assert(game.metalFX == nil)
game.metalFX = "performance"
game.metalFXDLSS = true
let restored = try JSONDecoder().decode([LibraryEntry].self, from: JSONEncoder().encode([game,other]))
assert(restored[0].metalFX == "performance" && restored[1].metalFX == nil)
assert(restored[0].metalFXDLSS == true && restored[1].metalFXDLSS == nil)
assert(restored[0].resolution == "1408x648") // original output and preferences preserved
print("PASS: DLSS profiles keep full display size; legacy spatial profiles decode without implicit NVEXT opt-in")
'''
c=r'''
#include <assert.h>
#include <string.h>
#include <math.h>
#include "graphics_profile.h"
int main(void) {
 setenv("DXMT_CONFIG", "dxgi.customDeviceDesc=\"[My GPU]\";[Ride.exe];d3d11.metalSpatialUpscaleFactor=1.1", 1);
 const char *original = strdup(getenv("DXMT_CONFIG"));
 madeira_apply_metalfx_profile(1.5);
 assert(!strcmp(getenv("DXMT_METALFX_SPATIAL_FACTOR"), "1.5"));
 assert(!strcmp(getenv("DXMT_METALFX_SPATIAL_SWAPCHAIN"), "1"));
 madeira_apply_metalfx_profile(2);
 assert(!strcmp(getenv("DXMT_METALFX_SPATIAL_FACTOR"), "2"));
 for (int i=0;i<3;i++) { madeira_apply_metalfx_profile(i == 0 ? 0 : i == 1 ? 1 : NAN); assert(!getenv("DXMT_METALFX_SPATIAL_FACTOR")); assert(!strcmp(getenv("DXMT_METALFX_SPATIAL_SWAPCHAIN"), "0")); }
 assert(!strcmp(getenv("DXMT_CONFIG"), original)); free((void *)original);
 puts("PASS: per-game bridge precedence/reset, invalid choices and unrelated DXMT settings");
}
'''
swift = resolution_choices() + swift

swift = madeira_config_parser() + swift

with tempfile.TemporaryDirectory(prefix='madeira-metalfx-') as tmp:
 p=Path(tmp);(p/'main.swift').write_text(swift);(p/'profile.c').write_text(c)
 subprocess.run(['swift',str(p/'main.swift')],check=True)
 subprocess.run(['clang','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I',str(root/'build'),str(p/'profile.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
bridge=(root/'app/Madeira/WineProcessBridge.m').read_text()
assert bridge.index('const double metalFXFactor') < bridge.index('madeira.cfg env:') < bridge.index('madeira_apply_metalfx_profile(metalFXFactor)')
renderer=(root/'dxmt/src/d3d11/d3d11_swapchain.cpp').read_text()
assert 'if (metalfx_scaler && upscaled_backbuffer_)' in renderer and 'if (!upscaled_present)' in renderer
assert 'D3D11_ASSERT(metalfx_scaler' not in renderer
print('PASS: common direct/Dock launch wiring and recoverable scaler failure')
