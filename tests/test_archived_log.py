"""Production previous-log compaction, using closed synthetic files only."""
from pathlib import Path
import subprocess, tempfile
root=Path(__file__).resolve().parents[1]
s=(root/'app/Madeira/LogStore.swift').read_text()
s=s[s.index('enum ArchivedLogMaintenance {'):s.index('\nfinal class LogStore:')]
fixture=r'''
let root = URL(fileURLWithPath: CommandLine.arguments[1])
let fm = FileManager.default
let url = root.appendingPathComponent("madeira-log.prev.txt")
var data = Data(repeating: 65, count: 120000)
data.replaceSubrange(119990..<120000, with: Data("LAST-LINES".utf8))
try data.write(to: url)
ArchivedLogMaintenance.compact(url, threshold: 100000, tailBytes: 4096)
let trimmed = try Data(contentsOf: url)
assert(trimmed.count < 70000 && trimmed.prefix(1024) == data.prefix(1024))
assert(trimmed.suffix(4096) == data.suffix(4096))
ArchivedLogMaintenance.compact(url, threshold: 100000, tailBytes: 4096)
assert(try Data(contentsOf: url) == trimmed)
let active = root.appendingPathComponent("madeira-log.txt")
try data.write(to: active)
ArchivedLogMaintenance.compact(active, threshold: 100000, tailBytes: 4096)
assert(try Data(contentsOf: active) == data)
try fm.removeItem(at: url)
try fm.createSymbolicLink(at: url, withDestinationURL: active)
ArchivedLogMaintenance.compact(url, threshold: 100000, tailBytes: 4096)
assert(try Data(contentsOf: active) == data)
print("PASS: archived logs retain header and tail, active logs and symlinks protected")
'''.replace('assert(try Data(contentsOf: url) == trimmed)','let again = try Data(contentsOf: url); assert(again == trimmed)').replace('assert(try Data(contentsOf: active) == data)','assert((try? Data(contentsOf: active)) == data)')
with tempfile.TemporaryDirectory(prefix='madeira-log-history-') as tmp:
 p=Path(tmp);(p/'main.swift').write_text('import Foundation\n'+s+fixture)
 subprocess.run(['swift',str(p/'main.swift'),tmp],check=True)
