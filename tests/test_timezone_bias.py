"""Exercise the real shared-clock timezone snapshot without running Wine."""
from pathlib import Path
import subprocess
import tempfile
root=Path(__file__).resolve().parents[1]
c=r'''
#include <assert.h>
#include <stdlib.h>
#include <pthread.h>
#include <stdio.h>
#include "timezone_bias.h"
int64_t madeira_timezone_bias_ticks;
static void check(const char *zone,int64_t stamp,long seconds_east){
    setenv("TZ",zone,1);tzset();
    time_t t=stamp;struct tm tm;assert(localtime_r(&t,&tm));
    assert(tm.tm_gmtoff==seconds_east);
    int64_t bias=madeira_timezone_bias_from_seconds(tm.tm_gmtoff);
    assert(bias==-(int64_t)seconds_east*10000000);
    int64_t utc=stamp*10000000,local=utc-bias;
    assert(local+bias==utc&&local/10000000==stamp+seconds_east);
    assert(madeira_update_timezone_bias());
    time_t now=time(NULL);assert(localtime_r(&now,&tm));
    assert(madeira_cached_timezone_bias()==madeira_timezone_bias_from_seconds(tm.tm_gmtoff));
}
static void *reader(void *unused){
    (void)unused;
    for(int i=0;i<100000;i++)assert(madeira_cached_timezone_bias()==-207000000000LL);
    return NULL;
}
int main(void){
    check("UTC",1704067200,0);
    check("Europe/Rome",1704067200,3600);check("Europe/Rome",1719792000,7200);
    check("America/New_York",1704067200,-18000);check("America/New_York",1719792000,-14400);
    check("Asia/Kolkata",1704067200,19800);check("Asia/Kathmandu",1719792000,20700);
    pthread_t workers[8];for(int i=0;i<8;i++)assert(!pthread_create(&workers[i],NULL,reader,NULL));
    for(int i=0;i<10000;i++)assert(madeira_update_timezone_bias());
    for(int i=0;i<8;i++)assert(!pthread_join(workers[i],NULL));
    puts("PASS: UTC, winter/summer DST, positive/negative/fractional zones, local/UTC identity, concurrent cached readers/refresh");
}
'''
with tempfile.TemporaryDirectory(prefix='madeira-timezone-') as folder:
    p=Path(folder);(p/'test.c').write_text(c)
    subprocess.run(['clang','-Wall','-Wextra','-Werror','-pthread','-fsanitize=address,undefined','-I',str(root/'build/wineserver'),str(p/'test.c'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)
fd=(root/'build/wineserver/fd_ios.c').read_text()
loop=fd[fd.index('void set_current_time(void)'):fd.index('/* add a timeout user */')]
assert 'madeira_cached_timezone_bias()' in loop
for call in ('localtime(', 'localtime_r(', 'gmtime(', 'mktime(', 'tzset(', 'wine_refresh_timezone('):
    assert call not in loop
sequence=['TimeZoneBias.High2Time','TimeZoneBias.LowPart','TimeZoneBias.High1Time']
assert [loop.index(s) for s in sequence]==sorted(loop.index(s) for s in sequence)
bridge=(root/'app/Madeira/WineServerBridge.m').read_text()
assert 'NSSystemTimeZoneDidChangeNotification' in bridge and 'UIApplicationSignificantTimeChangeNotification' in bridge
assert bridge.index('wine_refresh_timezone();',bridge.index('int wineserver_start('))<bridge.index('pthread_create(',bridge.index('int wineserver_start('))
print('PASS: real shared-page publication sequence and startup/live timezone refresh, no libc timezone work added to server event loop')
