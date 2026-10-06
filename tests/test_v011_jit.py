"""Exercise merged v0.1.1 JIT readiness/alias retry with fake Mach boundaries."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / 'app/Madeira/StikJITHelper.swift').read_text()
start = source.index('    static var ready: Bool')
ready = source[start:source.index('    /// Allocate a JIT memory pool', start)]
start = source.index('        var kr1: kern_return_t = KERN_NO_SPACE')
retry = source[start:source.index('        guard kr1 == KERN_SUCCESS else', start)]
program = r'''
import Foundation
var debugged = false, attached = false
struct SigningStatus { static var current: SigningStatus { SigningStatus() }; var debugged: Bool { jit_check_debugged() } }
func jit_check_debugged() -> Bool { debugged }
enum Policy {
    static var attachCheck = true, poolTaken = false
    static func isDebuggerAttached() -> Bool { attached }
''' + ready + r'''
}
for flag in [false, true] { for attach in [false, true] { for taken in [false, true] {
    debugged = flag; attached = attach; Policy.poolTaken = taken
    Policy.attachCheck = true
    assert(Policy.ready == (flag && (attach || taken)))
    assert(Policy.flaggedWithoutDebugger == (flag && !attach && !taken))
    Policy.attachCheck = false; assert(Policy.ready == flag)
}}}
typealias vm_address_t = UInt
typealias vm_size_t = UInt
typealias kern_return_t = Int
let mach_task_self_: UInt = 1
let KERN_NO_SPACE = 3, KERN_SUCCESS = 0, VM_FLAGS_ANYWHERE = 1, VM_INHERIT_NONE = 2
var hints: [UInt] = [], results: [Int] = []
func vm_remap(_ task: UInt, _ address: inout UInt, _ size: UInt, _ mask: Int,
              _ flags: Int, _ sourceTask: UInt, _ source: UInt, _ copy: Int,
              _ current: inout Int, _ maximum: inout Int, _ inherit: Int) -> Int {
    assert(size == UInt(896 << 20) && source == 0x140000000)
    assert(copy == 0 && flags == VM_FLAGS_ANYWHERE)
    let result = results[hints.count]; hints.append(address)
    if result == 0 { address = 0x500000000 }
    return result
}
enum MadeiraConfig {
    static var enabled = true
    static func flag(_ name: String) -> Bool { assert(name == "MADEIRA_RW_ALIAS_RETRY"); return enabled }
}
enum Level { case info, error }
struct LogStore {
    static let shared = LogStore()
    func log(_ value: String, level: Level) {}
}
func allocate() -> (Int, UInt) {
    var rwAddr: UInt = 0, curProt = 0, maxProt = 0
    let rxAddrV: UInt = 0x140000000
    let rxPtr = UnsafeMutableRawPointer(bitPattern: rxAddrV)!
    let poolSize = 896 << 20
''' + retry + r'''
    return (kr1, rwAddr)
}
for enabled in [false, true] { for first in [0, 3, 5] { for second in [0, 3, 5] { for third in [0, 3, 5] {
    MadeiraConfig.enabled = enabled; results = [first, second, third]; hints = []
    let actual = allocate()
    let count = !enabled || first != 3 ? 1 : second != 3 ? 2 : 3
    let expected: [UInt] = [0x7000000000, 0x140000000 + UInt(896 << 20), 0]
    assert(hints == Array(expected.prefix(count)))
    assert(actual.0 == results[count - 1])
    if actual.0 == 0 { assert(actual.1 == 0x500000000) }
}}}}
print("PASS: debugger readiness, pool retention, high/above-RX/kernel alias placement, opt-out and all 54 kernel-result scenarios")
'''
with tempfile.TemporaryDirectory(prefix='madeira-v011-jit-') as tmp:
    path = Path(tmp) / 'main.swift'
    path.write_text(program)
    subprocess.run(['swift', str(path)], check=True)

# Upstream fixes and our independent profiling/cache switches coexist.
bridge = (root / 'app/Madeira/WineProcessBridge.m').read_text()
virtual = (root / 'build/ntdll-unix/virtual_ios.c').read_text()
library = (root / 'app/Madeira/Library.swift').read_text()
assert 'madeira_ensure_locallow( prefix );' in bridge
assert 'ios_exe_win_stripped_request = (image_info->image_charact & IMAGE_FILE_RELOCS_STRIPPED)' in virtual
assert 'shared_status == STATUS_INVALID_PARAMETER && ios_shared_section_private()' in virtual
assert 'madeira_runtime_profiling_enabled()' in virtual
assert 'CacheStorageSettings()' in library and 'Toggle("Liquid metal"' in library
print('PASS: loader fixes, LocalLow, cache settings and upstream Appearance survive the merge')
