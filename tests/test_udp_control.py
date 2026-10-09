#!/usr/bin/env python3
"""Exercise Wine's production UDP control conversion with real Darwin datagrams."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / 'wine/dlls/ntdll/unix/socket.c').read_text()


def functions(text):
    start = text.index('static WSACMSGHDR *fill_control_message(')
    end = text.index('\nstruct ip_hdr', start)
    return text[start:end]


fixture = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <netinet/in.h>
#include <unistd.h>
typedef uint32_t ULONG;
typedef int32_t INT;
typedef struct { size_t cmsg_len; INT cmsg_level, cmsg_type; } WSACMSGHDR;
typedef struct { ULONG len; char *buf; } WSABUF;
struct afd_wsabuf_32 { ULONG len; uintptr_t buf; };
struct WS_in_pktinfo { struct in_addr ipi_addr; ULONG ipi_ifindex; };
struct WS_in6_pktinfo { struct in6_addr ipi6_addr; ULONG ipi6_ifindex; };
#define WS_IPPROTO_IP 0
#define WS_IPPROTO_IPV6 41
#define WS_IP_PKTINFO 19
#define WS_IP_TOS 3
#define WS_IP_TTL 4
#define WS_IPV6_HOPLIMIT 21
#define WS_IPV6_PKTINFO 19
#define WS_IPV6_TCLASS 39
#define WSA_CMSG_ALIGN(n) (((n) + sizeof(size_t) - 1) & ~(sizeof(size_t) - 1))
#define HAVE_STRUCT_IN6_PKTINFO_IPI6_ADDR 1
#define afd_guest_ptr(n) ((void *)(uintptr_t)(n))
static int unknown;
#define FIXME(...) (++unknown)
#define TRACE(...) ((void)0)
'''

checks = r'''
static void synthetic(void) {
    union { struct cmsghdr align; unsigned char bytes[128]; } native = {0};
    struct msghdr msg = {0};
    msg.msg_control = native.bytes; msg.msg_controllen = CMSG_SPACE(1);
    struct cmsghdr *c = CMSG_FIRSTHDR(&msg);
    c->cmsg_level = IPPROTO_IP; c->cmsg_type = IP_RECVTOS;
    c->cmsg_len = CMSG_LEN(1); *CMSG_DATA(c) = 0xab;
    union { WSACMSGHDR align; unsigned char bytes[128]; } converted;
    memset(converted.bytes, 0x5a, sizeof(converted.bytes));
    WSABUF out = {sizeof(converted.bytes), (char *)converted.bytes};
    assert(convert_control_headers(&msg, &out));
    assert(out.len == sizeof(WSACMSGHDR) + WSA_CMSG_ALIGN(sizeof(INT)));
    WSACMSGHDR *w = (WSACMSGHDR *)out.buf;
    assert(w->cmsg_len == sizeof(*w) + sizeof(INT));
    assert(w->cmsg_level == WS_IPPROTO_IP && w->cmsg_type == WS_IP_TOS);
    assert(*(INT *)(w + 1) == 0xab && !unknown);
    /* Exact 32-bit ABI capacity used to be rejected. Copying the complete
     * 64-bit message length also read/wrote past the payload. */
    unsigned char *buffer = malloc(16);
    struct afd_wsabuf_32 out32 = {16, (uintptr_t)buffer};
    assert(wow64_translate_control(&out, &out32) && out32.len == 16);
    struct cmsghdr_32 *w32 = (struct cmsghdr_32 *)buffer;
    assert(w32->cmsg_len == 16 && w32->cmsg_type == WS_IP_TOS);
    assert(*(INT *)(w32 + 1) == 0xab);
    out32.len = 15;
    assert(!wow64_translate_control(&out, &out32) && !out32.len);
    free(buffer);
    /* Native capacity and malformed input remain bounded. */
    out.len = sizeof(WSACMSGHDR) + sizeof(INT) - 1;
    assert(!convert_control_headers(&msg, &out));
    out.len = sizeof(WSACMSGHDR) - 1; out32.len = 16; out32.buf = (uintptr_t)converted.bytes;
    assert(!wow64_translate_control(&out, &out32) && !out32.len);
    out.len = 24; w->cmsg_len = sizeof(*w) - 1; out32.len = 16;
    assert(!wow64_translate_control(&out, &out32) && !out32.len);
    w->cmsg_len = 200; out32.len = 16;
    assert(!wow64_translate_control(&out, &out32) && !out32.len);
    /* Linux-style TOS still maps to the same Winsock message. */
    c->cmsg_type = IP_TOS; out.len = sizeof(converted.bytes);
    assert(convert_control_headers(&msg, &out) && *(INT *)(w + 1) == 0xab);
    /* A second message survives the compact 32-bit packing. */
    WSACMSGHDR *second = (WSACMSGHDR *)(converted.bytes + out.len);
    second->cmsg_len = sizeof(*second) + 4;
    second->cmsg_level = WS_IPPROTO_IPV6; second->cmsg_type = WS_IPV6_TCLASS;
    *(INT *)(second + 1) = 0x9e; out.len += 24;
    unsigned char *pair = malloc(32); out32.len = 32; out32.buf = (uintptr_t)pair;
    assert(wow64_translate_control(&out, &out32) && out32.len == 32);
    w32 = (struct cmsghdr_32 *)(pair + 16);
    assert(w32->cmsg_len == 16 && w32->cmsg_level == WS_IPPROTO_IPV6 && *(INT *)(w32 + 1) == 0x9e);
    free(pair);
}

static void datagram(int ipv6, int value) {
    int family = ipv6 ? AF_INET6 : AF_INET;
    int receiver = socket(family, SOCK_DGRAM, 0), sender = socket(family, SOCK_DGRAM, 0);
    assert(receiver >= 0 && sender >= 0);
    struct timeval timeout = {2, 0};
    assert(!setsockopt(receiver, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)));
    int yes = 1;
    assert(!setsockopt(receiver, ipv6 ? IPPROTO_IPV6 : IPPROTO_IP,
                      ipv6 ? IPV6_RECVTCLASS : IP_RECVTOS, &yes, sizeof(yes)));
    assert(!setsockopt(sender, ipv6 ? IPPROTO_IPV6 : IPPROTO_IP,
                      ipv6 ? IPV6_TCLASS : IP_TOS, &value, sizeof(value)));
    union { struct sockaddr_in v4; struct sockaddr_in6 v6; } address = {0};
    socklen_t address_size;
    if (ipv6) { address.v6.sin6_family = family; address.v6.sin6_addr = in6addr_loopback; address_size = sizeof(address.v6); }
    else { address.v4.sin_family = family; address.v4.sin_addr.s_addr = htonl(INADDR_LOOPBACK); address_size = sizeof(address.v4); }
    assert(!bind(receiver, (struct sockaddr *)&address, address_size));
    assert(!getsockname(receiver, (struct sockaddr *)&address, &address_size));
    assert(sendto(sender, "udp", 3, 0, (struct sockaddr *)&address, address_size) == 3);
    char payload[4]; struct iovec iov = {payload, sizeof(payload)};
    union { struct cmsghdr align; char bytes[256]; } native;
    struct msghdr msg = {0}; msg.msg_iov = &iov; msg.msg_iovlen = 1;
    msg.msg_control = native.bytes; msg.msg_controllen = sizeof(native.bytes);
    assert(recvmsg(receiver, &msg, 0) == 3 && !memcmp(payload, "udp", 3));
    union { WSACMSGHDR align; char bytes[256]; } converted;
    WSABUF out = {sizeof(converted.bytes), converted.bytes};
    assert(convert_control_headers(&msg, &out) && out.len && !unknown);
    WSACMSGHDR *w = (WSACMSGHDR *)out.buf;
    assert(w->cmsg_level == (ipv6 ? WS_IPPROTO_IPV6 : WS_IPPROTO_IP));
    assert(w->cmsg_type == (ipv6 ? WS_IPV6_TCLASS : WS_IP_TOS));
    assert(*(INT *)(w + 1) == value);
    unsigned char *buffer = malloc(16);
    struct afd_wsabuf_32 out32 = {16, (uintptr_t)buffer};
    assert(wow64_translate_control(&out, &out32) && out32.len == 16);
    assert(*(INT *)((struct cmsghdr_32 *)buffer + 1) == value);
    free(buffer); close(receiver); close(sender);
}

int main(void) {
    synthetic();
    for (int value = 0; value < 256; ++value) { datagram(0, value); datagram(1, value); }
    puts("PASS: 512 real IPv4/IPv6 UDP datagrams retain TOS/DSCP/ECN in native and 32-bit control data; exact capacity, multiple messages and malformed input are bounded");
}
'''

baseline = subprocess.check_output(['git', 'show', 'f06d6a0f83793ec780f336f15f8c05086ebd4ff5:dlls/ntdll/unix/socket.c'],
                                   cwd=root / 'wine', text=True)
baseline_checks = r'''
int main(void) {
    union { struct cmsghdr align; char bytes[64]; } native = {0};
    struct msghdr msg = {0}; msg.msg_control = native.bytes; msg.msg_controllen = CMSG_SPACE(1);
    struct cmsghdr *c = CMSG_FIRSTHDR(&msg); c->cmsg_len = CMSG_LEN(1);
    c->cmsg_level = IPPROTO_IP; c->cmsg_type = IP_RECVTOS; *CMSG_DATA(c) = 0xab;
    union { WSACMSGHDR align; char bytes[64]; } buf;
    WSABUF out = {sizeof(buf.bytes), buf.bytes};
    assert(convert_control_headers(&msg, &out) && !out.len && unknown == 1);
    WSACMSGHDR *w = (WSACMSGHDR *)out.buf; w->cmsg_len = 20;
    w->cmsg_level = WS_IPPROTO_IP; w->cmsg_type = WS_IP_TOS; *(INT *)(w + 1) = 0xab; out.len = 24;
    char compact[16]; struct afd_wsabuf_32 out32 = {16, (uintptr_t)compact};
    assert(!wow64_translate_control(&out, &out32));
    puts("CONFIRMED baseline: Darwin type 27 is discarded and a sufficient 16-byte Winsock32 control buffer is rejected");
}
'''
with tempfile.TemporaryDirectory(prefix='madeira-udp-control-') as directory:
    directory = Path(directory)
    for name, text, test in [('baseline', baseline, baseline_checks), ('fixed', source, checks)]:
        path = directory / (name + '.c')
        path.write_text(fixture + functions(text) + test)
        binary = directory / name
        subprocess.run(['xcrun', 'clang', '-std=c11', '-O1', '-g', '-Wall', '-Wextra',
                        '-Werror', '-fsanitize=address,undefined', str(path), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
