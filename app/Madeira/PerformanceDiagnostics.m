/* SPDX-License-Identifier: GPL-3.0-or-later
 * Bounded sampling; never suspends guest threads or enables FEX hot profiling. */
#import <Foundation/Foundation.h>
#import <QuartzCore/QuartzCore.h>
#import <mach/mach.h>
#import <os/lock.h>
#import <os/signpost.h>
#include <stdatomic.h>
#include <sys/resource.h>
#include <stdio.h>
#include "PerformanceMath.h"

#define SPAN_CAPACITY 8192
#define THREAD_CAPACITY 512
static os_unfair_lock perf_lock = OS_UNFAIR_LOCK_INIT;
static struct madeira_gpu_span spans[SPAN_CAPACITY], snapshot[SPAN_CAPACITY];
static unsigned span_count, missing, overflow, gpu_errors, completions;
static uint64_t commits, inflight, peak;
static double wait_seconds;
static double encode_seconds[2];
static uint64_t native_commands, resource_declarations, resource_calls;
static double role_cpu[MADEIRA_ROLE_COUNT];
static unsigned hottest_role = MADEIRA_ROLE_OTHER, unnamed_threads;
static double previous_wall, previous_cpu;
extern uint64_t madeira_get_present_count(void);
static uint64_t previous_frames;
struct thread_sample { uint64_t id; double cpu; };
static struct thread_sample old_threads[THREAD_CAPACITY];
static unsigned old_thread_count;
static dispatch_source_t perf_timer;
static unsigned current_phase;
static uint64_t phase_generation, previous_phase_generation;

static os_log_t profiling_log(void) {
    static os_log_t log;
    static dispatch_once_t once;
    dispatch_once(&once, ^{ log = os_log_create("com.willfaust.madeora", "Profiling"); });
    return log;
}
void madeira_perf_mark_phase(unsigned phase) {
    if (phase > 4) return;
    os_unfair_lock_lock(&perf_lock);
    current_phase = phase;
    uint64_t generation = ++phase_generation;
    os_unfair_lock_unlock(&perf_lock);
    const char *label = madeira_perf_phase_label(phase);
    double now = CACurrentMediaTime();
    fprintf(stderr, "[perf-phase] monotonic=%.3f phase=%s sequence=%llu\n", now, label,
            (unsigned long long)generation);
    os_signpost_event_emit(profiling_log(), OS_SIGNPOST_ID_EXCLUSIVE, "Gameplay phase",
                           "phase=%{public}s sequence=%llu", label, (unsigned long long)generation);
}

