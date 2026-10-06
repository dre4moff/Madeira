"""Actual host socket reuse through production poll-slot hooks, no Wine/Steam."""
from pathlib import Path
import subprocess, tempfile
root = Path(__file__).resolve().parents[1]
text = (root/'build/wineserver/fd_ios.c').read_text()
def function(signature):
    start = text.index(signature)
    return text[start:text.index('\n}', start)+2]
fixture = r'''
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>
static int fail_alloc, classifications;
static void *cache_malloc(size_t size){ if(fail_alloc){fail_alloc=0;errno=ENOMEM;return NULL;}return malloc(size); }
static int cached_getsockname(int fd,struct sockaddr *s,socklen_t *n){classifications++;return getsockname(fd,s,n);}
#define malloc cache_malloc
#define getsockname cached_getsockname
#include "poll_fd_cache.h"
#undef malloc
#undef getsockname
#include <poll.h>
struct fd {int unix_fd;};
static struct fd **poll_users, **freelist;
static struct pollfd *pollfd;
static int nb_users,allocated_users,active_users;
static void init_epoll(void){}
static void remove_epoll_user(struct fd *fd,int user){(void)fd;(void)user;}
static int madeira_runtime_profiling_cached(void){return 0;}
#define ws_log(...) ((void)0)
''' + function('static int add_poll_user(') + '\n' + function('static void remove_poll_user(') + r'''
int main(void){
 int pair[2];assert(socketpair(AF_UNIX,SOCK_STREAM,0,pair)==0);
 int inet=socket(AF_INET,SOCK_STREAM,0);assert(inet>=0);
 int target=dup(pair[0]);assert(target>=0);struct fd entry={target};
 int slot=add_poll_user(&entry);assert(slot==0);
 assert(ios_fd_is_inet(slot,target)==0);
 int calls=classifications;
 for(int i=0;i<10000;i++)assert(ios_fd_is_inet(slot,target)==0);
 assert(classifications==calls);
 for(int i=0;i<200;i++){
   remove_poll_user(&entry,slot);
   int is_inet=!(i&1);assert(dup2(is_inet?inet:pair[0],target)==target);
   assert(add_poll_user(&entry)==slot);
   errno=EPIPE;assert(ios_fd_is_inet(slot,target)==is_inet);assert(errno==EPIPE);
   calls=classifications;
   for(int k=0;k<100;k++)assert(ios_fd_is_inet(slot,target)==is_inet);
   assert(classifications==calls);
 }
 /* Growth failure never corrupts the old allocation or caches INET as a pipe. */
 struct ios_poll_fd_kind *base=ios_poll_fd_kinds;
 int count=ios_poll_fd_kind_count;fail_alloc=1;errno=EAGAIN;
 assert(ios_fd_is_inet(100,inet)==1 && errno==EAGAIN);
 assert(ios_poll_fd_kinds==base && ios_poll_fd_kind_count==count);
 assert(ios_fd_is_inet(slot,target)==0);
 assert(ios_fd_is_inet(100,inet)==1 && ios_poll_fd_kind_count>100);
 int inet6=socket(AF_INET6,SOCK_STREAM,0);assert(inet6>=0);
 assert(ios_fd_is_inet(200,inet6)==1);close(inet6);
 close(pair[0]);close(pair[1]);close(target);close(inet);
 free(ios_poll_fd_kinds);free(poll_users);free(pollfd);
 puts("PASS: production add/remove hooks invalidate 200 exact descriptor/slot reuses; hot cache avoids syscalls; OOM growth preserves old entries and classifies IPv4/IPv6 correctly");
}
'''
# Reproduce the pre-fix defect using the actual baseline classifier.
old = subprocess.check_output(['git','show','8263076d0c815d2dc47de3cc585d803da4f68012^:build/wineserver/fd_ios.c'],cwd=root,text=True)
a=old.index('static signed char ios_fd_is_inet(');b=old.index('\nvoid main_loop(void)',a)
regression='''
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>
#include <stdio.h>
'''+old[a:b]+r'''
int main(void){int p[2];assert(!socketpair(AF_UNIX,SOCK_STREAM,0,p));int inet=socket(AF_INET,SOCK_STREAM,0);assert(inet>=0);
 assert(!ios_fd_is_inet(1,p[0]));assert(dup2(inet,p[0])==p[0]);
 assert(!ios_fd_is_inet(1,p[0]));
 puts("CONFIRMED baseline defect: an IPv4 socket reusing a cached Unix descriptor is incorrectly classified as a pipe");}
'''
with tempfile.TemporaryDirectory(prefix='madeira-poll-reuse-') as folder:
 p=Path(folder)
 for name,source,sanitize in [('baseline',regression,False),('fixed',fixture,True)]:
  (p/(name+'.c')).write_text(source)
  flags=['-fsanitize=address,undefined'] if sanitize else []
  subprocess.run(['xcrun','clang','-Wall','-Wextra',*flags,'-I'+str(root/'build/wineserver'),str(p/(name+'.c')),'-o',str(p/name)],check=True)
  subprocess.run([str(p/name)],check=True)
