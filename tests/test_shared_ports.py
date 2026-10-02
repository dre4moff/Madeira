"""Run the actual iOS WMT register/lookup path with fake Mach send rights."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / "dxmt/src/winemetal/unix/winemetal_unix.c").read_text()
start = source.index("/* Private API to register a mach port")
end = source.index("@protocol MTLDeviceSPI", start)
implementation = source[start:end].replace(
    '#include "../../../../build/dxmt-ios/shared_port_registry.h"',
    '#include "shared_port_registry.h"')
harness = r'''
#include <assert.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#undef TARGET_OS_IOS
#define TARGET_OS_IOS 1
#define MACH_PORT_RIGHT_SEND 0
#define KERN_SUCCESS 0
#define STATUS_SUCCESS 0
#define STATUS_UNSUCCESSFUL 1
typedef uint32_t NTSTATUS;
static atomic_int refs[1024];
static atomic_int reject_port;
static unsigned task_self(void) { return 1; }
#define mach_task_self task_self
static int mach_port_mod_refs(unsigned task, uint32_t port, int right, int delta) {
    assert(task == 1 && right == MACH_PORT_RIGHT_SEND && delta == 1);
    if (port >= 1024 || (int)port == atomic_load(&reject_port)) return 5;
    atomic_fetch_add(&refs[port], delta);
    return KERN_SUCCESS;
}
static int mach_port_deallocate(unsigned task, uint32_t port) {
    assert(task == 1 && port < 1024);
    assert(atomic_fetch_sub(&refs[port], 1) > 0);
    return KERN_SUCCESS;
}
struct unixcall_bootstrap { char name[128]; uint32_t mach_port, reserved; };
static int fail_allocation;
static void *registry_malloc(size_t bytes) {
    return fail_allocation ? NULL : malloc(bytes);
}
#define malloc registry_malloc
''' + implementation + r'''
#undef malloc
static struct unixcall_bootstrap request(const char *name, uint32_t port) {
    struct unixcall_bootstrap p = {0};
    snprintf(p.name, sizeof(p.name), "%s", name); p.mach_port = port;
    return p;
}
static void *worker(void *arg) {
    unsigned id = (unsigned)(uintptr_t)arg;
    for (unsigned n = 0; n < 24; n++) {
        char name[128]; snprintf(name, sizeof(name), "DXMT_shared_resource_%u_%u", id, n);
        struct unixcall_bootstrap p = request(name, 100 + id);
        assert(_WMTBootstrapRegister(&p) == STATUS_SUCCESS);
        p.mach_port = 0;
        assert(_WMTBootstrapLookUp(&p) == STATUS_SUCCESS && p.mach_port == 100 + id);
        mach_port_deallocate(1, p.mach_port);
    }
    return NULL;
}
int main(void) {
    struct unixcall_bootstrap p = request("DXMT_shared_resource_texture", 23);
    atomic_store(&refs[23], 1); // creator's original send right
    assert(_WMTBootstrapRegister(&p) == STATUS_SUCCESS);
    assert(atomic_load(&refs[23]) == 2);
    mach_port_deallocate(1, 23); // registry survives release by the creator
    assert(atomic_load(&refs[23]) == 1);
    // A second pseudo-process/device resolves the actual shared port.
    struct unixcall_bootstrap child = request(p.name, 0);
    assert(_WMTBootstrapLookUp(&child) == STATUS_SUCCESS && child.mach_port == 23);
    assert(atomic_load(&refs[23]) == 2);
    mach_port_deallocate(1, child.mach_port);
    p.mach_port = 24;
    assert(_WMTBootstrapRegister(&p) == STATUS_UNSUCCESSFUL);
    assert(atomic_load(&refs[24]) == 0); // duplicate cannot replace a live resource
    p = request("DXMT_shared_resource_fence", 24);
    assert(_WMTBootstrapRegister(&p) == STATUS_SUCCESS);
    child = request(p.name, 0);
    assert(_WMTBootstrapLookUp(&child) == STATUS_SUCCESS && child.mach_port == 24);
    mach_port_deallocate(1, child.mach_port);
    child = request("missing", 99);
    assert(_WMTBootstrapLookUp(&child) == STATUS_UNSUCCESSFUL && child.mach_port == 0);
    p = request("", 25); assert(_WMTBootstrapRegister(&p) == STATUS_UNSUCCESSFUL);
    memset(p.name, 'x', sizeof(p.name)); assert(_WMTBootstrapRegister(&p) == STATUS_UNSUCCESSFUL);
    assert(_WMTBootstrapLookUp(&p) == STATUS_UNSUCCESSFUL && p.mach_port == 0);
    p = request("null", 0); assert(_WMTBootstrapRegister(&p) == STATUS_UNSUCCESSFUL);
    p = request("dead", UINT32_MAX); assert(_WMTBootstrapRegister(&p) == STATUS_UNSUCCESSFUL);
    p = request("allocation-failed", 26); fail_allocation = 1;
    assert(_WMTBootstrapRegister(&p) == STATUS_UNSUCCESSFUL && atomic_load(&refs[26]) == 0);
    fail_allocation = 0;
    assert(_WMTBootstrapRegister(&p) == STATUS_SUCCESS); // failed registration leaves no stale name
    p = request("refused", 25); atomic_store(&reject_port, 25);
    assert(_WMTBootstrapRegister(&p) == STATUS_UNSUCCESSFUL && atomic_load(&refs[25]) == 0);
    child = request("refused", 9);
    assert(_WMTBootstrapLookUp(&child) == STATUS_UNSUCCESSFUL && child.mach_port == 0);
    atomic_store(&reject_port, 23); child = request("DXMT_shared_resource_texture", 9);
    assert(_WMTBootstrapLookUp(&child) == STATUS_UNSUCCESSFUL && child.mach_port == 0);
    atomic_store(&reject_port, 0);
    pthread_t threads[8];
    for (uintptr_t i = 0; i < 8; i++) assert(!pthread_create(&threads[i], NULL, worker, (void *)i));
    for (int i = 0; i < 8; i++) assert(!pthread_join(threads[i], NULL));
    madeira_shared_ports_exit();
    for (int i = 0; i < 1024; i++) assert(atomic_load(&refs[i]) == 0);
    child = request("DXMT_shared_resource_texture", 9);
    assert(_WMTBootstrapLookUp(&child) == STATUS_UNSUCCESSFUL && child.mach_port == 0);
    puts("PASS: actual iOS register/lookup wrappers, texture/fence sharing, failure containment, concurrent clients and balanced mocked send rights");
}
'''
with tempfile.TemporaryDirectory(prefix="madeira-shared-port-test-") as tmp:
    path = Path(tmp) / "main.c"
    binary = Path(tmp) / "shared-port-test"
    path.write_text(harness)
    subprocess.run(["clang", "-Wall", "-Wextra", "-Werror", "-pthread", "-fsanitize=address,undefined",
                    "-I", str(root / "build/dxmt-ios"), str(path), "-o", str(binary)], check=True)
    result = subprocess.run([str(binary)], capture_output=True, text=True)
    if result.returncode:
        print(result.stderr[-3000:])
    result.check_returncode()
    print(result.stdout, end="")
