"""Exercise the real FD-send path with synthetic sendmsg outcomes, no Wine."""
from pathlib import Path
import tempfile
import subprocess
root=Path(__file__).resolve().parents[1]
s=(root/'build/wineserver/request_ios.c').read_text();a=s.index('int send_client_fd(');b=s.index('\n}',a)+2
source=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/socket.h>
#include <sys/uio.h>
#include <errno.h>
#include <string.h>
#include "runtime_profiling.h"
typedef uint32_t obj_handle_t;
struct process{unsigned id;int msg_fd;};struct thread{unsigned id;};
static struct thread *current;static int debug_level,logged,killed,reply=4,last_kill=-1;
static int get_unix_fd(int fd){return fd;}
#define ws_log(...) (++logged, errno=EINTR)
static void kill_process(struct process *p,int code){(void)p;last_kill=code;++killed;}
static int mock_sendmsg(int fd,const struct msghdr *msg,int flags){
 assert(fd==9 && !flags && msg->msg_iovlen==1 && msg->msg_iov->iov_len==4);
 assert(*(obj_handle_t *)msg->msg_iov->iov_base==123);
 struct cmsghdr *c=CMSG_FIRSTHDR((struct msghdr *)msg);
 assert(c->cmsg_type==SCM_RIGHTS && *(int *)CMSG_DATA(c)==7);
 errno=EPIPE;return reply;
}
#define sendmsg mock_sendmsg
'''+s[a:b]+r'''
int main(int argc,char **argv){
 assert(argc==2);setenv("MADEIRA_QUIET","1",1);setenv("MADEIRA_RUNTIME_PROFILING",argv[1],1);
 struct process p={1,9};int on=atoi(argv[1]);
 for(int i=0;i<10000;i++)assert(send_client_fd(&p,7,123)==0);
 assert(!killed && logged==on*20000);
 logged=0;reply=-1;assert(send_client_fd(&p,7,123)==-1 && killed==1 && last_kill==0 && logged>=2);
 logged=0;reply=2;assert(send_client_fd(&p,7,123)==-1 && killed==2 && last_kill==1 && logged>=2);
 puts("PASS: successful server FD handoffs preserve protocol with zero quiet-mode logs; errors remain logged and full profiling restores diagnostics");
}
'''
with tempfile.TemporaryDirectory() as folder:
 p=Path(folder);(p/'test.c').write_text(source)
 subprocess.run(['xcrun','clang','-fsanitize=address,undefined','-I'+str(root/'build/ntdll-unix'),str(p/'test.c'),'-o',str(p/'test')],check=True)
 for value in ['0','1']:subprocess.run([str(p/'test'),value],check=True)
