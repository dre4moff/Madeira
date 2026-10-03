"""Production early constructor with mocked Mach map; never touches live VM."""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parents[1]
s=(root/'app/Madeira/JITAllocator.c').read_text()
a=s.index('unsigned long madeira_early_window_base');b=s.index('\n}',s.index('static void madeira_early_va_claim',a))+2
code=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include "jit_reservation_policy.h"
typedef uint64_t vm_address_t;typedef uint64_t vm_size_t;typedef int kern_return_t;typedef unsigned mach_port_t;typedef unsigned mach_msg_type_number_t;typedef unsigned natural_t;typedef void *vm_region_info_t;typedef void *vm_region_recurse_info_t;
typedef struct {int unused;} vm_region_basic_info_data_64_t;
typedef struct {unsigned user_tag,protection;} vm_region_submap_info_data_64_t;
#define KERN_SUCCESS 0
#define KERN_INVALID_ADDRESS 1
#define VM_FLAGS_FIXED 0
#define VM_PROT_NONE 0
#define VM_REGION_BASIC_INFO_COUNT_64 1
#define VM_REGION_BASIC_INFO_64 1
#define VM_REGION_SUBMAP_INFO_COUNT_64 1
#define MACH_PORT_NULL 0
static int mode, attempts, released, ports;
static int mach_task_self(void){return 1;}
static int vm_allocate(int task,vm_address_t *a,vm_size_t size,int flags){assert(task==1 && flags==0);if(*a==0x140000000)return 0;++attempts;assert(*a>=0x119000000 && *a+size<=0x200000000);return mode==1?3:0;}
static int vm_protect(int task,vm_address_t a,vm_size_t size,int maximum,int protection){(void)task;(void)size;assert(!maximum && !protection);return mode==2 && a!=0x140000000?5:0;}
static int vm_deallocate(int task,vm_address_t a,vm_size_t size){(void)task;(void)size;assert(a!=0x149d00000);++released;return 0;}
static int mach_port_deallocate(int task,mach_port_t object){assert(task==1 && object==7);++ports;return 0;}
static int vm_region_64(int task,vm_address_t *a,vm_size_t *len,int flavor,vm_region_info_t info,mach_msg_type_number_t *count,mach_port_t *object){(void)task;(void)flavor;(void)info;(void)count;*object=7;
 if(mode==3)return 5;
 if(*a<0x148000000){*a=0x140000000;*len=0x8000000;return 0;}
 if(*a<=0x149d00000){*a=0x149d00000;*len=0x10000;return 0;}
 return KERN_INVALID_ADDRESS;
}
static int vm_region_recurse_64(int t,vm_address_t *a,vm_size_t *s,natural_t *d,vm_region_recurse_info_t i,mach_msg_type_number_t *n){(void)t;(void)a;(void)s;(void)d;(void)i;(void)n;return 5;}
'''+s[a:b].replace('__attribute__((constructor(101), used)) ','')+r'''
int main(void){
 for(mode=0;mode<4;mode++){
  madeira_early_pool_base=madeira_early_pool_size=0;attempts=released=ports=0;madeira_early_va_claim();
  assert(madeira_early_window_base==0x140000000 && madeira_early_window_size==0x8000000);
  if(mode==0){assert(madeira_early_pool_base==0x149d10000 && madeira_early_pool_size==(1152ull<<20));assert(attempts==1 && released==0 && ports==3);}
  else {assert(!madeira_early_pool_base && !madeira_early_pool_size);if(mode==1)assert(attempts==3 && released==0);if(mode==2)assert(attempts==3 && released==3);if(mode==3)assert(attempts==0);}
 }
 uint64_t base=0,size=0;madeira_consider_pool_hole(0,UINT64_MAX,&base,&size);assert(base==0x119000000 && size==(1152ull<<20));base=size=0;madeira_consider_pool_hole(0x1ff000000,0x7000000000,&base,&size);assert(!size);madeira_consider_pool_hole(0x149d00001,0x16ad00000,&base,&size);assert(!(base&0x3fff) && !(size&((16ull<<20)-1)));
 puts("PASS: actual constructor, tiny intruder, bounded largest native hole, guest-band exclusion, fixed no-overwrite, races/retries, protection failure cleanup, unknown Mach errors and object ports");
}
'''
with tempfile.TemporaryDirectory(prefix='madeira-jit-reservation-') as folder:
 p=Path(folder);(p/'test.c').write_text(code)
 subprocess.run(['clang','-fsanitize=address,undefined','-I'+str(root/'app/Madeira'),str(p/'test.c'),'-o',str(p/'test')],check=True);subprocess.run([str(p/'test')],check=True)
