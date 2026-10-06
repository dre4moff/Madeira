/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef MADEIRA_GRAPHICS_PROFILE_H
#define MADEIRA_GRAPHICS_PROFILE_H
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

static char *madeira_dlss_baseline, *madeira_dlss_applied;
static char *madeira_dlss_nvext_baseline;
static int madeira_dlss_nvext_applied;
static inline void madeira_restore_dlss_overrides(void) {
    const char *current = getenv("WINEDLLOVERRIDES");
    if (madeira_dlss_applied && current && !strcmp(current, madeira_dlss_applied)) {
        if (madeira_dlss_baseline) setenv("WINEDLLOVERRIDES", madeira_dlss_baseline, 1);
        else unsetenv("WINEDLLOVERRIDES");
    }
    free(madeira_dlss_baseline); free(madeira_dlss_applied);
    madeira_dlss_baseline = madeira_dlss_applied = NULL;
    if (madeira_dlss_nvext_applied) {
        if (madeira_dlss_nvext_baseline) setenv("DXMT_ENABLE_NVEXT", madeira_dlss_nvext_baseline, 1);
        else unsetenv("DXMT_ENABLE_NVEXT");
    }
    free(madeira_dlss_nvext_baseline);
    madeira_dlss_nvext_baseline = NULL;
    madeira_dlss_nvext_applied = 0;
}

static inline void madeira_apply_dlss_profile(int enabled) {
    madeira_restore_dlss_overrides();
    int on = 0;
    if (enabled) {
        const char *current = getenv("WINEDLLOVERRIDES");
        // Wine's loadorder parser replaces earlier options with later ones.
        // Appending keeps unrelated names even in a shared override clause.
        if (current) madeira_dlss_baseline = strdup(current);
        if (!current || madeira_dlss_baseline) {
            const char *base = current ? current : "";
            const char *suffix = ";nvapi64,nvngx=b";
            madeira_dlss_applied = malloc(strlen(base) + strlen(suffix) + 1);
            if (madeira_dlss_applied) {
                strcpy(madeira_dlss_applied, base); strcat(madeira_dlss_applied, suffix);
                on = !setenv("WINEDLLOVERRIDES", madeira_dlss_applied, 1);
            }
        }
    }
    if (on) {
        const char *nvext = getenv("DXMT_ENABLE_NVEXT");
        madeira_dlss_nvext_baseline = nvext ? strdup(nvext) : NULL;
        madeira_dlss_nvext_applied = (!nvext || madeira_dlss_nvext_baseline) && !setenv("DXMT_ENABLE_NVEXT", "1", 1);
        // DLSS already reconstructs the game's final output: never also scale Present.
        setenv("DXMT_METALFX_SPATIAL_SWAPCHAIN", "0", 1);
        unsetenv("DXMT_METALFX_SPATIAL_FACTOR");
        unsetenv("DXMT_METALFX_OUTPUT_WIDTH"); unsetenv("DXMT_METALFX_OUTPUT_HEIGHT");
    }
    fprintf(stderr, "[dlss-metalfx] enabled=%d temporal=1 display-resolution-preserved=1 (D3D11 + Madeira D3D12; enable DLSS in-game)\n", on);
}
static inline void madeira_apply_metalfx_profile(double factor) {
    const int on = factor == 1.5 || factor == 2.0;
    unsetenv("DXMT_METALFX_OUTPUT_WIDTH");
    unsetenv("DXMT_METALFX_OUTPUT_HEIGHT");
    setenv("DXMT_METALFX_SPATIAL_SWAPCHAIN", on ? "1" : "0", 1);
    if (on) setenv("DXMT_METALFX_SPATIAL_FACTOR", factor == 1.5 ? "1.5" : "2", 1);
    else unsetenv("DXMT_METALFX_SPATIAL_FACTOR");
    fprintf(stderr, "[metalfx-profile] enabled=%d factor=%.1f (D3D11)\n", on, on ? factor : 1.0);
}

static inline void madeira_apply_metalfx_output(double factor, const char *resolution) {
    char *end;
    long width, height;
    char value[16];
    if ((factor != 1.5 && factor != 2.0) || !resolution || !*resolution) return;
    width = strtol(resolution, &end, 10);
    if (end == resolution || *end != 'x') return;
    const char *height_start = end + 1;
    height = strtol(height_start, &end, 10);
    if (end == height_start || *end || width < 320 || width > 4096 || height < 240 || height > 4096) return;
    snprintf(value, sizeof(value), "%ld", width); setenv("DXMT_METALFX_OUTPUT_WIDTH", value, 1);
    snprintf(value, sizeof(value), "%ld", height); setenv("DXMT_METALFX_OUTPUT_HEIGHT", value, 1);
    fprintf(stderr, "[metalfx-profile] output-cap=%ldx%ld\n", width, height);
}
#endif
