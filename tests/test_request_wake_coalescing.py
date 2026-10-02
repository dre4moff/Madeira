"""Exercise production wake code with real host Mach semaphores, no Wine/game."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / 'build/wineserver/fd_ios.c').read_text()
a = source.index('semaphore_t ios_srv_wake_sem = 0;')
b = source.index('\n/* __WINESRC__', a)
production = source[a:b]
fixture = r'''
#include <assert.h>
#include <pthread.h>
#include <mach/mach.h>
#include <mach/semaphore.h>
#include <stdio.h>
#include <unistd.h>
#include "request_wake_gate.h"
static unsigned signals;
static kern_return_t counted_signal(semaphore_t sem) {
    __atomic_add_fetch(&signals, 1, __ATOMIC_RELAXED);
    return semaphore_signal(sem);
}
#define semaphore_signal counted_signal
''' + production + r'''
#undef semaphore_signal
static unsigned work, done;
static void *producer(void *unused) {
    (void)unused;
    for (unsigned i=0; i<10000; i++) {
        __atomic_add_fetch(&work, 1, __ATOMIC_RELEASE);
        ios_wineserver_wake();
        if (!(i % 64)) usleep(10);
    }
    __atomic_add_fetch(&done, 1, __ATOMIC_RELEASE);
    return NULL;
}
static int consume(unsigned ns) {
    mach_timespec_t timeout={0, ns};
    kern_return_t result=semaphore_timedwait(ios_srv_wake_sem, timeout);
    if (result==KERN_SUCCESS) madeira_request_wake_consumed(&ios_srv_wake_gate);
    return result==KERN_SUCCESS;
}
int main(void) {
    assert(semaphore_create(mach_task_self(), &ios_srv_wake_sem, SYNC_POLICY_FIFO, 0)==KERN_SUCCESS);
    for (unsigned i=0;i<100000;i++) ios_wineserver_wake();
    assert(signals==1 && consume(0) && !consume(0));
    // A producer paused between claim and signal must keep its claim on timeout.
    assert(madeira_request_wake_claim(&ios_srv_wake_gate));
    assert(!consume(0) && !madeira_request_wake_claim(&ios_srv_wake_gate));
    assert(semaphore_signal(ios_srv_wake_sem)==KERN_SUCCESS && consume(0));
    pthread_t clients[8]; unsigned seen=0;
    for (unsigned i=0;i<8;i++) assert(!pthread_create(&clients[i],NULL,producer,NULL));
    for (unsigned scans=0; scans<200000 && seen<80000; scans++) {
        consume(1000000);
        seen += __atomic_exchange_n(&work,0,__ATOMIC_ACQ_REL);
    }
    for (unsigned i=0;i<8;i++) assert(!pthread_join(clients[i],NULL));
    seen += __atomic_exchange_n(&work,0,__ATOMIC_ACQ_REL);
    assert(seen==80000 && done==8);
    while (consume(0)) {}
    // Preserve immediate signaling for a request posted after a scan starts.
    ios_wineserver_wake(); assert(consume(0));
    ios_wineserver_wake(); assert(consume(0));
    // A/B opt-out keeps the original counting behavior.
    ios_srv_coalesce=0; unsigned before=signals;
    for (unsigned i=0;i<100;i++) ios_wineserver_wake();
    assert(signals-before==100);
    for (unsigned i=0;i<100;i++) assert(consume(0));
    assert(!consume(0));
    assert(semaphore_destroy(mach_task_self(),ios_srv_wake_sem)==KERN_SUCCESS);
    puts("PASS: 100000 queued notifications -> 1 signal; 8 producers / 80000 work items delivered; timeout race, during-scan wake, opt-out preserved");
}
'''
with tempfile.TemporaryDirectory(prefix='madeira-wake-') as folder:
    p = Path(folder)
    (p / 'test.c').write_text(fixture)
    subprocess.run(['xcrun', 'clang', '-O2', '-Wall', '-Wextra', '-fsanitize=address,undefined',
                    '-I' + str(root / 'build/wineserver'), str(p / 'test.c'), '-o', str(p / 'test')], check=True)
    subprocess.run([str(p / 'test')], check=True, timeout=30)
