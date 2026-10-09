#!/usr/bin/env python3
"""Exercise the actual iOS native/WoW64 root enumerators across client processes."""
from pathlib import Path
import base64
import re
import struct
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
path = 'build/crypto-unix/crypt32_unixlib_ios.c'
source = (root / path).read_text()
baseline = subprocess.check_output(['git', 'show', 'ebcb895:' + path], cwd=root, text=True)


def production(text):
    start = text.index('#include <pthread.h>')
    end = text.index('\nconst unixlib_entry_t __wine_unix_call_funcs[]', start)
    thunk = text.index('static NTSTATUS wow64_enum_root_certs(')
    return text[start:end] + text[thunk:text.index('\n}', thunk) + 2]


fixture = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include "wine/list.h"
typedef uint32_t DWORD, PTR32;
typedef int BOOL, NTSTATUS;
#define TRUE 1
#define STATUS_SUCCESS 0
#define STATUS_NO_MORE_ENTRIES (-1)
#define STATUS_NO_MEMORY (-2)
struct enum_root_certs_params { void *buffer; DWORD size; DWORD *needed; };
struct root_cert { struct list entry; DWORD size; unsigned char data[]; };
static struct list root_cert_list = LIST_INIT(root_cert_list);
static unsigned char *expected[256];
static DWORD lengths[256], count, loads;
static const char *input;
static _Thread_local unsigned char guest[16384];
static void *ios_wow_host_ptr(PTR32 address) { return address ? guest + address : NULL; }
static void load_root_certs(void) {
    assert(++loads == 1);
    FILE *f = fopen(input, "rb"); assert(f);
    DWORD size;
    while (fread(&size, sizeof(size), 1, f)) {
        assert(size < 8000 && count < 256);
        struct root_cert *cert = malloc(sizeof(*cert) + size); assert(cert);
        cert->size = lengths[count] = size;
        assert(fread(cert->data, size, 1, f) == 1);
        expected[count] = malloc(size); assert(expected[count]);
        memcpy(expected[count++], cert->data, size);
        list_add_tail(&root_cert_list, &cert->entry);
    }
    assert(feof(f)); fclose(f);
}
'''

checks = r'''
static pthread_mutex_t barrier_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t barrier_cond = PTHREAD_COND_INITIALIZER;
static unsigned arrived;
#define WORKERS 64
static void barrier(void) {
    pthread_mutex_lock(&barrier_lock);
    if (++arrived == WORKERS) pthread_cond_broadcast(&barrier_cond);
    else while (arrived < WORKERS) pthread_cond_wait(&barrier_cond, &barrier_lock);
    pthread_mutex_unlock(&barrier_lock);
}
static NTSTATUS next(int wow, unsigned char *buffer, DWORD size, DWORD *needed) {
    if (!wow) {
        struct enum_root_certs_params p = {buffer, size, needed};
        return enum_root_certs(&p);
    }
    struct { PTR32 buffer; DWORD size; PTR32 needed; } p = {buffer ? 64 : 0, size, 12000};
    memset(guest + 64, 0x5a, 8000);
    *(DWORD *)(guest + 12000) = *needed;
    NTSTATUS status = wow64_enum_root_certs(&p);
    *needed = *(DWORD *)(guest + 12000);
    if (buffer) memcpy(buffer, guest + 64, size);
    return status;
}
static unsigned enumerate(int wow, int concurrent) {
    unsigned seen = 0;
    unsigned char buffer[8000]; DWORD needed = 0;
    while (next(wow, NULL, 0, &needed) == STATUS_SUCCESS) {
        assert(seen < count && needed == lengths[seen]);
        memset(buffer, 0x5a, sizeof(buffer));
        assert(next(wow, buffer, needed - 1, &needed) == STATUS_SUCCESS);
        assert(needed == lengths[seen]);
        for (DWORD j = 0; j < sizeof(buffer); j++) assert(buffer[j] == 0x5a);
        assert(next(wow, buffer, needed, &needed) == STATUS_SUCCESS);
        assert(needed == lengths[seen] && !memcmp(buffer, expected[seen], needed));
        for (DWORD j = needed; j < sizeof(buffer); j++) assert(buffer[j] == 0x5a);
        if (++seen == 1 && concurrent) barrier();
    }
    return seen;
}
static void *worker(void *arg) {
    int wow = (uintptr_t)arg & 1;
    assert(enumerate(wow, 1) == count);
    assert(enumerate(!wow, 0) == count);
    return NULL;
}
int main(int argc, char **argv) {
    assert(argc == 2); input = argv[1];
    unsigned first = enumerate(0, 0), second = enumerate(0, 0);
#ifdef BASELINE
    assert(first == count && second == 0 && list_empty(&root_cert_list));
    printf("r37 defect reproduced: first native import %u roots, second 0\n", first);
#else
    assert(first == count && second == count);
    assert(enumerate(1, 0) == count && enumerate(0, 0) == count);
    if (count) {
        pthread_t threads[WORKERS];
        for (uintptr_t i = 0; i < WORKERS; i++) assert(!pthread_create(&threads[i], NULL, worker, (void *)i));
        for (unsigned i = 0; i < WORKERS; i++) assert(!pthread_join(threads[i], NULL));
    }
    unsigned retained = 0; struct list *ptr;
    LIST_FOR_EACH(ptr, &root_cert_list) retained++;
    assert(retained == count && loads == 1);
    printf("%u CA roots preserved across native/WoW64 imports and %u concurrent callers\n", count, count ? WORKERS : 0);
#endif
    while (!list_empty(&root_cert_list)) {
        struct root_cert *cert = LIST_ENTRY(list_head(&root_cert_list), struct root_cert, entry);
        list_remove(&cert->entry); free(cert);
    }
    for (unsigned i = 0; i < count; i++) free(expected[i]);
    return 0;
}
'''

certs = [base64.b64decode(c) for c in re.findall(
    r'-----BEGIN CERTIFICATE-----\s*(.*?)\s*-----END CERTIFICATE-----',
    (root / 'app/Madeira/cacert.pem').read_text(), re.S)]
assert len(certs) == 121
with tempfile.TemporaryDirectory(prefix='madeira-ca-roots-') as folder:
    work = Path(folder)
    roots = work / 'roots.bin'
    roots.write_bytes(b''.join(struct.pack('<I', len(c)) + c for c in certs))
    empty = work / 'empty.bin'; empty.write_bytes(b'')
    for name, text, options in [('baseline', baseline, ['-DBASELINE']), ('fixed', source, [])]:
        c = work / (name + '.c'); exe = work / name
        c.write_text(fixture + production(text) + checks)
        subprocess.run(['xcrun', 'clang', '-std=c11', '-O1', '-g', '-pthread',
                        '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                        '-I' + str(root / 'wine/include'), *options, str(c), '-o', str(exe)], check=True)
        subprocess.run([str(exe), str(roots)], check=True)
        if name == 'fixed': subprocess.run([str(exe), str(empty)], check=True)
