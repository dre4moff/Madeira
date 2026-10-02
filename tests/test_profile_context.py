"""Real thread names from the device log and windows spanning phase changes."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = r'''
#include <assert.h>
#include <stdio.h>
#include "PerformanceMath.h"
int main(void) {
    assert(madeira_thread_role("Foreground Worker #0") == MADEIRA_ROLE_WORKER);
    assert(madeira_thread_role("Foreground Work") == MADEIRA_ROLE_WORKER);
    assert(madeira_thread_role("Background Worker #2") == MADEIRA_ROLE_WORKER);
    assert(madeira_thread_role("Background Work") == MADEIRA_ROLE_WORKER);
    assert(madeira_thread_role("FAsyncLoadingThread") == MADEIRA_ROLE_LOADING);
    assert(madeira_thread_role("FAsyncLoadingTh") == MADEIRA_ROLE_LOADING);
    assert(madeira_thread_role("IoDispatcher") == MADEIRA_ROLE_IO);
    assert(madeira_thread_role("dxmt-encode-thre") == MADEIRA_ROLE_ENCODE);
    assert(madeira_thread_role("Steam worker") == MADEIRA_ROLE_OTHER);
    assert(madeira_thread_role("") == MADEIRA_ROLE_OTHER);
    assert(!madeira_perf_phase_mixed(0, 0));
    assert(madeira_perf_phase_mixed(0, 1));
    assert(!madeira_perf_phase_mixed(1, 1));
    assert(madeira_perf_phase_mixed(1, 2));
    assert(!strcmp(madeira_perf_phase_label(1), "stationary"));
    assert(!strcmp(madeira_perf_phase_label(4), "repeat-route"));
    assert(!strcmp(madeira_perf_phase_label(99), "unmarked"));
    puts("PASS: observed/truncated worker names, loading/I/O separation and mixed phase boundaries");
}
'''
with tempfile.TemporaryDirectory(prefix="madeira-profile-context-") as directory:
    temporary = Path(directory)
    (temporary / "test.c").write_text(source)
    subprocess.run(["clang", "-O2", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined",
                    "-I", str(root / "app/Madeira"), str(temporary / "test.c"), "-o", str(temporary / "test")], check=True)
    subprocess.run([str(temporary / "test")], check=True)
