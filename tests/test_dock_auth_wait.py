# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 125hz
# Madeira Converter Exception: see LICENSE-EXCEPTION.md
"""Production Dock session driven by a synthetic client/clock; never Steam."""
from pathlib import Path
import subprocess, tempfile
root=Path(__file__).resolve().parents[1]
fixture=r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "session.h"
#include "auth.h"
#include "launch.h"
static uint64_t clock_ms;
static int online_mode, reports, phases, released, launched, callbacks;
static void *user_methods[183],*engine_methods[9];
static void **user_object=user_methods,**engine_object=engine_methods;
bool dock_method_is(uintptr_t m,void *o,unsigned slot,uintptr_t rva){(void)m;(void)o;(void)slot;(void)rva;return true;}
DWORD GetEnvironmentVariableW(const wchar_t *name,wchar_t *value,DWORD cap){(void)name;(void)value;(void)cap;return 0;}
bool dock_auth_consume_diagnostic(const wchar_t *p,struct dock_auth *a,struct dock_auth_failure *f){(void)p;(void)a;(void)f;assert(0);return false;}
void dock_auth_clear(void *b,size_t n){memset(b,0,n);}
static void *get_user(void *o,int32_t u,int32_t p){(void)o;assert(u==1&&p==2);return &user_object;}
static bool cached(void *o,const char *n){(void)o;assert(!strcmp(n,"synthetic"));return true;}
static bool selected(void *o,const char *n,bool remembered){(void)o;(void)n;assert(!remembered);return true;}
static int32_t logon(void *o,uint64_t id){(void)o;assert(id==76561197960265729ULL);return 1;}
static bool private_online(void *o){(void)o;assert(online_mode);return true;}
static bool connected(void *o){(void)o;assert(online_mode);return true;}
static bool subscribed(void *o,uint32_t app){(void)o;(void)app;return true;}
static int32_t subscriptions(void *o,uint32_t *apps,int32_t count,bool all){(void)o;assert(count==65536&&all);apps[0]=42;return 1;}
int sh_launch(HMODULE m,void *e,void *u,const struct sh_api *api,const struct sh_observer *obs,int32_t p,int32_t h,uint64_t id,uint32_t app,const struct dock_client_layout *l){(void)m;(void)e;(void)u;(void)api;(void)obs;(void)p;(void)h;(void)id;(void)l;assert(online_mode&&app==42);launched++;return 0;}
static int32_t create(int32_t *pipe){*pipe=2;return 1;}
static void release_user(int32_t p,int32_t u){assert(p==2&&u==1);released++;}
static bool release_pipe(int32_t p){assert(p==2);released++;return true;}
static bool get_callback(int32_t p,struct sh_callback *cb){assert(p==2);if(callbacks++==0){*cb=(struct sh_callback){1,304,NULL,0};return true;}return false;}
static void free_callback(int32_t p){assert(p==2);}
static bool public_online(int32_t u,int32_t p){assert(u==1&&p==2);return online_mode;}
static uint64_t now(void){return clock_ms;}
static void sleep_ms(uint32_t n){clock_ms+=n;}
static void event(const char *stage,int32_t v){
 if(!strcmp(stage,"session-auth-wait-ms")){assert(v>=0&&v<90000);reports++;}
 if(!strcmp(stage,"session-auth-state"))assert(v==(online_mode?7:0));
 if(!strcmp(stage,"session-auth-step")){assert(v>=1&&v<=5);phases++;}
 assert(!strstr(stage,"token=")&&!strstr(stage,"account="));
}
int main(void){
 setenv("MADEIRA_STEAM_HOST_LOGIN","1",1);setenv("MADEIRA_STEAM_HOST_ACCOUNT","synthetic",1);
 setenv("MADEIRA_STEAM_HOST_STEAMID","76561197960265729",1);setenv("MADEIRA_STEAM_HOST_APPID","42",1);setenv("MADEIRA_STEAM_HOST_LAUNCH","1",1);
 engine_methods[8]=(void *)get_user;user_methods[1]=(void *)logon;user_methods[4]=(void *)private_online;user_methods[6]=(void *)connected;
 user_methods[49]=(void *)cached;user_methods[50]=(void *)selected;user_methods[181]=(void *)subscribed;user_methods[182]=(void *)subscriptions;
 struct dock_client_layout layout={0};struct sh_api api={create,release_user,release_pipe,get_callback,free_callback,public_online};struct sh_observer obs={now,sleep_ms,event};
 clock_ms=100;assert(sh_session(NULL,&engine_object,&api,&obs,&layout)==34);
 assert(clock_ms==90100&&reports==9&&phases==27&&released==2&&!launched);
 online_mode=1;reports=phases=released=callbacks=0;clock_ms=100;
 assert(sh_session(NULL,&engine_object,&api,&obs,&layout)==0);
 assert(launched==1&&reports==1&&phases==5&&released==2&&clock_ms==5100);
 puts("PASS: production session times out unauthenticated at 90 s, emits only nine checkpoints, preserves short-circuit calls, and launches only after online state and subscription-list confirmation");
}
'''
with tempfile.TemporaryDirectory(prefix='madeira-auth-wait-') as folder:
 p=Path(folder)
 (p/'windows.h').write_text('#include <stdint.h>\n#include <stddef.h>\n#define __thiscall\n#define __cdecl\ntypedef void *HMODULE;typedef uint32_t DWORD;\nDWORD GetEnvironmentVariableW(const wchar_t *,wchar_t *,DWORD);\n')
 (p/'test.c').write_text(fixture)
 subprocess.run(['xcrun','clang','-std=c11','-D_WIN32','-D_WIN64','-fsanitize=address,undefined','-fno-sanitize=function','-I'+str(p),'-I'+str(root/'madeira-dock/src'),str(p/'test.c'),str(root/'madeira-dock/src/session.c'),str(root/'madeira-dock/src/validation.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
