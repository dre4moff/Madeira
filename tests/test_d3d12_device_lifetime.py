"""Production D3D12 destruction/status/reclamation, fake Metal, ASan/UBSan."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
c = (root / "madeira-d3d12/src/pe/madeira_d3d12.c").read_text()

def function(signature):
    start = c.index(signature)
    brace = c.index("{", start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (c[end] == "{") - (c[end] == "}")
        end += 1
    return c[start:end]

source = r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdarg.h>
typedef int32_t LONG, HRESULT; typedef int64_t LONG64;
typedef uint64_t UINT64, obj_handle_t; typedef unsigned long ULONG;
#define STDMETHODCALLTYPE
#define S_OK 0
#define DXGI_ERROR_DEVICE_REMOVED ((HRESULT)0x887a0005)
#define DXGI_ERROR_DEVICE_HUNG ((HRESULT)0x887a0006)
#define MEM_RELEASE 1
struct ring {obj_handle_t buf;};
struct retired {obj_handle_t heap;void *mem;UINT64 serial;};
struct theap {obj_handle_t heap;void *fl;};
struct pattern {obj_handle_t buf;};
struct mad_device {
 LONG refs,device_lost,fence_quit;LONG64 gpu_serial_failed;
 const char *name;
 void *fence_thread,*fence_wake;
 obj_handle_t gpu_event,dsso,mtl_queue,mtl_device;
 unsigned ntheaps,nfillpat,nring_pool,nring_retired,nmhret;
 struct theap *theaps;struct pattern *fillpat;
 struct ring *ring_pool,*ring_retired;
 struct retired *mhret;
 int heap_lock,fence_lock,ring_lock,live_lock,view_lock;
 void *hret,*fence_jobs,*vmap;
};
typedef struct mad_device ID3D12Device,ID3D12Device10;
static struct mad_device *g_hp_dev;
static unsigned refs[512],queries,freed_memory;static UINT64 completed;
static LONG InterlockedDecrement(LONG *p){return --*p;}
static LONG InterlockedExchange(LONG *p,LONG n){LONG old=*p;*p=n;return old;}
static LONG InterlockedCompareExchange(LONG *p,LONG n,LONG old){LONG r=*p;if(r==old)*p=n;return r;}
static LONG64 InterlockedCompareExchange64(LONG64 *p,LONG64 n,LONG64 old){LONG64 r=*p;if(r==old)*p=n;return r;}
static void EnterCriticalSection(int *p){(void)p;}
static void LeaveCriticalSection(int *p){(void)p;}
static void DeleteCriticalSection(int *p){(void)p;}
static void SetEvent(void *p){assert(p);}
static void CloseHandle(void *p){assert(p);}
static void WaitForSingleObject(void *p,unsigned n){assert(p && n==10000);}
static void mad_pd_purge(void *p){assert(p);}
static void d3d12_log(const char *fmt,...){(void)fmt;}
static void NSObject_release(obj_handle_t h){assert(h<512 && refs[h]==1);--refs[h];}
static UINT64 MTLSharedEvent_signaledValue(obj_handle_t h){assert(h==1 && refs[h]);++queries;return completed;}
static void mad_unresident(struct mad_device *d,obj_handle_t h){assert(d && refs[h]);}
static void VirtualFree(void *p,unsigned n,int flag){assert(p && !n && flag==MEM_RELEASE);free(p);++freed_memory;}
'''
source += function("static UINT64 mad_gpu_completed(") + "\n"
source += function("static void mad_mheap_reclaim(struct mad_device *d, int all) {") + "\n"
source += function("static HRESULT STDMETHODCALLTYPE device_GetDeviceRemovedReason(") + "\n"
source += function("static ULONG STDMETHODCALLTYPE device_Release(") + "\n"
source += r'''
static struct mad_device *make(unsigned n){
 struct mad_device *d=calloc(1,sizeof *d);d->refs=1;d->name="test";
 d->gpu_event=1;refs[1]=1;d->nmhret=n;d->mhret=calloc(n,sizeof *d->mhret);
 for(unsigned i=0;i<n;i++){d->mhret[i]=(struct retired){10+i,malloc(16),i};refs[10+i]=1;}
 return d;
}
int main(void){
 struct mad_device *d=make(0);g_hp_dev=d;
 assert(device_GetDeviceRemovedReason(d)==S_OK);
 d->gpu_serial_failed=1;assert(device_GetDeviceRemovedReason(d)==DXGI_ERROR_DEVICE_HUNG);
 d->device_lost=1;assert(device_GetDeviceRemovedReason(d)==DXGI_ERROR_DEVICE_REMOVED);
 assert(device_Release(d)==0 && !refs[1] && !g_hp_dev && !queries);
 d=make(130);d->nring_pool=2;d->nring_retired=1;
 d->ring_pool=calloc(2,sizeof *d->ring_pool);d->ring_retired=calloc(1,sizeof *d->ring_retired);
 d->ring_pool[0].buf=200;d->ring_pool[1].buf=201;d->ring_retired[0].buf=202;
 refs[200]=refs[201]=refs[202]=1;
 assert(device_Release(d)==0 && freed_memory==130 && !queries);
 for(unsigned i=0;i<512;i++)assert(!refs[i]);
 d=make(3);completed=2;mad_mheap_reclaim(d,0);
 assert(queries==1 && d->nmhret==2 && freed_memory==131 && refs[1]);
 assert(device_Release(d)==0 && queries==1 && freed_memory==133);
 puts("PASS: production empty-device teardown, 130 retired heaps, ring release, GPU-gated normal reclamation and healthy/removed/failed status; fake Metal, ASan/UBSan");
}
'''
with tempfile.TemporaryDirectory(prefix="madeira-d3d12-lifetime-") as folder:
    p = Path(folder)
    (p / "test.c").write_text(source)
    subprocess.run(["xcrun", "clang", "-std=c11", "-fsanitize=address,undefined",
                    str(p / "test.c"), "-o", str(p / "test")], check=True)
    subprocess.run([str(p / "test")], check=True)

# Verify the method is installed in the real device vtable, not just test code.
assert "g_device_vtbl.GetDeviceRemovedReason = device_GetDeviceRemovedReason;" in c
