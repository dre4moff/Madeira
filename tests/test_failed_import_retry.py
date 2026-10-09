#!/usr/bin/env python3
"""Run the production failed-import retry path under ASan/UBSan on the host."""
from pathlib import Path
import subprocess
import re
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / 'wine/dlls/ntdll/loader.c').read_text()
def function(signature):
    start = re.search(re.escape(signature) + r"[^;]*?\n\{", source).start()
    return source[start:source.index('\n}', start) + 2] + '\n'

# The private image is never reported as successfully initialized. A failed
# circular dependency must also fail process_attach, before any callback runs.
attach = function('static NTSTATUS process_attach(')
assert attach.index('if (wm->import_status)') < attach.index('/* Skip initialization')
assert 'RtlFreeHeap( GetProcessHeap(), 0, wm->resolved_imports );' in function('static void free_modref(')
build = function('static NTSTATUS build_module(')
assert 'retain_failed_import_module( wm, status );' in build
assert build.index('retain_failed_import_module') < build.index('complete_loaded_module')

harness = r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>
#include <wctype.h>
typedef uint32_t DWORD, ULONG; typedef int BOOL, NTSTATUS; typedef unsigned char BYTE;
typedef size_t SIZE_T; typedef uintptr_t ULONG_PTR; typedef wchar_t WCHAR;
typedef void *HMODULE, *HANDLE; typedef const WCHAR *LPCWSTR;
#define TRUE 1
#define STATUS_SUCCESS 0
#define STATUS_DLL_NOT_FOUND (-1)
#define STATUS_NO_MEMORY (-2)
#define NT_SUCCESS(x) ((x)>=0)
#define HEAP_ZERO_MEMORY 1
#define LDR_DONT_RESOLVE_REFS 1
#define LDR_COR_ILONLY 2
#define LDR_WINE_INTERNAL 4
#define LDR_IMAGE_IS_DLL 8
#define IMAGE_DIRECTORY_ENTRY_IMPORT 1
#define ViewShare 1
#define PAGE_EXECUTE_READ 1
#define HASH_MAP_SIZE 32
#define ERR(...) ((void)0)
#define TRACE(...) ((void)0)
#define TRACE_(x) TRACE
#define TRACE_ON(x) 0
#define CONTAINING_RECORD(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
typedef struct list {struct list *Flink,*Blink;} LIST_ENTRY;
typedef struct single {struct single *Next;} SINGLE_LIST_ENTRY;
typedef struct {SINGLE_LIST_ENTRY *Tail;} SINGLE_LIST;
static void InitializeListHead(LIST_ENTRY *h){h->Flink=h->Blink=h;}
static void InsertTailList(LIST_ENTRY *h,LIST_ENTRY *e){e->Blink=h->Blink;e->Flink=h;h->Blink->Flink=e;h->Blink=e;}
static void RemoveEntryList(LIST_ENTRY *e){e->Blink->Flink=e->Flink;e->Flink->Blink=e->Blink;}
typedef struct {WCHAR *Buffer;size_t Length,MaximumLength;} UNICODE_STRING;
typedef struct {int present;} RTL_BALANCED_NODE;
typedef struct {LIST_ENTRY InLoadOrderModuleList,InMemoryOrderModuleList;} LDR;
static LDR ldr;
typedef struct {LDR *LdrData;} PEB;
static PEB peb={&ldr};
static struct {PEB *Peb;} teb;
#define NtCurrentTeb() (&teb)
#define NtCurrentProcess() ((void *)1)
typedef struct {LIST_ENTRY Modules;SINGLE_LIST Dependencies,IncomingDependencies;} LDR_DDAG_NODE;
typedef struct {
 LIST_ENTRY InLoadOrderLinks,InMemoryOrderLinks,HashLinks,NodeModuleLink;
 RTL_BALANCED_NODE BaseAddressIndexNode;
 UNICODE_STRING BaseDllName,FullDllName;
 void *DllBase,*EntryPoint,*ActivationContext;DWORD Flags;int TlsIndex,LoadCount;
 LDR_DDAG_NODE *DdagNode;
} LDR_DATA_TABLE_ENTRY;
struct file_id {BYTE ObjectId[16];};
typedef struct _wine_modref {
 LDR_DATA_TABLE_ENTRY ldr; struct file_id id;ULONG CheckSum;BOOL system;
 LIST_ENTRY failed_import_entry;NTSTATUS import_status;BYTE *resolved_imports;
} WINE_MODREF;
static LIST_ENTRY failed_import_modules,hash_table[HASH_MAP_SIZE];
static WINE_MODREF *cached_modref;
static int base_address_index_tree;
static LDR_DDAG_NODE *node_ntdll,*node_kernel32;
static unsigned maps,tls_slots,contexts,ready_bindings,missing_bindings,dependencies;
static int dependency_available,allocation_failure;
static WINE_MODREF ready;
static void *GetProcessHeap(void){return NULL;}
static void *RtlAllocateHeap(void *heap,int flags,size_t size){if(allocation_failure)return NULL;return calloc(1,size);}
static int RtlEqualUnicodeString(const UNICODE_STRING *a,const UNICODE_STRING *b,int ci){
 if(a->Length!=b->Length)return 0;
 for(size_t i=0;i<a->Length/sizeof(WCHAR);i++)if((ci?towlower(a->Buffer[i]):a->Buffer[i])!=(ci?towlower(b->Buffer[i]):b->Buffer[i]))return 0;
 return 1;
}
static ULONG hash_basename(const UNICODE_STRING *s){return 0;}
static int base_address_compare(const void *key,const RTL_BALANCED_NODE *node){return 0;}
static int rtl_rb_tree_put(int *tree,void *key,RTL_BALANCED_NODE *node,int (*cmp)(const void *,const RTL_BALANCED_NODE *)){assert(!node->present);node->present=1;return 0;}
static void RtlRbRemoveNode(int *tree,RTL_BALANCED_NODE *node){assert(node->present);node->present=0;}
static unsigned public_count(void){unsigned n=0;for(LIST_ENTRY *e=ldr.InLoadOrderModuleList.Flink;e!=&ldr.InLoadOrderModuleList;e=e->Flink)n++;return n;}
static unsigned failed_count(void){unsigned n=0;for(LIST_ENTRY *e=failed_import_modules.Flink;e!=&failed_import_modules;e=e->Flink)n++;return n;}
static BOOL alloc_tls_slot(LDR_DATA_TABLE_ENTRY *m){tls_slots++;return TRUE;}
static NTSTATUS create_module_activation_context(LDR_DATA_TABLE_ENTRY *m){contexts++;m->ActivationContext=(void *)1;return 0;}
static void RtlActivateActivationContext(int f,void *h,ULONG_PTR *cookie){*cookie=1;}
static void RtlDeactivateActivationContext(int f,ULONG_PTR cookie){assert(cookie==1);}
typedef struct {DWORD Name,FirstThunk;} IMAGE_IMPORT_DESCRIPTOR;
static IMAGE_IMPORT_DESCRIPTOR imports[]={{1,1},{2,2},{0,0}};
static void *RtlImageDirectoryEntryToData(void *m,int mapped,int dir,DWORD *size){*size=sizeof(imports);return imports;}
static int import_dll(WINE_MODREF *m,const IMAGE_IMPORT_DESCRIPTOR *i,LPCWSTR path,WINE_MODREF **out){
 if(i->Name==1){ready_bindings++;assert(ready_bindings<=maps);*out=&ready;ready.ldr.LoadCount++;return 1;}
 if(!dependency_available){*out=NULL;return 0;}
 missing_bindings++;*out=NULL;return 1;
}
static BOOL add_module_dependency_after(LDR_DDAG_NODE *from,LDR_DDAG_NODE *to,SINGLE_LIST_ENTRY *after){
 assert(to==ready.ldr.DdagNode);dependencies++;from->Dependencies.Tail=(void *)1;return TRUE;
}
static NTSTATUS fixup_imports_ilonly(WINE_MODREF *m,LPCWSTR path,void **entry){m->ldr.Flags&=~LDR_DONT_RESOLVE_REFS;return dependency_available?0:STATUS_DLL_NOT_FOUND;}
static void RELAY_SetupDLL(HMODULE m){}
static void SNOOP_SetupDLL(HMODULE m){}
'''
# Use the real resolution loop, including successful-descriptor tracking, TLS,
# activation-context handling and status propagation.
harness += function('static NTSTATUS fixup_imports(')
for signature in ('static void retain_failed_import_module(', 'static WINE_MODREF *find_failed_import_module(',
                  'static NTSTATUS retry_failed_import_module(', 'static void complete_loaded_module('):
    harness += function(signature)
harness += r'''
typedef struct {int unused;} SECTION_IMAGE_INFORMATION;
static WINE_MODREF *find_existing_module(HMODULE m){return NULL;}
static NTSTATUS NtMapViewOfSection(HANDLE mapping,HANDLE p,void **m,int a,int b,void *c,SIZE_T *s,int d,int e,int f){
 maps++;*m=malloc(4096);assert(*m);return 0;
}
static NTSTATUS NtUnmapViewOfSection(HANDLE p,void *m){free(m);return 0;}
static NTSTATUS build_module(LPCWSTR path,const UNICODE_STRING *name,void **module,const SECTION_IMAGE_INFORMATION *info,const struct file_id *id,DWORD flags,BOOL sys,BOOL redirected,WINE_MODREF **out){
 WINE_MODREF *m=calloc(1,sizeof(*m));assert(m);m->ldr.DdagNode=calloc(1,sizeof(*m->ldr.DdagNode));assert(m->ldr.DdagNode);
 m->ldr.DllBase=*module;m->ldr.Flags=LDR_DONT_RESOLVE_REFS;m->ldr.LoadCount=1;m->id=*id;
 m->ldr.FullDllName=*name;m->ldr.FullDllName.Buffer+=4;m->ldr.FullDllName.Length-=4*sizeof(WCHAR);m->ldr.BaseDllName=m->ldr.FullDllName;
 InsertTailList(&ldr.InLoadOrderModuleList,&m->ldr.InLoadOrderLinks);InsertTailList(&ldr.InMemoryOrderModuleList,&m->ldr.InMemoryOrderLinks);InsertTailList(&hash_table[0],&m->ldr.HashLinks);
 m->ldr.BaseAddressIndexNode.present=1;cached_modref=m;
 NTSTATUS st=(flags&LDR_DONT_RESOLVE_REFS)?0:fixup_imports(m,path);
 if(st){retain_failed_import_module(m,st);*out=NULL;}else{complete_loaded_module(m);*out=m;}
 *module=NULL;return st;
}
'''
harness += function('static NTSTATUS load_native_dll(')
harness += r'''
static UNICODE_STRING name(WCHAR *s){return (UNICODE_STRING){s,wcslen(s)*sizeof(WCHAR),0};}
static WINE_MODREF *private_module(void){return CONTAINING_RECORD(failed_import_modules.Flink,WINE_MODREF,failed_import_entry);}
static void release_all(void){
 LIST_ENTRY *heads[]={&failed_import_modules,&ldr.InLoadOrderModuleList};
 for(unsigned h=0;h<2;h++)while(heads[h]->Flink!=heads[h]){
  WINE_MODREF *m=h?CONTAINING_RECORD(heads[h]->Flink,WINE_MODREF,ldr.InLoadOrderLinks):CONTAINING_RECORD(heads[h]->Flink,WINE_MODREF,failed_import_entry);
  RemoveEntryList(heads[h]->Flink);free(m->resolved_imports);free(m->ldr.DllBase);free(m->ldr.DdagNode);free(m);
 }
}
static void init(void){
 InitializeListHead(&failed_import_modules);InitializeListHead(&ldr.InLoadOrderModuleList);InitializeListHead(&ldr.InMemoryOrderModuleList);
 for(unsigned i=0;i<HASH_MAP_SIZE;i++)InitializeListHead(&hash_table[i]);
 static LDR_DDAG_NODE ready_node;ready.ldr.DdagNode=&ready_node;ready.ldr.LoadCount=1;
 maps=tls_slots=contexts=ready_bindings=missing_bindings=dependencies=0;dependency_available=allocation_failure=0;cached_modref=NULL;
 teb.Peb=&peb;
}
int main(void){
 init();UNICODE_STRING a=name(L"\\??\\C:\\plugins\\network.dll");struct file_id id={{1}};WINE_MODREF *out=NULL;
 for(unsigned i=0;i<10345;i++){
  assert(load_native_dll(NULL,&a,NULL,NULL,&id,0,0,0,&out)==STATUS_DLL_NOT_FOUND);assert(!out);
  assert(maps==1&&tls_slots==1&&contexts==1&&ready_bindings==1&&dependencies==1);
  assert(failed_count()==1&&public_count()==0&&!cached_modref);
 }
 WINE_MODREF *held=private_module();void *base=held->ldr.DllBase;
 assert(held->import_status==STATUS_DLL_NOT_FOUND&&held->resolved_imports[0]&&!held->resolved_imports[1]);
 assert(ready.ldr.LoadCount==2); // no repeated references to a resolved descriptor
 // File identity allows hard-link aliases, while replacement at the same path does not reuse stale bytes.
 UNICODE_STRING alias=name(L"\\??\\C:\\other\\alias.dll");assert(find_failed_import_module(&alias,&id)==held);
 struct file_id replacement={{2}};assert(!find_failed_import_module(&a,&replacement));
 struct file_id zero={{0}};assert(find_failed_import_module(&a,&zero)==held);assert(!find_failed_import_module(&alias,&zero));
 dependency_available=1;
 assert(load_native_dll(NULL,&a,NULL,NULL,&id,0,0,0,&out)==0&&out==held&&out->ldr.DllBase==base);
 assert(!failed_count()&&public_count()==1&&maps==1&&tls_slots==1&&contexts==1&&missing_bindings==1&&ready_bindings==1);
 assert(!out->import_status&&!(out->ldr.Flags&LDR_DONT_RESOLVE_REFS));release_all();
 // Bitmap OOM is retryable without another image or another TLS slot.
 init();allocation_failure=1;assert(load_native_dll(NULL,&a,NULL,NULL,&id,0,0,0,&out)==STATUS_NO_MEMORY);
 assert(maps==1&&tls_slots==1&&!private_module()->resolved_imports);
 allocation_failure=0;dependency_available=1;assert(!load_native_dll(NULL,&a,NULL,NULL,&id,0,0,0,&out));
 assert(maps==1&&tls_slots==1&&contexts==1);release_all();
 // Failed graph edges remain valid, including an incoming cyclic dependency.
 init();assert(load_native_dll(NULL,&a,NULL,NULL,&id,0,0,0,&out)==STATUS_DLL_NOT_FOUND);
 held=private_module();held->ldr.DdagNode->IncomingDependencies.Tail=(void *)1;
 for(unsigned i=0;i<345;i++)assert(load_native_dll(NULL,&a,NULL,NULL,&id,0,0,0,&out)==STATUS_DLL_NOT_FOUND);
 assert(private_module()==held&&held->ldr.DdagNode->IncomingDependencies.Tail==(void *)1&&maps==1);release_all();
 puts("PASS: 10345 retries use one image/TLS/context; no duplicate IAT binding/refcounts; live dependency recovery, file replacement, bitmap OOM and cyclic references");
}
'''
with tempfile.TemporaryDirectory(prefix='madeira-import-retry-') as tmp:
    p = Path(tmp); (p/'test.c').write_text(harness)
    subprocess.run(['clang','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-variable',
                    '-Wno-unused-function','-fsanitize=address,undefined','-fno-sanitize-recover=all',
                    str(p/'test.c'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)
