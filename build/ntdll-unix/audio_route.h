/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef MADEIRA_AUDIO_ROUTE_H
#define MADEIRA_AUDIO_ROUTE_H
#define MADEIRA_AUDIO_ENDPOINTS 16
struct madeira_audio_endpoint { char uid[256]; unsigned short name[128]; };
struct madeira_audio_routes {
    unsigned render_count, capture_count, capture_default;
    int microphone;
    struct madeira_audio_endpoint render[MADEIRA_AUDIO_ENDPOINTS], capture[MADEIRA_AUDIO_ENDPOINTS];
};
void madeira_audio_prepare(void);
void madeira_audio_refresh_routes(void);
void madeira_audio_get_routes(struct madeira_audio_routes *routes);
int madeira_audio_select_input(const char *uid);
#endif
