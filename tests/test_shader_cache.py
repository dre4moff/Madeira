"""Production cache resolver/SQLite classes, synthetic payloads, fake Metal API.
All files are confined to a temporary host directory. No Wine/game/GPU runs.
"""
from pathlib import Path
import subprocess, tempfile
root=Path(__file__).resolve().parents[1]
s=(root/'dxmt/src/winemetal/unix/cache.c').read_text()
classes=s[s.index('@interface CacheReader :'):s.index('\nint\n_CacheReader_alloc_init')]
classes=classes.replace('NSSearchPathForDirectoriesInDomains(', 'fakeSearchPaths(').replace('confstr(', 'fakeConfstr(')
wrapper=s[s.index('int\n_WMTSetMetalShaderCachePath('):s.index('\n#else\n\nint\nWMTSetMetalShaderCachePath')]
allocs=''
for name,next_name in [('_CacheReader_alloc_init','_CacheReader_get'),('_CacheWriter_alloc_init','_CacheWriter_set')]:
 start=s.index('int\n'+name+'(')
 allocs+=s[start:s.index('int\n'+next_name+'(',start)]
bridge=(root/'app/Madeira/WineProcessBridge.m').read_text()
trial_start=bridge.index('        setenv("DXMT_SHADER_CACHE", "0", 1);')
trial=bridge[trial_start:bridge.index("        // Session-only Wine load order",trial_start)]
assert bridge.index('madeira.cfg env:') < trial_start < bridge.index('madeira_apply_vcruntime_overrides(nativeVCRuntime);')
default='setenv("DXMT_IOS_CACHE_DIR", "1", 0);'
assert default in bridge and bridge.index(default)<bridge.index('madeira.cfg env:')
code=r'''
#import <Foundation/Foundation.h>
#include <dispatch/dispatch.h>
#include <sqlite3.h>
#include <fcntl.h>
#include <sys/file.h>
#include <unistd.h>
#include <limits.h>
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#undef TARGET_OS_IPHONE
#define TARGET_OS_IPHONE 1
static NSString *base, *metalPath;
static unsigned long window;
static int searchFails, legacyCalls, metalSets;
unsigned long ios_wow_base(void) { return window; }
static NSArray *fakeSearchPaths(NSSearchPathDirectory d, NSSearchPathDomainMask m, BOOL e) {
 (void)d; (void)m; (void)e; return searchFails ? @[] : @[base];
}
static size_t fakeConfstr(int n, char *buf, size_t cap) {
 (void)n; legacyCalls++;
 const char *s=[[base stringByAppendingPathComponent:@"legacy"] fileSystemRepresentation];
 size_t len=strlen(s)+1;
 if (cap>=len) memcpy(buf,s,len);
 return len;
}
void MTLSetShaderCachePath(NSString *path) { metalSets++; [metalPath release]; metalPath=[path copy]; }
NSString *MTLGetShaderCachePath(void) { return metalPath; }
typedef uint64_t obj_handle_t;
struct unixcall_cache_alloc_init {struct {const char *ptr;} path;uint64_t version;obj_handle_t ret_cache;};
struct unixcall_setmetalcachepath { struct { const char *ptr; } path; uint64_t ret_success; };
''' + classes + allocs + wrapper + '\nstatic void apply_trial(void) {\n'+trial+'}\n'+r'''
static void expect_data(dispatch_data_t data, const char *expected) {
 assert(data);
 const void *bytes; size_t size;
 dispatch_data_t flat=dispatch_data_create_map(data,&bytes,&size);
 assert(size==strlen(expected) && !memcmp(bytes,expected,size));
 dispatch_release(flat);
}
int main(int argc, char **argv) { @autoreleasepool {
 assert(argc==2); base=[[NSString alloc] initWithUTF8String:argv[1]];
 unsetenv("DXMT_IOS_CACHE_DIR");
''' + default + r'''
 assert(use_ios_cache_dir() && window==0); // actual app default enables x64 callers
 NSString *relative=@"dxmt/synthetic-game/shaders_320.db";
 NSString *resolved=resolve_cache_dir(relative,true);
 assert([resolved isEqualToString:[base stringByAppendingPathComponent:relative]]);
 assert(legacyCalls==0);
 NSString *absolute=[base stringByAppendingPathComponent:@"absolute/cache.db"];
 assert([resolve_cache_dir(absolute,true) isEqualToString:absolute]);
 CacheWriter *writer=[[CacheWriter alloc] initWithPath:relative version:15];
 CacheReader *reader=[[CacheReader alloc] initWithPath:relative version:15];
 assert(writer && reader);
 NSData *key=[@"fake-shader-digest" dataUsingEncoding:NSUTF8StringEncoding];
 assert(![reader get:key]);
 const char *value="synthetic-metallib-no-gpu";
 dispatch_data_t data=dispatch_data_create(value,strlen(value),NULL,DISPATCH_DATA_DESTRUCTOR_DEFAULT);
 [writer set:key value:data];
 dispatch_data_t hit=[reader get:key]; expect_data(hit,value); dispatch_release(hit);
 [reader release]; [writer release]; // reopen: persist across application sessions
 writer=[[CacheWriter alloc] initWithPath:relative version:15];
 reader=[[CacheReader alloc] initWithPath:relative version:15];
 hit=[reader get:key]; expect_data(hit,value); dispatch_release(hit);
 CacheWriter *otherWriter=[[CacheWriter alloc] initWithPath:relative version:16];
 CacheReader *otherReader=[[CacheReader alloc] initWithPath:relative version:16];
 assert(otherWriter && otherReader && ![otherReader get:key]);
 [otherReader release]; [otherWriter release];
 struct unixcall_setmetalcachepath params={{"dxmt/synthetic-game/com.apple.metal"},0};
 _WMTSetMetalShaderCachePath(&params); assert(params.ret_success && metalSets==1);
 assert([metalPath hasPrefix:base]);
 NSString *remembered=[metalPath copy]; searchFails=1;
 _WMTSetMetalShaderCachePath(&params); assert(!params.ret_success && metalSets==1);
 assert([metalPath isEqualToString:remembered]); searchFails=0; [remembered release];
 NSString *file=[base stringByAppendingPathComponent:@"blocked"];
 [@"file, not directory" writeToFile:file atomically:YES encoding:NSUTF8StringEncoding error:NULL];
 assert(!resolve_cache_dir([file stringByAppendingPathComponent:@"cache.db"],true));
 setenv("DXMT_IOS_CACHE_DIR","0",1); assert(!use_ios_cache_dir());
 assert([resolve_cache_dir(relative,true) hasPrefix:[base stringByAppendingPathComponent:@"legacy"]]);
 assert(legacyCalls==1);
 unsetenv("DXMT_IOS_CACHE_DIR"); window=1; assert(use_ios_cache_dir());
 window=0; assert(!use_ios_cache_dir());
 // Run the actual cache entry points, not only the path resolver.
 setenv("DXMT_SHADER_CACHE","1",1);setenv("DXMT_IOS_CACHE_DIR","1",1);
 struct unixcall_cache_alloc_init alloc={{[resolved fileSystemRepresentation]},15,0};
 _CacheReader_alloc_init(&alloc); assert(alloc.ret_cache);[(id)alloc.ret_cache release];
 _CacheWriter_alloc_init(&alloc); assert(alloc.ret_cache);[(id)alloc.ret_cache release];
 NSArray *beforeFiles=[[NSFileManager defaultManager] subpathsAtPath:base];
 NSData *beforeDB=[NSData dataWithContentsOfFile:resolved];
 NSDictionary *beforeAttrs=[[NSFileManager defaultManager] attributesOfItemAtPath:resolved error:NULL];
 setenv("DXMT_SHADER_CACHE","1",1);setenv("DXMT_CACHE_STATS","1",1);setenv("DXMT_USE_DEFAULT_METAL_CACHE","0",1);
 apply_trial();assert(!strcmp(getenv("DXMT_SHADER_CACHE"),"0") && !strcmp(getenv("DXMT_CACHE_STATS"),"0") && !strcmp(getenv("DXMT_USE_DEFAULT_METAL_CACHE"),"1"));
 int beforeSets=metalSets,beforeLegacy=legacyCalls;
 for (unsigned i=0;i<1000;i++) {
  // Invalid paths must not even be dereferenced in the disabled branch.
  alloc.path.ptr=(const char *)1;alloc.ret_cache=UINT64_MAX;
  _CacheReader_alloc_init(&alloc);assert(!alloc.ret_cache);
  alloc.ret_cache=UINT64_MAX;_CacheWriter_alloc_init(&alloc);assert(!alloc.ret_cache);
  params.path.ptr=(const char *)1;params.ret_success=99;
  _WMTSetMetalShaderCachePath(&params);assert(!params.ret_success);
 }
 assert(metalSets==beforeSets && legacyCalls==beforeLegacy);
 assert([beforeFiles isEqual:[[NSFileManager defaultManager] subpathsAtPath:base]]);
 assert([beforeDB isEqual:[NSData dataWithContentsOfFile:resolved]]);
 assert([beforeAttrs[NSFileModificationDate] isEqual:[[NSFileManager defaultManager] attributesOfItemAtPath:resolved error:NULL][NSFileModificationDate]]);
 unsetenv("DXMT_SHADER_CACHE");
 puts("PASS: actual reader/writer/Metal entry points bypass 3000 calls before path/SQLite/Metal access, preserve files; trial overrides user config");
 [reader release]; [writer release]; dispatch_release(data); [metalPath release]; [base release];
 puts("PASS: actual iOS cache resolution, opt-out, absolute paths, SQLite cold/warm/reopen/version separation and failure fallback; Metal API mocked");
} }
'''
with tempfile.TemporaryDirectory(prefix='madeira-shader-cache-') as tmp:
 p=Path(tmp); (p/'check.m').write_text(code)
 subprocess.run(['clang','-fblocks','-Wall','-Wextra','-Wno-incompatible-pointer-types','-fsanitize=address,undefined','-framework','Foundation','-lsqlite3',str(p/'check.m'),'-o',str(p/'check')],check=True)
 subprocess.run([str(p/'check'),str(p/'sandbox')],check=True)
