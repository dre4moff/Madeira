/* LGPL-2.1-or-later: host timezone snapshot for the iOS Wine shared clock. */
#ifndef MADEIRA_TIMEZONE_BIAS_H
#define MADEIRA_TIMEZONE_BIAS_H
#include <stdint.h>
#include <time.h>

/* Windows stores UTC minus local time, in 100 ns units (including DST). */
extern int64_t madeira_timezone_bias_ticks;
static inline int64_t madeira_timezone_bias_from_seconds(long seconds_east)
{
    return -(int64_t)seconds_east * INT64_C(10000000);
}
/* Called at startup and on actual timezone/time changes, never by the server
 * event loop. The loop reads a single cached atomic value. */
static inline int madeira_update_timezone_bias(void)
{
    time_t now = time(NULL);
    struct tm local;
    if (now == (time_t)-1 || !localtime_r(&now, &local)) return 0;
    __atomic_store_n(&madeira_timezone_bias_ticks,
                    madeira_timezone_bias_from_seconds(local.tm_gmtoff), __ATOMIC_RELEASE);
    return 1;
}
static inline int64_t madeira_cached_timezone_bias(void)
{
    return __atomic_load_n(&madeira_timezone_bias_ticks, __ATOMIC_ACQUIRE);
}
#endif
