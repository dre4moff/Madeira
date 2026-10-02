"""Production D3D12 NGX backend: fake COM/Metal boundaries, ASan/UBSan, no GPU."""
from pathlib import Path
import subprocess
import tempfile
root=Path(__file__).resolve().parents[1]
backend=root/'madeira-d3d12/src/pe/madeira_dlss.h'
c=(root/'madeira-d3d12/src/pe/madeira_d3d12.c').read_text()
cleanup=c[c.index('static void mad_list_release_temporal('):c.index('static HRESULT STDMETHODCALLTYPE list_QI(')]
replay=c[c.index('        case MC_TEMPORAL: {'):c.index('        case MC_PSO:')]
replay=replay.replace('        case MC_TEMPORAL: {','static void replay(struct mad_queue *q, struct mad_cmd *c) {\nstruct mad_exec e={0};obj_handle_t cb=20; {').replace('            break;','').rstrip()+'\n}\n'
source=r'''
#include <assert.h>
#include <stdio.h>
#include <math.h>
#include <string.h>
#include <stdlib.h>
#define DXMT_NATIVE 1
#include "winemetal.h"
#include "madeira_dlss_abi.h"
typedef int32_t HRESULT;typedef unsigned UINT;typedef uint64_t UINT64;
#define S_OK 0
#define E_INVALIDARG ((int32_t)0x80070057)
#define E_NOTIMPL ((int32_t)0x80004001)
#define E_OUTOFMEMORY ((int32_t)0x8007000e)
#define FAILED(x) ((x)<0)
#define D3D12_COMMAND_LIST_TYPE_DIRECT 0
#define D3D12_COMMAND_LIST_TYPE_COMPUTE 2
#define D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS 4
static int g_device_vtbl,g_list_vtbl,g_res_vtbl;
struct mad_device {const void *vtbl;obj_handle_t mtl_device;unsigned refs;};
struct mad_resource {const void *vtbl;struct mad_device *owner;obj_handle_t texture;unsigned samples,tex_type,width,height,refs;enum WMTPixelFormat tex_pf;struct {unsigned DepthOrArraySize,Flags;} desc;};
typedef struct mad_device ID3D12Device;typedef struct mad_resource ID3D12Resource;
static void ID3D12Device_AddRef(ID3D12Device *d){++d->refs;}
static void ID3D12Device_Release(ID3D12Device *d){assert(d->refs);--d->refs;}
static void ID3D12Resource_AddRef(ID3D12Resource *r){++r->refs;}
static void ID3D12Resource_Release(ID3D12Resource *r){assert(r->refs>1);--r->refs;}
struct mad_dlss_command {obj_handle_t scaler,motion,pipeline;struct mad_resource *resources[5];struct WMTFXTemporalScalerProps props;};
enum {MC_TEMPORAL=7};
struct mad_cmd {int kind;union {struct mad_dlss_command *temporal;} u;};
struct mad_list {const void *vtbl;int closed,type;struct mad_device *device;unsigned ncmds,used;struct mad_cmd cmds[16];};
static struct mad_cmd *mad_list_push(struct mad_list *l,int kind){if(l->ncmds==16)return NULL;struct mad_cmd *c=&l->cmds[l->ncmds++];c->kind=kind;return c;}
static void mad_list_note_used(struct mad_list *l,struct mad_resource *r){assert(r);++l->used;}
#define d3d12_log(...) ((void)0)
static unsigned next_object=100,refs[4096],fail_scaler,fail_pipeline,hardware=1,creates;
static obj_handle_t object(void){refs[next_object]=1;return next_object++;}
void NSObject_retain(obj_handle_t h){assert(h && refs[h]);++refs[h];}
void NSObject_release(obj_handle_t h){if(h){assert(refs[h]);--refs[h];}}
bool MTLDevice_supportsFXTemporalScaler(obj_handle_t d){assert(d);return hardware;}
obj_handle_t MTLDevice_newTemporalScaler(obj_handle_t d,const struct WMTFXTemporalScalerInfo *i){assert(d && i->input_width);++creates;return fail_scaler?0:object();}
obj_handle_t MTLDevice_newTexture(obj_handle_t d,struct WMTTextureInfo *i){assert(d && i->pixel_format==WMTPixelFormatRG32Float);return object();}
obj_handle_t DispatchData_alloc_init(uint64_t p,uint64_t n){assert(p && n);return object();}
obj_handle_t MTLDevice_newLibrary(obj_handle_t d,obj_handle_t data,obj_handle_t *err){(void)err;assert(d && data);return object();}
obj_handle_t MTLLibrary_newFunction(obj_handle_t lib,const char *name){assert(lib && !strcmp(name,"cs_downscale_dilated_mv"));return object();}
obj_handle_t MTLDevice_newComputePipelineState(obj_handle_t d,const struct WMTComputePipelineInfo *i,obj_handle_t *err){(void)err;assert(d && i->compute_function);return fail_pipeline?0:object();}
'''+f'#include "{backend}"\n'+cleanup+r'''
struct mad_queue {struct mad_device *device;};
struct mad_exec {int fence_needed,f6_sync_needed,f6_list_start,f7_reason;};
static char sequence[64];static unsigned steps;static struct WMTFXTemporalScalerProps last;static obj_handle_t last_motion;
static void step(char c){sequence[steps++]=c;sequence[steps]=0;}
static void exec_end(struct mad_exec *e){(void)e;step('E');}
static void f6_join(struct mad_queue *q){assert(q);step('J');}
static obj_handle_t mad_enc_fence_obj(struct mad_device *d){assert(d);return 42;}
static void exec_note_write(struct mad_exec *e,struct mad_resource *r){assert(e->fence_needed && e->f6_sync_needed && e->f6_list_start && e->f7_reason==2 && r);step('O');}
enum {F6_COMPUTE=2};
static void f6_encode(obj_handle_t enc,int kind,const obj_handle_t *waits,unsigned n,obj_handle_t update){assert(enc && kind==F6_COMPUTE);if(n){assert(waits[0]==42);step('W');}if(update){assert(update==42);step('F');}}
obj_handle_t MTLCommandBuffer_computeCommandEncoder(obj_handle_t cb,bool concurrent){assert(cb==20 && !concurrent);step('C');return 30;}
void MTLComputeCommandEncoder_encodeCommands(obj_handle_t encoder,const struct wmtcmd_base *head){
 assert(encoder==30);const struct wmtcmd_compute_setpso *p=(const void *)head;assert(p->type==WMTComputeCommandSetPSO && refs[p->pso]);
 const struct wmtcmd_compute_settexture *src=p->next.ptr,*dst=src->next.ptr;
 const struct wmtcmd_compute_setbytes *scale=dst->next.ptr;
 const struct wmtcmd_compute_dispatch *dispatch=scale->next.ptr;
 assert(src->index==0 && dst->index==1 && refs[dst->texture]);
 assert(((float *)scale->bytes.ptr)[0]==1280 && scale->length==8);
 assert(dispatch->type==WMTComputeCommandDispatchThreads && dispatch->size.width==640 && dispatch->size.height==360 && !dispatch->next.ptr);
 step('D');
}
void MTLCommandEncoder_endEncoding(obj_handle_t enc){assert(enc==30);step('X');}
void MTLCommandBuffer_encodeTemporalScale(obj_handle_t cb,obj_handle_t scaler,obj_handle_t color,obj_handle_t output,obj_handle_t depth,obj_handle_t motion,obj_handle_t exposure,obj_handle_t fence,const struct WMTFXTemporalScalerProps *props){
 assert(cb==20 && refs[scaler] && color && output && depth && motion && !exposure && fence==42);last=*props;last_motion=motion;step('T');
}
'''+replay+r'''
static struct mad_resource resource(struct mad_device *d,unsigned w,unsigned h,enum WMTPixelFormat pf){struct mad_resource r={&g_res_vtbl,d,1,1,WMTTextureType2D,w,h,1,pf,{1,4}};return r;}
int main(void){
 struct mad_device d={&g_device_vtbl,1,1},other={&g_device_vtbl,2,1};
 struct mad_list list={.vtbl=&g_list_vtbl,.device=&d};
 uint64_t feature=123;
 assert(MadeiraD3D12TemporalCreate(NULL,640,360,1280,720,2,&feature)==E_INVALIDARG && !feature);
 assert(MadeiraD3D12TemporalCreate(&list,400,360,1280,720,2,&feature)==E_NOTIMPL);
 hardware=0;assert(MadeiraD3D12TemporalCreate(&list,640,360,1280,720,2,&feature)==E_NOTIMPL);hardware=1;
 assert(MadeiraD3D12TemporalCreate(&list,640,360,1280,720,6,&feature)==E_NOTIMPL);
 assert(MadeiraD3D12TemporalCreate(&list,640,360,1280,720,2|8,&feature)==S_OK && d.refs==2);
 struct mad_resource color=resource(&d,640,360,WMTPixelFormatRGBA16Float),output=resource(&d,1280,720,WMTPixelFormatRGBA16Float),depth=resource(&d,640,360,WMTPixelFormatR32Float),motion=resource(&d,640,360,WMTPixelFormatRG16Float);
 struct madeira_dlss_desc desc={.size=96,.version=1,.flags=10,.input_width=640,.input_height=360,.output_width=1280,.output_height=720,.color=(uintptr_t)&color,.output=(uintptr_t)&output,.depth=(uintptr_t)&depth,.motion=(uintptr_t)&motion,.motion_scale_x=1280,.motion_scale_y=720,.pre_exposure=1};
 fail_scaler=1;assert(MadeiraD3D12TemporalRecord(&list,feature,&desc)==E_NOTIMPL && !list.ncmds);fail_scaler=0;
 motion.owner=&other;assert(MadeiraD3D12TemporalRecord(&list,feature,&desc)==E_INVALIDARG);motion.owner=&d;
 desc.input_width=500;assert(MadeiraD3D12TemporalRecord(&list,feature,&desc)==E_NOTIMPL);
 desc.input_width=641;assert(MadeiraD3D12TemporalRecord(&list,feature,&desc)==E_INVALIDARG);desc.input_width=640;
 assert(MadeiraD3D12TemporalRecord(&list,feature,&desc)==S_OK && color.refs==2 && list.ncmds==1);
 unsigned created=creates;assert(MadeiraD3D12TemporalRecord(&list,feature,&desc)==S_OK && creates==created && color.refs==3);
 struct mad_queue q={&d};replay(&q,&list.cmds[0]);assert(!strcmp(sequence,"EJTO") && last.reset && last.depth_reversed);
 MadeiraD3D12TemporalRelease(feature);assert(d.refs==1 && color.refs==3);mad_list_release_temporal(&list);assert(color.refs==1);list.ncmds=0;
 // High-resolution vectors use the existing kernel, ordered before MetalFX.
 assert(MadeiraD3D12TemporalCreate(&list,640,360,1280,720,8,&feature)==S_OK);desc.flags=8;motion.width=1280;motion.height=720;
 fail_pipeline=1;assert(MadeiraD3D12TemporalRecord(&list,feature,&desc)==E_NOTIMPL && !list.ncmds);fail_pipeline=0;
 assert(MadeiraD3D12TemporalRecord(&list,feature,&desc)==S_OK);
 MadeiraD3D12TemporalRelease(feature);steps=0;replay(&q,&list.cmds[0]);
 assert(!strcmp(sequence,"EJCWDFXTO") && last.motion_vector_scale_x==1 && last.motion_vector_scale_y==1 && last_motion!=motion.texture);
 mad_list_release_temporal(&list);assert(color.refs==1 && d.refs==1);
 for(unsigned i=100;i<next_object;i++)assert(refs[i]==0);
 puts("PASS: production D3D12 feature lifecycle, owner/dimension/HW rejection, cache reuse, low/high-res motion, command ordering and resource lifetime; fake Metal/COM");
}
'''
with tempfile.TemporaryDirectory() as folder:
 p=Path(folder);(p/'test.c').write_text(source);(p/'dxmt_command.h').write_text('static unsigned char dxmt_command[]={0};static unsigned dxmt_command_len=1;')
 subprocess.run(['xcrun','clang','-std=gnu2x','-fsanitize=address,undefined','-I'+str(p),'-I'+str(root/'dxmt/src/winemetal'),'-I'+str(root/'dxmt/include'),str(p/'test.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
assert 'mad_list_wait_idle(l)' in c[c.index('static HRESULT STDMETHODCALLTYPE list_Reset'):c.index('static HRESULT STDMETHODCALLTYPE list_Reset')+1000]
assert 'mad_list_release_temporal(l)' in c[c.index('static ULONG STDMETHODCALLTYPE list_Release'):c.index('static void mad_list_wait_idle')]
