"""Gigabyte-scale crash dumps require opt-in; no JIT/game execution."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = r'''
#include <assert.h>
#include <stdlib.h>
#include "runtime_profiling.h"
int main(void) {
 unsetenv("MADEIRA_JIT_DUMP");
 unsetenv("MADEIRA_QUIET");
 assert(!madeira_jit_dump_enabled());
 setenv("MADEIRA_RUNTIME_PROFILING","1",1);
 assert(!madeira_jit_dump_enabled());
 const char *off[]={"", "0", "true", "yes", "11"};
 for(unsigned i=0;i<sizeof off/sizeof off[0];i++) {
   setenv("MADEIRA_JIT_DUMP",off[i],1);assert(!madeira_jit_dump_enabled());
 }
 setenv("MADEIRA_JIT_DUMP","1",1);assert(madeira_jit_dump_enabled());
 return 0;
}
'''
with tempfile.TemporaryDirectory(prefix="madeira-jit-dump-") as folder:
    p = Path(folder)
    (p / "test.c").write_text(source)
    subprocess.run(["xcrun", "clang", "-fsanitize=address,undefined",
                    "-I" + str(root / "build/ntdll-unix"), str(p / "test.c"),
                    "-o", str(p / "test")], check=True)
    subprocess.run([str(p / "test")], check=True)
signal = (root / "build/ntdll-unix/signal_arm64_ios.c").read_text()
assert "cnt == 1 && madeira_jit_dump_enabled() &&" in signal
assert "if (madeira_jit_dump_enabled() && __sync_bool_compare_and_swap(&ill_dumped" in signal
print("PASS: dump disabled by default even with profiling, exact explicit opt-in, both fault paths gated")
