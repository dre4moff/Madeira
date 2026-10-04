"""Production serialization/UI gate under a deliberately blocked cleanup scan."""
from pathlib import Path
import tempfile,subprocess
root=Path(__file__).resolve().parents[1]
s=(root/'app/Madeira/CacheMaintenance.swift').read_text();a=s.index('enum CacheMaintenance {');b=s.index('    private static func clean(',a)
code=r'''
import Foundation
struct OwnedCacheCleaner {struct Result {var removedBytes:Int64=0;var cacheBytes:Int64=0;var protectedBytes:Int64=0;var driverBytes:Int64=0;var failedItems=0}}
struct UserDefaults {static let standard=UserDefaults();func object(forKey:String)->Any? {nil}}
let entered=DispatchSemaphore(value:0), releaseScan=DispatchSemaphore(value:0), launchedSignal=DispatchSemaphore(value:0)
'''+s[a:b]+r'''
    private static func clean(purgeShaderCaches: Bool = false) -> OwnedCacheCleaner.Result {
        entered.signal();assert(releaseScan.wait(timeout:.now()+3)==.success)
        return OwnedCacheCleaner.Result()
    }
}
CacheMaintenance.start()
assert(entered.wait(timeout:.now()+3)==.success)
let before=Date();assert(CacheMaintenance.available);assert(Date().timeIntervalSince(before)<0.1)
DispatchQueue.global().async {CacheMaintenance.prepareForLaunch();launchedSignal.signal()}
assert(launchedSignal.wait(timeout:.now()+0.05)==.timedOut)
releaseScan.signal();assert(launchedSignal.wait(timeout:.now()+3)==.success)
assert(!CacheMaintenance.available)
var done=false
CacheMaintenance.manual {message in assert(message.contains("Restart Madeira"));done=true}
let deadline=Date().addingTimeInterval(3)
while !done && Date()<deadline {RunLoop.current.run(until:Date().addingTimeInterval(0.01))}
assert(done);assert(entered.wait(timeout:.now()+0.01)==.timedOut)
print("PASS: UI gate does not block on scan, launch still serializes behind scan, post-launch cleanup refuses without touching files")
'''
code=code.replace(')==.', ') == .')
with tempfile.TemporaryDirectory(prefix='madeira-cache-gate-') as folder:
 p=Path(folder);(p/'main.swift').write_text(code);subprocess.run(['swift',str(p/'main.swift')],check=True,timeout=20)
