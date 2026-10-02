"""Exercise production log batching with a real Combine publisher, no file writer."""
from pathlib import Path
import subprocess, tempfile
root = Path(__file__).resolve().parents[1]
s = (root / 'app/Madeira/LogStore.swift').read_text()
entry = s[s.index('    struct LogEntry:'):s.index('    private init()')]
handle = s[s.index('    private func handleRawLine'):s.index('    /// Filter rules')].replace('private func', 'func')
flush = s[s.index('    private func flushPending'):s.index('    /// Manual clear')].replace('private func', 'func')
code = """
import Foundation
import Combine
final class LogStore: ObservableObject {
 @Published var entries: [LogEntry] = []
 var sigToIndex: [String:Int] = [:], stateLock = NSLock()
 var pendingNew: [LogEntry] = []
 var pendingUpdates: [(index:Int,count:Int,lastRaw:String,lastTimestamp:Date)] = []
 var displaySuppressed = false
 let maxEntries = 200
 func shouldDropLine(_ raw:String) -> Bool { false }
""" + entry + handle + flush + r"""
}
enum LogPattern {
 static func canonicalize(_ raw: String) -> (String,LogStore.LogEntry.Level) { (raw,.info) }
}
let store = LogStore()
var publications = 0
let token = store.$entries.dropFirst().sink { _ in publications += 1 }
for _ in 0..<10000 { store.handleRawLine("same") }
store.flushPending()
assert(publications == 1 && store.entries.count == 1 && store.entries[0].count == 10000)
for _ in 0..<10000 { store.handleRawLine("same") }
store.handleRawLine("second"); store.handleRawLine("second")
store.flushPending()
assert(publications == 2 && store.entries[0].count == 20000 && store.entries[1].count == 2)
store.flushPending(); assert(publications == 2)
for i in 0..<300 { store.handleRawLine("row-\(i)") }
store.flushPending(); assert(publications == 3 && store.entries.count == 200)
for (sig, index) in store.sigToIndex { assert(store.entries[index].signature == sig) }
let signature = store.entries[100].signature, oldCount = store.entries[100].count
store.handleRawLine(signature); store.flushPending()
assert(publications == 4 && store.entries[100].count == oldCount + 1)
store.displaySuppressed = true; store.handleRawLine("hidden"); store.flushPending()
assert(publications == 4)
print("PASS: real Combine sends once per nonempty batch; 20000 repeated events retained; eviction/reindex and suppression preserved")
"""
with tempfile.TemporaryDirectory(prefix='madeira-log-batch-') as tmp:
 p=Path(tmp); (p/'main.swift').write_text(code)
 subprocess.run(['xcrun','swiftc','-O','-assert-config','Debug','-sanitize=address',str(p/'main.swift'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
