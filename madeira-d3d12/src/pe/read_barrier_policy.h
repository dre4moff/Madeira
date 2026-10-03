/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef MADEIRA_READ_BARRIER_POLICY_H
#define MADEIRA_READ_BARRIER_POLICY_H
/* Metal has no D3D state/layout transition to perform between these read
 * usages. Preserve all producer/write, COMMON/PRESENT, split, UAV, aliasing
 * and unknown-state barriers, including every previously queued fence. */
static inline int madeira_read_barrier_redundant(const D3D12_RESOURCE_BARRIER *b)
{
    const UINT read = D3D12_RESOURCE_STATE_VERTEX_AND_CONSTANT_BUFFER | D3D12_RESOURCE_STATE_INDEX_BUFFER |
        D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE | D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE |
        D3D12_RESOURCE_STATE_INDIRECT_ARGUMENT | D3D12_RESOURCE_STATE_COPY_SOURCE |
        D3D12_RESOURCE_STATE_RESOLVE_SOURCE | D3D12_RESOURCE_STATE_DEPTH_READ;
    if (b->Type != D3D12_RESOURCE_BARRIER_TYPE_TRANSITION || b->Flags != D3D12_RESOURCE_BARRIER_FLAG_NONE ||
        !b->Transition.pResource) return 0;
    UINT before = b->Transition.StateBefore, after = b->Transition.StateAfter;
    return before && after && !(before & ~read) && !(after & ~read);
}
#endif
