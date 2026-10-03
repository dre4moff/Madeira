"""Exercise upstream guest RWX and cage policies alongside the fork allocator."""
from pathlib import Path
import subprocess
import tempfile
root = Path(__file__).resolve().parents[1]
s = (root / 'build/ntdll-unix/virtual_ios.c').read_text()
a = s.index('static int ios_alloc_ec_code;')
policy = s[a:s.index('static inline int mprotect_exec(', a)]
a = s.index('static int ios_cage_release_on_exhaustion(')
cage = s[a:s.index('static ULONG_PTR ios_wow_window_pick(', a)]
code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>
#define WINE_IOS 1
#define ULONG_PTR uintptr_t
#define VPROT_WRITE 2
#define VPROT_EXEC 4
#define SEC_IMAGE 8
#define VPROT_ARM64EC 16
#define VPROT_SYSTEM 32
#define SEC_FILE 64
#define SEC_RESERVE 128
#define SEC_COMMIT 256
struct file_view { void *base; size_t size; unsigned protect; };
static struct file_view views[4];
static int is_view_valloc(const struct file_view *v){return !(v->protect&(SEC_FILE|SEC_RESERVE|SEC_COMMIT));}
static struct file_view *find_view(const void *p,size_t n){
 (void)n;for(unsigned i=0;i<4;i++)if((uintptr_t)p>=(uintptr_t)views[i].base && (uintptr_t)p<(uintptr_t)views[i].base+views[i].size)return &views[i];return NULL;
}
static int arm64ec_view=1,alias;
void *ios_jit_rx_base_global=(void*)0x119000000ULL;
size_t ios_jit_pool_size_global=0x8000000;
int ios_jit_anon_alias_find_cover(void *p,size_t n,void **rw,void **rx){(void)p;(void)n;(void)rw;(void)rx;return alias;}
#define IOS_CAGE_BASE 0x7200000000ULL
#define IOS_CAGE_REAL_SIZE 0x1ffff0000ULL
static int ios_cage_holdback_live=1,grants;
static uintptr_t reserved_base;static size_t reserved_size;
static size_t ios_wow_guard_size(void){return 0x4000;}
static void mmap_add_reserved_area(void *p,size_t n){++grants;reserved_base=(uintptr_t)p;reserved_size=n;}
''' + policy + cage + r'''
int main(int argc,char **argv){
 (void)argv;
 views[0]=(struct file_view){(void*)0x7050000000ULL,0x41000,VPROT_WRITE|VPROT_EXEC};
 uintptr_t b=(uintptr_t)views[0].base;
 if(argc>1){setenv("MADEIRA_GUEST_RWX_DATA","0",1);assert(!ios_guest_anon_rwx_is_host_data((void*)b,0x44000));return 0;}
 assert(ios_guest_anon_rwx_is_host_data((void*)b,0x44000));
 assert(!ios_guest_anon_rwx_is_host_data((void*)b,0));
 unsigned deny[]={SEC_IMAGE,VPROT_ARM64EC,VPROT_SYSTEM,SEC_FILE,SEC_RESERVE,SEC_COMMIT};
 for(unsigned i=0;i<6;i++){views[0].protect|=deny[i];assert(!ios_guest_anon_rwx_is_host_data((void*)b,0x44000));views[0].protect&=~deny[i];}
 views[0].protect=VPROT_EXEC;assert(!ios_guest_anon_rwx_is_host_data((void*)b,0x44000));views[0].protect=VPROT_WRITE|VPROT_EXEC;
 views[0].size=0x100000;assert(!ios_guest_anon_rwx_is_host_data((void*)b,0x100000));
 views[0].size=0x5000;assert(!ios_guest_anon_rwx_is_host_data((void*)b,0x5000));views[0].size=0x41000;
 arm64ec_view=0;assert(!ios_guest_anon_rwx_is_host_data((void*)b,0x44000));arm64ec_view=1;
 ios_alloc_ec_code=1;assert(!ios_guest_anon_rwx_is_host_data((void*)b,0x44000));ios_alloc_ec_code=0;
 alias=1;assert(!ios_guest_anon_rwx_is_host_data((void*)b,0x44000));alias=0;
 views[0].base=ios_jit_rx_base_global;assert(!ios_guest_anon_rwx_is_host_data(views[0].base,0x44000));views[0].base=(void*)b;
 views[1]=(struct file_view){(void*)(b+0x41000),0x1000,SEC_IMAGE|VPROT_WRITE|VPROT_EXEC};
 assert(!ios_guest_anon_rwx_is_host_data((void*)b,0x44000));views[1].size=0;
 assert(!ios_cage_release_on_exhaustion((void*)IOS_CAGE_BASE,(void*)(IOS_CAGE_BASE+IOS_CAGE_REAL_SIZE),0x100000));
 setenv("MADEIRA_CAGE_RELEASE","1",1);
 assert(!ios_cage_release_on_exhaustion((void*)0,(void*)IOS_CAGE_BASE,0x100000));
 assert(!ios_cage_release_on_exhaustion((void*)IOS_CAGE_BASE,(void*)(IOS_CAGE_BASE+0x5000),0x100000));
 assert(ios_cage_release_on_exhaustion((void*)IOS_CAGE_BASE,(void*)(IOS_CAGE_BASE+IOS_CAGE_REAL_SIZE),0x100000));
 assert(grants==1 && !ios_cage_holdback_live && reserved_base==IOS_CAGE_BASE+0x4000 && reserved_size==IOS_CAGE_REAL_SIZE-0x4000);
 assert(!ios_cage_release_on_exhaustion((void*)IOS_CAGE_BASE,(void*)(IOS_CAGE_BASE+IOS_CAGE_REAL_SIZE),0x100000));
 puts("PASS: production guest RWX heap policy excludes images, native/JIT/file/code pages and neighbors; opt-out honored; cage release is opt-in, range-bounded, one-shot and retains guard page");
}
'''
with tempfile.TemporaryDirectory(prefix='madeira-v013-memory-') as tmp:
 p=Path(tmp);(p/'test.c').write_text(code)
 subprocess.run(['clang','-fsanitize=address,undefined',str(p/'test.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
 subprocess.run([str(p/'test'),'off'],check=True)
