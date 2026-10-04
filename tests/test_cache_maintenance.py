"""Owned temporary fixtures only; compile actual cleanup code, no app/Wine launch."""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parents[1]
s=(root/'app/Madeira/CacheMaintenance.swift').read_text()
s=s[s.index('struct OwnedCacheCleaner {'):s.index('\nenum CacheMaintenance {')]
fixture=r'''
let fm = FileManager.default
let root = URL(fileURLWithPath: CommandLine.arguments[1])
let caches = root.appendingPathComponent("Caches"), temporary = root.appendingPathComponent("tmp")
try fm.createDirectory(at: caches, withIntermediateDirectories: true)
try fm.createDirectory(at: temporary, withIntermediateDirectories: true)
let now = Date(), stale = now.addingTimeInterval(-40 * 86400)
func file(_ path: String, size: Int, date: Date = Date()) throws -> URL {
    let url = root.appendingPathComponent(path)
    try fm.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
    try Data(repeating: 42, count: size).write(to: url)
    try fm.setAttributes([.modificationDate: date], ofItemAtPath: url.path)
    return url
}
let old = try file("Caches/dxmt/Old.exe/shaders_320.db", size: 2048, date: stale)
try fm.setAttributes([.modificationDate: stale], ofItemAtPath: old.deletingLastPathComponent().path)
let recent = try file("Caches/dxmt/Recent.exe/shaders_320.db", size: 4096)
let outside = try file("user-saves/progress.sav", size: 100)
let steam = try file("Documents/wine/drive_c/Steam/depotcache/manifest", size: 100)
let other = try file("Caches/unrelated/file", size: 100)
let swap = try file("tmp/madeira-swap.bin", size: 4096)
let abandonedName = "madeira-runtime-" + UUID().uuidString
let abandoned = try file("tmp/" + abandonedName + "/archive", size: 2048, date: stale)
try fm.setAttributes([.modificationDate: stale], ofItemAtPath: abandoned.deletingLastPathComponent().path)
let activeName = "madeira-runtime-" + UUID().uuidString
let active = try file("tmp/" + activeName + "/archive", size: 128)
let foreign = try file("tmp/unrelated.tmp", size: 100)
let symlink = caches.appendingPathComponent("dxmt/Link.exe")
try fm.createSymbolicLink(at: symlink, withDestinationURL: outside.deletingLastPathComponent())
let result = OwnedCacheCleaner(caches: caches, temporary: temporary, now: now, targetBytes: 1024).clean()
assert(!fm.fileExists(atPath: old.path) && !fm.fileExists(atPath: swap.path) && !fm.fileExists(atPath: abandoned.path))
for url in [recent, outside, steam, other, active, foreign, symlink] { assert(fm.fileExists(atPath: url.path), url.path) }
assert(result.removedBytes == 8192 && result.cacheBytes == 4096 && result.protectedBytes == 4096)
let again = OwnedCacheCleaner(caches: caches, temporary: temporary, now: now, targetBytes: 0).clean()
assert(again.removedBytes == 0 && again.cacheBytes == 4096) // warm cache survives any budget
// Parent symlink, not merely a leaf: refuse cleanup even when target is owned-looking.
let cacheAlias = root.appendingPathComponent("cache-alias")
try fm.createSymbolicLink(at: cacheAlias, withDestinationURL: caches)
let aliasResult = OwnedCacheCleaner(caches: cacheAlias, temporary: temporary, now: now, targetBytes: 0).clean()
assert(aliasResult.removedBytes == 0)

// D3D12 entries share the soft target; stale temp fragments are removed.
let docs = root.appendingPathComponent("Documents")
let dump = try file("Documents/fex-jit-dump.bin", size: 1024)
let oldDX = try file("Documents/shadercache/0000000000000001.mdxc", size: 2048, date: stale)
let warmDX = try file("Documents/shadercache/0000000000000002.mdsc", size: 4096)
let orphanDX = try file("Documents/shadercache/0000000000000003.mdxc.tmp123", size: 256, date: stale)
let currentDX = try file("Documents/shadercache/0000000000000004.mdsc.tmp123", size: 256)
let foreignDX = try file("Documents/shadercache/user-file.dat", size: 1024, date: stale)
let driver = try file("Caches/signed.bundle/com.apple.metal/cache.bin", size: 8192, date: stale)
let linkDX = docs.appendingPathComponent("shadercache/0000000000000005.mdxc")
try fm.createSymbolicLink(at: linkDX, withDestinationURL: outside)
let all = OwnedCacheCleaner(caches: caches, temporary: temporary, now: now, targetBytes: 1,
                           documents: docs, metalDriverCache: driver.deletingLastPathComponent()).clean()
assert(all.removedBytes == 3328 && all.cacheBytes == 8192 && all.protectedBytes == 8192 && all.driverBytes == 8192)
assert(!fm.fileExists(atPath: dump.path))
assert(!fm.fileExists(atPath: oldDX.path) && !fm.fileExists(atPath: orphanDX.path))
for url in [warmDX, currentDX, foreignDX, driver, linkDX, outside, steam] { assert(fm.fileExists(atPath: url.path), url.path) }
let warmAgain = OwnedCacheCleaner(caches: caches, temporary: temporary, now: now, targetBytes: 0, documents: docs).clean()
assert(warmAgain.removedBytes == 0 && warmAgain.cacheBytes == 8192)
let diagnosticDump = try file("Documents/fex-jit-dump.bin", size: 1024)
setenv("MADEIRA_JIT_DUMP", "1", 1)
let optedIn = OwnedCacheCleaner(caches: caches, temporary: temporary, now: now, targetBytes: 0, documents: docs).clean()
assert(optedIn.removedBytes == 0 && fm.fileExists(atPath: diagnosticDump.path))
unsetenv("MADEIRA_JIT_DUMP")
try fm.removeItem(at: diagnosticDump)
try fm.createSymbolicLink(at: diagnosticDump, withDestinationURL: outside)
let linkedDump = OwnedCacheCleaner(caches: caches, temporary: temporary, now: now, targetBytes: 0, documents: docs).clean()
assert(linkedDump.removedBytes == 0 && fm.fileExists(atPath: outside.path))
// Symlinked Documents must not grant access to an outside cache directory.
let docsAlias = root.appendingPathComponent("docs-alias")
try fm.createSymbolicLink(at: docsAlias, withDestinationURL: docs)
let aliasDX = OwnedCacheCleaner(caches: caches, temporary: temporary, now: now, targetBytes: 0, documents: docsAlias).clean()
assert(aliasDX.removedBytes == 0 && aliasDX.cacheBytes == 4096)


// Explicit manual purge ignores recency and budget while preserving foreign/linked files.
let manual = OwnedCacheCleaner(caches: caches, temporary: temporary, now: now, targetBytes: Int64.max,
                              documents: docs, metalDriverCache: driver.deletingLastPathComponent(),
                              purgeShaderCaches: true).clean()
assert(manual.removedBytes == 8448 && manual.cacheBytes == 0)
for url in [recent, warmDX, currentDX] { assert(!fm.fileExists(atPath: url.path), url.path) }
for url in [outside, steam, other, foreignDX, driver, linkDX, symlink, active, foreign] {
    assert(fm.fileExists(atPath: url.path), url.path)
}
assert(fm.fileExists(atPath: docs.appendingPathComponent("shadercache").path)) // foreign files remain
let isolated = root.appendingPathComponent("isolated")
let isolatedCaches = isolated.appendingPathComponent("Caches")
let isolatedDocs = isolated.appendingPathComponent("Documents")
_ = try file("isolated/Caches/dxmt/Game.exe/shaders_320.db", size: 64)
_ = try file("isolated/Caches/dxmt/Game.exe/shaders_320.db-wal", size: 32)
_ = try file("isolated/Caches/dxmt/Game.exe/shaders_320.db-shm", size: 32)
_ = try file("isolated/Caches/dxmt/Game.exe/metal.bin", size: 128)
_ = try file("isolated/Documents/shadercache/0000000000000001.mdsc", size: 64)
_ = try file("isolated/Documents/shadercache/0000000000000002.mdxc", size: 64)
_ = try file("isolated/Documents/shadercache/0000000000000003.mdxc.tmp123", size: 32)
let isolatedResult = OwnedCacheCleaner(caches: isolatedCaches, temporary: temporary, now: now,
                                     targetBytes: Int64.max, documents: isolatedDocs,
                                     purgeShaderCaches: true).clean()
assert(isolatedResult.removedBytes == 416)
assert(!fm.fileExists(atPath: isolatedCaches.appendingPathComponent("dxmt").path))
assert(!fm.fileExists(atPath: isolatedDocs.appendingPathComponent("shadercache").path))
print("PASS: stale owned cache eviction, warm protection, temporary cleanup, unrelated/user/Steam data and symlink safety")
'''
with tempfile.TemporaryDirectory(prefix='madeira-cache-cleanup-') as tmp:
 p=Path(tmp);(p/'main.swift').write_text('import Foundation\n'+s+fixture)
 subprocess.run(['swiftc','-sanitize=address',str(p/'main.swift'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test'),str(p/'fixtures')],check=True)
# Serial startup/manual cleanup cannot race the launch opening its DBs.
assert 'stateLock.lock(); launched = true; stateLock.unlock()' in (root/'app/Madeira/CacheMaintenance.swift').read_text()
content=(root/'app/Madeira/ContentView.swift').read_text()
assert content.index('CacheMaintenance.prepareForLaunch()') < content.index('profile.applyEnvironment()')
print('PASS: launch/cache-cleanup serialization')
