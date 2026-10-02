/* SPDX-License-Identifier: LGPL-2.1-or-later */
#ifndef MADEIRA_REQUEST_WAKE_GATE_H
#define MADEIRA_REQUEST_WAKE_GATE_H

/* One signal covers an entire upcoming scan, not one request. Consume the
 * token BEFORE scanning descriptors. Posts after consumption can signal the
 * next scan; earlier posts are already in their pipes for this scan.
 * Never clear on timeout: a producer may still be about to signal. */
struct madeira_request_wake_gate { unsigned pending; };
static inline int madeira_request_wake_claim(struct madeira_request_wake_gate *gate)
{
    return !__atomic_exchange_n(&gate->pending, 1, __ATOMIC_ACQ_REL);
}
static inline void madeira_request_wake_consumed(struct madeira_request_wake_gate *gate)
{
    __atomic_store_n(&gate->pending, 0, __ATOMIC_RELEASE);
}
#endif
