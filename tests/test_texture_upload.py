"""Actual texture upload branch/helper, mock Metal buffer and padded mip/volume data."""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parents[1]
init=(root/'dxmt/src/dxmt/dxmt_resource_initializer.cpp').read_text()
start=init.index('    if (direct_uploads_ && cpu_address) {')
branch=init[start:init.index('    copy->type = WMTBlitCommandCopyFromBufferToTexture;',start)]
src=r'''
#include <vector>
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include "dxmt_texture_upload.hpp"
using dxmt::copyTextureUpload;
size_t align(size_t x,size_t y) {return (x+y-1)/y*y;}
const char *ptr_add(const void *p,size_t n) {return static_cast<const char *>(p)+n;}
struct Buffer {
 std::vector<unsigned char> bytes;
 size_t calls=0;
 void updateContents(size_t offset,const void *p,size_t length) { calls++; memcpy(bytes.data()+offset,p,length); }
};
void upload(Buffer &temp,const void *data,bool direct_uploads_,bool mapped,
 size_t rows,size_t depth_sub,size_t bytes_per_row_needed,size_t bytes_per_row_increment,
 size_t bytes_per_image_increment,size_t bytes_per_row_valid,size_t bytes_per_image_valid) {
 const size_t temp_offset=32,bytes_per_image_needed=rows*bytes_per_row_needed,height_sub=rows,block_size=1;
 void *cpu_address=mapped ? temp.bytes.data() : nullptr;
''' + branch + r'''
}
int main() {
 for (size_t rows: {1u,4u,6u}) for(size_t depth: {1u,3u}) for(size_t pitch: {8u,16u,24u}) {
   size_t image=pitch*rows, needed=16*rows;
   std::vector<unsigned char> input(image*depth);
   for(size_t i=0;i<input.size();i++) input[i]=static_cast<unsigned char>(i*13+7);
   Buffer reference{std::vector<unsigned char>(32+needed*depth+16,0)}, direct=reference, remote=reference, optout=reference;
   auto run=[&](Buffer &b,bool on,bool mapped) { upload(b,input.data(),on,mapped,rows,depth,16,pitch,image,std::min(pitch,size_t(16)),needed); };
   run(reference,false,false);run(direct,true,true);run(remote,true,false);run(optout,false,true);
   assert(direct.bytes==reference.bytes && remote.bytes==reference.bytes && optout.bytes==reference.bytes);
   assert(direct.calls==0 && remote.calls==reference.calls && optout.calls==reference.calls);
   assert(reference.calls==(pitch==16 ? depth : rows*depth));
 }
 // Short 3D slice pitch: same row pitch, only existing source bytes copied.
 std::vector<unsigned char> data(96,17);
 Buffer ref{std::vector<unsigned char>(32+192+16)}, direct=ref;
 upload(ref,data.data(),false,false,6,2,16,16,48,16,48);
 upload(direct,data.data(),true,true,6,2,16,16,48,16,48);
 assert(ref.bytes==direct.bytes && direct.calls==0 && ref.calls==2);
 puts("PASS: texture data/strides/volumes match original uploads, no boundary overwrite; local direct path avoids all updateContents calls; remote/opt-out retain uploads");
}
'''
with tempfile.TemporaryDirectory(prefix='madeira-texture-test-') as tmp:
 p=Path(tmp);(p/'test.cpp').write_text(src)
 subprocess.run(['clang++','-std=c++20','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I',str(root/'dxmt/src/dxmt'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
ring=(root/'dxmt/src/dxmt/dxmt_ring_bump_allocator.hpp').read_text()
assert '!(block.buffer.handle & (1ull << 63))' in ring
assert 'free(cpu_address)' not in ring
assert 'current_seq_id_, cached_coherent_seq_id' in init
assert 'supports_bc_ = device.supportsBCTextureCompression();' in init
print('PASS: remote handle fallback, non-owning pointer and existing completion fence allocation retained')
