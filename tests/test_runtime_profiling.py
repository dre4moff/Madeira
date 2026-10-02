"""Execute production profiling gates with mocked worker/timer dispatch only."""
from pathlib import Path
import subprocess, tempfile
root = Path(__file__).resolve().parents[1]
server = (root/'build/ntdll-unix/server_ios.c').read_text()
start = server.index('        if (madeira_runtime_profiling_enabled() &&')
end = server.index('        if (madeira_runtime_profiling_enabled())', start)
arm = server[start:end]
assert 'if (!getenv("MADEIRA_QUIET"))' not in server
winios = (root/'app/Madeira/Winios/Winios.m').read_text()
start = winios.index('    static dispatch_source_t stack_timer;')
end = winios.index('\n}\n', start)
timer = winios[start:end]
assert 'madeira_runtime_profiling_enabled() && !stack_timer' in timer
c = r'''
#include <assert.h>
#include <stdio.h>
#include "runtime_profiling.h"
static int ios_ts_armed, workers, timers;
static void ios_thread_sampler_main(void) { workers++; }
static void ios_xprobe_main(void) { workers++; }
static void ios_wprof_main(void) { workers++; }
#define dispatch_async(q, work) ((work)())
typedef int dispatch_source_t;
#define dispatch_source_create(a,b,c,d) (++timers)
#define dispatch_source_set_timer(a,b,c,d) ((void)0)
#define dispatch_source_set_event_handler(a,b) ((void)0)
#define dispatch_resume(a) ((void)0)
static void arm_workers(void) {
''' + arm + r'''
}
static void arm_stacks(void) {
''' + timer + r'''
}
static void settings(const char *quiet, const char *choice) {
 unsetenv("MADEIRA_QUIET"); unsetenv("MADEIRA_RUNTIME_PROFILING");
 if (quiet) setenv("MADEIRA_QUIET", quiet, 1);
 if (choice) setenv("MADEIRA_RUNTIME_PROFILING", choice, 1);
}
int main(void) {
 settings("1", NULL); assert(!madeira_runtime_profiling_enabled());
 arm_workers(); arm_stacks(); assert(!workers && !timers && !ios_ts_armed);
 settings(NULL,"0"); assert(!madeira_runtime_profiling_enabled());
 arm_workers(); arm_stacks(); assert(!workers && !timers);
 settings("1","bad"); assert(!madeira_runtime_profiling_enabled());
 settings("1","1"); assert(madeira_runtime_profiling_enabled());
 arm_workers(); arm_stacks(); assert(workers==3 && timers==1);
 arm_workers(); arm_stacks(); assert(workers==3 && timers==1); // one task-wide set
 settings(NULL,NULL); assert(madeira_runtime_profiling_enabled());
 settings("0",NULL); assert(madeira_runtime_profiling_enabled());
 settings("1",""); assert(!madeira_runtime_profiling_enabled());
 puts("PASS: actual quiet/explicit profiling gates, three workers, stack timer, opt-in/out and once-only dispatch; no profiler executed");
}
'''
with tempfile.TemporaryDirectory(prefix='madeira-profiling-') as tmp:
 p=Path(tmp); (p/'check.c').write_text(c)
 subprocess.run(['clang','-std=c11','-fblocks','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I',str(root/'build/ntdll-unix'),str(p/'check.c'),'-o',str(p/'check')],check=True)
 subprocess.run([str(p/'check')],check=True)
