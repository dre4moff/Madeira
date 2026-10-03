"""Production streamed-upload branch/ring, with host buffers and completion fences.
No Metal device, game, Wine process or account is used.
"""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root/'dxmt/src/d3d11/d3d11_context_impl.cpp').read_text()
start = source.index('      if (direct_uploads && cpu_address) {')
branch = source[start:source.index('      SwitchToBlitEncoder(', start)]
ring = (root/'dxmt/src/dxmt/dxmt_ring_bump_allocator.hpp').read_text()
ring_class = ring[ring.index('template <typename Allocator, size_t BlockSize ='):ring.index('\nclass GpuPrivateBufferBlockAllocator')]
ring_impl = ring[ring.index('template <typename Allocator, size_t BlockSize, class mutex, bool InclusiveCompletion>'):ring.rindex('\n} // namespace dxmt')]
initializer = (root/'dxmt/src/dxmt/dxmt_resource_initializer.cpp').read_text()
batch = initializer[initializer.index('uint64_t\nResourceInitializer::finishUploadBatch()'):initializer.index('\nstd::uint64_t\nResourceInitializer::flushInternal()')]
cpp = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <mutex>
#include <queue>
#include <string>
#include <vector>
#include <cstdio>
#include "dxmt_texture_upload.hpp"
using dxmt::copyTextureUpload;
namespace dxmt { using mutex=std::mutex; }
namespace env { std::string getEnvVar(const char *n) {const char *v=getenv(n);return v?v:"";} }
#define WARN(...) ((void)0)
bool ringOversizeReuseEnabled() {return false;}
constexpr size_t kStagingBlockSize=32u<<20, kStagingBlockLifetime=300;
size_t align(size_t x,size_t a) {return (x+a-1)/a*a;}
struct Buffer {
 std::vector<unsigned char> data;
 unsigned calls=0;
 void updateContents(size_t off,const void *p,size_t n) {calls++;memcpy(data.data()+off,p,n);}
};
void upload(Buffer &staging_buffer,const void *pSrcData,unsigned SrcRowPitch,unsigned SrcDepthPitch,
            size_t rows,size_t depth,size_t row,bool direct_uploads,bool local) {
 struct { size_t EffectiveRows,EffectiveBytesPerRow;struct {size_t depth;} DstSize; } cmd{rows,row,{depth}};
 const size_t offset=32,bytes_per_depth_slice=rows*row;
 void *cpu_address=local?staging_buffer.data.data():nullptr;
''' + branch + r'''
}
struct State {size_t calls=0,live=0,peak=0,next=0;};
struct Allocator {
 std::shared_ptr<State> state;
 struct Block {
  std::shared_ptr<State> state;size_t size=0,id=0;
  Block(std::shared_ptr<State> s,size_t n):state(s),size(n),id(++s->next) {
   state->calls++;state->live+=size;state->peak=std::max(state->peak,state->live);
  }
  Block(Block&&b):state(std::move(b.state)),size(b.size),id(b.id) {b.size=0;}
  ~Block() {if(state)state->live-=size;}
 };
 Block allocate(size_t n) {return {state,n};}
};
''' + ring_class + ring_impl + r'''
using OldRing=RingBumpState<Allocator,32u<<20>;
using UploadRing=RingBumpState<Allocator,8u<<20,dxmt::mutex,true>;
struct ResourceInitializer {
 uint64_t current_seq_id_=1;
 size_t pending_upload_bytes_=0,submitted=0;
 uint64_t finishUploadBatch();
 void flushInternal() {assert(pending_upload_bytes_);submitted++;current_seq_id_++;pending_upload_bytes_=0;}
};
#define DXMT_IOS 1
''' + batch + r'''
int main(int argc,char **argv) {
 (void)argv;
 if(argc>1) {
  setenv("DXMT_RING_OVERSIZE_REUSE","0",1);
  auto s=std::make_shared<State>();UploadRing r(Allocator{s});
  r.allocate(1,0,20u<<20,256);r.seal_latest();r.free_blocks(1);
  assert(s->live==0);r.allocate(2,1,20u<<20,256);assert(s->calls==2);
  puts("PASS: medium upload reuse explicit opt-out");return 0;
 }
 for(size_t rows:{1u,4u,257u}) for(size_t depth:{1u,3u}) for(size_t pitch:{16u,24u}) {
  const size_t image=pitch*rows+32;std::vector<unsigned char> src(image*depth);
  for(size_t i=0;i<src.size();i++)src[i]=static_cast<unsigned char>(i*17+3);
  Buffer old{std::vector<unsigned char>(32+rows*16*depth+32,0xA5)},direct=old,remote=old,optout=old;
  upload(old,src.data(),pitch,image,rows,depth,16,false,false);
  upload(direct,src.data(),pitch,image,rows,depth,16,true,true);
  upload(remote,src.data(),pitch,image,rows,depth,16,true,false);
  upload(optout,src.data(),pitch,image,rows,depth,16,false,true);
  assert(old.data==direct.data && old.data==remote.data && old.data==optout.data);
  assert(direct.calls==0 && remote.calls==old.calls && optout.calls==old.calls);
  assert(old.calls==(pitch==16?depth:rows*depth));
 }
 // One small transfer reserves 8 instead of 32 MiB; this is allocated
 // capacity, not physical-device residency or a measured 200MiB saving.
 auto a=std::make_shared<State>(),b=std::make_shared<State>();
 {OldRing old(Allocator{a});UploadRing next(Allocator{b});
  old.allocate(1,0,1u<<20,256);next.allocate(1,0,1u<<20,256);
  assert(a->live==32u<<20 && b->live==8u<<20);
 }
 assert(a->live==0 && b->live==0);
 {
  auto s=std::make_shared<State>();UploadRing r(Allocator{s});
  auto first=r.allocate(1,0,8u<<20,256).first.id;
  auto second=r.allocate(2,0,8u<<20,256).first.id;
  assert(first!=second && s->live==16u<<20); // both still in flight
  auto reuse=r.allocate(3,1,8u<<20,256).first.id;
  assert(reuse==first && s->calls==2); // completed sequence is inclusive
  auto other=r.allocate(3,3,8u<<20,256).first.id;
  assert(other==second); // last_used=2 < completed=3
  auto current=r.allocate(3,3,8u<<20,256).first.id;
  assert(current!=reuse && current!=other); // never reset current batch
  r.free_blocks(2);assert(s->live==24u<<20); // no in-flight retirement
  r.free_blocks(~0ull);assert(s->live==0);
 }
 {
  auto s=std::make_shared<State>();UploadRing r(Allocator{s});r.preallocate(1);
  assert(s->calls==1);r.allocate(1,0,8u<<20,256);assert(s->calls==1);
 }
 {
  auto s=std::make_shared<State>();UploadRing r(Allocator{s});
  for(uint64_t seq=1;seq<=10000;seq++) {
   r.allocate(seq,seq-1,20u<<20,256);r.seal_latest();r.free_blocks(seq);
  }
  assert(s->calls==1 && s->live==20u<<20); // no new medium upload churn
  r.free_blocks(10301);assert(s->live==0); // original expiry
 }
 {
  auto s=std::make_shared<State>();UploadRing r(Allocator{s});
  r.allocate(1,0,20u<<20,256);r.allocate(2,0,20u<<20,256);r.allocate(3,0,20u<<20,256);
  assert(s->live==60u<<20);r.free_blocks(3); // third is never kept warm
  r.allocate(4,3,24u<<20,256); // retire undersized completed prefix
  assert(s->live==24u<<20);
  r.free_blocks(4);r.free_blocks(305);assert(s->live==0);
  r.allocate(306,305,64u<<20,256);r.free_blocks(306);assert(s->live==0);
 }
 {
  ResourceInitializer init;size_t peak=0;
  for(unsigned i=0;i<900;i++) {
   const auto owning_seq=init.current_seq_id_;
   init.pending_upload_bytes_+=1200u*1024;
   peak=std::max(peak,init.pending_upload_bytes_);
   assert(init.finishUploadBatch()==owning_seq);
  }
  assert(init.submitted==16 && peak<=(64u<<20)+1200u*1024);
  init.pending_upload_bytes_=128u<<20;const auto seq=init.current_seq_id_;
  assert(init.finishUploadBatch()==seq && init.current_seq_id_==seq+1);
  const auto submits=init.submitted;
  assert(init.finishUploadBatch()==seq+1 && init.submitted==submits); // idle never submits
  puts("PASS: 900 creation uploads submit at 64MiB boundaries; pending bytes bounded by threshold plus one upload, owning event IDs preserved");
 }
 puts("PASS: actual streamed copies preserve rows/depth/guards, local upload removes up to 771 bridge calls; remote/opt-out retain original delivery");
 puts("PASS: actual ring capacity 32->8MiB, inclusive completed reuse, in-flight/current-batch protection, 10000 medium uploads/one allocation, two-block bound, expiry and oversize release");
}
'''
with tempfile.TemporaryDirectory(prefix='madeira-stream-test-') as tmp:
 p=Path(tmp);(p/'check.cpp').write_text(cpp)
 subprocess.run(['clang++','-std=c++20','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-pthread',
                 '-I',str(root/'dxmt/src/dxmt'),str(p/'check.cpp'),'-o',str(p/'check')],check=True)
 subprocess.run([str(p/'check')],check=True)
 subprocess.run([str(p/'check'),'opt-out'],check=True)
for name in ('imm','def'):
 s=(root/f'dxmt/src/d3d11/d3d11_context_{name}.cpp').read_text()
 assert 'AllocateStagingBuffer(size_t size, size_t alignment, void **cpu_address)' in s
 assert 'size, alignment, cpu_address' in s
assert '!(block.buffer.handle & (1ull << 63))' in ring
assert 'RingBumpState<StagingBufferBlockAllocator, kTextureUploadBlockSize,' in (root/'dxmt/src/dxmt/dxmt_command_queue.hpp').read_text()
assert 'gpu_command_heap_allocator.allocate(\n      current_seq_id_, cached_coherent_seq_id' in (root/'dxmt/src/dxmt/dxmt_resource_initializer.cpp').read_text()
assert 'if (block.buffer) pending_upload_bytes_ += size;' in initializer
assert 'pending_upload_bytes_ = 0;' in initializer[initializer.index('ResourceInitializer::reset()'):]
created = initializer[initializer.index('ResourceInitializer::initWithData('):initializer.index('uint64_t\nResourceInitializer::finishUploadBatch()')]
assert created.rstrip().endswith('return finishUploadBatch();\n}')
assert 'upload_queue_ = device.newCommandQueue(kResourceInitializerChunks);' in initializer
print('PASS: immediate/deferred contexts and initialization retain fence ownership and remote handle guard')
