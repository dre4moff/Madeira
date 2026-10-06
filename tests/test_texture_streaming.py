"""Exercise the real native upload entry, streamed branch and WoW64 wrapper.
Host byte/call-count validation; no physical-device FPS claim.
"""
from pathlib import Path
import os, re, subprocess, tempfile
root=Path(__file__).resolve().parents[1]
src=(root/'dxmt/src/d3d11/d3d11_context_impl.cpp').read_text()
start=src.index('      if (direct_uploads && cpu_address) {')
branch=src[start:src.index('      /* ml1252:',start)]
unix=(root/'dxmt/src/winemetal/unix/winemetal_unix.c').read_text()
start=unix.index('static NTSTATUS\n_MTLBuffer_updateTextureContents(')
handler=unix[start:unix.index('static NTSTATUS\n_WMTGetOSVersion(',start)]
start=unix.index('static NTSTATUS\n_MTLBuffer_updateTextureContents32(')
wrapper=unix[start:unix.index('static NTSTATUS\n_DispatchData_alloc_init32(',start)]
cpp=r'''#import <Foundation/Foundation.h>
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <vector>
#include "texture_upload_copy.h"
#undef TARGET_OS_IOS
#define TARGET_OS_IOS 1
using NTSTATUS=int;
constexpr int STATUS_SUCCESS=0, STATUS_INVALID_PARAMETER=1;
using obj_handle_t=uint64_t;
struct WMTConstMemoryPointer {const void *ptr;};
struct unixcall_mtlbuffer_updatecontents {obj_handle_t buffer;uint64_t offset;WMTConstMemoryPointer data;uint64_t length;};
struct unixcall_mtlbuffer_updatetexturecontents {obj_handle_t buffer;uint64_t offset;WMTConstMemoryPointer data;uint64_t rows,depth,dst_row,src_row,src_image,valid_row,valid_image;};
static_assert(sizeof(unixcall_mtlbuffer_updatetexturecontents)==80);
static bool remote=false;
static size_t remote_calls=0, contents_calls=0;
static unsigned char *remote_memory=nullptr;
bool wmtr_enabled(){return remote;}
NTSTATUS _MTLBuffer_updateContents(void *obj) {
 auto *p=static_cast<unixcall_mtlbuffer_updatecontents *>(obj);
 remote_calls++;memcpy(remote_memory+p->offset,p->data.ptr,p->length);return 0;
}
static const void *mapped_guest=nullptr;
const void *wow_in(const void *) {return mapped_guest;}
@protocol MTLBuffer
-(NSUInteger)length;
-(void *)contents;
@end
@interface NativeBuffer:NSObject<MTLBuffer> {@public unsigned char *memory;size_t capacity;}
@end
@implementation NativeBuffer
-(NSUInteger)length{return capacity;}
-(void *)contents{contents_calls++;return memory;}
@end
''' + handler + wrapper + r'''
struct Buffer {
 std::vector<unsigned char> data;
 size_t original_calls=0,native_calls=0;
 void updateContents(size_t off,const void *p,size_t n) {original_calls++;memcpy(data.data()+off,p,n);}
 void updateTextureContents(size_t off,const void *p,size_t rows,size_t depth,size_t row,size_t pitch,size_t image,size_t valid_row,size_t valid_image) {
   native_calls++;
   NativeBuffer *b=[NativeBuffer new];b->memory=data.data();b->capacity=data.size();
   unixcall_mtlbuffer_updatetexturecontents args={(uint64_t)b,off,{p},rows,depth,row,pitch,image,valid_row,valid_image};
   assert(_MTLBuffer_updateTextureContents(&args)==0);[b release];
 }
};
void upload(Buffer &staging_buffer,const void *pSrcData,unsigned SrcRowPitch,unsigned SrcDepthPitch,
            size_t rows,size_t depth,size_t row,bool direct_uploads,bool local) {
 struct {size_t EffectiveRows,EffectiveBytesPerRow;struct {size_t depth;} DstSize;} cmd{rows,row,{depth}};
 size_t offset=32,bytes_per_depth_slice=rows*row;
 void *cpu_address=local?staging_buffer.data.data():nullptr;
''' + branch + r'''
}
int main() {@autoreleasepool {
 size_t max_old_calls=0;
 for(size_t rows:{1u,4u,257u}) for(size_t depth:{1u,3u}) for(size_t pitch:{16u,24u}) for(size_t extra:{0u,32u}) {
   size_t row=16,image=pitch*rows+extra,needed=row*rows*depth;
   std::vector<unsigned char> input(image*depth);
   for(size_t i=0;i<input.size();i++)input[i]=(i*17+3)%256;
   Buffer ref{std::vector<unsigned char>(32+needed+32,0x5a)},native=ref,optout=ref,remote_path=ref;
   auto run=[&](Buffer &b,bool on,bool local){upload(b,input.data(),pitch,image,rows,depth,row,on,local);};
   run(ref,false,false);run(native,true,true);run(optout,false,true);run(remote_path,true,false);
   assert(native.data==ref.data && optout.data==ref.data && remote_path.data==ref.data);
   assert(native.native_calls==1 && native.original_calls==0);
   assert(optout.native_calls==0 && optout.original_calls==ref.original_calls);
   assert(remote_path.native_calls==0 && remote_path.original_calls==ref.original_calls);
   max_old_calls=std::max(max_old_calls,ref.original_calls);
 }
 // Real remote entry must preserve explicit delivery and never touch an ObjC handle.
 std::vector<unsigned char> input(24*4*3,0x23),output(32+16*4*3+32,0x5a);
 remote=true;remote_memory=output.data();size_t before=contents_calls;
 unixcall_mtlbuffer_updatetexturecontents p={1ull<<63,32,{input.data()},4,3,16,24,96,16,64};
 assert(_MTLBuffer_updateTextureContents(&p)==0 && remote_calls==12 && contents_calls==before);
 for(size_t z=0;z<3;z++)for(size_t y=0;y<4;y++)assert(!memcmp(output.data()+32+z*64+y*16,input.data()+z*96+y*24,16));
 remote=false;
 // Actual WoW64 wrapper translates and restores only the source pointer.
 NativeBuffer *b=[NativeBuffer new];b->memory=output.data();b->capacity=output.size();
 p.buffer=(uint64_t)b;p.data.ptr=(void *)0x1234;mapped_guest=input.data();
 assert(_MTLBuffer_updateTextureContents32(&p)==0 && p.data.ptr==(void *)0x1234);
 // Bounds/overflow rejection occurs before a destination lookup/copy.
 before=contents_calls;p.rows=SIZE_MAX;
 assert(_MTLBuffer_updateTextureContents(&p)==STATUS_INVALID_PARAMETER && contents_calls==before);
 p.rows=4;p.data.ptr=input.data();p.offset=SIZE_MAX;
 assert(_MTLBuffer_updateTextureContents(&p)==STATUS_INVALID_PARAMETER && contents_calls==before);
 p.offset=output.size()-1;
 assert(_MTLBuffer_updateTextureContents(&p)==STATUS_INVALID_PARAMETER && contents_calls==before);
 [b release];
 // Short valid data is zero padded without reading guest padding or crossing a guard.
 unsigned char short_src[8]={1,2,3,4,5,6,7,8},padded[24];memset(padded,0x5a,sizeof padded);
 wmt_copy_texture_upload(padded+4,short_src,2,1,8,4,8,4,16);
 assert(!memcmp(padded+4,short_src,4) && !memcmp(padded+12,short_src+4,4));
 for(unsigned i:{8u,9u,10u,11u,16u,17u,18u,19u})assert(padded[i]==0);
 for(unsigned i:{0u,3u,20u,23u})assert(padded[i]==0x5a);
 printf("PASS: real native entry/streamed branch preserve padded rows, depths and guards; %zu bridge calls become one native call; remote/opt-out and WoW64 ordering preserved\n",max_old_calls);
 }}
'''
with tempfile.TemporaryDirectory(prefix='madeira-native-upload-') as tmp:
 p=Path(tmp);(p/'check.mm').write_text(cpp)
 subprocess.run(['clang++','-std=c++20','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-fsanitize=address,undefined','-framework','Foundation',
 '-I',str(root/'dxmt/src/winemetal/unix'),str(p/'check.mm'),'-o',str(p/'check')],check=True)
 subprocess.run([str(p/'check')],check=True)
# Existing ABI slots are immutable; the new operation is appended to both tables.
old=subprocess.check_output(['git','show','2abb0b:src/winemetal/unix/winemetal_unix.c'],cwd=root/'dxmt',text=True)
for table in ('__wine_unix_call_funcs','__wine_unix_call_wow64_funcs'):
 def slots(text):
  body=re.search(r'const void \*'+table+r'\[\] = \{(.*?)\n\};',text,re.S).group(1)
  return re.findall(r'^\s*(&?[A-Za-z0-9_]+|NULL)\s*,',body,re.M)
 assert slots(unix)[:-1]==slots(old) and len(slots(unix))==152
ring=(root/'dxmt/src/dxmt/dxmt_ring_bump_allocator.hpp').read_text()
assert 'kCompactTextureStaging' not in ring and 'InclusiveCompletion' not in ring
initializer=(root/'dxmt/src/dxmt/dxmt_resource_initializer.cpp').read_text()
assert 'finishUploadBatch' not in initializer and 'pending_upload_bytes_' not in initializer
print('PASS: all original dispatch slots, ring allocation/lifetime policy and resource batch scheduling preserved')
