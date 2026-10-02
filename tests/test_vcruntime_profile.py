"""Host-only tests of the real LibraryEntry stored fields; never starts Wine."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / "app/Madeira/Library.swift").read_text()
fields = source[source.index("struct LibraryEntry: Codable, Identifiable {"):source.index("    var displayMode: DisplayMode")]
test = r'''
import Foundation
// On-screen controls are unrelated to this test; old fixtures contain none.
struct TouchControl: Codable {}
''' + fields + r'''
}
var first = LibraryEntry(title: "RV There Yet?", relativePath: "Games/Ride.exe", bits: 64)
let second = LibraryEntry(title: "Other game", relativePath: "Games/Other.exe", bits: 64)
assert(first.nativeVCRuntime == nil && second.nativeVCRuntime == nil)
let encoder = JSONEncoder()
let decoder = JSONDecoder()
// The old v0.1.0 format must still load, without the added field.
var old = try JSONSerialization.jsonObject(with: encoder.encode(first)) as! [String: Any]
old.removeValue(forKey: "nativeVCRuntime")
old.removeValue(forKey: "forceDirectX11")
let loaded = try decoder.decode(LibraryEntry.self, from: JSONSerialization.data(withJSONObject: old))
assert(loaded.nativeVCRuntime == nil)
assert(loaded.forceDirectX11 == nil)
first.nativeVCRuntime = true
let stored = try decoder.decode([LibraryEntry].self, from: encoder.encode([first, second]))
assert(stored[0].nativeVCRuntime == true && stored[1].nativeVCRuntime == nil)
assert(stored[0].id == first.id && stored[1].relativePath == second.relativePath)
first.nativeVCRuntime = false
let off = try decoder.decode(LibraryEntry.self, from: encoder.encode(first))
assert(off.nativeVCRuntime == false)
print("PASS: old library compatibility, persistence, per-game isolation and disabling")
'''
with tempfile.TemporaryDirectory(prefix="madeira-profile-test-") as tmp:
    path = Path(tmp) / "main.swift"
    path.write_text(test)
    subprocess.run(["swift", str(path)], check=True)

# Both Steam Dock and direct starts must reach the common profile and bridge.
content = (root / "app/Madeira/ContentView.swift").read_text()
assert "runWineFullSequence(profile: entry)" in content
assert "runWineFullSequence(profile: profile)" in content
assert "profile.applyEnvironment()" in content
bridge = (root / "app/Madeira/WineProcessBridge.m").read_text()
assert bridge.index("madeira_apply_vcruntime_overrides(nativeVCRuntime)") > bridge.index("madeira.cfg env:")
assert "NSArray *vcrtTargets = use_arm64ec ? @[sysx64Dir, sys32Dir] : @[sysx64Dir];" in bridge
print("PASS: direct/Steam launch wiring, config precedence, opt-in DLL staging")
