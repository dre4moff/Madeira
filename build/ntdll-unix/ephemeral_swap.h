/* SPDX-License-Identifier: LGPL-2.1-or-later */
#ifndef MADEIRA_EPHEMERAL_SWAP_H
#define MADEIRA_EPHEMERAL_SWAP_H
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

/* Unlink only the app-created backing file. Open descriptors and mappings
 * retain the inode; the OS reclaims it when they close, including on a crash.
 * No paging, allocation or sync policy changes. */
static inline int madeira_detach_swap_file(int fd, const char *path)
{
    struct stat opened, named;
    const char *choice = getenv("MADEIRA_SWAP_EPHEMERAL");
    const char *name;
    if (!choice || strcmp(choice, "1") || !path) return 0;
    name = strrchr(path, '/');
    name = name ? name + 1 : path;
    if (strcmp(name, "madeira-swap.bin")) return 0;
    if (fstat(fd, &opened) || lstat(path, &named)) return 0;
    if (!S_ISREG(opened.st_mode) || !S_ISREG(named.st_mode) ||
        opened.st_uid != geteuid() || named.st_uid != geteuid() ||
        opened.st_nlink != 1 || named.st_nlink != 1 ||
        opened.st_dev != named.st_dev || opened.st_ino != named.st_ino) return 0;
    return unlink(path) == 0;
}
#endif
