import Foundation
import SwiftUI

/// Only reconstructible, explicitly owned paths. Never walks the Wine prefix,
/// Steam downloads, Application Support, saves, library or login data.
struct OwnedCacheCleaner {
    struct Result {
        var removedBytes: Int64 = 0
        var cacheBytes: Int64 = 0
        var protectedBytes: Int64 = 0
        var driverBytes: Int64 = 0
        var failedItems = 0
    }
    let caches: URL
    let temporary: URL
    let now: Date
    let targetBytes: Int64
    var documents: URL? = nil
    var metalDriverCache: URL? = nil
    let fm = FileManager.default
    private let keys: Set<URLResourceKey> = [.isSymbolicLinkKey, .isDirectoryKey, .isRegularFileKey,
                                             .fileSizeKey, .contentModificationDateKey]

    private func safe(_ url: URL) -> Bool {
        guard let values = try? url.resourceValues(forKeys: keys), values.isSymbolicLink != true else { return false }
        // System /var aliases are legitimate on iOS; reject links below our roots.
        var anchors = [caches.standardizedFileURL, temporary.standardizedFileURL]
        if let documents,
           (try? documents.resourceValues(forKeys: [.isSymbolicLinkKey]).isSymbolicLink) == false {
            anchors.append(documents.appendingPathComponent("shadercache").standardizedFileURL)
            anchors.append(documents.appendingPathComponent("fex-jit-dump.bin").standardizedFileURL)
        }
        guard let anchor = anchors.first(where: { url.standardizedFileURL.path == $0.path || url.standardizedFileURL.path.hasPrefix($0.path + "/") }) else { return false }
        var current = url.standardizedFileURL
        while current.path != anchor.path {
            guard let item = try? current.resourceValues(forKeys: [.isSymbolicLinkKey]), item.isSymbolicLink != true else { return false }
            let parent = current.deletingLastPathComponent()
            guard parent.path != current.path else { return false }
            current = parent
        }
        return true
    }
    private func sizeAndDate(_ url: URL) -> (Int64, Date) {
        guard safe(url), let values = try? url.resourceValues(forKeys: keys) else { return (0, .distantFuture) }
        var bytes: Int64 = Int64(values.fileSize ?? 0)
        var date = values.contentModificationDate ?? .distantFuture
        if values.isDirectory == true {
            bytes = 0
            guard let iterator = fm.enumerator(at: url, includingPropertiesForKeys: Array(keys), options: []) else { return (0, .distantFuture) }
            for case let file as URL in iterator {
                guard safe(file), let item = try? file.resourceValues(forKeys: keys) else {
                    // An unowned/symlink child makes the whole cache group protected.
                    return (bytes, .distantFuture)
                }
                if item.isRegularFile == true { bytes += Int64(item.fileSize ?? 0) }
                date = max(date, item.contentModificationDate ?? .distantFuture)
            }
        }
        return (bytes, date)
    }
    func clean() -> Result {
        var result = Result()
        // This exact file is an old generated crash dump, never a shader cache.
        // Preserve it when the owner explicitly requests a new diagnostic dump.
        if let documents, ProcessInfo.processInfo.environment["MADEIRA_JIT_DUMP"] != "1" {
            let dump = documents.appendingPathComponent("fex-jit-dump.bin")
            if safe(dump), let kind = try? dump.resourceValues(forKeys: keys), kind.isRegularFile == true {
                let bytes = Int64(kind.fileSize ?? 0)
                if (try? fm.removeItem(at: dump)) != nil { result.removedBytes += bytes }
                else { result.failedItems += 1 }
            }
        }
        // Survive a crash/force quit: these temporary paths never contain user data.
        if safe(temporary), let items = try? fm.contentsOfDirectory(at: temporary, includingPropertiesForKeys: Array(keys)) {
            for file in items {
                let name = file.lastPathComponent
                let ownedStage = name.hasPrefix("madeira-runtime-") && UUID(uuidString: String(name.dropFirst("madeira-runtime-".count))) != nil
                guard name == "madeira-swap.bin" || ownedStage else { continue }
                guard let kind = try? file.resourceValues(forKeys: keys),
                      name == "madeira-swap.bin" ? kind.isRegularFile == true : kind.isDirectory == true else { continue }
                let (bytes, date) = sizeAndDate(file)
                // A current download may still be extracting in this process.
                guard safe(file), name == "madeira-swap.bin" || now.timeIntervalSince(date) > 24 * 3600 else { continue }
                if (try? fm.removeItem(at: file)) != nil { result.removedBytes += bytes }
                else { result.failedItems += 1 }
            }
        }
        let root = caches.appendingPathComponent("dxmt", isDirectory: true)
        var groups: [(url: URL, info: (Int64, Date))] = []
        if safe(caches), safe(root), let games = try? fm.contentsOfDirectory(at: root, includingPropertiesForKeys: Array(keys)) {
            groups += games.map { (url: $0, info: sizeAndDate($0)) }
        }
        // D3D12 owns only content-keyed conversion entries in this exact
        // directory. Never enumerate the rest of Documents or the Wine prefix.
        if let documents {
            let shaders = documents.appendingPathComponent("shadercache", isDirectory: true)
            if safe(shaders), let files = try? fm.contentsOfDirectory(at: shaders, includingPropertiesForKeys: Array(keys)) {
                for file in files where safe(file) {
                    let name = file.lastPathComponent
                    guard (try? file.resourceValues(forKeys: keys).isRegularFile) == true else { continue }
                    let info = sizeAndDate(file)
                    if name.range(of: "^[0-9a-f]{16}\\.(mdsc|mdxc)$", options: .regularExpression) != nil {
                        groups.append((file, info))
                    } else if name.range(of: "^[0-9a-f]{16}\\.(mdsc|mdxc)\\.tmp[0-9]+$", options: .regularExpression) != nil,
                              now.timeIntervalSince(info.1) > 24 * 3600 {
                        if (try? fm.removeItem(at: file)) != nil { result.removedBytes += info.0 }
                        else { result.failedItems += 1 }
                    }
                }
            }
        }
        // Metal also keeps a driver cache under the signed bundle ID. Measure
        // it separately; its storage/eviction belongs to the OS, not our budget.
        if let metalDriverCache, safe(metalDriverCache) {
            result.driverBytes = sizeAndDate(metalDriverCache).0
        }
        result.cacheBytes = groups.reduce(0) { $0 + $1.info.0 }
        // A soft target: retain every cache used in the last 30 days, even if
        // it exceeds the budget. Deleting a warm shader DB hurts performance.
        for game in groups.sorted(by: { $0.info.1 < $1.info.1 }) {
            let recent = now.timeIntervalSince(game.info.1) <= 30 * 24 * 3600
            if recent { result.protectedBytes += game.info.0; continue }
            guard result.cacheBytes > targetBytes, safe(game.url) else { continue }
            if (try? fm.removeItem(at: game.url)) != nil {
                result.removedBytes += game.info.0
                result.cacheBytes -= game.info.0
            } else { result.failedItems += 1 }
        }
        return result
    }
}

