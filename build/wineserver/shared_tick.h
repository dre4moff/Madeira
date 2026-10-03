/* LGPL-2.1-or-later. TickCount is stored in milliseconds by this Wine port.
 * Direct Windows readers apply a Q24 multiplier; unity preserves those units. */
#ifndef MADEIRA_SHARED_TICK_H
#define MADEIRA_SHARED_TICK_H
#define MADEIRA_TICK_MULTIPLIER (1u << 24)
#endif
