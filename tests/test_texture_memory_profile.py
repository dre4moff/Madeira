"""Exercise saved per-game texture presets, compatibility and reversible edits."""
from pathlib import Path
import subprocess
import tempfile
from library_host_fixture import resolution_choices, control_action

root = Path(__file__).resolve().parents[1]
library = (root / 'app/Madeira/Library.swift').read_text()
cfg = (root / 'app/Madeira/MadeiraConfig.swift').read_text()

def block(source, header):
    start = source.index(header)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]

fields = library[library.index('struct LibraryEntry:'):library.index('    var launchArguments: String')]
swift = ('import Foundation\nstruct TouchControl: Codable {}\n' + control_action()
         + resolution_choices() + '\nenum DisplayMode: String { case fit }\n'
         + 'enum MadeiraConfig {\n' + block(cfg, '    static func parse(_ text: String)') + '\n}\n'
         + fields + '}\n' + r'''
var game = LibraryEntry(title: "Supermarket Together", relativePath: "Game.exe", bits: 64)
let other = LibraryEntry(title: "Other", relativePath: "Other.exe", bits: 64)
assert(game.textureMemoryStartMB == 0 && game.config == nil)
game.config = "dxmt = d3d11.mipClampAuto=1;d3d11.mipClampAutoMB=4096\n"
assert(game.gameConfigText!.contains("texture-memory-start-mb = 4096"))
assert(game.textureMemoryStartMB == 4096) // Recognize the already verified r33 profile.
game.textureMemoryStartMB = 0
assert(game.textureMemoryStartMB == 0 && game.config == nil)
game.textureMemoryStartMB = 4096
assert(game.textureMemoryStartMB == 4096 && other.textureMemoryStartMB == 0)
let restored = try JSONDecoder().decode([LibraryEntry].self, from: JSONEncoder().encode([game, other]))
assert(restored[0].textureMemoryStartMB == 4096 && restored[1].textureMemoryStartMB == 0)
assert(restored[0].id == game.id && restored[1].config == nil)
assert(restored[0].gameConfigText == game.config)
game.textureMemoryStartMB = 2048
assert(game.textureMemoryStartMB == 2048 && game.config == "texture-memory-start-mb = 2048")
game.textureMemoryStartMB = 4096
assert(game.textureMemoryStartMB == 4096 && game.config == "texture-memory-start-mb = 4096")
game.textureMemoryStartMB = 0
assert(game.config == nil)

let original = "# personal notes\nfence-chain = 6\ndxmt = d3d11.preferredMaxFrameRate=30;dxgi.customDeviceId=2544\nenv.FEX_MULTIBLOCK = 1"
game.config = original
game.textureMemoryStartMB = 4096
let on = game.config
game.textureMemoryStartMB = 4096
assert(game.config == on) // Repeated activation must not accumulate options.
assert(game.config!.contains("preferredMaxFrameRate=30") && game.config!.contains("customDeviceId=2544"))
game.textureMemoryStartMB = 0
assert(game.config == original) // Unrelated settings and comments survive.
game.config = "# dxmt = d3d11.mipClampAuto=1;d3d11.mipClampAutoMB=4096\nfence-chain = 6"
assert(game.textureMemoryStartMB == 0)
game.textureMemoryStartMB = 4096
game.textureMemoryStartMB = 0
assert(game.config!.hasPrefix("# dxmt =") && game.config!.hasSuffix("fence-chain = 6"))
game.config = "dxmt = d3d11.mipClampAuto=1;d3d11.mipClampAutoMB=4096\ndxmt = d3d11.preferredMaxFrameRate=30"
assert(game.textureMemoryStartMB == 0) // Same precedence as the runtime: last dxmt line wins.
game.textureMemoryStartMB = 4096
game.textureMemoryStartMB = 0
assert(game.config == "dxmt = d3d11.preferredMaxFrameRate=30")
game.config = "dxmt = d3d11.mipClampAuto=1;d3d11.mipClampAuto=0;d3d11.mipClampAutoMB=4096"
assert(game.textureMemoryStartMB == 0)
game.config = "  dxmt = d3d11.mipClampAuto = 1 ; d3d11.mipClampAutoMB = 4096\r\nfence-chain = 6"
assert(game.textureMemoryStartMB == 4096)
game.textureMemoryStartMB = 0
assert(MadeiraConfig.parse(game.config ?? "")["fence-chain"] == "6")
game.metalFXUpscale = 2
game.textureMemoryStartMB = 4096
assert(game.gameConfigText!.hasPrefix("metalfx-upscale = 2.0\n"))
print("PASS: Off/4 GB/2 GB round trip, legacy D3D12 launch normalization, default off, r33 profile recognition, saved library compatibility, per-game isolation, disabling, idempotence, comments, unrelated DXMT options, duplicate precedence and spatial upscaling coexistence")
''')
with tempfile.TemporaryDirectory(prefix='madeira-texture-profile-') as tmp:
    source = Path(tmp) / 'main.swift'
    source.write_text(swift)
    subprocess.run(['swift', str(source)], check=True)