int madeira_perf_enabled(void) {
    static _Atomic int enabled = -1;
    int value = atomic_load_explicit(&enabled, memory_order_relaxed);
    if (value < 0) {
        const char *setting = getenv("MADEIRA_BOTTLENECK_STATS");
        value = !setting || !*setting || strcmp(setting, "1") == 0;
        atomic_store_explicit(&enabled, value, memory_order_relaxed);
    }
    return value;
}
static double process_cpu(void) {
    struct rusage usage;
    if (getrusage(RUSAGE_SELF, &usage)) return -1;
    return madeira_cpu_seconds(usage.ru_utime.tv_sec, usage.ru_utime.tv_usec,
                              usage.ru_stime.tv_sec, usage.ru_stime.tv_usec);
}
static double hottest_thread(double wall, unsigned *thread_count, unsigned *partial) {
    thread_act_array_t threads = NULL;
    mach_msg_type_number_t count = 0;
    struct thread_sample next[THREAD_CAPACITY];
    unsigned used = 0;
    double hottest = 0;
    memset(role_cpu, 0, sizeof(role_cpu)); hottest_role = MADEIRA_ROLE_OTHER; unnamed_threads = 0;
    if (task_threads(mach_task_self(), &threads, &count) != KERN_SUCCESS) { *partial = 1; return -1; }
    *thread_count = count;
    if (count > THREAD_CAPACITY) *partial = 1;
    for (unsigned i = 0; i < count; ++i) {
        thread_basic_info_data_t basic;
        thread_identifier_info_data_t identity;
        mach_msg_type_number_t n = THREAD_BASIC_INFO_COUNT, m = THREAD_IDENTIFIER_INFO_COUNT;
        if (used < THREAD_CAPACITY &&
            thread_info(threads[i], THREAD_BASIC_INFO, (thread_info_t)&basic, &n) == KERN_SUCCESS &&
            thread_info(threads[i], THREAD_IDENTIFIER_INFO, (thread_info_t)&identity, &m) == KERN_SUCCESS) {
            double cpu = madeira_cpu_seconds(basic.user_time.seconds, basic.user_time.microseconds,
                                            basic.system_time.seconds, basic.system_time.microseconds);
            for (unsigned j = 0; j < old_thread_count; ++j) if (old_threads[j].id == identity.thread_id) {
                double fraction = fmax(0, cpu - old_threads[j].cpu) / wall;
                unsigned role = MADEIRA_ROLE_OTHER;
                thread_extended_info_data_t extended;
                mach_msg_type_number_t x = THREAD_EXTENDED_INFO_COUNT;
                if (thread_info(threads[i], THREAD_EXTENDED_INFO, (thread_info_t)&extended, &x) == KERN_SUCCESS) {
                    extended.pth_name[sizeof(extended.pth_name)-1] = 0;
                    role = madeira_thread_role(extended.pth_name);
                } else ++unnamed_threads;
                role_cpu[role] += fraction;
                if (fraction > hottest) { hottest = fraction; hottest_role = role; }
                break;
            }
            next[used++] = (struct thread_sample){identity.thread_id, cpu};
        } else *partial = 1;
        /* task_threads grants a send right for EVERY element, even when its
         * query fails or the bounded sample is already full. */
        mach_port_deallocate(mach_task_self(), threads[i]);
    }
    vm_deallocate(mach_task_self(), (vm_address_t)threads, count * sizeof(*threads));
    if (!old_thread_count) *partial = 1;
    memcpy(old_threads, next, used * sizeof(*next)); old_thread_count = used;
    return hottest;
}
static void report(void) {
    @autoreleasepool {
        double now = CACurrentMediaTime(), cpu = process_cpu(), wall = now - previous_wall;
        uint64_t frames = madeira_get_present_count(), frame_delta = frames - previous_frames;
        if (wall <= 0) return;
        unsigned n, lost, dropped, errors, done;
        uint64_t submitted, queued, queue_peak;
        double waits, native_render, native_compute;
        uint64_t commands, declarations, calls;
        unsigned phase;
        uint64_t generation;
        os_unfair_lock_lock(&perf_lock);
        n = span_count; memcpy(snapshot, spans, n * sizeof(*spans)); span_count = 0;
        for (unsigned i = 0; i < n; ++i) if (snapshot[i].end > now && span_count < SPAN_CAPACITY)
            spans[span_count++] = snapshot[i];
        lost = missing; dropped = overflow; errors = gpu_errors; done = completions;
        missing = overflow = gpu_errors = completions = 0;
        submitted = commits; commits = 0; queued = inflight; queue_peak = peak; peak = inflight;
        waits = wait_seconds; wait_seconds = 0;
        native_render = encode_seconds[0]; native_compute = encode_seconds[1];
        encode_seconds[0] = encode_seconds[1] = 0;
        commands = native_commands; declarations = resource_declarations; calls = resource_calls;
        native_commands = resource_declarations = resource_calls = 0;
        phase = current_phase; generation = phase_generation;
        os_unfair_lock_unlock(&perf_lock);
        unsigned thread_count = 0, partial = 0;
        double hottest = hottest_thread(wall, &thread_count, &partial);
        double busy = madeira_gpu_busy(snapshot, n, previous_wall, now);
        double cores = cpu >= 0 && previous_cpu >= 0 ? fmax(0, cpu - previous_cpu) / wall : -1;
        if (frame_delta || submitted || queued) {
            /* GPU busy is a lower bound for COMPLETED buffers: pending/missing
             * timestamps remain explicit, and sums across queues are not added. */
            fprintf(stderr, "[perf-bottleneck] window=%.1fs fps=%.1f cpu-cores=%.2f hottest-thread=%.0f%% threads=%u thread-partial=%u gpu-completed-busy=%.0f%% gpu-samples=%u missing=%u overflow=%u errors=%u commits=%llu queued=%llu peak=%llu wait-ms/frame=%.2f gpu-time-kind=completed-buffer-intervals wait-kind=aggregate-buffer-completion thermal=%ld low-power=%d\n",
                wall, frame_delta / wall, cores, hottest * 100, thread_count, partial,
                busy * 100 / wall, done, lost, dropped, errors,
                (unsigned long long)submitted, (unsigned long long)queued, (unsigned long long)queue_peak,
                frame_delta ? waits * 1000 / frame_delta : 0,
                (long)NSProcessInfo.processInfo.thermalState, NSProcessInfo.processInfo.lowPowerModeEnabled);
            const char *roles[] = {"game", "render", "rhi", "dxmt-encode", "dxmt-finish", "worker", "other", "loading", "io"};
            fprintf(stderr, "[perf-work] hot-role=%s game-cores=%.2f render-cores=%.2f rhi-cores=%.2f encode-cores=%.2f finish-cores=%.2f worker-cores=%.2f other-cores=%.2f name-missing=%u native-render-ms/frame=%.2f native-compute-ms/frame=%.2f commands/frame=%.1f resource-decls/frame=%.1f resource-calls/frame=%.1f batching-saved=%llu native-time-kind=wall-batch\n",
                roles[hottest_role], role_cpu[0], role_cpu[1], role_cpu[2], role_cpu[3], role_cpu[4], role_cpu[5], role_cpu[6], unnamed_threads,
                frame_delta ? native_render * 1000 / frame_delta : 0,
                frame_delta ? native_compute * 1000 / frame_delta : 0,
                frame_delta ? (double)commands / frame_delta : 0,
                frame_delta ? (double)declarations / frame_delta : 0,
                frame_delta ? (double)calls / frame_delta : 0,
                (unsigned long long)(declarations >= calls ? declarations - calls : 0));
            int mixed = madeira_perf_phase_mixed(previous_phase_generation, generation);
            const char *label = mixed ? "mixed" : madeira_perf_phase_label(phase);
            fprintf(stderr, "[perf-context] monotonic=%.3f frame-total=%llu phase=%s phase-mixed=%d sequence=%llu loading-cores=%.2f io-cores=%.2f\n",
                    now, (unsigned long long)frames, label, mixed, (unsigned long long)generation,
                    role_cpu[MADEIRA_ROLE_LOADING], role_cpu[MADEIRA_ROLE_IO]);
            os_signpost_event_emit(profiling_log(), OS_SIGNPOST_ID_EXCLUSIVE, "Performance sample",
                                   "phase=%{public}s mixed=%d fps=%.1f cpu-cores=%.2f", label, mixed, frame_delta / wall, cores);
        }
        previous_phase_generation = generation;
        previous_wall = now; previous_cpu = cpu; previous_frames = frames;
    }
}
static void start(void) {
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        previous_wall = CACurrentMediaTime(); previous_cpu = process_cpu();
        previous_frames = madeira_get_present_count();
        dispatch_queue_t queue = dispatch_get_global_queue(QOS_CLASS_UTILITY, 0);
        perf_timer = dispatch_source_create(DISPATCH_SOURCE_TYPE_TIMER, 0, 0, queue);
        dispatch_source_set_timer(perf_timer, dispatch_time(DISPATCH_TIME_NOW, 10 * NSEC_PER_SEC),
                                 10 * NSEC_PER_SEC, NSEC_PER_SEC);
        dispatch_source_set_event_handler(perf_timer, ^{ report(); });
        dispatch_resume(perf_timer);
    });
}
void madeira_perf_commit(void) {
    start();
    os_unfair_lock_lock(&perf_lock);
    ++commits; ++inflight; if (inflight > peak) peak = inflight;
    os_unfair_lock_unlock(&perf_lock);
}
void madeira_perf_gpu(double from, double to, int failed) {
    os_unfair_lock_lock(&perf_lock);
    if (inflight) --inflight;
    ++completions;
    if (failed) ++gpu_errors;
    if (isfinite(from) && isfinite(to) && from > 0 && to > from) {
        if (span_count < SPAN_CAPACITY) spans[span_count++] = (struct madeira_gpu_span){from, to};
        else ++overflow;
    } else ++missing;
    os_unfair_lock_unlock(&perf_lock);
}
void madeira_perf_wait(double seconds) {
    if (!isfinite(seconds) || seconds <= 0) return;
    os_unfair_lock_lock(&perf_lock); wait_seconds += seconds; os_unfair_lock_unlock(&perf_lock);
}

/* One accumulation per native command batch, not per draw/declaration. */
void madeira_perf_encode(double seconds, uint64_t commands, uint64_t declarations,
                         uint64_t calls, int compute) {
    if (!isfinite(seconds) || seconds < 0 || calls > declarations || compute < 0 || compute > 1) return;
    os_unfair_lock_lock(&perf_lock);
    encode_seconds[compute] += seconds;
    native_commands += commands; resource_declarations += declarations; resource_calls += calls;
    os_unfair_lock_unlock(&perf_lock);
}
