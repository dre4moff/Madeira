/* GPL-3.0-or-later with the Madeira Converter Exception. */
#ifndef MADEIRA_LAUNCH_ARGUMENTS_H
#define MADEIRA_LAUNCH_ARGUMENTS_H
#include <stddef.h>
#include <string.h>

/* Decode Windows command-line quoting into argv, which Wine re-encodes for the
 * executable. No shell expansion. Refuse malformed or oversized input instead
 * of silently dropping tokens. Input and output must not overlap. */
static inline int madeira_parse_launch_arguments(const char *input, char *buffer,
        size_t capacity, char **argv, size_t max_args)
{
    const char *p = input ? input : "";
    size_t used = 0, argc = 0;
    if (!capacity || strlen(p) >= capacity) return -1;
#define MADEIRA_ARG_PUT(c) do { if (used >= capacity) return -1; buffer[used++] = (c); } while (0)
    while (*p)
    {
        int quoted = 0;
        while (*p == ' ' || *p == '\t') ++p;
        if (!*p) break;
        if (argc >= max_args) return -1;
        argv[argc++] = buffer + used;
        while (*p && (quoted || (*p != ' ' && *p != '\t')))
        {
            size_t slashes = 0;
            while (*p == '\\') { ++slashes; ++p; }
            if (*p == '"')
            {
                for (size_t i = 0; i < slashes / 2; ++i) MADEIRA_ARG_PUT('\\');
                if (slashes & 1) MADEIRA_ARG_PUT('"');
                else if (quoted && p[1] == '"') { MADEIRA_ARG_PUT('"'); ++p; }
                else quoted = !quoted;
                ++p;
            }
            else
            {
                for (size_t i = 0; i < slashes; ++i) MADEIRA_ARG_PUT('\\');
                if (!*p || (!quoted && (*p == ' ' || *p == '\t'))) break;
                if (*p == '\r' || *p == '\n') return -1;
                MADEIRA_ARG_PUT(*p++);
            }
        }
        if (quoted) return -1;
        MADEIRA_ARG_PUT('\0');
    }
#undef MADEIRA_ARG_PUT
    return (int)argc;
}
#endif
