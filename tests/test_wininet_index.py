"""Real Wine cache lock/unlock/growth with shadow mappings and failing Win32 I/O.
No Wine, app, game, network service or GPU is executed.
"""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parents[1]
source=(root/'wine/dlls/wininet/urlcache.c').read_text()
def function(name, source=source):
 a=source.index(name+'(');a=source.rfind('\nstatic ',0,a)+1;b=source.index('\n}',a)+2;return source[a:b]
code=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>
typedef uint8_t BYTE;typedef uint32_t DWORD;typedef int BOOL;typedef wchar_t WCHAR;
typedef void *HANDLE;typedef void *LPVOID;
#define TRUE 1
#define FALSE 0
#define NULL_HANDLE ((HANDLE)0)
#define INVALID_HANDLE_VALUE ((HANDLE)(intptr_t)-1)
#define INVALID_SET_FILE_POINTER UINT32_MAX
#define ERROR_SUCCESS 0
#define ERROR_NOT_ENOUGH_MEMORY 8
#define ERROR_INVALID_DATA 13
#define ERROR_WRITE_FAULT 29
#define INFINITE UINT32_MAX
#define FILE_MAP_WRITE 2
#define FILE_BEGIN 0
#define GENERIC_READ 1
#define GENERIC_WRITE 2
#define FILE_SHARE_READ 1
#define FILE_SHARE_WRITE 2
#define OPEN_EXISTING 3
#define MAX_PATH 260
#define MIN_BLOCK_NO 128
#define MAX_BLOCK_NO 1024
#define FILE_SIZE(n) ((n)*128+16384)
#define min(a,b) ((a)<(b)?(a):(b))
#define TRACE(...) ((void)0)
#define ERR(...) ((void)0)
#define WARN(...) ((void)0)
#define debugstr_a(x) (x)
#define debugstr_w(x) (x)
#define lstrcpyW wcscpy
#define lstrcatW wcscat
struct Dir {char name[8];};
typedef struct {char signature[28];DWORD size,capacity_in_blocks,dirs_no;struct Dir directory_data[8];} urlcache_header;
typedef struct {char *cache_prefix;WCHAR *path;HANDLE mapping;DWORD file_size;HANDLE mutex;DWORD default_entry_type;urlcache_header *index_view;} cache_container;
struct Mapping {BYTE *bytes;unsigned refs;DWORD size;int closed;};
static BYTE disk[FILE_SIZE(MAX_BLOCK_NO)];static DWORD disk_size,cursor;
static unsigned map_count,unmap_count,lock_depth,writes,closed,opens;
static DWORD last_error=87;static int failure,failed,leaked;static unsigned chunk=UINT32_MAX;
static struct Mapping *latest;
static struct Mapping *all[64];static unsigned all_count;
static void remember(struct Mapping *m) {all[all_count++]=m;}
static int fail(int stage) {if(failure==stage && !failed){failed=1;return 1;}return 0;}
static DWORD GetLastError(void) {return last_error;}
static void SetLastError(DWORD e){last_error=e;}
static DWORD WaitForSingleObject(HANDLE m,DWORD t){(void)m;(void)t;++lock_depth;return 0;}
static BOOL ReleaseMutex(HANDLE m){(void)m;assert(lock_depth);--lock_depth;return 1;}
static HANDLE CreateFileW(const WCHAR *p,DWORD a,DWORD b,void *c,DWORD d,DWORD e,HANDLE f) {
 (void)p;(void)a;(void)b;(void)c;(void)d;(void)e;(void)f;++opens;cursor=0;
 return fail(1)?INVALID_HANDLE_VALUE:(HANDLE)1;
}
static DWORD SetFilePointer(HANDLE f,DWORD p,void *h,DWORD how){(void)f;(void)h;(void)how;cursor=p;return p;}
static BOOL SetEndOfFile(HANDLE f){(void)f;if(fail(3))return 0;assert(cursor<=sizeof(disk));disk_size=cursor;return 1;}
static BOOL WriteFile(HANDLE f,const void *p,DWORD n,DWORD *done,void *o) {
 (void)f;(void)o;assert(cursor+n<=sizeof(disk));++writes;
 if((failure==2 && !failed) || (failure==6 && !failed && disk_size>FILE_SIZE(MIN_BLOCK_NO))) {failed=1;return 0;}
 if(fail(7)){*done=0;return 1;}
 *done=min(n,chunk);memcpy(disk+cursor,p,*done);cursor+=*done;if(cursor>disk_size)disk_size=cursor;return 1;
}
static HANDLE cache_container_map_index(HANDLE f,const WCHAR *p,DWORD n,BOOL *v) {
 (void)f;(void)p;(void)v;if(fail(4))return NULL;
 struct Mapping *m=calloc(1,sizeof(*m));m->bytes=calloc(1,n);m->size=n;memcpy(m->bytes,disk,min(disk_size,n));latest=m;remember(m);return m;
}
static void *MapViewOfFile(HANDLE h,DWORD access,DWORD x,DWORD y,DWORD z) {
 (void)access;(void)x;(void)y;(void)z;if(fail(5))return NULL;
 struct Mapping *m=h;assert(m && !m->closed);++m->refs;++map_count;return m->bytes;
}
static BOOL UnmapViewOfFile(const void *p) {
 for(unsigned i=0;i<all_count;++i)if(all[i]->bytes==p){assert(all[i]->refs);--all[i]->refs;++unmap_count;return 1;}

 assert(0);return 0;
}
static BOOL CloseHandle(HANDLE h){if(h && h!=(HANDLE)1){struct Mapping *m=h;m->closed=1;++closed;}return 1;}
static int urlcache_clean_leaked_entries(cache_container *c,urlcache_header *h){(void)c;(void)h;return leaked;}
static DWORD cache_container_open_index(cache_container *c,DWORD blocks) {
 (void)blocks;if(c->mapping)return 0;c->mapping=cache_container_map_index((HANDLE)1,c->path,disk_size,NULL);
 if(!c->mapping)return 87;c->file_size=disk_size;return 0;
}
static void *test_malloc(size_t n){if(fail(8))return NULL;return malloc(n);}
'''
code+=function('cache_container_close_index')+'\n'+function('cache_container_lock_index')+'\n'+function('cache_container_unlock_index')+'\n'
baseline=subprocess.check_output(['git','-C',str(root/'wine'),'show','4f5b19718f4de88ecc5cb0dc08b119497a67ba8f:dlls/wininet/urlcache.c'],text=True)
for name in ['cache_container_lock_index','cache_container_unlock_index']:
 code+=function(name,baseline).replace(name,'baseline_'+name)+'\n'
code+='#define malloc test_malloc\n'+function('cache_index_write')+'\n'+function('cache_container_clean_index')+'\n#undef malloc\n'
code+=r'''
static cache_container setup(void) {
 assert(!lock_depth);for(unsigned i=0;i<all_count;++i){assert(!all[i]->refs);free(all[i]->bytes);free(all[i]);}
 all_count=0;latest=NULL;map_count=unmap_count=writes=closed=opens=0;failed=leaked=0;chunk=UINT32_MAX;
 memset(disk,0,sizeof(disk));disk_size=FILE_SIZE(MIN_BLOCK_NO);urlcache_header *h=(void *)disk;
 h->size=disk_size;h->capacity_in_blocks=MIN_BLOCK_NO;h->dirs_no=2;
 for(unsigned i=sizeof(*h);i<disk_size;++i)disk[i]=(BYTE)(i*19+3);
 cache_container c={.path=L"C:\\cache\\",.file_size=disk_size,.mutex=(HANDLE)2};
 int saved=failure;failure=0;c.mapping=cache_container_map_index((HANDLE)1,c.path,disk_size,NULL);failure=saved;
 return c;
}
int main(void) {
 failure=0;cache_container c=setup();urlcache_header *h=NULL;
 for(unsigned i=0;i<50000;++i){h=baseline_cache_container_lock_index(&c);assert(h);assert(baseline_cache_container_unlock_index(&c,h));}
 assert(map_count==50000 && unmap_count==50000 && writes==0 && !lock_depth);
 cache_container_close_index(&c);c=setup();
 for(unsigned i=0;i<50000;++i){h=cache_container_lock_index(&c);assert(h);assert(cache_container_unlock_index(&c,h));}
 assert(map_count==1 && unmap_count==0 && writes==0 && lock_depth==0);
 // Initial mapping failure must release the mutex and leave a retryable handle.
 cache_container_close_index(&c);c=setup();failure=5;
 assert(!cache_container_lock_index(&c) && !c.index_view && !lock_depth);
 failure=0;h=cache_container_lock_index(&c);assert(h);cache_container_unlock_index(&c,h);
 // A second DLL/container instance shares the old named mapping.
 cache_container peer=c;peer.index_view=NULL;
 urlcache_header *ph=cache_container_lock_index(&peer);cache_container_unlock_index(&peer,ph);
 BYTE original[FILE_SIZE(MIN_BLOCK_NO)];memcpy(original,h,sizeof(original));
 WaitForSingleObject(c.mutex,INFINITE);assert(cache_container_clean_index(&c,&h)==0);
 assert(h->capacity_in_blocks==256 && h==c.index_view && h->size==FILE_SIZE(256));
 assert(!memcmp((BYTE *)h+sizeof(*h),original+sizeof(*h),sizeof(original)-sizeof(*h)));
 assert(!memcmp(disk,h,h->size));
 for(unsigned i=sizeof(original);i<h->size;++i)assert(!((BYTE *)h)[i]);
 cache_container_unlock_index(&c,h);
 ph=cache_container_lock_index(&peer);assert(ph->size==h->size && peer.file_size==h->size);
 cache_container_unlock_index(&peer,ph);cache_container_close_index(&peer);cache_container_close_index(&c);
 // Every failure keeps the old live mapping, payload and lock balance.
 for(int stage=1;stage<=8;++stage) {
  failure=0;c=setup();h=cache_container_lock_index(&c);assert(h);failure=stage;BYTE copy[FILE_SIZE(MIN_BLOCK_NO)];memcpy(copy,h,sizeof(copy));
  HANDLE previous=c.mapping;DWORD err=cache_container_clean_index(&c,&h);assert(err && failed);
  assert(c.mapping==previous && h==c.index_view && !memcmp(h,copy,sizeof(copy)));
  assert(c.file_size==sizeof(copy) && disk_size==sizeof(copy) && !memcmp(disk,copy,sizeof(copy)));
  cache_container_unlock_index(&c,h);cache_container_close_index(&c);
 }
 failure=0;c=setup();h=cache_container_lock_index(&c);chunk=13;
 while(h->capacity_in_blocks<MAX_BLOCK_NO){assert(cache_container_clean_index(&c,&h)==0);}
 assert(cache_container_clean_index(&c,&h)==ERROR_NOT_ENOUGH_MEMORY);
 assert(disk_size==FILE_SIZE(MAX_BLOCK_NO));
 h->capacity_in_blocks=0;assert(cache_container_clean_index(&c,&h)==ERROR_INVALID_DATA);
 leaked=1;assert(cache_container_clean_index(&c,&h)==0);
 cache_container_unlock_index(&c,h);cache_container_close_index(&c);failure=0;c=setup();cache_container_close_index(&c);
 for(unsigned i=0;i<all_count;++i){assert(!all[i]->refs);free(all[i]->bytes);free(all[i]);}all_count=0;
 puts("PASS: actual WinINet lock/growth: 50000 lookups: baseline 50000 maps/unmaps, fixed one view, zero unmaps/writes; preserved entries/tail/shadow persistence/peer refresh; eight failure rollbacks; short writes and original size ceiling");
}
'''
with tempfile.TemporaryDirectory(prefix='madeira-wininet-index-') as tmp:
 p=Path(tmp);(p/'test.c').write_text(code)
 subprocess.run(['clang','-std=c11','-O2','-fsanitize=address,undefined',str(p/'test.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True,timeout=60)
