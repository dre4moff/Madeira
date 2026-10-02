"""Exercise the production launch policy with fake configuration paths only."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
config = (root / 'app/Madeira/MadeiraConfig.swift').read_text()
start = config.index('    static func applyEarlyRuntimeProfilingPolicy() {')
end = config.index('\n    /// Set or remove', start)
method = config[start:end]
source = '''import Foundation
enum MadeiraConfig {
    static var present = false
    static var documents: URL? = nil
    static var values: [String: String] = [:]
    static func all() -> [String: String] { values }
''' + method + '''
}
func env(_ name: String) -> String? { getenv(name).map { String(cString: $0) } }
let folder = URL(fileURLWithPath: CommandLine.arguments[1])
MadeiraConfig.documents = folder
unsetenv("MADEIRA_RUNTIME_PROFILING")
setenv("MADEIRA_QUIET", "0", 1)
MadeiraConfig.applyEarlyRuntimeProfilingPolicy()
assert(env("MADEIRA_QUIET") == "1")
assert(env("MADEIRA_RUNTIME_PROFILING") == nil)
setenv("MADEIRA_RUNTIME_PROFILING", "1", 1)
MadeiraConfig.applyEarlyRuntimeProfilingPolicy()
assert(env("MADEIRA_RUNTIME_PROFILING") == "1")
try "# comment\\nMADEIRA_RUNTIME_PROFILING=0\\nMADEIRA_RUNTIME_PROFILING=1\\nMADEIRA_QUIET=0\\nUNRELATED=changed\\n".write(to: folder.appendingPathComponent("madeira-env.txt"), atomically: true, encoding: .utf8)
MadeiraConfig.applyEarlyRuntimeProfilingPolicy()
assert(env("MADEIRA_QUIET") == "0" && env("MADEIRA_RUNTIME_PROFILING") == "1")
assert(env("UNRELATED") == nil)
MadeiraConfig.present = true
MadeiraConfig.values = ["env.MADEIRA_RUNTIME_PROFILING": "0", "env.MADEIRA_QUIET": "1"]
MadeiraConfig.applyEarlyRuntimeProfilingPolicy()
assert(env("MADEIRA_QUIET") == "1" && env("MADEIRA_RUNTIME_PROFILING") == "0")
MadeiraConfig.values = ["env.MADEIRA_RUNTIME_PROFILING": "1"]
MadeiraConfig.applyEarlyRuntimeProfilingPolicy()
assert(env("MADEIRA_RUNTIME_PROFILING") == "1")
print("PASS: early quiet policy preserves inherited choice, config/legacy precedence and diagnostic opt-in")
'''
with tempfile.TemporaryDirectory(prefix='madeira-early-policy-') as tmp:
    p = Path(tmp)
    (p / 'test.swift').write_text(source)
    subprocess.run(['xcrun', 'swiftc', str(p / 'test.swift'), '-o', str(p / 'test')], check=True)
    subprocess.run([str(p / 'test'), tmp], check=True)
launch = (root / 'app/Madeira/ContentView.swift').read_text()
start = launch.index('    private func runWineFullSequence(')
end = launch.index('    private func startDock(', start)
launch = launch[start:end]
assert launch.index('MadeiraConfig.applyEarlyRuntimeProfilingPolicy()') < launch.index('StikJITHelper.allocatePool(')
print('PASS: profiling policy is established before native JIT/server startup')
