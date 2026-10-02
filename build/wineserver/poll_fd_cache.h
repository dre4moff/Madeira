/* SPDX-License-Identifier: LGPL-2.1-or-later */
#ifndef MADEIRA_POLL_FD_CACHE_H
#define MADEIRA_POLL_FD_CACHE_H
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>

struct ios_poll_fd_kind { int fd; signed char inet; };
static struct ios_poll_fd_kind *ios_poll_fd_kinds;
static int ios_poll_fd_kind_count;

/* Poll slots AND Unix descriptors are recycled. Invalidate on each slot
 * lifetime, even when the new object has exactly the same descriptor number. */
static void ios_poll_fd_cache_invalidate(int user)
{
    if (user >= 0 && user < ios_poll_fd_kind_count)
        ios_poll_fd_kinds[user].fd = -1;
}

static signed char ios_fd_is_inet(int user, int fd)
{
    struct sockaddr_storage ss;
    socklen_t length = sizeof(ss);
    int saved_errno = errno;
    signed char inet;
    if (user < 0 || fd < 0) return 0;
    if (user >= ios_poll_fd_kind_count)
    {
        int count = (user + 64) & ~63;
        struct ios_poll_fd_kind *next = malloc((size_t)count * sizeof(*next));
        if (next)
        {
            for (int i = 0; i < count; ++i) next[i].fd = -1;
            if (ios_poll_fd_kind_count)
                memcpy(next, ios_poll_fd_kinds, (size_t)ios_poll_fd_kind_count * sizeof(*next));
            free(ios_poll_fd_kinds);
            ios_poll_fd_kinds = next;
            ios_poll_fd_kind_count = count;
        }
        /* Allocation failure must still classify the socket correctly.
         * The next poll retries growth; the existing allocation stays valid. */
    }
    if (user < ios_poll_fd_kind_count && ios_poll_fd_kinds[user].fd == fd)
    {
        errno = saved_errno;
        return ios_poll_fd_kinds[user].inet;
    }
    inet = getsockname(fd, (struct sockaddr *)&ss, &length) == 0 &&
        (ss.ss_family == AF_INET || ss.ss_family == AF_INET6);
    errno = saved_errno;
    if (user < ios_poll_fd_kind_count)
        ios_poll_fd_kinds[user] = (struct ios_poll_fd_kind){fd, inet};
    return inet;
}
#endif
