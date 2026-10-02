/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef MADEIRA_PERFORMANCE_MATH_H
#define MADEIRA_PERFORMANCE_MATH_H
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
enum madeira_perf_role { MADEIRA_ROLE_GAME, MADEIRA_ROLE_RENDER, MADEIRA_ROLE_RHI,
    MADEIRA_ROLE_ENCODE, MADEIRA_ROLE_FINISH, MADEIRA_ROLE_WORKER, MADEIRA_ROLE_OTHER,
    MADEIRA_ROLE_LOADING, MADEIRA_ROLE_IO, MADEIRA_ROLE_COUNT };
static inline unsigned madeira_thread_role(const char *name) {
    if (!strcmp(name, "GameThread")) return MADEIRA_ROLE_GAME;
    if (!strncmp(name, "RenderThread", 12)) return MADEIRA_ROLE_RENDER;
    if (!strncmp(name, "RHIThread", 9)) return MADEIRA_ROLE_RHI;
    if (!strncmp(name, "dxmt-encode", 11)) return MADEIRA_ROLE_ENCODE;
    if (!strncmp(name, "dxmt-finish", 11)) return MADEIRA_ROLE_FINISH;
    if (!strncmp(name, "TaskGraphThread", 15) || !strncmp(name, "LowLevelTasks", 13) ||
        !strncmp(name, "Foreground Work", 15) || !strncmp(name, "Background Work", 15)) return MADEIRA_ROLE_WORKER;
    if (!strncmp(name, "FAsyncLoading", 13) || !strncmp(name, "AsyncLoading", 12)) return MADEIRA_ROLE_LOADING;
    if (!strncmp(name, "IoDispatcher", 12)) return MADEIRA_ROLE_IO;
    return MADEIRA_ROLE_OTHER;
}
/* A transition splits a reporting window: do not label its earlier frames as
 * belonging to the new phase. Markers contain fixed labels only. */
static inline const char *madeira_perf_phase_label(unsigned phase) {
    switch (phase) {
    case 1: return "stationary";
    case 2: return "camera-turn";
    case 3: return "moving";
    case 4: return "repeat-route";
    default: return "unmarked";
    }
}
static inline int madeira_perf_phase_mixed(uint64_t before, uint64_t after) { return before != after; }
struct madeira_gpu_span { double start, end; };
static inline int madeira_span_compare(const void *a, const void *b) {
    double x = ((const struct madeira_gpu_span *)a)->start;
    double y = ((const struct madeira_gpu_span *)b)->start;
    return (x > y) - (x < y);
}
/* Completion order differs between Metal queues. Sum their interval UNION,
 * clipped to wall time, rather than presenting overlapped work as >100% busy. */
static inline double madeira_gpu_busy(struct madeira_gpu_span *spans, size_t count, double from, double to) {
    if (!isfinite(from) || !isfinite(to) || to <= from) return 0;
    size_t valid = 0;
    for (size_t i = 0; i < count; ++i)
        if (isfinite(spans[i].start) && isfinite(spans[i].end) && spans[i].end > spans[i].start)
            spans[valid++] = spans[i];
    count = valid;
    qsort(spans, count, sizeof(*spans), madeira_span_compare);
    double total = 0, end = from;
    for (size_t i = 0; i < count; ++i) {
        double a = fmax(from, spans[i].start), b = fmin(to, spans[i].end);
        if (!isfinite(spans[i].start) || !isfinite(spans[i].end) || b <= a) continue;
        a = fmax(a, end);
        if (b > a) total += b - a;
        end = fmax(end, b);
    }
    return total;
}
static inline double madeira_cpu_seconds(long user_s, long user_us, long system_s, long system_us) {
    return user_s + system_s + (user_us + system_us) * 1e-6;
}
#endif
