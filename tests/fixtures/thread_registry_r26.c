/* LGPL-2.1-or-later; extracted unchanged from d0fae4e signal_arm64_ios.c. */
#define IOS_MAX_WINE_THREADS 512

struct ios_thread_entry {
    thread_t mach_thread;
    uintptr_t teb;
    void *trampoline;
};
static struct ios_thread_entry ios_thread_registry[IOS_MAX_WINE_THREADS];
static volatile int32_t ios_thread_count = 0;

/* Exact-match registry probe — NO slot-0 fallback.
 *
 * ml540: ios_lookup_thread() returns 1 even when it fell back to slot 0, so no
 * caller can use it to answer "is this a guest thread at all?". Fault handling
 * needs exactly that: since #67 we hold the TASK-level exception port, so this
 * handler now sees faults from EVERY thread in the process — including the
 * SwiftUI UI thread, which has no TEB and must never be handed guest exception
 * delivery. */
/* ml559: read-only accessors so other TUs can walk the registry without the
 * array itself leaving this file (ntdll-unix globals crossing TUs have broken
 * pseudo-processes before — see the S1 CreateProcess rule). Lock-free, same
 * snapshot discipline as ios_thread_is_registered. */
int ios_thread_registry_count(void)
{
    int count = __sync_fetch_and_add(&ios_thread_count, 0);
    return count > IOS_MAX_WINE_THREADS ? IOS_MAX_WINE_THREADS : count;
}

uintptr_t ios_thread_registry_teb(int i)
{
    if (i < 0 || i >= IOS_MAX_WINE_THREADS) return 0;
    return ios_thread_registry[i].teb;
}

thread_t ios_thread_registry_mach(int i)
{
    if (i < 0 || i >= IOS_MAX_WINE_THREADS) return 0;
    return ios_thread_registry[i].mach_thread;
}

static int ios_thread_is_registered(thread_t mach_thread)
{
    int count = __sync_fetch_and_add(&ios_thread_count, 0);
    if (count > IOS_MAX_WINE_THREADS) count = IOS_MAX_WINE_THREADS;
    for (int i = 0; i < count; i++)
        if (ios_thread_registry[i].mach_thread == mach_thread) return 1;
    return 0;
}

/* ml558: is this pointer a TEB we actually installed?
 *
 * TSD slot 275 is NOT ours (see pthread_exit_wrapper) -- on a native thread it
 * holds whatever framework legitimately owns that key. Signal handlers that read
 * slot 275 must validate the value before dereferencing it, and must do so
 * WITHOUT locks or Mach traps. Scanning the registry for a matching TEB is both:
 * lock-free (same pattern as ios_thread_is_registered) and it answers the exact
 * question -- not "is this thread ours" but "is this VALUE one of ours". */
static int ios_teb_is_registered(uintptr_t teb)
{
    int count = __sync_fetch_and_add(&ios_thread_count, 0);
    if (!teb) return 0;
    if (count > IOS_MAX_WINE_THREADS) count = IOS_MAX_WINE_THREADS;
    for (int i = 0; i < count; i++)
        if (ios_thread_registry[i].teb == teb) return 1;
    return 0;
}

/* A released guest window is about to become PROT_NONE, and every TEB inside
 * it with it.  Entries naming those TEBs must go first: the registry is keyed
 * by Mach port, ports are recycled, and the exception path's port lookup would
 * otherwise hand the fault handler a pointer into the replaced range.  Only
 * called from the guest-window teardown (virtual_ios.c). */
int ios_thread_registry_purge_range( uintptr_t base, uintptr_t size )
{
    int count = ios_thread_registry_count(), purged = 0, i;

    for (i = 0; i < count; i++)
    {
        uintptr_t teb = ios_thread_registry[i].teb;

        if (!teb || teb < base || teb - base >= size) continue;
        ios_thread_registry[i].mach_thread = 0;
        __sync_synchronize();
        ios_thread_registry[i].teb = 0;
        ios_thread_registry[i].trampoline = NULL;
        purged++;
    }
    return purged;
}

/* Is a thread whose TEB lies in [base, base+size) still alive?  An exited
 * process's workers can stay asleep long after its main thread is gone.  Only
 * the Mach thread's existence is asked, its TEB is never dereferenced; an
 * unexpected query failure counts as alive (keep the memory). */
int ios_thread_registry_range_busy( uintptr_t base, uintptr_t size )
{
    int count = ios_thread_registry_count(), i;

    for (i = 0; i < count; i++)
    {
        uintptr_t teb = ios_thread_registry[i].teb;
        thread_t port = ios_thread_registry[i].mach_thread;
        struct thread_basic_info info;
        mach_msg_type_number_t length = THREAD_BASIC_INFO_COUNT;
        kern_return_t kr;

        if (!port || !teb || teb < base || teb - base >= size) continue;
        kr = thread_info( port, THREAD_BASIC_INFO, (thread_info_t)&info, &length );
        if (kr != KERN_INVALID_ARGUMENT && kr != MACH_SEND_INVALID_DEST && kr != KERN_TERMINATED) return 1;
    }
    return 0;
}

