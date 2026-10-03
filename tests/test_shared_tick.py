"""Real server clock publication: Windows-scaled ticks and Wine APIs agree."""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parents[1]
source=(root/'build/wineserver/fd_ios.c').read_text()
fn=source[source.index('void set_current_time(void)'):source.index('/* add a timeout user */')]
c=r'''
#include <stdint.h>
#include <assert.h>
#include <sys/time.h>
#include <stdio.h>
#include "timezone_bias.h"
#include "shared_tick.h"
#define WINE_IOS 1
#define TICKS_PER_SEC 10000000LL
typedef int64_t timeout_t;
struct shared_time {int32_t High2Time;uint32_t LowPart;int32_t High1Time;};
struct shared_data {uint32_t TickCountMultiplier;struct shared_time SystemTime,TimeZoneBias,InterruptTime,TickCount;uint32_t TickCountLowDeprecated;};
static struct shared_data page,*user_shared_data=&page;
static timeout_t current_time,monotonic_time,counter;
int64_t madeira_timezone_bias_ticks=-72000000000LL;
static timeout_t monotonic_counter(void){return counter;}
static int ios_usd_time_enabled(void){return 1;}
static void atomic_store_long(int32_t *p,int64_t v){*p=(int32_t)v;}
static void atomic_store_ulong(uint32_t *p,int64_t v){*p=(uint32_t)v;}
''' + fn + r'''
static uint64_t combine(struct shared_time *t){assert(t->High1Time==t->High2Time);return ((uint64_t)(uint32_t)t->High1Time<<32)|t->LowPart;}
int main(void){
 uint64_t ticks[]={1,280100661,0xffffffffULL,0x100000000ULL,0x123456789ULL};
 for(unsigned i=0;i<sizeof ticks/sizeof *ticks;i++){
  counter=(timeout_t)ticks[i]*10000;set_current_time();
  uint64_t raw=combine(&page.TickCount);
  uint64_t windows=(((uint64_t)page.TickCount.LowPart*page.TickCountMultiplier)>>24)+
      (((uint64_t)(uint32_t)page.TickCount.High1Time*page.TickCountMultiplier)<<8);
  assert(raw==ticks[i]&&windows==raw&&page.TickCountLowDeprecated==(uint32_t)raw);
  assert(page.TickCountMultiplier==0x1000000&&combine(&page.InterruptTime)==(uint64_t)counter);
  assert((int64_t)combine(&page.TimeZoneBias)==madeira_timezone_bias_ticks);
  assert((int64_t)combine(&page.SystemTime)==current_time);
 }
 user_shared_data=NULL;set_current_time();
 puts("PASS: production shared clock publication, identity Q24 scaling, rollover, UTC/bias/interrupt times and null-page guard; no clock spoofing");
}
'''
with tempfile.TemporaryDirectory(prefix='madeira-shared-tick-') as folder:
 p=Path(folder);(p/'test.c').write_text(c)
 subprocess.run(['clang','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I',str(root/'build/wineserver'),str(p/'test.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
