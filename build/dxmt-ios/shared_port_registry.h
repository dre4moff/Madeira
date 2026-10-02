#ifndef MADEIRA_SHARED_PORT_REGISTRY_H
#define MADEIRA_SHARED_PORT_REGISTRY_H

#include <pthread.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

/* Madeira's Wine processes are threads in one native iOS process. A shared
 * texture/fence therefore needs a process-local name service, not launchd.
 * Retain a send right for each registered name, and another for each lookup,
 * matching bootstrap lookup's ownership. Names live for the host lifetime,
 * as the guest interface has no unregister operation. Never evict a live name.
 * Callbacks keep the table host-testable without Mach or Metal operations. */
struct madeira_shared_port_entry {
    struct madeira_shared_port_entry *next;
    char name[128];
    uint32_t port;
};
struct madeira_shared_port_registry {
    pthread_mutex_t lock;
    struct madeira_shared_port_entry *entries;
};
#define MADEIRA_SHARED_PORT_REGISTRY_INIT { PTHREAD_MUTEX_INITIALIZER, NULL }

static int madeira_shared_port_valid_name(const char name[128])
{
    return name && name[0] && strnlen(name, 128) < 128;
}

static int madeira_shared_port_register(struct madeira_shared_port_registry *registry,
                                       const char name[128], uint32_t port,
                                       int (*retain)(uint32_t))
{
    struct madeira_shared_port_entry *entry;
    if (!madeira_shared_port_valid_name(name) || !port || port == UINT32_MAX) return 0;
    pthread_mutex_lock(&registry->lock);
    for (entry = registry->entries; entry; entry = entry->next)
        if (!strcmp(entry->name, name)) {
            pthread_mutex_unlock(&registry->lock);
            return 0;
        }
    entry = malloc(sizeof(*entry));
    if (!entry || !retain(port)) {
        free(entry);
        pthread_mutex_unlock(&registry->lock);
        return 0;
    }
    strcpy(entry->name, name);
    entry->port = port;
    entry->next = registry->entries;
    registry->entries = entry;
    pthread_mutex_unlock(&registry->lock);
    return 1;
}

static int madeira_shared_port_lookup(struct madeira_shared_port_registry *registry,
                                     const char name[128], uint32_t *port,
                                     int (*retain)(uint32_t))
{
    struct madeira_shared_port_entry *entry;
    int found = 0;
    if (!port) return 0;
    *port = 0;
    if (!madeira_shared_port_valid_name(name)) return 0;
    pthread_mutex_lock(&registry->lock);
    for (entry = registry->entries; entry; entry = entry->next)
        if (!strcmp(entry->name, name)) {
            if (retain(entry->port)) { *port = entry->port; found = 1; }
            break;
        }
    pthread_mutex_unlock(&registry->lock);
    return found;
}

/* Only at native process exit; never clear names during a Wine session. */
static void madeira_shared_port_clear(struct madeira_shared_port_registry *registry,
                                     void (*release)(uint32_t))
{
    struct madeira_shared_port_entry *entry, *next;
    pthread_mutex_lock(&registry->lock);
    entry = registry->entries;
    registry->entries = NULL;
    while (entry) {
        next = entry->next;
        release(entry->port);
        free(entry);
        entry = next;
    }
    pthread_mutex_unlock(&registry->lock);
}

#endif
