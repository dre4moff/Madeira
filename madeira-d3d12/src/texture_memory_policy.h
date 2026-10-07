/* Shared trigger arithmetic and logical-to-physical mip translation. */
#ifndef MADEIRA_TEXTURE_MEMORY_POLICY_H
#define MADEIRA_TEXTURE_MEMORY_POLICY_H
#include <stdint.h>
static inline uint32_t mad_texture_headroom_mb(uint32_t start_mb, uint64_t budget_bytes) {
    if (start_mb != 2048 && start_mb != 4096) return 0;
    uint64_t budget_mb = budget_bytes >> 20;
    uint64_t threshold = budget_mb > start_mb ? budget_mb - start_mb : 0;
    if (threshold < 1536) threshold = 1536;
    return threshold > UINT32_MAX ? UINT32_MAX : (uint32_t)threshold;
}
/* Copies into removed top mips are intentionally discarded. Retained mip
 * extents and buffer pitches are unchanged: logical mip N is physical N-bias. */
static inline int mad_texture_copy_level(uint32_t bias, uint32_t *level) {
    if (*level < bias) return 0;
    *level -= bias;
    return 1;
}
static inline void mad_texture_view_levels(uint32_t bias, uint32_t physical_mips,
                                           uint32_t *first, uint32_t *count) {
    uint32_t logical_mips = physical_mips + bias;
    if (*first >= logical_mips) *first = logical_mips - 1;
    if (!*count || *count == UINT32_MAX || *count > logical_mips - *first)
        *count = logical_mips - *first;
    uint32_t end = *first + *count;
    *first = *first > bias ? *first - bias : 0;
    end = end > bias ? end - bias : 1;
    *count = end - *first;
}
#endif
