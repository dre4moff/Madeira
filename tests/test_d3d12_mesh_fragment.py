"""Exercise production mesh fragment selection and failure/lifetime boundaries."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
c = (root / "madeira-d3d12/src/pe/madeira_d3d12.c").read_text()
start = c.index("static int mad_mesh_fragment(")
end = c.index("\nstatic int mad_tess_build(", start)
helper = c[start:end]
source = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define DXMT_NATIVE 1
#include "winemetal.h"
#define MADEIRA_IR_OS_MACOS 1
struct { unsigned os; } g_target;
struct mad_device {obj_handle_t mtl_device;};
struct mad_pso {obj_handle_t ps_fn,ps_lib,mesh_null_lib,mesh_null_fn; char ps_name[64];};
static unsigned char madeira_mesh_null_macos[]={11},madeira_mesh_null_ios[]={22};
static unsigned madeira_mesh_null_macos_len=1,madeira_mesh_null_ios_len=1;
static unsigned refs[256],next=20,creates,fail_data,fail_lib,fail_fn,target_byte;
static obj_handle_t object(void){refs[next]=1;return next++;}
static void mad_resolve_target(struct mad_device *d){assert(d->mtl_device);}
static void mad_log_nserror(const char *s,obj_handle_t e){assert(s && e);}
#define d3d12_log(...) ((void)0)
obj_handle_t DispatchData_alloc_init(uint64_t p,uint64_t n){assert(n==1);target_byte=*(const unsigned char *)(uintptr_t)p;return fail_data?0:object();}
obj_handle_t MTLDevice_newLibrary(obj_handle_t device,obj_handle_t data,obj_handle_t *err){assert(device && refs[data]);++creates;if(fail_lib){*err=1;return 0;}return object();}
obj_handle_t MTLLibrary_newFunction(obj_handle_t lib,const char *name){assert(refs[lib] && !strcmp(name,"madeira_mesh_null_fragment"));return fail_fn?0:object();}
void NSObject_release(obj_handle_t o){assert(o && refs[o]);--refs[o];}
''' + helper + r'''
static struct WMTMeshRenderPipelineInfo info(void){
 struct WMTMeshRenderPipelineInfo i={0};i.rasterization_enabled=true;i.alpha_to_coverage_enabled=true;
 i.depth_pixel_format=WMTPixelFormatDepth32Float_Stencil8;i.stencil_pixel_format=i.depth_pixel_format;i.raster_sample_count=4;
 for(unsigned k=0;k<8;k++){i.colors[k].pixel_format=WMTPixelFormatRGBA8Unorm;i.colors[k].write_mask=15;i.colors[k].blending_enabled=true;}
 return i;
}
static void clean(struct mad_pso *p){if(p->mesh_null_fn)NSObject_release(p->mesh_null_fn);if(p->mesh_null_lib)NSObject_release(p->mesh_null_lib);memset(p,0,sizeof *p);}
int main(void){
 struct mad_device d={1};struct mad_pso p={0};struct WMTGeometryEmulationInfo ge={0};
 struct WMTMeshRenderPipelineInfo i=info();g_target.os=0;
 assert(mad_mesh_fragment(&d,&p,&i,&ge) && target_byte==22 && i.fragment_function==p.mesh_null_fn);
 assert(i.rasterization_enabled && i.depth_pixel_format==WMTPixelFormatDepth32Float_Stencil8 && i.stencil_pixel_format==i.depth_pixel_format && i.raster_sample_count==4);
 assert(!i.alpha_to_coverage_enabled && ge.fragment_library==p.mesh_null_lib && !strcmp(ge.fragment_function,"madeira_mesh_null_fragment"));
 for(unsigned k=0;k<8;k++)assert(!i.colors[k].write_mask && !i.colors[k].blending_enabled && i.colors[k].pixel_format==WMTPixelFormatRGBA8Unorm);
 unsigned before=creates;i=info();assert(mad_mesh_fragment(&d,&p,&i,NULL) && creates==before);clean(&p);
 g_target.os=MADEIRA_IR_OS_MACOS;i=info();assert(mad_mesh_fragment(&d,&p,&i,NULL) && target_byte==11);clean(&p);
 p.ps_fn=2;p.ps_lib=3;strcpy(p.ps_name,"ActualGamePS");i=info();struct WMTMeshRenderPipelineInfo original=i;before=creates;
 assert(mad_mesh_fragment(&d,&p,&i,&ge) && creates==before && i.fragment_function==2);
 original.fragment_function=2;assert(!memcmp(&original,&i,sizeof i) && ge.fragment_library==3 && !strcmp(ge.fragment_function,"ActualGamePS"));memset(&p,0,sizeof p);
 for(unsigned fail=0;fail<3;fail++){
  fail_data=fail==0;fail_lib=fail==1;fail_fn=fail==2;i=info();
  assert(!mad_mesh_fragment(&d,&p,&i,&ge) && !p.mesh_null_lib && !p.mesh_null_fn);
  assert(!i.fragment_function);fail_data=fail_lib=fail_fn=0;
 }
 for(unsigned k=20;k<next;k++)assert(!refs[k]);
 puts("PASS: PS-less mesh depth/stencil/MSAA retained, color suppressed, real PS intact, cached function, platform selection, allocation failures and lifetime");
}
'''
with tempfile.TemporaryDirectory(prefix="madeira-mesh-fragment-") as tmp:
    p = Path(tmp)
    (p / "test.c").write_text(source)
    subprocess.run(["clang", "-fsanitize=address,undefined", "-g", "-I"+str(root / "dxmt/src/winemetal"), str(p / "test.c"), "-o", str(p / "test")], check=True)
    subprocess.run([str(p / "test")], check=True)

# Cover every mesh creation path, not just the helper in isolation.
for begin, finish in [("static int mad_tess_build(", "static int mad_bc_is_dxbc("),
                      ("static int mad_gsx_build(", "static HRESULT STDMETHODCALLTYPE device_CreateGraphicsPipelineState(")]:
    part = c[c.index(begin):c.index(finish, c.index(begin))]
    assert part.index("mad_mesh_fragment(d, p, &mp, NULL)") < part.index("MTLDevice_newMeshRenderPipelineState(")
part = c[c.index("    if (p->gs_emu) {   /* ml927 */"):]
assert part.index("mad_mesh_fragment(d, p, &mp, &ge)") < part.index("MTLDevice_newGeometryEmulationPipelineState(")
assert c.index("if (!p->vs_fn || (desc->PS.pShaderBytecode && !p->ps_fn))") < c.index("    if (p->gs_emu) {   /* ml927 */")
destructor = c[c.index("static ULONG STDMETHODCALLTYPE pso_Release("):c.index("/* ---- serialized root signatures")]
assert "NSObject_release(p->mesh_null_fn)" in destructor and "NSObject_release(p->mesh_null_lib)" in destructor
print("PASS: geometry DXIL/DXBC and tessellation all covered; failed real PS conversion remains an error")
