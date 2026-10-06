"""Check that local source publication cannot accidentally carry the FEX gate."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
pin = "3bec2ac498bf78156ab47c0c194b0e8cb2849756"
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root / "FEX", text=True).strip() == pin
subprocess.run(["git", "diff", "--exit-code", pin, "--"], cwd=root / "FEX", check=True)
for path in ("FEXCore/Source/Interface/Core/Core.cpp", "FEXCore/Source/Utils/ArchHelpers/Arm64.cpp"):
    original = subprocess.check_output(["git", "show", pin + ":" + path], cwd=root / "FEX")
    assert (root / "FEX" / path).read_bytes() == original
assert b"MADEIRA_RUNTIME_PROFILING" not in (root / "app/Madeira/arm64ec-windows/xtajit64.dll").read_bytes()
print("PASS: FEX pin and tracked source restored; custom gate absent from the Windows engine")
