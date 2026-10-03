/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef MADEIRA_JIT_RESERVATION_POLICY_H
#define MADEIRA_JIT_RESERVATION_POLICY_H
#include <stdint.h>

/* Native low-address band only: never select the Wine guest band or xzone.
 * Callers pass actual unmapped holes, not existing mappings to overwrite. */
#define MADEIRA_EARLY_POOL_LOW UINT64_C(0x119000000)
#define MADEIRA_EARLY_POOL_HIGH UINT64_C(0x200000000)
static inline void madeira_consider_pool_hole(uint64_t begin, uint64_t end,
                                             uint64_t *best_base, uint64_t *best_size)
{
    const uint64_t step = UINT64_C(16) << 20, maximum = UINT64_C(1152) << 20;
    if (begin < MADEIRA_EARLY_POOL_LOW) begin = MADEIRA_EARLY_POOL_LOW;
    if (end > MADEIRA_EARLY_POOL_HIGH) end = MADEIRA_EARLY_POOL_HIGH;
    if (begin >= end) return;
    begin = (begin + UINT64_C(0x3fff)) & ~UINT64_C(0x3fff);
    if (begin >= end) return;
    uint64_t size = (end - begin) & ~(step - 1);
    if (size > maximum) size = maximum;
    if (size >= (UINT64_C(256) << 20) && size > *best_size) {
        *best_base = begin; *best_size = size;
    }
}
#endif
