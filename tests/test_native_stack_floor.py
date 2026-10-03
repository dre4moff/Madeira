"""Replay the r25 voice-thread failure through production VM/stack functions.

Synthetic allocator only: no Wine process, guest executable or microphone runs.
The same harness also compiles the former boot-time reset to demonstrate the
failure before the fix, rather than merely checking the new source spelling.
"""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / "build/ntdll-unix/virtual_ios.c").read_text()

def function(start, end):
    begin = source.index(start)
    return source[begin:source.index(end, begin)]

boot = function("void virtual_set_large_address_space(void)", "/***********************************************************************")
view = function("static NTSTATUS map_view( struct file_view **view_ret", "/***********************************************************************")
stack = function("NTSTATUS virtual_alloc_thread_stack(", "static const WCHAR shared_data_nameW")
stub = r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <sys/mman.h>
#include <signal.h>
static int ios_cage_release_on_exhaustion(void *start, void *end, size_t want) { (void)start;(void)end;(void)want;return 0; }
#define WINE_IOS 1
#define _WIN64 1
#define BOOL int
#define TRUE 1
#define FALSE 0
#define NTSTATUS int
#define ULONG_PTR uintptr_t
#define SIZE_T size_t
#define STATUS_SUCCESS 0
#define STATUS_INVALID_PARAMETER 1
#define STATUS_CONFLICTING_ADDRESSES 2
#define STATUS_WORKING_SET_LIMIT_RANGE 3
#define STATUS_NO_MEMORY 4
#define MEM_REPLACE_PLACEHOLDER 1
#define MEM_TOP_DOWN 2
#define VPROT_READ 1
#define VPROT_WRITE 2
#define VPROT_COMMITTED 4
#define VPROT_GUARD 8
#define VPROT_FREE_PLACEHOLDER 16
#define VPROT_PLACEHOLDER 32
#define VPROT_WRITEWATCH 64
#define IMAGE_FILE_LARGE_ADDRESS_AWARE 32
#define TRACE(...) ((void)0)
#define ERR(...) ((void)0)
#define VIRTUAL_DEBUG_DUMP_VIEW(...) ((void)0)
#define min(a,b) ((a)<(b)?(a):(b))
#define max(a,b) ((a)>(b)?(a):(b))
#define ROUND_SIZE(addr,size,mask) (((uintptr_t)(addr)+(size)+(mask))&~(uintptr_t)(mask))
struct file_view {void *base; size_t size; unsigned protect;};
typedef struct {void *OldStackBase,*OldStackLimit,*DeallocationStack,*StackBase,*StackLimit;} INITIAL_TEB;
typedef struct {size_t MaximumStackSize,CommittedStackSize;} SECTION_IMAGE_INFORMATION;
static SECTION_IMAGE_INFORMATION image={0x200000,0x10000};
static const SECTION_IMAGE_INFORMATION *ios_cur_image_info(void){return &image;}
static struct {unsigned ImageCharacteristics;} main_image_info;
static int is_win64=1,use_kernel_writewatch,virtual_mutex;
static uintptr_t wow_base,limit_4g=0x100000000ULL,limit_2g=0x80000000ULL;
static uintptr_t ios_wow_base(void){return wow_base;}
static void *address_space_start=(void*)0x100010000ULL;
static void *address_space_limit=(void*)0x8000000000ULL;
static void *host_addr_space_limit=(void*)0x8000000000ULL;
static void *user_space_limit=(void*)0x8000000000ULL,*working_set_limit;
static uintptr_t user_space_wow_limit,ios_furniture_ceiling=0x73ffff0000ULL;
static uintptr_t ios_usable_va_floor=0x702f000000ULL,ios_spill_cap;
static size_t granularity_mask=0xffff,host_page_mask=0x3fff,host_page_size=0x4000,page_size=0x1000;
static int ios_wow_window_count,ios_wow_placeholder_count,ios_wow_laa_synth,ios_va_pressure;
static unsigned ios_va_scan_tries,ios_va_scan_skips,ios_scan_views;
static void *ios_scan_base,*ios_scan_end,*ios_scan_fail_addr;
static size_t ios_scan_maxgap,ios_scan_tailgap;
static int ios_scan_stop,ios_scan_fail_errno;
static struct {int stage;} ios_af;
static unsigned scan_calls,anon_calls,create_calls,unmap_calls,guard_calls,clamp_calls;
static int anonymous_failure,view_failure;
static uintptr_t next_base=0x180000000ULL;
static struct file_view result_view;
static uintptr_t ios_wow_ceiling_for_charact(unsigned c){return ((c&32)?limit_4g:limit_2g)-1;}
static void ios_wow_note_laa(unsigned c){(void)c;}
static void ios_clamp_user_space_limit(const char *why){(void)why;clamp_calls++;}
static void free_reserved_memory(void *a,void *b){(void)a;(void)b;}
static int get_unix_prot(unsigned p){(void)p;return PROT_READ|PROT_WRITE;}
static struct file_view *find_view(void *p,size_t s){(void)p;(void)s;return NULL;}
static void set_vprot(struct file_view *v,void *p,size_t s,unsigned f){(void)v;(void)p;(void)s;(void)f;}
static void kernel_writewatch_register_range(struct file_view *v,void *p,size_t s){(void)v;(void)p;(void)s;}
static void reset_write_watches(void *p,size_t s){(void)p;(void)s;}
static int is_beyond_limit(void *p,size_t s,void *end){return (uintptr_t)p>(uintptr_t)end || s>(uintptr_t)end-(uintptr_t)p;}
static int map_fixed_area(void *p,size_t s,int prot){(void)p;(void)s;(void)prot;return STATUS_SUCCESS;}
static int ios_wow_limits_in_window(uintptr_t low,uintptr_t high){return wow_base && low>=wow_base && high<wow_base+limit_4g && high>=low;}
static void ios_wow_exclude_windows(void **low,void **high){(void)low;(void)high;}
static void *ios_wow_bias_end(void *low,void *high){(void)low;return high;}
static int ios_wow_laa_low_first(void){return 0;}
static void *map_reserved_area(void *a,void *b,size_t s,int t,int p,size_t m){(void)a;(void)b;(void)s;(void)t;(void)p;(void)m;return NULL;}
static void *map_free_area(void *a,void *b,size_t s,int t,int p,size_t m){
 (void)s;(void)t;(void)p;(void)m;scan_calls++;ios_scan_base=a;ios_scan_end=b;
 ios_scan_fail_addr=a;ios_scan_fail_errno=ENOMEM;return NULL;
}
static void ios_furniture_census(void){}
static void ios_va_describe(void *p,char *s,size_t n){(void)p;if(n)s[0]=0;}
static int ios_storm_gate(unsigned long *n){(*n)++;return 0;}
static const char *ios_scan_stop_name(int s){(void)s;return "synthetic-full-advisory-window";}
static void ios_af_set(int s,int e,void *p,size_t n){(void)e;(void)p;(void)n;ios_af.stage=s;}
static void *anon_mmap_alloc(size_t s,int p){(void)p;anon_calls++;if(anonymous_failure){errno=ENOMEM;return MAP_FAILED;}void *r=(void*)next_base;next_base+=s+0x10000;return r;}
static void ios_pool_va_warn(const char *s,void *p,size_t n){(void)s;(void)p;(void)n;}
static size_t unmap_area_above_user_limit(void *p,size_t n){(void)p;return n;}
static void *unmap_extra_space(void *p,size_t all,size_t used,size_t mask){(void)all;(void)used;return (void*)(((uintptr_t)p+mask)&~mask);}
static int create_view(struct file_view **out,void *p,size_t n,unsigned f){create_calls++;if(view_failure)return STATUS_NO_MEMORY;result_view=(struct file_view){p,n,f};*out=&result_view;return STATUS_SUCCESS;}
static void unmap_area(void *p,size_t n){(void)p;(void)n;unmap_calls++;}
static void ios_wow_translate_limits(uintptr_t *a,uintptr_t *b){if(wow_base && *b && *b<limit_4g){*a+=wow_base;*b+=wow_base;}}
static void server_enter_uninterrupted_section(int *m,sigset_t *s){(void)m;(void)s;}
static void server_leave_uninterrupted_section(int *m,sigset_t *s){(void)m;(void)s;}
static void set_page_vprot(void *p,size_t n,unsigned f){(void)p;(void)n;(void)f;guard_calls++;}
static void mprotect_range(void *p,size_t n,int a,int b){(void)p;(void)n;(void)a;(void)b;}
'''
main = r'''
int main(void){
 INITIAL_TEB stack;struct file_view *view=NULL;
 /* Every 64-bit pseudo-process boots through the real function. */
 virtual_set_large_address_space();assert(clamp_calls==1);
 for(unsigned i=0;i<160;i++){
  int status=virtual_alloc_thread_stack(&stack,limit_4g,0,0x100000,0x100000,FALSE);
#ifdef EXPECT_OLD
  assert(status==STATUS_NO_MEMORY && !anon_calls && !create_calls);
#else
  assert(status==STATUS_SUCCESS && (uintptr_t)stack.DeallocationStack>=limit_4g);
  assert((uintptr_t)stack.StackBase-(uintptr_t)stack.DeallocationStack==0x100000);
  assert(stack.StackLimit==stack.DeallocationStack && !guard_calls);
#endif
 }
#ifndef EXPECT_OLD
 assert(address_space_start==(void*)0x100010000ULL && anon_calls==160);
 /* Host emulator stacks and guarded guest stacks retain their sizes. */
 assert(virtual_alloc_thread_stack(&stack,limit_4g,0,0x40000,0x40000,FALSE)==STATUS_SUCCESS);
 assert((uintptr_t)stack.StackBase-(uintptr_t)stack.DeallocationStack==0x100000);
 assert(virtual_alloc_thread_stack(&stack,0,0,0x200000,0x10000,TRUE)==STATUS_SUCCESS);
 assert((uintptr_t)stack.StackBase-(uintptr_t)stack.DeallocationStack==0x800000);
 assert((uintptr_t)stack.StackLimit-(uintptr_t)stack.DeallocationStack==0x8000 && guard_calls==2);
 /* An actual caller high bound or restrictive low bound never falls back. */
 unsigned calls=anon_calls;
 assert(map_view(&view,NULL,0x100000,0,7,limit_4g,0x200000000ULL,0)==STATUS_NO_MEMORY);
 assert(map_view(&view,NULL,0x100000,0,7,0x7100000000ULL,0,0)==STATUS_NO_MEMORY);
 assert(anon_calls==calls);
 /* WoW process boot must not reset the native floor or its translated bounds. */
 wow_base=0x7200000000ULL;main_image_info.ImageCharacteristics=0;
 virtual_set_large_address_space();assert(user_space_wow_limit==limit_2g-1);
 assert(address_space_start==(void*)0x100010000ULL);
 assert(virtual_alloc_thread_stack(&stack,0,limit_2g-1,0x100000,0x10000,TRUE)==STATUS_NO_MEMORY);
 assert(ios_scan_base==(void*)wow_base && ios_scan_end==(void*)(wow_base+limit_2g));
 assert(anon_calls==calls);
 main_image_info.ImageCharacteristics=32;virtual_set_large_address_space();assert(user_space_wow_limit==limit_4g-1);
 wow_base=0;virtual_set_large_address_space();
 /* Fixed addresses retain validation; native OS/view failures remain errors. */
 assert(map_view(&view,(void*)0x190000000ULL,0x100000,0,7,limit_4g,0,0)==STATUS_SUCCESS);
 assert(map_view(&view,(void*)0x190000000ULL,0x100000,0,7,0x200000000ULL,0,0)==STATUS_CONFLICTING_ADDRESSES);
 assert(map_view(&view,NULL,0x100000,0,7,5,4,0)==STATUS_INVALID_PARAMETER);
 anonymous_failure=1;assert(virtual_alloc_thread_stack(&stack,limit_4g,0,0x100000,0x100000,FALSE)==STATUS_NO_MEMORY);
 anonymous_failure=0;view_failure=1;assert(virtual_alloc_thread_stack(&stack,limit_4g,0,0x100000,0x100000,FALSE)==STATUS_NO_MEMORY && unmap_calls==1);
 puts("PASS: production boot/map_view/stack replay: 160 voice workers recover; caller bounds, WoW windows, guard sizing, fixed mappings and real failures preserved");
#else
 puts("PASS: former r25 boot reset reproduces fatal 1 MiB kernel-stack failure before any anonymous fallback");
#endif
}
'''
with tempfile.TemporaryDirectory(prefix="madeira-native-stack-") as folder:
    p = Path(folder)
    for old in (True, False):
        boot_fn = boot
        if old:
            boot_fn = boot_fn.replace("address_space_start = (void *)0x100010000;", "address_space_start = (void *)0x10000;")
        c = p / "test.c"
        c.write_text(stub + boot_fn + view + stack + main)
        command = ["clang", "-fsanitize=address,undefined", "-Wno-unused-function", "-Wno-unused-variable", str(c), "-o", str(p / "test")]
        if old:
            command.insert(1, "-DEXPECT_OLD=1")
        subprocess.run(command, check=True)
        result = subprocess.run([str(p / "test")], check=True, capture_output=True, text=True)
        print(result.stdout.strip())
