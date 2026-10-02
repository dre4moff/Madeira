"""Exercise production POSIX detachment with synthetic mappings, never Wine."""
from pathlib import Path
import subprocess, tempfile
root=Path(__file__).resolve().parents[1]
src=r'''
#include <assert.h>
#include <fcntl.h>
#include <stdio.h>
#include <sys/mman.h>
#include "ephemeral_swap.h"
int main(int argc, char **argv) {
 assert(argc==2); assert(!chdir(argv[1]));
 int fd=open("madeira-swap.bin", O_RDWR|O_CREAT|O_EXCL,0600); assert(fd>=0);
 assert(!ftruncate(fd,8192));
 unsigned char *p=mmap(NULL,8192,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0); assert(p!=MAP_FAILED);
 p[4096]=99;
 assert(!madeira_detach_swap_file(fd,"madeira-swap.bin"));
 setenv("MADEIRA_SWAP_EPHEMERAL","1",1);
 assert(!rename("madeira-swap.bin","user-file"));
 assert(!symlink("user-file","madeira-swap.bin"));
 assert(!madeira_detach_swap_file(fd,"madeira-swap.bin"));
 assert(!unlink("madeira-swap.bin")); assert(!rename("user-file","madeira-swap.bin"));
 assert(!link("madeira-swap.bin","extra-link"));
 assert(!madeira_detach_swap_file(fd,"madeira-swap.bin")); assert(!unlink("extra-link"));
 int other=open("different",O_RDWR|O_CREAT,0600); assert(other>=0);
 assert(!madeira_detach_swap_file(other,"madeira-swap.bin")); close(other); unlink("different");
 assert(madeira_detach_swap_file(fd,"madeira-swap.bin"));
 assert(access("madeira-swap.bin",F_OK)!=0);
 assert(p[4096]==99); p[0]=42; assert(!msync(p,8192,MS_SYNC));
 unsigned char byte=0; assert(pread(fd,&byte,1,0)==1 && byte==42);
 struct stat st; assert(!fstat(fd,&st) && st.st_nlink==0 && st.st_size==8192);
 assert(!munmap(p,8192)); assert(!close(fd));
 puts("PASS: detached swap remains readable/writable/mappable; wrong inode, symlink, hardlink and opt-out protected");
}
'''
with tempfile.TemporaryDirectory(prefix='madeira-swap-test-') as tmp:
 p=Path(tmp);(p/'test.c').write_text(src)
 subprocess.run(['clang','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I',str(root/'build/ntdll-unix'),str(p/'test.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test'),tmp],check=True)
bridge=(root/'app/Madeira/WineProcessBridge.m').read_text()
assert 'setenv("MADEIRA_SWAP_EPHEMERAL", "1", 1)' in bridge
v=(root/'build/ntdll-unix/virtual_ios.c').read_text()
assert v.index('ftruncate( ios_swap_fd') < v.index('madeira_detach_swap_file(ios_swap_fd, f)')
