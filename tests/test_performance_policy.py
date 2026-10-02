"""Host-only tests of the actual census gate and session present sampler."""
from pathlib import Path
import subprocess
import tempfile
root = Path(__file__).resolve().parents[1]
source = (root / 'dxmt/src/dxmt/dxmt_mem_census.cpp').read_text()
gate = source[source.index('static bool\nmem_census_throttled('):source.index('\nvoid\nmem_census_report(')]
gate = gate.replace('using clock = std::chrono::steady_clock;', 'using clock = FakeClock;')
bridge = (root / 'app/Madeira/WineProcessBridge.m').read_text()
default = 'setenv("DXMT_CENSUS_THROTTLE", "1", 0);'
assert default in bridge and bridge.index(default) < bridge.index('madeira.cfg env:')
assert b'DXMT_CENSUS_THROTTLE' in (root / 'app/Madeira/arm64ec-windows/d3d11.dll').read_bytes()
cpp = r'''
#include <atomic>
#include <chrono>
#include <thread>
#include <vector>
#include <cstdlib>
#include <cstring>
#include <cassert>
#include <cstdio>
static std::atomic<uint64_t> now_ns{1};
struct FakeClock {
 static auto now() { return std::chrono::time_point<std::chrono::steady_clock, std::chrono::nanoseconds>(std::chrono::nanoseconds(now_ns.load())); }
};
static bool madeiraSwitch(const char *name) { const char *value = getenv(name); return value && strcmp(value, "0"); }
''' + gate + '\nint main(int argc, char **argv) {\n' + default + r'''
 if (argc > 1) {
   setenv("DXMT_CENSUS_THROTTLE", "0", 1); // explicit cfg export runs after defaults
   for (int i = 0; i < 100; ++i) assert(!mem_census_throttled("seq"));
   puts("PASS: explicit unthrottled configuration"); return 0;
 }
 (void)argv;
 assert(!mem_census_throttled("seq"));
 now_ns = 10000000000ull;
 assert(mem_census_throttled("seq"));
 assert(!mem_census_throttled("warning"));
 assert(!mem_census_throttled("warn-memory"));
 assert(mem_census_throttled("seq")); // warning does not consume/reset periodic interval
 now_ns = 10000000001ull;
 assert(!mem_census_throttled(nullptr));
 assert(mem_census_throttled("w"));
 now_ns = 20000000001ull;
 std::atomic<int> reports{0};
 std::vector<std::thread> clients;
 for (int i = 0; i < 32; ++i) clients.emplace_back([&] { if (!mem_census_throttled("seq")) reports++; });
 for (auto &client : clients) client.join();
 assert(reports == 1);
 puts("PASS: first report, ten-second census gate, warnings and concurrent callers");
}
'''
library = (root / 'app/Madeira/Library.swift').read_text()
rate = library[library.index('struct SessionPresentRate {'):library.index('// Serialized off the main actor.')]
swift = 'import Foundation\n' + rate + r'''
var rate = SessionPresentRate()
rate.reset(count: 100, time: 20)
assert(rate.sample(count: 240, time: 29.5) == nil)
let a = rate.sample(count: 250, time: 30)!
assert(a.fps == 15 && abs(a.intervalMS - 66.6666667) < 0.001)
let b = rate.sample(count: 250, time: 40)!
assert(b.fps == 0 && b.intervalMS == 0)
assert(rate.sample(count: 1, time: 41) == nil)
assert(rate.sample(count: 1, time: .nan) == nil)
assert(rate.sample(count: 1, time: 39) == nil)
let c = rate.sample(count: 301, time: 59)!
assert(c.fps == 15 && c.seconds == 20)
rate.reset(count: UInt64.max - 5, time: 0)
assert(rate.sample(count: 2, time: 10) == nil)
print("PASS: present cadence, zero frames, delayed timer, reset and invalid time")
'''
with tempfile.TemporaryDirectory(prefix='madeira-performance-') as tmp:
    tmp = Path(tmp)
    (tmp / 'gate.cpp').write_text(cpp)
    subprocess.run(['clang++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined', '-pthread', str(tmp / 'gate.cpp'), '-o', str(tmp / 'gate')], check=True)
    subprocess.run([str(tmp / 'gate')], check=True)
    subprocess.run([str(tmp / 'gate'), 'config=0'], check=True)
    (tmp / 'main.swift').write_text(swift)
    subprocess.run(['swift', str(tmp / 'main.swift')], check=True)
