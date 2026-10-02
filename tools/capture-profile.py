#!/usr/bin/env python3
"""Capture an already-running Madeira host after its JIT setup; never launches a game."""
import argparse
from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--list", action="store_true", help="List devices and capture templates only")
parser.add_argument("--record", action="store_true", help="Actually start recording; otherwise print the command")
parser.add_argument("--device", help="Connected physical iPhone UDID or exact device name")
parser.add_argument("--process", default="Madeira", help="Native host process name or PID, not a Wine guest PID")
parser.add_argument("--kind", choices=("cpu", "gpu"), default="cpu")
parser.add_argument("--seconds", type=int, default=150)
parser.add_argument("--output", type=Path, help="New .trace directory; existing traces are never overwritten")
args = parser.parse_args()
env = os.environ.copy()
env.setdefault("DEVELOPER_DIR", "/Applications/Xcode.app/Contents/Developer")
if args.list:
    for command in (["xcrun", "xctrace", "list", "devices"], ["xcrun", "xctrace", "list", "templates"]):
        subprocess.run(command, env=env, check=True)
    sys.exit(0)
if not args.device:
    parser.error("Specify --device. Use --list to identify a connected physical iPhone.")
if not 30 <= args.seconds <= 180:
    parser.error("--seconds must be 30–180 to bound capture duration and disk usage.")
output = (args.output or root / ".build/profiling-captures" /
          (datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + args.kind + ".trace")).resolve()
if output.suffix != ".trace" or output.exists():
    parser.error("--output must be a new .trace directory.")
template = "Time Profiler" if args.kind == "cpu" else "Metal System Trace"
command = ["xcrun", "xctrace", "record", "--device", args.device,
           "--template", template, "--attach", args.process,
           "--time-limit", str(args.seconds) + "s", "--output", str(output)]
print("Target: running native host; no relaunch or JIT allocation is performed.")
print("Capture:", template, "for", args.seconds, "seconds; output:", output)
if not args.record:
    import shlex
    print(shlex.join(command))
    print("Dry run. Add --record when Madeira is already running in the map.")
    sys.exit(0)
output.parent.mkdir(parents=True, exist_ok=True)
result = subprocess.run(command, env=env)
if result.returncode:
    print("Recording failed. The partial trace, if any, is kept for inspection.", file=sys.stderr)
    sys.exit(result.returncode)
subprocess.run(["xcrun", "xctrace", "export", "--input", str(output), "--toc",
                "--output", str(output.with_suffix(".toc.xml"))], env=env, check=True)
print("Saved local trace and table of contents. Open the .trace in Instruments.")
