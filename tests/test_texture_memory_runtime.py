"""Run production mip eligibility, view translation and copy recording on host."""
from pathlib import Path
import re, subprocess, tempfile
root = Path(__file__).resolve().parents[1]
src = (root/'madeira-d3d12/src/pe/madeira_d3d12.c').read_text()
def cut(signature):
    match=re.search(re.escape(signature)+r'[^;{]*\{',src)
    assert match, signature
    a=match.start(); b=match.end()-1; depth=1; e=b+1
    while depth:
        depth+=(src[e]=='{')-(src[e]=='}'); e+=1
    return src[a:e]
formats=(root/'toolchains/llvm-mingw-20260421-ucrt-macos-universal/generic-w64-mingw32/include/dxgiformat.h').read_text()
enums=',\n'.join(re.findall(r'\b(DXGI_FORMAT_\w+\s*=\s*(?:0x[0-9a-fA-F]+|\d+))',formats))
harness=r'''
#include <stdint.h>
#include <string.h>
#include <assert.h>
#include <stdio.h>
#include "texture_memory_policy.h"
typedef unsigned UINT; typedef uint64_t UINT64; typedef int DXGI_FORMAT, D3D12_HEAP_TYPE;
#define D3D12_HEAP_TYPE_DEFAULT 1
#define D3D12_RESOURCE_DIMENSION_TEXTURE2D 3
#define D3D12_RESOURCE_DIMENSION_TEXTURE3D 4
#define D3D12_TEXTURE_LAYOUT_UNKNOWN 0
#define STDMETHODCALLTYPE
struct D3D12_RESOURCE_DESC { UINT Dimension, Flags, Layout, MipLevels, Height, DepthOrArraySize; UINT64 Width; DXGI_FORMAT Format; struct {UINT Count;} SampleDesc; };
typedef struct D3D12_RESOURCE_DESC D3D12_RESOURCE_DESC;
struct madeira_ctl_args {UINT op,ret; UINT64 len,ptr;};
static int query_ok=1; static uint64_t headroom=4096ull<<20,footprint=4096ull<<20; static long long start_mb=4096;
static long long mad_cfg_int_pe(const char *key,long long fallback){return start_mb;}
static void MadeiraCtl(struct madeira_ctl_args *a){assert(a->op==7);a->ret=query_ok;a->len=headroom;a->ptr=footprint;}
static void d3d12_log(const char *fmt,...){ }
struct mad_resource {void *texture,*buffer; UINT mip_bias,is_depth,has_stencil; UINT64 size; D3D12_RESOURCE_DESC desc;};
typedef struct mad_resource ID3D12Resource;
struct footprint {UINT Format,Width,Height,Depth,RowPitch;};
typedef struct {UINT64 Offset;struct footprint Footprint;} D3D12_PLACED_SUBRESOURCE_FOOTPRINT;
typedef struct {ID3D12Resource *pResource; UINT Type,SubresourceIndex; D3D12_PLACED_SUBRESOURCE_FOOTPRINT PlacedFootprint;} D3D12_TEXTURE_COPY_LOCATION;
typedef struct {UINT left,top,front,right,bottom,back;} D3D12_BOX;
enum {MC_COPY_B2T,MC_COPY_T2B,MC_COPY_T2T};
struct mad_cmd {int type; union {struct {struct mad_resource *tex,*buf; UINT64 off;UINT level,slice,plane,w,h,d,row,rows,x,y,z;}bt;
struct {struct mad_resource *src,*dst;UINT dlevel,dslice,dplane,slevel,sslice,splane,dx,dy,dz,w,h,d,sx,sy,sz;}tt;}u;};
struct mad_list {struct mad_cmd cmd;UINT count;};typedef struct mad_list ID3D12GraphicsCommandList;
static struct mad_cmd *mad_list_push(struct mad_list *l,int type){l->count++;memset(&l->cmd,0,sizeof l->cmd);l->cmd.type=type;return &l->cmd;}
static void list_CopyBufferRegion(ID3D12GraphicsCommandList *l,ID3D12Resource *d,UINT64 doff,ID3D12Resource *s,UINT64 soff,UINT64 len){assert(0);}
'''
functions='\n'.join(cut(sig) for sig in ('static void mad_format_info(', 'static UINT mad_texture_mip_bias(', 'static void mad_subresource_plane(', 'static void mad_mip_dims(', 'static void STDMETHODCALLTYPE list_CopyTextureRegion('))
cases=r'''
int main(void){
 assert(mad_texture_headroom_mb(4096,8192ull<<20)==4096);
 assert(mad_texture_headroom_mb(2048,8192ull<<20)==6144);
 assert(mad_texture_headroom_mb(4096,4096ull<<20)==1536);
 assert(mad_texture_headroom_mb(2048,4096ull<<20)==2048);
 assert(mad_texture_headroom_mb(1234,8192ull<<20)==0);
 D3D12_RESOURCE_DESC desc={.Dimension=3,.Width=2048,.Height=2048,.MipLevels=12,.DepthOrArraySize=6,.Format=DXGI_FORMAT_BC7_UNORM,.SampleDesc={1}};
 assert(mad_texture_mip_bias(1,&desc,1)==0); // exactly at 4 GiB trigger
 footprint+=1ull<<20;headroom-=1ull<<20;assert(mad_texture_mip_bias(1,&desc,1)==1);
 footprint=3000ull<<20;headroom=5192ull<<20;assert(mad_texture_mip_bias(1,&desc,1)==0);
 start_mb=2048;assert(mad_texture_mip_bias(1,&desc,1)==1);
 start_mb=0;assert(mad_texture_mip_bias(1,&desc,1)==0);start_mb=2048;
 query_ok=0;assert(mad_texture_mip_bias(1,&desc,1)==0);query_ok=1;
 assert(mad_texture_mip_bias(1,&desc,0)==0);assert(mad_texture_mip_bias(2,&desc,1)==0);
 desc.Flags=4;assert(!mad_texture_mip_bias(1,&desc,1));desc.Flags=0;
 desc.Layout=1;assert(!mad_texture_mip_bias(1,&desc,1));desc.Layout=0;
 desc.Format=DXGI_FORMAT_R8G8B8A8_UNORM;assert(!mad_texture_mip_bias(1,&desc,1));desc.Format=DXGI_FORMAT_BC7_UNORM;
 desc.Width=1030;assert(!mad_texture_mip_bias(1,&desc,1));desc.Width=2048;
 desc.MipLevels=1;assert(!mad_texture_mip_bias(1,&desc,1));desc.MipLevels=12;
 desc.SampleDesc.Count=4;assert(!mad_texture_mip_bias(1,&desc,1));desc.SampleDesc.Count=1;
 desc.Dimension=4;assert(!mad_texture_mip_bias(1,&desc,1));desc.Dimension=3;
 UINT first=0,count=~0u;mad_texture_view_levels(1,11,&first,&count);assert(first==0&&count==11);
 first=0;count=1;mad_texture_view_levels(1,11,&first,&count);assert(first==0&&count==1);
 first=3;count=2;mad_texture_view_levels(1,11,&first,&count);assert(first==2&&count==2);
 first=~0u;count=~0u;mad_texture_view_levels(1,11,&first,&count);assert(first==10&&count==1);
 struct mad_resource tex={.texture=(void*)1,.mip_bias=1,.desc=desc},buf={.buffer=(void*)1};
 struct mad_list list={0};D3D12_TEXTURE_COPY_LOCATION dst={.pResource=&tex},src={.pResource=&buf};
 src.PlacedFootprint=(D3D12_PLACED_SUBRESOURCE_FOOTPRINT){.Offset=512,.Footprint={.Width=1024,.Height=1024,.Depth=1,.RowPitch=4096}};
 list_CopyTextureRegion(&list,&dst,0,0,0,&src,0);assert(list.count==0); // discard removed mip, no command or retained refs
 dst.SubresourceIndex=13; // array slice 1, logical mip 1
 list_CopyTextureRegion(&list,&dst,0,0,0,&src,0);
 assert(list.count==1&&list.cmd.u.bt.level==0&&list.cmd.u.bt.slice==1);
 assert(list.cmd.u.bt.w==1024&&list.cmd.u.bt.h==1024&&list.cmd.u.bt.row==4096&&list.cmd.u.bt.rows==256);
 D3D12_BOX box={.left=4,.top=8,.right=36,.bottom=24,.back=1};
 list_CopyTextureRegion(&list,&dst,2,3,0,&src,&box);
 assert(list.cmd.u.bt.off==512+2*4096+16&&list.cmd.u.bt.w==32&&list.cmd.u.bt.h==16&&list.cmd.u.bt.rows==256);
 D3D12_TEXTURE_COPY_LOCATION read=src;
 list_CopyTextureRegion(&list,&read,4,8,0,&dst,0);
 assert(list.cmd.type==MC_COPY_T2B&&list.cmd.u.bt.level==0&&list.cmd.u.bt.slice==1&&list.cmd.u.bt.w==1024&&list.cmd.u.bt.off==512+2*4096+16);
 struct mad_resource full=tex;full.mip_bias=0;read.pResource=&full;read.SubresourceIndex=13;
 list_CopyTextureRegion(&list,&read,0,0,0,&dst,0);
 assert(list.cmd.type==MC_COPY_T2T&&list.cmd.u.tt.dlevel==1&&list.cmd.u.tt.slevel==0&&list.cmd.u.tt.w==1024&&list.cmd.u.tt.dslice==1);
 assert(tex.desc.Width==2048&&tex.desc.MipLevels==12); // logical GetDesc/footprints retained
 puts("PASS: trigger, safe eligibility, remote/unknown budget, logical views, uploads/readback/array copies, retained row pitches and removed top mips");
}
'''
with tempfile.TemporaryDirectory(prefix='madeira-texture-runtime-') as tmp:
    p=Path(tmp);(p/'test.c').write_text('enum {\n'+enums+'\n};\n'+harness+functions+cases)
    subprocess.run(['clang','-std=c11','-Wall','-Werror','-Wno-unused-function','-Wno-unused-parameter','-I',str(root/'madeira-d3d12/src'),str(p/'test.c'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)
# Check public entry points preserve resource ownership distinctions.
assert 'NULL, 0, 0);' in cut('static HRESULT mad_create_resource(')
assert 'h, offset, 0);' in cut('static HRESULT STDMETHODCALLTYPE device_CreatePlacedResource(')
assert 'mad_create_resource(d, D3D12_HEAP_TYPE_DEFAULT, desc, riid, out)' in cut('static HRESULT mad_create_reserved(')
assert 'D3D12_HEAP_FLAG_SHARED_CROSS_ADAPTER' in cut('static HRESULT STDMETHODCALLTYPE device_CreateCommittedResource(')
assert 'mad_texture_view_levels(r->mip_bias' in cut('static UINT64 mad_texture_view_id(')
