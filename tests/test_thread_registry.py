"""Replay cumulative worker exhaustion and the observed Mono return epilogue.

Compiles the production host functions with mocked Mach calls, under ASan/UBSan.
No game, Wine process, Steam session, or microphone is started.
"""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
current = (root / 'build/ntdll-unix/signal_arm64_ios.c').read_text()
old = (root / 'tests/fixtures/thread_registry_r26.c').read_text()
def registry(s):
    a = s.index('#define IOS_MAX_WINE_THREADS')
    return s[a:s.index('/* ml398 (task #60)', a)]
a = old.index('    /* Register this thread in the registry.', old.index('static void ios_setup_mach_exception_handler'))
b = old.index('    /* Set exception port for this thread', a)
old_register = 'static int ios_register_thread(thread_t pe_thread, uintptr_t teb, void *trampoline) {\n' + old[a:b] + '\nreturn idx;\n}\n'
stub = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <pthread.h>
typedef unsigned thread_t;
typedef int kern_return_t;
typedef unsigned mach_msg_type_number_t;
typedef void *thread_info_t;
typedef uint64_t mach_vm_address_t, mach_vm_size_t;
struct thread_basic_info { int dummy; };
#define KERN_SUCCESS 0
#define KERN_INVALID_ARGUMENT 1
#define MACH_SEND_INVALID_DEST 2
#define KERN_TERMINATED 3
#define THREAD_BASIC_INFO 0
#define THREAD_BASIC_INFO_COUNT 1
#define MACH_PORT_RIGHT_SEND 0
#define ERR(...) ((void)0)
static int life[12000], refs[12000], deallocations, pin_failure;
static unsigned mach_task_self(void){return 1;}
static int thread_info(thread_t port,int flavor,thread_info_t out,unsigned *size){
 (void)flavor;(void)out;(void)size;assert(port<12000);return life[port];
}
static int mach_port_mod_refs(unsigned task,thread_t port,int right,int delta){
 (void)task;(void)right;if(pin_failure)return 99;refs[port]+=delta;return 0;
}
static int mach_port_deallocate(unsigned task,thread_t port){
 (void)task;assert(refs[port]>0);refs[port]--;deallocations++;return 0;
}
static uint32_t code[3]={0xd63f0080,0xf94bc64b,0x3900057f};
static uint64_t pc=0x13e1fbf48ULL, teb=0x70947e0000ULL, area=0x70a3c40000ULL, frame=0x7f7d001140ULL;
static unsigned char callback=1;
static int read_failure;
static int mach_vm_read_overwrite(unsigned task,uint64_t addr,uint64_t n,uint64_t dest,uint64_t *got){
 (void)task;*got=0;if(read_failure)return 99;
 const void *p=NULL;
 if(addr==pc-8&&n==sizeof(code))p=code;
 if(addr==teb+0x1788&&n==8)p=&area;
 if(addr==area+0x30&&n==8)p=&frame;
 if(addr==area+1&&n==1)p=&callback;
 if(!p)return 99;memcpy((void*)(uintptr_t)dest,p,n);*got=n;return 0;
}
static uintptr_t own_teb(unsigned p){return 0x100000000ULL+(uintptr_t)p*0x10000;}
'''
before = r'''
int main(void){
 for(unsigned p=1;p<=600;p++) {
  life[p]=0;ios_register_thread(p,own_teb(p),(void*)own_teb(p));
  if(p>64)life[p-64]=KERN_TERMINATED;
 }
 uintptr_t t;void *tr;
 assert(ios_thread_count==600);
 assert(ios_lookup_thread(600,&t,&tr));
 assert(t==own_teb(1)&&t!=own_teb(600));
 puts("REPRODUCED r26: 600 starts / 64 live workers -> missing registration, foreign slot-0 TEB");
}
'''
after = r'''
static void reset(void){
 ios_thread_registry_purge_range(0,UINTPTR_MAX);
 memset(ios_thread_registry,0,sizeof(ios_thread_registry));ios_thread_count=0;
 memset(life,0,sizeof(life));memset(refs,0,sizeof(refs));
}
int main(void){
 uintptr_t t;void *tr;
 for(unsigned p=1;p<=4000;p++) {
  life[p]=0;
  if(p>64)life[p-64]=KERN_TERMINATED;
  assert(ios_register_thread(p,own_teb(p),(void*)(own_teb(p)+32))>=0);
  assert(ios_lookup_thread(p,&t,&tr)&&t==own_teb(p)&&tr==(void*)(t+32));
 }
 assert(ios_thread_count==64&&deallocations==(4000-64)*4);
 assert(!ios_lookup_thread(1,&t,&tr)&&!t&&!tr);
 assert(!ios_lookup_thread(9000,&t,&tr)&&!ios_thread_is_registered(9000));
 assert(ios_register_thread(4000,own_teb(4000)+1,(void*)1)>=0&&refs[4000]==4);
 assert(ios_lookup_thread(4000,&t,&tr)&&t==own_teb(4000)+1);
 reset();
 for(unsigned p=1;p<=512;p++)assert(ios_register_thread(p,own_teb(p),(void*)1)>=0);
 assert(ios_register_thread(513,own_teb(513),(void*)1)<0&&ios_thread_count==512);
 assert(!ios_lookup_thread(513,&t,&tr)&&!t);
 life[1]=99;assert(ios_register_thread(513,own_teb(513),(void*)1)<0);
 life[1]=KERN_INVALID_ARGUMENT;assert(ios_register_thread(513,own_teb(513),(void*)1)==0);
 assert(!refs[1]&&refs[513]==4);
 assert(ios_thread_registry_purge_range(own_teb(513),1)==1);
 assert(!ios_thread_is_registered(513)&&!ios_teb_is_registered(own_teb(513)));
 pin_failure=1;assert(ios_register_thread(514,own_teb(514),(void*)1)==0);pin_failure=0;
 life[514]=MACH_SEND_INVALID_DEST;
 assert(ios_register_thread(515,own_teb(515),(void*)1)==0);
 assert(refs[514]==0&&refs[515]==4);
 struct ios_thread_entry snap;
 __atomic_fetch_add(&ios_thread_registry[0].generation,1,__ATOMIC_ACQ_REL);
 assert(!ios_thread_snapshot(0,&snap));
 __atomic_fetch_add(&ios_thread_registry[0].generation,1,__ATOMIC_RELEASE);
 reset();
 uint64_t g[29]={0},saved[29];g[28]=frame;g[17]=0x48ad;memcpy(saved,g,sizeof(g));
 assert(ios_repair_mono_callback_return(pc,1,teb,g));
 assert(g[11]==area&&g[18]==teb&&g[17]==saved[17]&&g[28]==frame);
 for(unsigned i=0;i<29;i++)if(i!=11&&i!=18)assert(g[i]==saved[i]);
 memcpy(g,saved,sizeof(g));
 assert(!ios_repair_mono_callback_return(pc,1,0,g));
 assert(!ios_repair_mono_callback_return(pc,2,teb,g));
 frame++;assert(!ios_repair_mono_callback_return(pc,1,teb,g));frame--;
 callback=0;assert(!ios_repair_mono_callback_return(pc,1,teb,g));callback=1;
 for(unsigned i=0;i<3;i++){code[i]^=1;assert(!ios_repair_mono_callback_return(pc,1,teb,g));code[i]^=1;}
 read_failure=1;assert(!ios_repair_mono_callback_return(pc,1,teb,g));read_failure=0;
 g[11]=area;assert(!ios_repair_mono_callback_return(pc,1,teb,g));
 puts("PASS: 4000 starts, live-only reuse, exact TEB, bounded full registry, no foreign fallback, Mach failures, pin balancing, purge, publication and exact Mono epilogue/StateFrame/flag guards");
}
'''
with tempfile.TemporaryDirectory(prefix='madeira-thread-registry-') as d:
    d=Path(d)
    for name,source,main in [('before',registry(old)+old_register,before),('after',registry(current),after)]:
        path=d/(name+'.c');path.write_text(stub+source+main)
        subprocess.run(['clang','-std=c11','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-pthread',str(path),'-o',str(d/name)],check=True)
        subprocess.run([str(d/name)],check=True)
