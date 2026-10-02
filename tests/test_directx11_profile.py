"""Host-only DirectX 11 tests. No client DLL, game or Wine process is executed."""
from pathlib import Path
import re
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
library = (root / "app/Madeira/Library.swift").read_text()
helper = library[library.index("enum LibraryLaunchArguments {"):library.index("struct LibraryEntry:")]
fields = library[library.index("struct LibraryEntry: Codable, Identifiable {"):library.index("    var displayMode:")]
computed = library[library.index("    var launchArguments: String {"):library.index('    /// What a launch starts')]
swift = "import Foundation\nstruct TouchControl: Codable {}\n" + helper + fields + computed + r'''
}
let original = "-windowed  -dx12 -path \"Maps -dx12\""
assert(LibraryLaunchArguments.directX11(original, enabled: false) == original)
assert(LibraryLaunchArguments.directX11(original, enabled: true) == "-windowed -path \"Maps -dx12\" -dx11")
assert(LibraryLaunchArguments.directX11("-D3D12 -vulkan -dx11 -d3d11", enabled: true) == "-dx11")
assert(LibraryLaunchArguments.directX11("-foo=\"A B\" -d3d12", enabled: true) == "-foo=\"A B\" -dx11")
var game = LibraryEntry(title: "RV There Yet?", relativePath: "Games/Ride.exe", bits: 64)
let other = LibraryEntry(title: "Other game", relativePath: "Games/Other.exe", bits: 64)
assert(game.forceDirectX11 == nil && game.launchArguments == "")
game.forceDirectX11 = true
assert(game.launchArguments == "-dx11" && other.launchArguments == "")
game.arguments = "-windowed -dx12"
assert(game.launchArguments == "-windowed -dx11")
game.steamAppID = 3949040
game.steamStart = "game"
game.steamProgramArguments = "-windowed -d3d12"
assert(game.startsSteamGameDirectly && game.launchArguments == "-windowed -dx11")
let encoder = JSONEncoder(), decoder = JSONDecoder()
let restored = try decoder.decode([LibraryEntry].self, from: encoder.encode([game, other]))
assert(restored[0].forceDirectX11 == true && restored[1].forceDirectX11 == nil)
game.forceDirectX11 = false
assert(game.launchArguments == "-windowed -d3d12")
game.forceDirectX11 = true
game.desktop = true
assert(!game.launchArguments.contains("-dx11"))
print("PASS: per-game DX11 arguments, saved profiles, direct/Steam direct starts, quoted values and disabling")
'''

dock = (root / "madeira-dock/src/launch.c").read_text()
wide_flag = dock[dock.index("static bool wide_flag("):dock.index("/* Returns 0 once")]
choice = re.search(r'    const char \*user_args = .+;', dock).group(0)
calls = re.findall(r"^\s*(?:uint64_t )?call = (\(\(launch_fn\).+);", dock, re.M)
assert len(calls) == 2, "Initial launch and retry must both forward the selected arguments"
bridge = (root / "app/Madeira/WineProcessBridge.m").read_text()
capture_start = bridge.index('        const char *directX11Choice')
capture_end = bridge.index('        /* Perf:', capture_start)
capture = bridge[capture_start:capture_end]
export_start = bridge.index('        if (forceDirectX11) setenv')
export_end = bridge.index('        dprintf', export_start)
export = bridge[export_start:export_end]
assert export_start > bridge.index("madeira.cfg env:")
assert 'setenv("MADEIRA_GAME_DIRECTX11", forceDirectX11 == true && desktop != true ? "1" : "0", 1)' in library
assert 'o->event("launch-directx11", user_args[0] != 0)' in dock
assert '"launch-directx11"' in (root / "app/Madeira/MadeiraDock.swift").read_text()
c = r'''
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>
#include <stdio.h>
typedef unsigned long DWORD;
typedef int BOOL;
#define __thiscall
static const wchar_t *setting;
static DWORD GetEnvironmentVariableW(const wchar_t *name, wchar_t *dest, DWORD cap) {
    assert(!wcscmp(name, L"MADEIRA_STEAM_HOST_DIRECTX11"));
    if (!setting) return 0;
    size_t n = wcslen(setting);
    if (n >= cap) return (DWORD)n + 1;
    wcscpy(dest, setting);
    return (DWORD)n;
}
''' + wide_flag + r'''
typedef uint64_t (*launch_fn)(void *, const uint64_t *, uint32_t, int32_t, const char *);
static const char *expected;
static unsigned submitted;
static uint64_t fake_launch(void *manager, const uint64_t *gameid, uint32_t source, int32_t option, const char *args) {
    assert(manager && *gameid == 3949040 && source == 0 && option == 0);
    assert(!strcmp(args, expected));
    submitted++;
    return 42;
}
static void exercise(const wchar_t *flag, const char *wanted) {
    setting = flag;
    expected = wanted;
    submitted = 0;
    void *vtable[] = {NULL, NULL, (void *)fake_launch};
    void **vptr = vtable;
    void *manager = &vptr;
    uint64_t gameid = 3949040;
''' + choice + "\n    uint64_t call = " + calls[0] + ";\n    call = " + calls[1] + r''';
    assert(call == 42 && submitted == 2);
}
static void transfer(const char *flag) {
    unsetenv("MADEIRA_GAME_DIRECTX11");
    if (flag) setenv("MADEIRA_GAME_DIRECTX11", flag, 1);
    // A global config/stale previous game must not retain the enabled choice.
    setenv("MADEIRA_STEAM_HOST_DIRECTX11", "1", 1);
''' + capture + export + r'''
    assert(!getenv("MADEIRA_GAME_DIRECTX11"));
    if (flag && !strcmp(flag, "1"))
        assert(!strcmp(getenv("MADEIRA_STEAM_HOST_DIRECTX11"), "1"));
    else assert(!getenv("MADEIRA_STEAM_HOST_DIRECTX11"));
}
int main(void) {
    exercise(NULL, "");
    exercise(L"0", "");
    exercise(L"1", "-dx11");
    exercise(L"1", "-dx11");
    exercise(L"0", "");
    exercise(L"11", "");
    exercise(L"badlongflag", "");
    transfer("1"); transfer("0"); transfer(NULL);
    puts("PASS: actual Dock initial launch/retry arguments and per-session config precedence/reset");
}
'''
with tempfile.TemporaryDirectory(prefix="madeira-dx11-test-") as tmp:
    tmp = Path(tmp)
    (tmp / "main.swift").write_text(swift)
    subprocess.run(["swift", str(tmp / "main.swift")], check=True)
    (tmp / "main.c").write_text(c)
    subprocess.run(["clang", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined",
                    str(tmp / "main.c"), "-o", str(tmp / "test")], check=True)
    subprocess.run([str(tmp / "test")], check=True)

