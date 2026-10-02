"""Exercise production bounded CPU/GPU accounting with synthetic Mach data."""
from pathlib import Path
import subprocess
import tempfile
root = Path(__file__).resolve().parents[1]
text = (root/'app/Madeira/PerformanceDiagnostics.m').read_text()
a=text.index('static double hottest_thread(');b=text.index('static void report(',a)
source=r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include "PerformanceMath.h"
#define THREAD_CAPACITY 512
#define THREAD_BASIC_INFO_COUNT 1
#define THREAD_IDENTIFIER_INFO_COUNT 2
#define THREAD_EXTENDED_INFO_COUNT 3
#define THREAD_EXTENDED_INFO 3
#define THREAD_BASIC_INFO 1
#define THREAD_IDENTIFIER_INFO 2
#define KERN_SUCCESS 0
typedef unsigned *thread_act_array_t;
typedef unsigned mach_msg_type_number_t;
typedef uintptr_t vm_address_t;
typedef void *thread_info_t;
typedef struct {struct {long seconds,microseconds;} user_time,system_time;} thread_basic_info_data_t;
typedef struct {char pth_name[64];} thread_extended_info_data_t;
typedef struct {uint64_t thread_id;} thread_identifier_info_data_t;
struct thread_sample {uint64_t id;double cpu;};
static struct thread_sample old_threads[THREAD_CAPACITY];static unsigned old_thread_count;
static double role_cpu[MADEIRA_ROLE_COUNT];
static unsigned hottest_role, unnamed_threads;
static unsigned count=3,rights=0,arrays=0,rounds=0,fail=0;
static unsigned mach_task_self(void){return 1;}
static int task_threads(unsigned task,thread_act_array_t *out,unsigned *n){
 (void)task;*out=malloc(count*sizeof(unsigned));*n=count;++arrays;
 for(unsigned i=0;i<count;i++)(*out)[i]=i+1;rights+=count;return 0;
}
static int thread_info(unsigned port,unsigned kind,void *out,unsigned *n){
 (void)n;if(fail && port==2)return 1;
 if(kind==1){thread_basic_info_data_t *v=out;memset(v,0,sizeof *v);v->user_time.seconds=rounds*port;}
 else if(kind==2) ((thread_identifier_info_data_t *)out)->thread_id=port;
 else {thread_extended_info_data_t *v=out;memset(v,0,sizeof *v);strcpy(v->pth_name,port==3 ? "dxmt-encode-thread" : "GameThread");}
 return 0;
}
static void mach_port_deallocate(unsigned task,unsigned port){(void)task;(void)port;assert(rights);--rights;}
static void vm_deallocate(unsigned task,uintptr_t ptr,unsigned bytes){(void)task;(void)bytes;free((void *)ptr);assert(arrays);--arrays;}
'''+text[a:b]+r'''
int main(void){
 struct madeira_gpu_span spans[]={{8,12},{3,5},{1,4},{4,8},{NAN,10},{-20,-1},{7,7},{0,INFINITY}};
 assert(fabs(madeira_gpu_busy(spans,8,2,10)-8)<1e-12);
 struct madeira_gpu_span overlap[]={{3,4},{1,2},{1.5,3.5}};
 assert(madeira_gpu_busy(overlap,3,0,5)==3);
 assert(madeira_gpu_busy(overlap,3,5,5)==0);
 assert(madeira_cpu_seconds(2,900000,1,500000)==4.4);
 unsigned n=0,partial=0;
 assert(hottest_thread(10,&n,&partial)==0 && n==3 && partial && !rights && !arrays);
 rounds=1;partial=0;
 assert(hottest_thread(10,&n,&partial)==.3 && !partial && !rights && !arrays);
 assert(hottest_role==MADEIRA_ROLE_ENCODE && role_cpu[MADEIRA_ROLE_ENCODE]==.3);
 assert(fabs(role_cpu[MADEIRA_ROLE_GAME]-.3)<1e-12);
 assert(madeira_thread_role("dxmt-encode-thr")==MADEIRA_ROLE_ENCODE);
 assert(madeira_thread_role("dxmt-finish-thr")==MADEIRA_ROLE_FINISH);
 assert(madeira_thread_role("dxmt-finish-thread")==MADEIRA_ROLE_FINISH);
 assert(madeira_thread_role("private-account-name")==MADEIRA_ROLE_OTHER);
 assert(madeira_thread_role("RHIThread")==MADEIRA_ROLE_RHI && madeira_thread_role("RenderThread 2")==MADEIRA_ROLE_RENDER);
 rounds=2;fail=1;partial=0;
 assert(hottest_thread(10,&n,&partial)==.3 && partial && !rights && !arrays);
 count=600;fail=0;partial=0;rounds=3;
 hottest_thread(10,&n,&partial);assert(partial && n==600 && old_thread_count==512 && !rights && !arrays);
 puts("PASS: GPU overlap/invalid timestamps/clipping, CPU deltas, failed Mach queries and bounded samples release every right and array");
}
'''
with tempfile.TemporaryDirectory() as folder:
 p=Path(folder);(p/'test.c').write_text(source)
 subprocess.run(['xcrun','clang','-std=c11','-fsanitize=address,undefined','-I'+str(root/'app/Madeira'),str(p/'test.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
# Native sampling is confined to commit/completion and an optional wait timer.
wmt=(root/'dxmt/src/winemetal/unix/winemetal_unix.c').read_text()
assert 'madeira_perf_gpu(buffer.GPUStartTime, buffer.GPUEndTime' in wmt
assert 'if (madeira_perf_enabled())' in wmt
assert '10 * NSEC_PER_SEC' in text and 'task_suspend(' not in text and 'thread_suspend(' not in text
