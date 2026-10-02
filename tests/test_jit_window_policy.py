"""Inspect synthetic PE fixtures and allocation geometry; never starts Wine."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / "app/Madeira/StikJITHelper.swift").read_text()
policy = source[source.index("enum JITExecutableWindowPolicy {"):]
harness = r'''
import Foundation
''' + policy + r'''
func pe(base: UInt64 = 0x140000000, relocatable: Bool = true) -> Data {
    var d = Data(repeating: 0, count: 0x500)
    func put(_ at: Int, _ value: UInt64, _ count: Int) {
        for i in 0..<count { d[at+i] = UInt8(truncatingIfNeeded: value >> (8*i)) }
    }
    put(0, 0x5a4d, 2); put(60, 0x80, 4)
    put(0x80, 0x4550, 4); put(0x84, 0x8664, 2); put(0x86, 1, 2)
    put(0x94, 240, 2); put(0x96, relocatable ? 0 : 1, 2)
    let opt = 0x98
    put(opt, 0x20b, 2); put(opt+24, base, 8); put(opt+56, 0x20000, 4)
    put(opt+70, relocatable ? 0x40 : 0, 2); put(opt+108, 16, 4)
    put(opt+152, relocatable ? 0x1000 : 0, 4); put(opt+156, relocatable ? 12 : 0, 4)
    let section = opt+240
    put(section+12, 0x1000, 4); put(section+16, 0x100, 4); put(section+20, 0x400, 4)
    put(0x400, 0x1000, 4); put(0x404, 12, 4); put(0x408, 0xa010, 2)
    return d
}
let fm = FileManager.default
let drive = fm.temporaryDirectory.appendingPathComponent(UUID().uuidString)
defer { try? fm.removeItem(at: drive) }
let game = drive.appendingPathComponent("steamapps/common/Ride")
let exe = game.appendingPathComponent("Ride.exe")
try fm.createDirectory(at: game, withIntermediateDirectories: true)
try pe().write(to: exe)
assert(JITExecutableWindowPolicy.canRelocateOutsideWindow(exe))
assert(JITExecutableWindowPolicy.canReuse(drive: drive, relativePath: "steamapps/common/Ride", steam: true))
assert(JITExecutableWindowPolicy.canReuse(drive: drive, relativePath: "steamapps/common/Ride/Ride.exe", steam: false))
let nested = game.appendingPathComponent("Binaries/Win64")
try fm.createDirectory(at: nested, withIntermediateDirectories: true)
let helper = nested.appendingPathComponent("Helper.EXE")
try pe(relocatable: false).write(to: helper)
assert(!JITExecutableWindowPolicy.canReuse(drive: drive, relativePath: "steamapps/common/Ride", steam: true))
assert(!JITExecutableWindowPolicy.canReuse(drive: drive, relativePath: "steamapps/common/Ride/Ride.exe", steam: false))
// A fixed image outside this particular window keeps its preferred address.
try pe(base: 0x180000000, relocatable: false).write(to: helper)
assert(JITExecutableWindowPolicy.canReuse(drive: drive, relativePath: "steamapps/common/Ride", steam: true))
try fm.removeItem(at: helper)
// Missing relocation data, unsupported relocation types and malformed blocks.
var bad = pe(); bad[0x408] = 0x10; bad[0x409] = 0x30
try bad.write(to: exe); assert(!JITExecutableWindowPolicy.canRelocateOutsideWindow(exe))
bad = pe(); bad[0x404] = 7
try bad.write(to: exe); assert(!JITExecutableWindowPolicy.canRelocateOutsideWindow(exe))
bad = pe(); bad[0x98+70] = 0
try bad.write(to: exe); assert(!JITExecutableWindowPolicy.canRelocateOutsideWindow(exe))
bad = pe(); bad[0x98+153] = 0
try bad.write(to: exe); assert(!JITExecutableWindowPolicy.canRelocateOutsideWindow(exe))
bad = pe(); bad[0x96] = 1
try bad.write(to: exe); assert(!JITExecutableWindowPolicy.canRelocateOutsideWindow(exe))
bad = pe(); bad[0x400] = 1
try bad.write(to: exe); assert(!JITExecutableWindowPolicy.canRelocateOutsideWindow(exe))
for length in [0, 2, 63, 128, 151, 160, 390, 1024, 1031] {
    try pe().prefix(length).write(to: exe)
    assert(!JITExecutableWindowPolicy.canRelocateOutsideWindow(exe))
}
// Even a sparse image with a huge declared header offset reads bounded bytes.
bad = pe(); for i in 60..<64 { bad[i] = 255 }
try bad.write(to: exe); assert(!JITExecutableWindowPolicy.canRelocateOutsideWindow(exe))
try pe().write(to: exe)
assert(!JITExecutableWindowPolicy.canReuse(drive: drive, relativePath: "../other/Ride.exe", steam: false))
assert(!JITExecutableWindowPolicy.canReuse(drive: drive, relativePath: "missing", steam: true))
try fm.createSymbolicLink(at: game.appendingPathComponent("alias"), withDestinationURL: nested)
assert(!JITExecutableWindowPolicy.canReuse(drive: drive, relativePath: "steamapps/common/Ride", steam: true))
try fm.removeItem(at: game.appendingPathComponent("alias"))
try fm.removeItem(at: exe)
assert(!JITExecutableWindowPolicy.canReuse(drive: drive, relativePath: "steamapps/common/Ride", steam: true))
print("PASS: relocatable/fixed/helper PE files, damaged headers, bounded reads, traversal, links and missing games")
'''
with tempfile.TemporaryDirectory(prefix="madeira-jit-window-test-") as tmp:
    path = Path(tmp) / "main.swift"
    path.write_text(harness)
    subprocess.run(["swift", str(path)], check=True)

# Execute the actual reservation-release block with a fake Mach allocator.
# No real mappings, debugger or executable pages are created.
start = source.index("        if reuseExecutableWindow && windowHeld")
release = source[start:source.index("        let goodLow =", start)]
start = source.index("        func overlapsExeWindow(")
overlaps = source[start:source.index("        let skipWindow", start)]
allocation = r'''
import Foundation
typealias vm_address_t = UInt
typealias vm_size_t = UInt
struct FakeTask {}
let mach_task_self_ = FakeTask()
let KERN_SUCCESS = 0
var result = 0, calls = 0
func vm_deallocate(_ task: FakeTask, _ base: UInt, _ size: UInt) -> Int {
    assert(base == 0x140000000 && size == 0x8000000)
    calls += 1
    return result
}
enum Level { case success, error }
struct LogStore {
    static let shared = LogStore()
    func log(_ message: String, level: Level) {}
}
struct Allocator {
    static var executableWindowReused = false
    static func prepare(_ reuseExecutableWindow: Bool, owned: Bool) -> (Bool, Bool) {
        let exeWinBase: UInt = 0x140000000, exeWinSize: UInt = 0x8000000
        var windowHeld = owned
''' + overlaps + release + r'''
        return (windowHeld, overlapsExeWindow(0x140000000, 688 << 20))
    }
}
for owned in [false, true] {
    for allowed in [false, true] {
        for kr in [0, 3] {
            result = kr; calls = 0; Allocator.executableWindowReused = false
            setenv("WINE_IOS_EXE_WINDOW", "140000000:8000000", 1)
            let state = Allocator.prepare(allowed, owned: owned)
            let reclaimed = allowed && owned && kr == 0
            assert(calls == (allowed && owned ? 1 : 0))
            assert(state.0 == (owned && !reclaimed))
            assert(state.1 == !reclaimed)
            assert(Allocator.executableWindowReused == reclaimed)
            assert((getenv("WINE_IOS_EXE_WINDOW") == nil) == reclaimed)
        }
    }
}
print("PASS: actual release block with mocked Mach allocation: opt-out, ownership, failure, success, environment and pool placement")
'''
with tempfile.TemporaryDirectory(prefix="madeira-jit-allocation-test-") as tmp:
    path = Path(tmp) / "main.swift"
    path.write_text(allocation)
    subprocess.run(["swift", str(path)], check=True)

# Replay the observed pool budget, without changing the image-copy algorithm.
pool, head, tail = 0x23000000, 0x1dc90000, 0x500c000
d3d12, eos = 0x11b8000, 0x1314000
assert pool - head - tail < min(d3d12, eos)
assert pool + (128 << 20) - head - tail >= d3d12 + eos
assert "!executableWindowReused && base < exeWinBase" in source
assert "if reuseExecutableWindow && windowHeld" in source
assert source.index("if kr == KERN_SUCCESS", source.index("if reuseExecutableWindow")) < source.index("executableWindowReused = true")
content = (root / "app/Madeira/ContentView.swift").read_text()
assert "if StikJITHelper.executableWindowReused" in content
assert "reuseExecutableWindow: reuseExecutableWindow" in content
assert "[jit-budget] requested=" in content
print("PASS: captured exhaustion budget fits with reclaimed reservation; launch/reset guard and actual-budget diagnostics wired")