static int ios_lookup_thread(thread_t mach_thread, uintptr_t *teb_out, void **tramp_out)
{
    int count = __sync_fetch_and_add(&ios_thread_count, 0);
    if (count > IOS_MAX_WINE_THREADS) count = IOS_MAX_WINE_THREADS;
    for (int i = 0; i < count; i++)
    {
        if (ios_thread_registry[i].mach_thread == mach_thread)
        {
            *teb_out = ios_thread_registry[i].teb;
            *tramp_out = ios_thread_registry[i].trampoline;
            return 1;
        }
    }
    /* Fallback: use first registered thread */
    /* ml390 (task #66): a thread that registered CORRECTLY (0184: idx=75 port
     * 0x4493 teb ok) later resolved to the slot-0 TEB here — either the
     * exception message named the thread differently than mach_thread_self()
     * did at registration (name drift), or the entry was clobbered.  Print the
     * sought name so it can be diffed against the registration line offline. */
    {
        static int miss_n;
        if (miss_n < 32)
        {
            miss_n++;
            ERR( "[reg-miss] #%d port=0x%x not in registry (count=%d) -> slot-0 fallback teb=%p\n",
                 miss_n, mach_thread, count, count > 0 ? (void *)ios_thread_registry[0].teb : NULL );
        }
    }
    if (count > 0)
    {
        *teb_out = ios_thread_registry[0].teb;
        *tramp_out = ios_thread_registry[0].trampoline;
        return 1;
    }
    *teb_out = 0;
    *tramp_out = NULL;
    return 0;
}

/* ml398 (task #60): fixture boundary */
static void ios_setup_mach_exception_handler(void) {
    /* Register this thread in the registry.
     * ml384: replace an existing entry for the same port first — the kernel
     * recycles thread port names, and a stale entry earlier in the array would
     * shadow the new registration in ios_lookup_thread (first match wins). */
    int idx, reg_count = __sync_fetch_and_add(&ios_thread_count, 0);
    if (reg_count > IOS_MAX_WINE_THREADS) reg_count = IOS_MAX_WINE_THREADS;
    for (idx = 0; idx < reg_count; idx++)
        if (ios_thread_registry[idx].mach_thread == pe_thread) break;
    if (idx == reg_count)
    {
        idx = __sync_fetch_and_add(&ios_thread_count, 1);
        if (idx >= IOS_MAX_WINE_THREADS)
        {
            ERR("[thread-registry] FULL (%d slots) — thread 0x%x teb=%p NOT registered; "
                "Mach events on it will resolve to the slot-0 TEB (wrong process!)\n",
                IOS_MAX_WINE_THREADS, pe_thread, (void *)teb);
            idx = -1;
        }
    }
    if (idx >= 0)
    {
        /* ml390 (task #66): make the replace path LOUD.  If a name gets
         * recycled while its previous owner still has live guest state, this
         * overwrite silently redirects that thread's TEB resolution — and a
         * thread_set_state aimed at the new owner could land on the old one
         * (zeroed-state suspect).  old_teb!=0 && old_teb!=new_teb = the case
         * to correlate offline against [reg-miss] and fault dumps. */
        if (idx < reg_count && ios_thread_registry[idx].teb &&
            ios_thread_registry[idx].teb != teb)
            ERR( "[thread-registry] REPLACE idx=%d port=0x%x old_teb=%p new_teb=%p\n",
                 idx, pe_thread, (void *)ios_thread_registry[idx].teb, (void *)teb );
        ios_thread_registry[idx].teb = teb;
        ios_thread_registry[idx].trampoline = trampoline;
        __sync_synchronize();
        ios_thread_registry[idx].mach_thread = pe_thread;
        /* ml401 (tasks #60/#66): EVERY registry port name proved
         * MACH_SEND_INVALID_DEST when the census sampler tried to use it —
         * something deallocates the mach_thread_self() ref after we store the
         * name, leaving the registry full of dead keys ([pump-sample] blind,
         * and dead names are exactly what the kernel recycles = the #66
         * wrong-thread hazard).  Pin extra send refs so the name outlives any
         * stray deallocate; dead-name lingering after thread exit is harmless
         * and prevents recycling. */
        {
            kern_return_t krr = mach_port_mod_refs( mach_task_self(), pe_thread,
                                                    MACH_PORT_RIGHT_SEND, 4 );
            if (krr != KERN_SUCCESS)
                ERR( "[thread-registry] mod_refs(+4) port=0x%x FAILED kr=%d\n", pe_thread, krr );
        }
    }

    /* Set exception port for this thread (fixture boundary) */
}
