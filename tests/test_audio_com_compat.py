"""Run the production COM compatibility/MTA lifetime code with host boundaries."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
com = (root / 'wine/dlls/combase/combase.c').read_text()
apt = (root / 'wine/dlls/combase/apartment.c').read_text()
helper = com[com.index('static struct apartment *madeira_audio_get_apartment('):com.index('\nstatic HRESULT com_get_class_object(', com.index('static struct apartment *madeira_audio_get_apartment('))]
usage = apt[apt.index('struct mta_cookie\n'):apt.index('\nstatic const WCHAR aptwinclassW[]')]
source = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>
#include <pthread.h>
#include <stdatomic.h>
#define WINAPI
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define FAILED(hr) ((int32_t)(hr)<0)
#define ERR(...) ((void)0)
#define S_OK 0
#define E_OUTOFMEMORY ((int32_t)0x8007000e)
#define COINIT_MULTITHREADED 0
#define CLSCTX_INPROC_SERVER 1
#define CLSCTX_LOCAL_SERVER 4
#define NULL_COOKIE ((void *)0)
typedef int32_t HRESULT;
typedef uint32_t DWORD;
typedef wchar_t WCHAR;
typedef void *CO_MTA_USAGE_COOKIE;
typedef struct {uint32_t a;uint16_t b,c;uint8_t d[8];} CLSID;
typedef const CLSID *REFCLSID;
#define IsEqualCLSID(a,b) (!memcmp((a),(b),sizeof(CLSID)))
struct list {struct list *next,*prev;};
static void list_init(struct list *l){l->next=l->prev=l;}
static void list_add_head(struct list *l,struct list *n){n->next=l->next;n->prev=l;l->next->prev=n;l->next=n;}
static void list_remove(struct list *n){n->prev->next=n->next;n->next->prev=n->prev;}
#define LIST_FOR_EACH_ENTRY(v,head,type,member) for(struct list *node=(head)->next;node!=(head) && ((v)=(type*)node,1);node=node->next)
struct apartment {unsigned refs;struct list usage_cookies;};
struct tlsdata {struct apartment *apt;void *implicit_mta_cookie;unsigned inits;};
static _Thread_local struct tlsdata tls;
static struct apartment *mta;
static pthread_mutex_t apt_cs;
static int fail_alloc,fail_construct,fail_tls;
static atomic_uint allocations,frees,constructed,released;
static const wchar_t *policy;
static void *test_malloc(size_t n){if(fail_alloc)return NULL;++allocations;return malloc(n);}
static void test_free(void *p){if(p){++frees;free(p);}}
#define malloc test_malloc
#define free test_free
static void EnterCriticalSection(pthread_mutex_t *m){assert(!pthread_mutex_lock(m));}
static void LeaveCriticalSection(pthread_mutex_t *m){assert(!pthread_mutex_unlock(m));}
static struct apartment *apartment_construct(DWORD model){assert(model==0);if(fail_construct)return NULL;struct apartment *a=malloc(sizeof *a);if(a){a->refs=1;list_init(&a->usage_cookies);++constructed;}return a;}
static void apartment_addref(struct apartment *a){++a->refs;}
static void apartment_release(struct apartment *a){EnterCriticalSection(&apt_cs);assert(a->refs);if(!--a->refs){assert(a->usage_cookies.next==&a->usage_cookies);if(mta==a)mta=NULL;++released;free(a);}LeaveCriticalSection(&apt_cs);}
static struct apartment *apartment_get_current_or_mta(void){EnterCriticalSection(&apt_cs);struct apartment *a=tls.apt?tls.apt:mta;if(a)apartment_addref(a);LeaveCriticalSection(&apt_cs);return a;}
static HRESULT com_get_tlsdata(struct tlsdata **out){if(fail_tls)return E_OUTOFMEMORY;*out=&tls;return S_OK;}
static DWORD GetEnvironmentVariableW(const WCHAR *key,WCHAR *out,DWORD size){assert(!wcscmp(key,L"MADEIRA_MMDEVICE_IMPLICIT_MTA"));if(!policy)return 0;size_t n=wcslen(policy);if(n>=size)return n+1;wcscpy(out,policy);return n;}
''' + usage + helper + r'''
static const CLSID audio={0xbcde0395,0xe52f,0x467c,{0x8e,0x3d,0xc4,0x57,0x92,0x91,0x69,0x2e}};
static void detach(void){if(tls.apt)apartment_release(tls.apt);if(tls.implicit_mta_cookie)apartment_decrement_mta_usage(tls.implicit_mta_cookie);memset(&tls,0,sizeof tls);}
static atomic_uint arrived,finished;
static void *worker(void *unused){(void)unused;struct apartment *a=madeira_audio_get_apartment(&audio,1);assert(a && !tls.apt && !tls.inits);atomic_fetch_add(&arrived,1);while(atomic_load(&arrived)!=16){};apartment_release(a);atomic_fetch_add(&finished,1);while(atomic_load(&finished)!=16){};detach();return NULL;}
int main(void){
 pthread_mutexattr_t attr;pthread_mutexattr_init(&attr);pthread_mutexattr_settype(&attr,PTHREAD_MUTEX_RECURSIVE);pthread_mutex_init(&apt_cs,&attr);pthread_mutexattr_destroy(&attr);
 CLSID other=audio;other.a++;
 for(unsigned k=0;k<4;k++){policy=k==0?NULL:k==1?L"0":k==2?L"10":L"true";assert(!madeira_audio_get_apartment(&audio,1) && !allocations);}
 policy=L"1";assert(!madeira_audio_get_apartment(&other,1));assert(!madeira_audio_get_apartment(&audio,CLSCTX_LOCAL_SERVER));assert(!allocations);
 fail_tls=1;assert(!madeira_audio_get_apartment(&audio,1));fail_tls=0;
 fail_alloc=1;assert(!madeira_audio_get_apartment(&audio,1) && !tls.implicit_mta_cookie);fail_alloc=0;
 fail_construct=1;assert(!madeira_audio_get_apartment(&audio,1) && !tls.implicit_mta_cookie && !mta);fail_construct=0;assert(allocations==frees);
 struct apartment *a=madeira_audio_get_apartment(&audio,1);assert(a && tls.implicit_mta_cookie && !tls.apt && !tls.inits);unsigned before=allocations;
 struct apartment *b=madeira_audio_get_apartment(&audio,1);assert(a==b && allocations==before);apartment_release(b);apartment_release(a);detach();assert(!mta && allocations==frees);
 /* Explicit STA/MTA apartment wins, including unrelated classes/disabled policy. */
 tls.apt=apartment_construct(0);tls.inits=3;policy=L"0";before=allocations;a=madeira_audio_get_apartment(&other,4);assert(a==tls.apt && tls.inits==3 && !tls.implicit_mta_cookie && allocations==before);apartment_release(a);detach();assert(!mta && allocations==frees);
 /* Later explicit initialization must retain the original worker init count. */
 policy=L"1";a=madeira_audio_get_apartment(&audio,1);apartment_release(a);tls.apt=apartment_construct(0);tls.inits=1;detach();assert(!mta && allocations==frees);
 pthread_t threads[16];for(unsigned k=0;k<16;k++)assert(!pthread_create(&threads[k],NULL,worker,NULL));for(unsigned k=0;k<16;k++)assert(!pthread_join(threads[k],NULL));
 assert(!mta && allocations==frees && constructed==released);pthread_mutex_destroy(&apt_cs);
 puts("PASS: exact audio CLSID/inproc/opt-in scope, existing apartments, repeat reuse, implicit TLS lifetime, 16 workers, retryable allocation failures; no init-count changes/leaks");
}
'''
with tempfile.TemporaryDirectory(prefix='madeira-audio-com-') as folder:
    p=Path(folder)
    (p/'test.c').write_text(source)
    subprocess.run(['clang','-Wall','-Wextra','-Werror','-pthread','-fsanitize=address,undefined','-g',str(p/'test.c'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)
# Confirm the real call path and existing cleanup consume the same cookie.
body=com[com.index('static HRESULT com_get_class_object('):com.index(' *           CoGetClassObject')]
assert body.index('if (!obj)') < body.index('madeira_audio_get_apartment(rclsid, clscontext)')
assert 'return CO_E_NOTINITIALIZED;' in body and 'apartment_get_inproc_class_object' in body
cleanup=com[com.index('static void com_cleanup_tlsdata('):com.index('static void com_cleanup_tlsdata(')+2500]
assert 'apartment_decrement_mta_usage(tlsdata->implicit_mta_cookie)' in cleanup
leave=apt[apt.index('void leave_apartment('):apt.index('struct mta_cookie\n')]
assert 'apartment_decrement_mta_usage(data->implicit_mta_cookie)' in leave
assert 'data->implicit_mta_cookie = NULL' in leave
print('PASS: real class factory/error path preserved; existing Wine thread/uninitialize cleanup balances compatibility cookie')
