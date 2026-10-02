"""Execute baseline/new production allocators with synthetic fenced resources."""
from pathlib import Path
import subprocess
import tempfile
import re

root = Path(__file__).resolve().parents[1]
new = (root/'dxmt/src/dxmt/dxmt_dynamic.cpp').read_text()
old = subprocess.check_output(['git', 'show', 'HEAD:src/dxmt/dxmt_dynamic.cpp'], cwd=root/'dxmt').decode()
def allocator(source, cls):
    a = source.index('Rc<BufferAllocation>\nDynamicBuffer::allocate(')
    b = source.index('\nvoid\nDynamicBuffer::updateImmediateName(', a)
    return source[a:b].replace('DynamicBuffer::allocate(', cls+'::allocate(')
functions = allocator(old, 'Baseline') + allocator(new, 'Optimized')
# The production fields are diagnostic atomics only, stubbed without Metal.
fields = sorted(set(re.findall(r'g_mem_census\.(\w+)', functions)))
stat_fields = sorted(set(re.findall(r'(?:st|g_dyn_stats\[census_id_\])\.(\w+)', functions)))
cpp = r'''
#include <atomic>
#include <cassert>
#include <cstdint>
#include <deque>
#include <memory>
#include <mutex>
#include <random>
#include <cstdio>
#include <vector>
namespace dxmt { using mutex=std::mutex; }
static bool diagnostics;
static bool madeiraTextureDiagnosticsEnabled() { return diagnostics; }
static unsigned reports, fresh;
static void mem_census_report(const char *) { ++reports; }
template<typename T> struct Rc {
  std::shared_ptr<T> value;
  T *ptr() const { return value.get(); }
  T *operator->() const { return ptr(); }
};
struct BufferAllocation { uint64_t census_bytes_=16; unsigned id; };
struct Buffer {
  Rc<BufferAllocation> allocate(int, const char *) {
    ++fresh;return {std::make_shared<BufferAllocation>(BufferAllocation{16,100000+fresh})};
  }
};
constexpr unsigned DYN_CENSUS_SLOTS=8192;
struct DynStat {
''' + ''.join(' std::atomic<uint64_t> '+s+'{0};\n' for s in stat_fields) + r'''
};
static DynStat g_dyn_stats[DYN_CENSUS_SLOTS];
static struct {
''' + ''.join(' std::atomic<uint64_t> '+s+'{0};\n' for s in fields) + r'''
} g_mem_census;
static std::atomic<uint64_t> g_trim_total_n{0},g_trim_total_bytes{0},g_trim_regret{0};
struct QueueEntry { Rc<BufferAllocation> allocation; uint64_t will_free_at; };
struct CountedQueue : std::deque<QueueEntry> {
  mutable unsigned visits=0;
  struct Iterator {
    std::deque<QueueEntry>::const_iterator i;
    const CountedQueue *owner;
    const QueueEntry &operator*() const { ++owner->visits; return *i; }
    Iterator &operator++() { ++i;return *this; }
    bool operator!=(const Iterator &o) const { return i!=o.i; }
  };
  Iterator begin() const { return {std::deque<QueueEntry>::begin(),this}; }
  Iterator end() const { return {std::deque<QueueEntry>::end(),this}; }
};
struct Base {
  dxmt::mutex mutex_;
  CountedQueue fifo;
  unsigned census_id_=0;
  bool trimmed_last_=false;
  int flags_=0;
  Buffer backing;
  Buffer *buffer=&backing;
};
struct Baseline : Base { Rc<BufferAllocation> allocate(uint64_t, bool *); };
struct Optimized : Base { Rc<BufferAllocation> allocate(uint64_t, bool *); };
''' + functions + r'''
static void populate(Base &a,Base &b,unsigned n,uint64_t fence) {
  for(unsigned i=0;i<n;++i) {
    auto alloc=std::make_shared<BufferAllocation>(BufferAllocation{16,i});
    QueueEntry entry={{alloc},fence+i/4};
    a.fifo.push_back(entry);b.fifo.push_back(entry);
  }
}
int main() {
  unsigned compared=0;
  for(bool diag : {false,true}) for(unsigned id : {0u,DYN_CENSUS_SLOTS+1}) {
    diagnostics=diag;
    std::mt19937 random(425);
    for(unsigned trial=0;trial<1500;++trial) {
      Baseline a;Optimized b;a.census_id_=b.census_id_=id;
      unsigned n=random()%400;uint64_t first=random()%50,coherent=random()%160;
      populate(a,b,n,first);
      bool x=false,y=false;fresh=0;
      auto r1=a.allocate(coherent,&x);fresh=0;auto r2=b.allocate(coherent,&y);
      assert(x==y && r1->id==r2->id && a.fifo.size()==b.fifo.size());
      assert(a.trimmed_last_==b.trimmed_last_);
      for(unsigned k=0;k<a.fifo.size();++k) {
        assert(a.fifo[k].allocation.ptr()==b.fifo[k].allocation.ptr());
        assert(a.fifo[k].will_free_at==b.fifo[k].will_free_at);
      }
      ++compared;
    }
  }
  diagnostics=false;
  Baseline a;Optimized b;populate(a,b,64,10);
  a.allocate(0,nullptr);b.allocate(0,nullptr);
  assert(a.fifo.visits==64 && b.fifo.visits==0); // small fenced reserve: no census
  Baseline c;Optimized d;populate(c,d,10000,10);
  c.allocate(0,nullptr);d.allocate(0,nullptr);
  assert(c.fifo.visits==10000 && d.fifo.visits==1 && d.fifo.size()==10000); // fenced tail never scanned/freed
  Baseline e;Optimized f;populate(e,f,100,0);
  e.allocate(100,nullptr);f.allocate(100,nullptr);
  assert(e.fifo.size()==64 && f.fifo.size()==64); // identical warm reserve
  printf("PASS: %u baseline-equivalent recycling/trim cases, diagnostic overflow/opt-in, fenced tails, reserve and scan reduction 10000->1\n",compared);
}
'''
with tempfile.TemporaryDirectory(prefix='madeira-r16-recycling-') as folder:
    p = Path(folder); (p/'test.cpp').write_text(cpp)
    subprocess.run(['xcrun','clang++','-std=c++20','-O2','-pthread','-fsanitize=address,undefined',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True,timeout=60)
