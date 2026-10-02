/* SPDX-License-Identifier: LGPL-2.1-or-later */
#ifndef MADEIRA_RUNTIME_PROFILING_H
#define MADEIRA_RUNTIME_PROFILING_H
#include <stdlib.h>
#include <string.h>

/* Diagnostic workers are separate from execution/memory safety machinery.
 * Preserve the developer default without quiet mode; allow an explicit
 * opt-in even in quiet mode, and an explicit opt-out in developer mode. */
static inline int madeira_runtime_profiling_enabled(void)
{
    const char *choice = getenv("MADEIRA_RUNTIME_PROFILING");
    if (choice && *choice) return strcmp(choice, "1") == 0;
    const char *quiet = getenv("MADEIRA_QUIET");
    return !quiet || !*quiet || strcmp(quiet, "0") == 0;
}

/* Hot diagnostic hooks run only after the launch environment is configured.
 * Avoid getenv and shared read/modify/write counters on every Wine wait. */
static inline int madeira_runtime_profiling_cached(void)
{
    static int cached = -1;
    int value = __atomic_load_n(&cached, __ATOMIC_RELAXED);
    if (value < 0)
    {
        value = madeira_runtime_profiling_enabled();
        __atomic_store_n(&cached, value, __ATOMIC_RELAXED);
    }
    return value;
}
#endif
