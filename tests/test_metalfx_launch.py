"""Actual Steam desktop sizing and output cap; host-only synthetic profiles."""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parents[1]
l=(root/'app/Madeira/Library.swift').read_text()
helper=l[l.index('enum LibraryMetalFX {'):l.index('\nstruct LibraryEntry:')]
fields=l[l.index('struct LibraryEntry:'):l.index('    var displayMode: DisplayMode')]
prop=l[l.index('    var sessionRenderResolution: String {'):l.index('\n    func configureLaunch()',l.index('    var sessionRenderResolution: String {'))]
view=(root/'app/Madeira/ContentView.swift').read_text()
start=view.index('            // Explorer must use the same render mode')
branch=view[start:view.index('            setenv("MADEIRA_EXE"',start)]
swift='import Foundation\nstruct TouchControl: Codable {}\nvar supported=true\nfunc madeira_supports_spatial_upscaling()->Int32 {supported ? 1 : 0}\nstruct MockLog {func log(_ s:String) {}}\nlet logStore=MockLog()\n'+helper+fields+prop+'}\n'+r'''
func dockMode(_ profile: LibraryEntry?) -> String {
 var width=1280,height=720
'''+branch+r'''
 return "\(width)x\(height)"
}
var game=LibraryEntry(title:"RV",relativePath:"Steam/common/Ride",bits:64)
game.resolution="1920x1080";game.metalFX="balanced"
assert(game.sessionRenderResolution=="1920x1080" && dockMode(game)=="1920x1080")
assert(game.resolution=="1920x1080")
game.metalFXDLSS=true; assert(dockMode(game)=="1920x1080")
game.resolution="1408x648";game.metalFX="performance";assert(dockMode(game)=="1408x648")
game.resolution="1920x1080"
game.metalFX="performance";assert(dockMode(game)=="1920x1080")
game.metalFX=nil;assert(dockMode(game)=="1920x1080")
game.metalFX="balanced";supported=false;assert(dockMode(game)=="1920x1080")
supported=true;game.desktop=true;assert(dockMode(game)=="1920x1080")
assert(dockMode(nil)=="1280x720")
print("PASS: actual Dock desktop preserves output resolution for DLSS and retired spatial profiles; off, unsupported, desktop and no-profile defaults retained")
'''
c=r'''
#include <cassert>
#include <iostream>
#include "util_metalfx_profile.hpp"
using namespace dxmt;
int main() {
 auto x=metalFXOutput(1280,720,1.5,1920,1080);assert(x.factor==1.5 && x.width==1920 && x.height==1080);
 x=metalFXOutput(1920,1080,1.5,1920,1080);assert(x.factor==1 && x.width==1920 && x.height==1080);
 x=metalFXOutput(3840,2160,2,1920,1080);assert(x.factor==1 && x.width==3840 && x.height==2160);
 x=metalFXOutput(960,540,2,1920,1080);assert(x.factor==2 && x.width==1920 && x.height==1080);
 x=metalFXOutput(1600,900,1.5,1920,1080);assert(x.width==1920 && x.height==1080 && x.factor>1);
 x=metalFXOutput(939,432,1.5,1408,648);assert(x.width<=1408 && x.height<=648);
 x=metalFXOutput(1280,720,1.5,0,0);assert(x.width==1920 && x.height==1080);
 assert(metalFXOutputLimit("")==0 && metalFXOutputLimit("-1")==0 && metalFXOutputLimit("2048bad")==0 && metalFXOutputLimit("999999999999999999")==0);
 assert(metalFXOutputLimit("1920")==1920);
 for(unsigned w=320;w<=1920;w+=13)for(unsigned h=240;h<=1080;h+=17) {
  x=metalFXOutput(w,h,2,1920,1080);assert(x.width<=1920 && x.height<=1080);
 }
 puts("PASS: actual MetalFX cap prevents r9 1080p->1620p supersampling, permits lower-resolution inputs and restores scaling after a resize; rounding bounded");
}
'''
profile=r'''
#include <assert.h>
#include <string.h>
#include "graphics_profile.h"
int main() {
 madeira_apply_metalfx_profile(1.5);madeira_apply_metalfx_output(1.5,"1920x1080");
 assert(!strcmp(getenv("DXMT_METALFX_OUTPUT_WIDTH"),"1920") && !strcmp(getenv("DXMT_METALFX_OUTPUT_HEIGHT"),"1080"));
 madeira_apply_metalfx_profile(0);madeira_apply_metalfx_output(0,"1920x1080");
 assert(!getenv("DXMT_METALFX_OUTPUT_WIDTH") && !getenv("DXMT_METALFX_OUTPUT_HEIGHT"));
 madeira_apply_metalfx_profile(2);madeira_apply_metalfx_output(2,"invalid");assert(!getenv("DXMT_METALFX_OUTPUT_WIDTH"));
 madeira_apply_metalfx_output(2,"999999999999999999x1080");assert(!getenv("DXMT_METALFX_OUTPUT_WIDTH"));
 madeira_apply_metalfx_output(2,"960x540trailing");assert(!getenv("DXMT_METALFX_OUTPUT_WIDTH"));
 puts("PASS: output bound validates, applies after config and clears between profiles");
}
'''
with tempfile.TemporaryDirectory(prefix='madeira-metalfx-launch-') as tmp:
 p=Path(tmp);(p/'main.swift').write_text(swift);(p/'test.cpp').write_text(c);(p/'profile.c').write_text(profile)
 subprocess.run(['swift',str(p/'main.swift')],check=True)
 for compiler,file,include in [('clang++','test.cpp','dxmt/src/util'),('clang','profile.c','build')]:
  flags=['-std=c++20'] if compiler=='clang++' else []
  subprocess.run([compiler,*flags,'-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I',str(root/include),str(p/file),'-o',str(p/'test')],check=True)
  subprocess.run([str(p/'test')],check=True)
renderer=(root/'dxmt/src/d3d11/d3d11_swapchain.cpp').read_text()
assert renderer.index('const auto dimensions = metalFXOutput') < renderer.index('    ApplyLayerProps();')
assert 'requested_scale_factor = scale_factor' in renderer and 'info.output_width = output_width' in renderer
