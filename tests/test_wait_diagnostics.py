"""Actual native wait registry hooks and heap-check block; fake TEB/clock/heap only."""
from pathlib import Path
import subprocess,tempfile,os,re
root=Path(__file__).resolve().parents[1]
s=(root/'build/ntdll-unix/server_ios.c').read_text()
start=s.index('struct ios_wait_entry\n')
block=s[start:s.index('\nunsigned int server_wait(',start)]
v=(root/'build/ntdll-unix/virtual_ios.c').read_text()
start=v.index('            {\n                extern boolean_t malloc_zone_check')
zone=v[start:v.index('\n\n            /* ml359',start)]
event=(root/'wine/server/event.c').read_text()
data_start=event.index('#define IOS_EVT_RING_N 1024')
data=event[data_start:event.index('\nvoid ios_evt_record(',data_start)]
record_start=event.index('void ios_evt_record( void *obj, void *sync, int op, int state )\n{')
record=event[record_start:event.index('\n/* Print every recorded operation',record_start)]
src=r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <time.h>
#include <sys/time.h>
#include "runtime_profiling.h"
#define IOS_WAITREG_SLOTS 512
#define UINT unsigned int
typedef int64_t timeout_t;
typedef size_t data_size_t;
typedef unsigned int obj_handle_t;
union select_op {unsigned int op; struct {unsigned int op;obj_handle_t handles[8];} wait;};
struct MockTEB {struct {void *UniqueThread;} ClientId;};
static struct MockTEB teb={{(void *)0x0038}};
static struct MockTEB *NtCurrentTeb(void) {return &teb;}
static unsigned clocks,heap_checks;
static int fake_clock(int clock,struct timespec *ts) {(void)clock;clocks++;ts->tv_sec=42;ts->tv_nsec=0;return 0;}
#define clock_gettime fake_clock
'''+block+data+r'''
struct event {int unused;};
static unsigned history_records;
static struct {unsigned id;} current_thread={0x38};
#define current (&current_thread)
static void ios_evt_stat(struct event *event,int op,unsigned status,unsigned seq) {(void)event;(void)op;(void)status;(void)seq;history_records++;}
'''+record+r'''
typedef int boolean_t;
#define malloc_zone_check fake_zone_check
boolean_t malloc_zone_check(malloc_zone_t *zone) {(void)zone;heap_checks++;return 1;}
static void heap_probe(void) {unsigned cycle=1;
'''+zone+r'''
}
int main(int argc,char **argv) {
 assert(argc==2);int profiling=argv[1][0]=='1';
 union select_op op={0};op.wait.op=1;op.wait.handles[0]=0x1234;
 for(unsigned i=0;i<100000;i++) {ios_wait_enter(&op,sizeof(op),3,500,(void *)123);ios_wait_leave();}
 struct ios_wait_entry *e=ios_wait_slot();
 assert(clocks==(profiling?100000:0));assert(e->seq==(profiling?200000:0));
 if(profiling)assert(e->t0_ns==42000000000ULL && e->handles[0]==0x1234);
 heap_probe();assert(heap_checks==(unsigned)profiling);
 struct event event={0};
 for(unsigned i=0;i<100000;i++)ios_evt_record(&event,NULL,IOS_EVT_SET,0);
 assert(history_records==(profiling?100000:0));assert(ios_evt_seq==(profiling?100000:0));
 assert(ios_evt_op_name[IOS_EVT_SET][0]=='S');
 puts(profiling?"PASS: event histories restored with diagnostic opt-in":"PASS: quiet event operations skip ring writes and lifetime diagnostic counters");
 puts(profiling?"PASS: opt-in restores wait records and heap validation":"PASS: 100000 quiet Wine waits skip diagnostic fences/stores/clock calls; whole-heap check also skipped");
}
'''
with tempfile.TemporaryDirectory(prefix='madeira-wait-diag-') as tmp:
 p=Path(tmp);(p/'test.c').write_text(src)
 subprocess.run(['clang','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I',str(root/'build/ntdll-unix'),str(p/'test.c'),'-o',str(p/'test')],check=True)
 for choice,enabled in [('0',False),('1',True)]:
  env=os.environ.copy();env['MADEIRA_RUNTIME_PROFILING']=choice;env['MADEIRA_QUIET']='1'
  subprocess.run([str(p/'test'),'1' if enabled else '0'],env=env,check=True)
assert 'madeira_runtime_profiling_enabled() && (cycle == 2 || (cycle % 5) == 0)' in v
assert 'madeira_runtime_profiling_enabled() && (cycle % 5) == 0 && rx' in v
assert 'if (madeira_runtime_profiling_enabled()) {\n                        static kern_return_t last[4]' in v
sig=(root/'build/ntdll-unix/signal_arm64_ios.c').read_text()
assert sig.index('ios_orphan_check( stamps, ns );') < sig.index('    if (!profiling) return;')
assert 'sink += rx[o]' in v and 'sink += rw[o]' in v
fd=(root/'build/wineserver/fd_ios.c').read_text();assert "qdump_on = madeira_runtime_profiling_enabled() && (d && *d == '1')" in fd
print('PASS: VM scan/allocation diagnostics gated, JIT alias warming and orphan-lock recovery retained')
