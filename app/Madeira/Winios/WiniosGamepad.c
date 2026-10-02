/* GPL-3.0-or-later WITH the Madeira Converter Exception, version 1. */
#include "WiniosGamepad.h"
#include <pthread.h>
#include <string.h>
#include <stdio.h>

/* ml1920: protect the payload as well as the version. A sequence counter
 * around a non-atomic struct copy still constitutes a C data race. The lock
 * covers only a 20-byte snapshot, never framework work or a Wine server call. */
static pthread_mutex_t pad_lock = PTHREAD_MUTEX_INITIALIZER;
static struct winios_gamepad pads[WINIOS_GAMEPAD_MAX];
/* Bounded diagnostic beacons, rather than logging a game's polling loop. */
static unsigned char reported_read[WINIOS_GAMEPAD_MAX];
static unsigned char reported_input[WINIOS_GAMEPAD_MAX];
static int has_input(const struct winios_gamepad *pad)
{
    return pad->buttons || pad->left_trigger || pad->right_trigger ||
           pad->lx || pad->ly || pad->rx || pad->ry;
}

void winios_gamepad_set_state(int index, const struct winios_gamepad *state)
{
    struct winios_gamepad next = {0};
    if (index < 0 || index >= WINIOS_GAMEPAD_MAX) return;
    if (state && state->connected) {
        next = *state;
        next.connected = 1;
        memset(next.reserved, 0, sizeof(next.reserved));
    }
    pthread_mutex_lock(&pad_lock);
    int connection_changed = next.connected != pads[index].connected;
    next.packet = pads[index].packet;
    if (memcmp(&next, &pads[index], sizeof(next))) {
        next.packet++;
        pads[index] = next;
    }
    pthread_mutex_unlock(&pad_lock);
    if (connection_changed)
        fprintf(stderr, "[xinput-host] publish slot=%d connected=%u\n", index, next.connected);
}

int winios_gamepad_get_state(int index, struct winios_gamepad *out)
{
    struct winios_gamepad value = {0};
    int report = 0;
    if (index >= 0 && index < WINIOS_GAMEPAD_MAX) {
        pthread_mutex_lock(&pad_lock);
        value = pads[index];
        unsigned char bit = value.connected ? 2 : 1;
        if (!(reported_read[index] & bit)) {
            reported_read[index] |= bit;
            report = 1;
        }
        if (value.connected && has_input(&value) && !reported_input[index]) {
            reported_input[index] = 1;
            report = 1;
        }
        pthread_mutex_unlock(&pad_lock);
    }
    if (report)
        fprintf(stderr, "[xinput-host] read slot=%d connected=%u input=%d packet=%u\n",
                index, value.connected, has_input(&value), value.packet);
    if (out) {
        if (value.connected) *out = value;
        else memset(out, 0, sizeof(*out));
    }
    return value.connected != 0;
}