enum CacheMaintenance {
    private static let queue = DispatchQueue(label: "com.madeira.cache-maintenance", qos: .utility)
    private static var launched = false
    private static var startupDone = false
    static var available: Bool { queue.sync { !launched } }
    static func start() {
        queue.async {
            guard !startupDone, !launched else { return }
            startupDone = true
            if UserDefaults.standard.object(forKey: "madeiraAutomaticCacheCleanup") as? Bool != false { _ = clean() }
        }
    }
    /// Serializes with startup/manual cleanup before any Wine/cache files open.
    static func prepareForLaunch() { queue.sync { launched = true } }
    static func manual(completion: @escaping (String) -> Void) {
        queue.async {
            let message: String
            if launched { message = "Restart Madeira to clean caches safely." }
            else {
                let result = clean()
                message = summary(result)
            }
            DispatchQueue.main.async { completion(message) }
        }
    }
    static func summary(_ result: OwnedCacheCleaner.Result) -> String {
        func size(_ bytes: Int64) -> String { ByteCountFormatter.string(fromByteCount: bytes, countStyle: .file) }
        let cleanup = result.removedBytes > 0 ? "Removed \(size(result.removedBytes))." : "No obsolete files to remove."
        let shaders = result.cacheBytes > 0 ? "Shader caches: \(size(result.cacheBytes)) kept for reuse (\(size(result.protectedBytes)) recently used)." : "No saved shader cache files found yet."
        let driver = result.driverBytes > 0 ? " Metal driver cache: \(size(result.driverBytes)) (system-managed)." : ""
        let failures = result.failedItems > 0 ? " \(result.failedItems) items could not be removed." : ""
        return cleanup + " " + shaders + driver + failures
    }
    private static func clean() -> OwnedCacheCleaner.Result {
        let fm = FileManager.default
        let base = fm.urls(for: .cachesDirectory, in: .userDomainMask)[0]
        let saved = UserDefaults.standard.integer(forKey: "madeiraCacheTargetMB")
        let mb = [512, 1024, 2048].contains(saved) ? saved : 1024
        let documents = fm.urls(for: .documentDirectory, in: .userDomainMask).first
        let driver = Bundle.main.bundleIdentifier.map { base.appendingPathComponent($0).appendingPathComponent("com.apple.metal") }
        let result = OwnedCacheCleaner(caches: base, temporary: fm.temporaryDirectory,
                                      now: Date(), targetBytes: Int64(mb) << 20,
                                      documents: documents, metalDriverCache: driver).clean()
        fputs("[cache-cleanup] removed=\(result.removedBytes) shader-cache=\(result.cacheBytes) protected-recent=\(result.protectedBytes) metal-driver=\(result.driverBytes) failures=\(result.failedItems) target=\(mb)MB\n", stderr)
        return result
    }
}

struct CacheStorageSettings: View {
    @AppStorage("madeiraAutomaticCacheCleanup") private var automatic = true
    @AppStorage("madeiraCacheTargetMB") private var target = 1024
    @State private var cleaning = false
    @State private var message = ""
    var body: some View {
        Section {
            Toggle("Automatic cache clean-up", isOn: $automatic)
            Picker("Shader cache target", selection: $target) {
                Text("512 MB").tag(512)
                Text("1 GB").tag(1024)
                Text("2 GB").tag(2048)
            }
            Button("Clean temporary & obsolete files") {
                cleaning = true
                CacheMaintenance.manual { message = $0; cleaning = false }
            }.disabled(cleaning || !CacheMaintenance.available)
            if !message.isEmpty { Text(message).font(.caption).foregroundStyle(.secondary) }
        } header: { Text("Storage & caches") } footer: {
            Text("Cleans leftover temporary files at startup. Shader caches unused for 30 days are removed only above the target; recent caches are kept even above it to avoid recompilation. Games, saves and Steam data are preserved. Restart Madeira after playing to clean safely.")
        }
    }
}
