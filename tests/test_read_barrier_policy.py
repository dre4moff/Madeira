"""Production D3D12 recorder: omission must retain every producer hazard."""
from pathlib import Path
import tempfile,subprocess,re
root=Path(__file__).resolve().parents[1]
s=(root/'madeira-d3d12/src/pe/madeira_d3d12.c').read_text();a=s.index('static void STDMETHODCALLTYPE list_ResourceBarrier(');b=s.index('\n/* ml889:',a)
# Use exact published header state values, not a duplicate implementation.
h=(root/'wine/include/d3d12.idl').read_text()
names=['VERTEX_AND_CONSTANT_BUFFER','INDEX_BUFFER','NON_PIXEL_SHADER_RESOURCE','PIXEL_SHADER_RESOURCE','INDIRECT_ARGUMENT','COPY_SOURCE','RESOLVE_SOURCE','DEPTH_READ','RENDER_TARGET','UNORDERED_ACCESS','DEPTH_WRITE','STREAM_OUT','COPY_DEST','RESOLVE_DEST']
constants='\n'.join('#define D3D12_RESOURCE_STATE_'+n+' '+re.search(r'D3D12_RESOURCE_STATE_'+n+r'\s*=\s*([^,\n]+)',h).group(1) for n in names)
code=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef unsigned UINT;typedef unsigned char UINT8;typedef long LONG;
#define STDMETHODCALLTYPE
#define D3D12_RESOURCE_BARRIER_TYPE_TRANSITION 0
#define D3D12_RESOURCE_BARRIER_TYPE_ALIASING 1
#define D3D12_RESOURCE_BARRIER_TYPE_UAV 2
#define D3D12_RESOURCE_BARRIER_FLAG_NONE 0
#define D3D12_RESOURCE_BARRIER_FLAG_BEGIN_ONLY 1
#define D3D12_RESOURCE_BARRIER_FLAG_END_ONLY 2
struct mad_resource{int unused;};
typedef struct {int Type,Flags;struct {void *pResource;UINT StateBefore,StateAfter;} Transition;struct {void *pResource;} UAV;} D3D12_RESOURCE_BARRIER;
'''+constants+r'''
#include "read_barrier_policy.h"
enum {BC_NONE,BC_RAR,BC_RAW_ATT,BC_RAW_COPY,BC_RAW_UAV,BC_ALL,MC_BARRIER=20};
struct mad_cmd{int kind;union {struct {int n,all,cls_noref;UINT8 cls[8];struct mad_resource *res[8];} barrier;}u;};
struct mad_list{int ncmds;struct mad_cmd cmds[32];};
typedef struct mad_list ID3D12GraphicsCommandList;
static LONG g_barriers,g_read_barriers_elided;static int g_read_barrier_elision=-1;
static int mad_cfg_int_pe(const char *key,int value){assert(!strcmp(key,"read-barrier-elision"));return value;}
#define InterlockedIncrement(p) (++*(p))
#define InterlockedExchangeAdd(p,v) (*(p)+=(v))
static struct mad_cmd *mad_list_push(struct mad_list *l,int kind){assert(l->ncmds<32);struct mad_cmd *c=&l->cmds[l->ncmds++];memset(c,0,sizeof *c);c->kind=kind;return c;}
'''+s[a:b]+r'''
int main(void){
 struct mad_list l={0};struct mad_resource resource={0};
 D3D12_RESOURCE_BARRIER b={.Type=0,.Transition={.pResource=&resource,.StateBefore=D3D12_RESOURCE_STATE_COPY_SOURCE,.StateAfter=D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE}};
 list_ResourceBarrier(&l,1,&b);assert(l.ncmds==0 && g_read_barriers_elided==1);
 UINT states[]={0,D3D12_RESOURCE_STATE_RENDER_TARGET,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_STATE_DEPTH_WRITE,D3D12_RESOURCE_STATE_COPY_DEST,D3D12_RESOURCE_STATE_RESOLVE_DEST,0x80000000};
 for(unsigned i=0;i<sizeof states/sizeof states[0];i++){l=(struct mad_list){0};b.Transition.StateBefore=states[i];list_ResourceBarrier(&l,1,&b);assert(l.ncmds==1 && l.cmds[0].u.barrier.n==1);}
 b.Transition.StateBefore=D3D12_RESOURCE_STATE_RENDER_TARGET;l=(struct mad_list){0};list_ResourceBarrier(&l,1,&b);unsigned cls=l.cmds[0].u.barrier.cls[0];b.Transition.StateBefore=D3D12_RESOURCE_STATE_COPY_SOURCE;list_ResourceBarrier(&l,1,&b);assert(l.ncmds==1 && l.cmds[0].u.barrier.n==1 && l.cmds[0].u.barrier.cls[0]==cls);
 for(int flag=1;flag<=2;flag++){l=(struct mad_list){0};b.Flags=flag;list_ResourceBarrier(&l,1,&b);assert(l.ncmds==1);}b.Flags=0;
 for(int type=1;type<=2;type++){l=(struct mad_list){0};b.Type=type;list_ResourceBarrier(&l,1,&b);assert(l.ncmds==1 && l.cmds[0].u.barrier.all);}b.Type=0;
 D3D12_RESOURCE_BARRIER batch[12];for(int i=0;i<12;i++){batch[i]=b;batch[i].Transition.StateBefore=i%2?D3D12_RESOURCE_STATE_COPY_DEST:D3D12_RESOURCE_STATE_COPY_SOURCE;}
 l=(struct mad_list){0};list_ResourceBarrier(&l,12,batch);assert(l.ncmds==1 && l.cmds[0].u.barrier.n==6);
 for(int i=0;i<12;i++)batch[i].Transition.StateBefore=D3D12_RESOURCE_STATE_COPY_DEST;l=(struct mad_list){0};list_ResourceBarrier(&l,12,batch);assert(l.cmds[0].u.barrier.all && l.cmds[0].u.barrier.cls_noref==BC_ALL);
 g_read_barrier_elision=0;l=(struct mad_list){0};list_ResourceBarrier(&l,1,&b);assert(l.ncmds==1);
 puts("PASS: actual recorder skips read-only transitions without empty commands; writes, COMMON/PRESENT, split, UAV/alias, unknown bits, prior queued fences, mixed batches, overflow and opt-out preserved");
}
'''
with tempfile.TemporaryDirectory(prefix='madeira-read-barriers-') as folder:
 p=Path(folder);(p/'test.c').write_text(code);subprocess.run(['clang','-fsanitize=address,undefined','-I'+str(root/'madeira-d3d12/src/pe'),str(p/'test.c'),'-o',str(p/'test')],check=True);subprocess.run([str(p/'test')],check=True)
