"""Synthetic production wait/query paths; no Wine, graphics or device execution."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
bridge = (root / 'app/Madeira/WineProcessBridge.m').read_text()
for name in ['DXMT_WAIT_ON_ADDRESS', 'DXMT_QUERY_POLL_YIELD']:
    default = f'setenv("{name}", "1", 0);'
    assert default in bridge and bridge.index(default) < bridge.index('madeira.cfg env:')

query = (root / 'dxmt/src/d3d11/d3d11_query.hpp').read_text()
policy = query[query.index('constexpr size_t kEventStallThreshold'):query.index('struct MTLD3D11EventQuery')]
implementation = query[query.index('template <typename DataType>\nclass MTLD3D11EventQueryImpl'):query.index('\nHRESULT CreateOcculusionQuery')]
cpp = r'''
#include <atomic>
#include <cassert>
#include <chrono>
#include <condition_variable>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <thread>
#include <vector>
#include <cstdio>
#include "util_futex.hpp"
#include "util_madeira_switch.hpp"
namespace dxmt::env {
std::string getEnvVar(const char *name) { auto value = getenv(name); return value ? value : ""; }
}
// Host model of the Wine compare/enqueue/wake lock protocol, including
// store-before-enqueue races. Periodic spurious returns exercise the recheck.
namespace dxmt::futex {
std::mutex lock;
std::condition_variable condition;
std::atomic<unsigned> parks{0}, wakes{0}, sizes{0};
WaitBackend backend() {
  static auto selected = madeiraSwitch("DXMT_WAIT_ON_ADDRESS") ? WaitBackend::AddressWait : WaitBackend::StdAtomic;
  return selected;
}
void address_wait(const void *addr, const void *compare, size_t size) {
  assert(size==1 || size==2 || size==4 || size==8);
  unsigned n=++parks; sizes.fetch_or(1u<<size);
  std::unique_lock guard(lock);
  if (n%7==0) return; // deliberate spurious wake
  condition.wait(guard, [&] {
    switch(size) {
    case 1: return static_cast<const std::atomic<uint8_t> *>(addr)->load()!=*static_cast<const uint8_t *>(compare);
    case 2: return static_cast<const std::atomic<uint16_t> *>(addr)->load()!=*static_cast<const uint16_t *>(compare);
    case 4: return static_cast<const std::atomic<uint32_t> *>(addr)->load()!=*static_cast<const uint32_t *>(compare);
    case 8: return static_cast<const std::atomic<uint64_t> *>(addr)->load()!=*static_cast<const uint64_t *>(compare);
    }
    return false;
  });
}
void address_wake_one(const void *) { std::lock_guard guard(lock); ++wakes; condition.notify_all(); }
void address_wake_all(const void *a) { address_wake_one(a); }
}
template<typename T> void exchange_test() {
  std::atomic<T> word{0};
  std::atomic<unsigned> seen{0};
  std::thread reader([&] {
    for(unsigned i=0;i<2000;++i) {
      dxmt::atomic_wait(word,T(0));
      assert(word.load(std::memory_order_acquire)==T(1));
      ++seen; word.store(0,std::memory_order_release); dxmt::atomic_notify_one(word);
    }
  });
  std::this_thread::sleep_for(std::chrono::milliseconds(2));
  for(unsigned i=0;i<2000;++i) {
    dxmt::atomic_wait(word,T(1)); word.store(1,std::memory_order_release); dxmt::atomic_notify_one(word);
    if(i%31==0) std::this_thread::yield();
  }
  reader.join(); assert(seen==2000 && word.load()==0);
}
static unsigned yields=0;
int SwitchToThread() { ++yields; return 1; }
#define STDMETHODCALLTYPE
using UINT=unsigned;
struct MTLD3D11Device {};
struct D3D11_QUERY_DESC {};
struct MTLD3D11EventQuery {};
enum class QueryState { Undefined, Issued, Signaled };
enum class EventState { Pending, Signaled, Stall, StallYield, Invalid };
template<typename T> struct MTLD3DQueryBase {
  MTLD3DQueryBase(MTLD3D11Device *, const D3D11_QUERY_DESC *) {}
  virtual ~MTLD3DQueryBase()=default;
  virtual UINT GetDataSize()=0;
  virtual void Issue(uint64_t)=0;
  virtual EventState CheckEventState(uint64_t)=0;
};
using dxmt::madeiraSwitch;
''' + policy + implementation + r'''
int main(int argc, char **) {
  // Mirrors app defaults followed by explicit cfg overrides, before first use.
  setenv("DXMT_WAIT_ON_ADDRESS","1",0);
  setenv("DXMT_QUERY_POLL_YIELD","1",0);
  if(argc>1) { setenv("DXMT_WAIT_ON_ADDRESS","0",1); setenv("DXMT_QUERY_POLL_YIELD","0",1); }
  exchange_test<uint8_t>(); exchange_test<uint16_t>(); exchange_test<uint32_t>(); exchange_test<uint64_t>();
  std::atomic<uint64_t> gate{0};
  std::atomic<unsigned> arrived{0}, finished{0};
  std::vector<std::thread> waiters;
  for(int i=0;i<16;++i) waiters.emplace_back([&] {
    ++arrived; dxmt::atomic_wait(gate,uint64_t(0)); assert(gate.load()==1); ++finished;
  });
  while(arrived!=16) std::this_thread::yield();
  gate.store(1,std::memory_order_release); dxmt::atomic_notify_all(gate);
  for(auto &thread:waiters) thread.join(); assert(finished==16);
  if(argc>1) assert(dxmt::futex::parks==0 && dxmt::futex::wakes==0);
  else assert(dxmt::futex::parks>0 && dxmt::futex::sizes==(1u<<1|1u<<2|1u<<4|1u<<8));
  D3D11_QUERY_DESC desc;
  MTLD3D11EventQueryImpl<uint64_t> query(nullptr,&desc);
  assert(query.GetDataSize()==8 && query.CheckEventState(0)==EventState::Invalid && yields==0);
  query.Issue(3);
  for(int i=0;i<64;++i) assert(query.CheckEventState(2)==EventState::Pending);
  assert(yields==0);
  for(int i=0;i<500000;++i) {
    auto expected = argc==1 && (i+1)%64==0 ? EventState::StallYield : EventState::Stall;
    assert(query.CheckEventState(2)==expected);
  }
  assert(yields==(argc>1 ? 0 : 500000/64));
  assert(query.CheckEventState(3)==EventState::Signaled);
  auto before=yields;
  for(int i=0;i<100;++i) assert(query.CheckEventState(3)==EventState::Signaled);
  assert(yields==before);
  query.Issue(5);
  for(int i=0;i<64;++i) assert(query.CheckEventState(4)==EventState::Pending);
  for(int i=0;i<63;++i) assert(query.CheckEventState(4)==EventState::Stall);
  assert(yields==before); // completion/reissue reset the entire budget
  assert(query.CheckEventState(5)==EventState::Signaled && yields==before);
  puts("PASS: production atomic handoffs for four sizes, 16 waiters, spurious wakes, query polling/reset and explicit opt-outs");
}
'''
with tempfile.TemporaryDirectory(prefix='madeira-r15-scheduling-') as folder:
    p = Path(folder)
    (p / 'test.cpp').write_text(cpp)
    subprocess.run(['xcrun', 'clang++', '-std=c++20', '-O2', '-Wall', '-Wextra', '-Werror', '-pthread',
                    '-fsanitize=address,undefined', '-I'+str(root/'dxmt/src/util'), str(p/'test.cpp'), '-o', str(p/'test')], check=True)
    for args in [[], ['override=0']]:
        subprocess.run([str(p/'test'), *args], check=True, timeout=60)

# Ready/pending/invalid handling and flush policy in GetData have not changed.
context = (root/'dxmt/src/d3d11/d3d11_context_imm.cpp').read_text()
assert 'CheckEventState(cmd_queue.SignaledEventSeqId())' in context
assert 'if (hr == S_FALSE && (GetDataFlags & D3D11_ASYNC_GETDATA_DONOTFLUSH) == 0)' in context
assert 'case EventState::Invalid:\n        return DXGI_ERROR_INVALID_CALL;' in context
print('PASS: app default ordering and GetData preserves genuine shared-event completion/flush policy')
