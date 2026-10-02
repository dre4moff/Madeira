"""Production native Metal declaration cases with a fake Objective-C encoder."""
from pathlib import Path
import re
import subprocess
import tempfile

root=Path(__file__).resolve().parents[1]
header=(root/'dxmt/src/winemetal/winemetal.h').read_text()
source=(root/'dxmt/src/winemetal/unix/winemetal_unix.c').read_text()
def definition(kind,name):
    return re.search(r'\b'+kind+r' '+name+r'[^;]*?\{.*?\n\};',header,re.S)[0]
definitions='\n'.join(definition('enum',n) for n in ['WMTResourceUsage','WMTRenderStage','WMTComputeCommandType','WMTRenderCommandType'])
definitions+='\n'+'\n'.join(definition('struct',n) for n in ['wmtcmd_base','wmtcmd_compute_useresource','wmtcmd_render_useresource'])
cases=[]
for prefix in ['Compute','Render']:
    a=source.index('    case WMT'+prefix+'CommandUseResource: {')
    b=source.index('\n    case ',a+12)
    cases.append(source[a:b])
a=source.index('static NTSTATUS\n_NSObject_release(NSObject **obj) {')
b=source.index('\nstatic NTSTATUS',a+20)
release=source[a:b]
cpp=r'''
#import <Foundation/Foundation.h>
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
typedef uint64_t obj_handle_t;
struct WMTMemoryPointer { const void *ptr; };
'''+definitions+r'''
#include "wmt_resource_batch.h"
typedef uint64_t MTLResourceUsage;
typedef uint64_t MTLRenderStages;
@protocol MTLResource @end
struct Record { uint64_t resource,usage,stages; };
static struct Record actual[1024];
static unsigned recorded, calls, stale;
@interface FakeEncoder : NSObject
- (void)useResource:(id<MTLResource>)r usage:(MTLResourceUsage)u stages:(MTLRenderStages)s;
- (void)useResources:(const id<MTLResource> *)r count:(NSUInteger)n usage:(MTLResourceUsage)u stages:(MTLRenderStages)s;
- (void)useResource:(id<MTLResource>)r usage:(MTLResourceUsage)u;
- (void)useResources:(const id<MTLResource> *)r count:(NSUInteger)n usage:(MTLResourceUsage)u;
@end
@implementation FakeEncoder
- (void)useResource:(id<MTLResource>)r usage:(MTLResourceUsage)u stages:(MTLRenderStages)s {
  ++calls;actual[recorded++]=(struct Record){(uint64_t)r,u,s};
}
- (void)useResources:(const id<MTLResource> *)r count:(NSUInteger)n usage:(MTLResourceUsage)u stages:(MTLRenderStages)s {
  ++calls;assert(n>1 && n<=64);
  for(unsigned i=0;i<n;++i) actual[recorded++]=(struct Record){(uint64_t)r[i],u,s};
}
- (void)useResource:(id<MTLResource>)r usage:(MTLResourceUsage)u { [self useResource:r usage:u stages:0]; }
- (void)useResources:(const id<MTLResource> *)r count:(NSUInteger)n usage:(MTLResourceUsage)u { [self useResources:r count:n usage:u stages:0]; }
@end
static void wmt_stale_check(uint64_t resource,const char *where) { (void)resource;(void)where;++stale; }
static void execute(const struct wmtcmd_base *next,FakeEncoder *encoder,int compute,int resource_batch) {
  uint64_t command_count=0,declarations=0,declaration_calls=0;
  while(next) {
    ++command_count;
    if(compute) switch((enum WMTComputeCommandType)next->type) {
'''+cases[0]+r'''
      default: actual[recorded++]=(struct Record){0,next->type,0};break;
    }
    else switch((enum WMTRenderCommandType)next->type) {
'''+cases[1]+r'''
      default: actual[recorded++]=(struct Record){0,next->type,0};break;
    }
    next=next->next.ptr;
  }
  assert(declarations==stale && declaration_calls==calls && command_count==recorded);
}
'''+r'''
#import <objc/runtime.h>
static int profiling,probe;
static unsigned releases,retain_queries;
typedef int NTSTATUS;
#define STATUS_SUCCESS 0
#define RM_IS_REMOTE(x) 0
#define RM_OP_RELEASE 0
struct rm_arg_handle {uint64_t handle;};
static int wmtr_enabled(void) {return 0;}
static int madeira_runtime_profiling_cached(void) {return profiling;}
static int wmt_stale_probe_on(void) {return probe;}
static void wmtr_buf_remove(uint64_t x) {(void)x;}
static void wmtr_call(int a,void *b,size_t c,void *d,size_t e,int f) {(void)a;(void)b;(void)c;(void)d;(void)e;(void)f;}
static void wmtr_pool_drain(void) {}
static void wmt_freed_set(uintptr_t p,int f) {(void)p;(void)f;}
static struct {uintptr_t p;const char *cls;} g_wmt_rel[16384];
static uint64_t g_wmt_rel_n;
@interface LifeObject : NSObject
@end
@implementation LifeObject
- (NSUInteger)retainCount {++retain_queries;return [super retainCount];}
- (oneway void)release {++releases;[super release];}
@end
'''+release+r'''
int main(void) { @autoreleasepool {
  FakeEncoder *encoder=[FakeEncoder new];
  assert(wmt_collect_resources(NULL,0).count==0);
  for(int compute=0;compute<2;++compute) for(unsigned n=1;n<=260;++n) {
    // Render records are large enough to hold either actual wire body.
    struct wmtcmd_render_useresource rows[260]={0};
    struct Record reference[1024];unsigned reference_count=0;
    for(unsigned i=0;i<n;++i) {
      uint64_t usage=1+(i/83)%2, stages=1+(i/91)%2;
      rows[i].type=(enum WMTRenderCommandType)(compute ? WMTComputeCommandUseResource : WMTRenderCommandUseResource);
      rows[i].next.ptr=i+1<n ? &rows[i+1] : NULL;
      rows[i].resource=0x1234+i%75;rows[i].usage=usage;rows[i].stages=stages;
      if(i==90 || i==157) rows[i].type=(enum WMTRenderCommandType)(compute ? WMTComputeCommandWaitForFence : WMTRenderCommandDraw);
    }
    for(int batching=0;batching<2;++batching) {
      recorded=calls=stale=0;execute((const void *)rows,encoder,compute,batching);
      if(!batching) {reference_count=recorded;memcpy(reference,actual,recorded*sizeof(*actual));}
      else assert(recorded==reference_count && !memcmp(reference,actual,recorded*sizeof(*actual)));
    }
  }
  struct wmtcmd_render_useresource rows[256]={0};
  for(unsigned i=0;i<256;++i) {
    rows[i].type=WMTRenderCommandUseResource;rows[i].usage=1;rows[i].stages=3;rows[i].resource=i+1;
    rows[i].next.ptr=i+1<256 ? &rows[i+1] : NULL;
  }
  recorded=calls=stale=0;execute((const void *)rows,encoder,0,1);assert(calls==4 && recorded==256);
  recorded=calls=stale=0;execute((const void *)rows,encoder,0,0);assert(calls==256 && recorded==256);
  for(int mode=0;mode<3;++mode) {
    profiling=mode==1;probe=mode==2;releases=retain_queries=0;g_wmt_rel_n=0;
    NSObject *object=[LifeObject new];
    assert(_NSObject_release(&object)==STATUS_SUCCESS);
    assert(releases==1 && retain_queries==(mode ? 1u : 0u) && g_wmt_rel_n==(mode ? 1u : 0u));
  }
  profiling=probe=0;NSObject *empty=nil;
  assert(_NSObject_release(&empty)==STATUS_SUCCESS);
  [encoder release];
  puts("PASS: production render/compute declarations equivalent in 520 sequences; masks/fences/draws/duplicates/capacity/opt-out; synthetic homogeneous calls 256->4; real release preserved in quiet/profiling/probe modes");
} }
'''
with tempfile.TemporaryDirectory(prefix='madeira-r16-batch-') as folder:
    p=Path(folder);(p/'test.m').write_text(cpp)
    subprocess.run(['xcrun','clang','-std=gnu2x','-O2','-fsanitize=address,undefined','-framework','Foundation',
        '-I'+str(root/'dxmt/src/winemetal/unix'),str(p/'test.m'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True,timeout=60)
